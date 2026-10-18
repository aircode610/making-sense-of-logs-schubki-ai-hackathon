"""Analytics tools for team leads and managers (plan 011): roll-ups with subtotals, week × team heatmaps, a computed
reliability trend, latency profiles and one team's risk. SQL features: GROUP BY ROLLUP, PIVOT, generate_series
(zero-filled buckets), regr_slope, quantile_cont. Every number is computed in SereneDB; verdicts are fixed rules that
are returned with the rule."""
import time
from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import Field

from core import MAX_ROWS, Dataset, DatasetOpt, check_dataset, envelope, query, render
from outliers import VALUE

Start = Annotated[Optional[datetime], Field(description="Inclusive start time (default: the dataset's first line).")]
End = Annotated[Optional[datetime], Field(description="Exclusive end time (default: after the dataset's last line).")]
Unit = Annotated[Literal["bursts", "lines"], Field(
    description="'bursts' = recurrences of a pattern (> 30 min apart), the incident-like unit; 'lines' = log entries.")]
# Same rule as priority_table / top_patterns: stored Jev p_problem (max(fault × (1 − dump), threat), load/96) AND the
# pattern has problem-level lines (error-or-worse, WARN, HTTP 5xx or no level).
PROBLEM_J = "j.p_problem >= 0.5 AND p.problem_lines > 0"
OWN = "LEFT JOIN ownership o ON o.dataset = {t}.dataset AND o.component = {t}.component"


def _source(unit: str, problem_only: bool, dataset, start, end) -> tuple[str, str, dict]:
    """(FROM … WHERE … clause, timestamp column, params) for bursts or lines, with the team join."""
    params = {"d": dataset, "s": start, "e": end}
    if unit == "bursts":
        frm = ("FROM bursts b JOIN patterns p ON p.dataset = b.dataset AND p.pattern_id = b.pattern_id "
               + OWN.format(t="p") + " LEFT JOIN pattern_judgments j ON j.dataset = p.dataset AND j.pattern_id = p.pattern_id "
               "WHERE TRUE")
        ts = "b.start_ts"
        frm += f" AND {PROBLEM_J}" if problem_only else ""
        frm += " AND b.dataset = %(d)s" if dataset else ""
    else:
        frm = ("FROM logs l " + OWN.format(t="l") + (" LEFT JOIN patterns p ON p.dataset = l.dataset AND p.pattern_id = l.pattern_id "
               "LEFT JOIN pattern_judgments j ON j.dataset = l.dataset AND j.pattern_id = l.pattern_id" if problem_only else "")
               + " WHERE TRUE" + (f" AND {PROBLEM_J}" if problem_only else "") + (" AND l.dataset = %(d)s" if dataset else ""))
        ts = "l.ts"
    frm += (f" AND {ts} >= %(s)s" if start else "") + (f" AND {ts} < %(e)s" if end else "")
    return frm, ts, params


DIM = {"bursts": {"team": "coalesce(o.team, 'unowned')", "component": "p.component", "severity": "p.severity",
                  "dataset": "b.dataset"},
       "lines": {"team": "coalesce(o.team, 'unowned')", "component": "l.component", "severity": "l.severity",
                 "dataset": "l.dataset"}}


def rollup(
    dataset: DatasetOpt = None,
    start: Start = None,
    end: End = None,
    by: Annotated[list[Literal["dataset", "team", "component", "severity"]], Field(
        description="Hierarchy to roll up, coarse → fine, e.g. ['team', 'component'].")] = ["team", "component"],
    unit: Unit = "bursts",
    problem_only: Annotated[bool, Field(description="Only patterns the stored Jev judgment calls a real fault.")] = True,
    limit: Annotated[int, Field(ge=1, le=200, description="Rows to return (subtotals first).")] = 60,
) -> dict:
    """Totals with subtotals in ONE query (GROUP BY ROLLUP): per team, per team × component, … and the grand total,
    in bursts (recurrences) or lines. The whole-corpus aggregation the brief asks for: e.g. "node-platform 268 problem
    bursts, of which KERNEL 240". Each row has `level` (0 = finest … n = grand total) and NULL = 'all' for rolled-up
    columns. Default problem_only=True: real-fault patterns only (stored Jev judgment).
    """
    t0 = time.perf_counter()
    check_dataset(dataset)
    frm, _, params = _source(unit, problem_only, dataset, start, end)
    cols = [DIM[unit][b] for b in by]
    sel = ", ".join(f"{c} AS {b}" for b, c in zip(by, cols))
    gid = "grouping(" + ", ".join(cols) + ")"
    val = "count(*)" if unit == "bursts" else "count(*)"
    sql = (f"SELECT {sel}, {val} AS {unit}, {gid} AS grp {frm} GROUP BY ROLLUP ({', '.join(cols)}) "
           f"ORDER BY grp DESC, {unit} DESC LIMIT {limit + 1}")
    rows = query(sql, params)
    for r in rows:
        r["level"] = bin(r.pop("grp")).count("1")
    truncated = len(rows) > limit
    f = dict(dataset=dataset, start=start, end=end)
    return envelope("rollup", dict(by=by, unit=unit, problem_only=problem_only, limit=limit, **f), [render(sql, params)], f,
                    scope=f"{dataset or 'all datasets'}, {start or 'corpus start'} → {end or 'corpus end'}; unit = {unit}"
                          + ("; problem patterns only (Jev)" if problem_only else ""),
                    rows=rows[:limit], t0=t0, total_matches=rows[0][unit] if rows else 0, truncated=truncated,
                    note="level = number of rolled-up columns; the first row is the grand total")


COL = {"week": "date_trunc('week', {ts})::DATE::VARCHAR", "day": "date_trunc('day', {ts})::DATE::VARCHAR",
       "month": "date_trunc('month', {ts})::DATE::VARCHAR", "hour_of_day": "lpad(hour({ts})::VARCHAR, 2, '0')",
       "weekday": "dayname({ts})"}


def heatmap(
    dataset: Dataset,
    start: Start = None,
    end: End = None,
    rows: Annotated[Literal["team", "component", "severity"], Field(description="One matrix row per …")] = "team",
    cols: Annotated[Literal["week", "day", "month", "hour_of_day", "weekday"], Field(
        description="One matrix column per time bucket (or hour of day / weekday for daily rhythm).")] = "week",
    unit: Unit = "bursts",
    problem_only: Annotated[bool, Field(description="Only real-fault patterns (stored Jev judgment).")] = True,
    top_rows: Annotated[int, Field(ge=1, le=30, description="Keep the N largest rows.")] = 10,
) -> dict:
    """A matrix (SQL PIVOT) of bursts or lines: rows = teams / components / severities, columns = weeks, days, months,
    hours of day or weekdays. Shows at a glance which team's problems grow week over week, or at which hour faults
    cluster. rows = one dict per matrix row with one key per column (missing = 0).
    """
    t0 = time.perf_counter()
    check_dataset(dataset)
    frm, ts, params = _source(unit, problem_only, dataset, start, end)
    r_expr = DIM[unit][rows]
    c_expr = COL[cols].format(ts=ts)
    top_sql = f"SELECT {r_expr} AS r {frm} GROUP BY 1 ORDER BY count(*) DESC LIMIT {top_rows}"
    keep = [x["r"] for x in query(top_sql, params)]
    inner = f"SELECT {r_expr} AS {rows}, {c_expr} AS c {frm}"
    keep_sql = ", ".join("'" + str(k).replace("'", "''") + "'" for k in keep) or "NULL"
    col_sql = f"SELECT DISTINCT c FROM ({inner}) ORDER BY 1"
    cvals = [x["c"] for x in query(col_sql, params) if x["c"] is not None]
    # PIVOT with bound parameters needs its column values spelled out (ON c IN (...))
    in_list = ", ".join("'" + str(c).replace("'", "''") + "'" for c in cvals) or "NULL"
    sql = (f"PIVOT (SELECT * FROM ({inner}) WHERE {rows} IN ({keep_sql})) ON c IN ({in_list}) USING count(*) "
           f"GROUP BY {rows} ORDER BY {rows}")
    out = query(sql, params) if keep and cvals else []
    colnames = sorted({k for r in out for k in r if k != rows})
    for r in out:
        for c in colnames:
            r[c] = r.get(c) or 0
        r["total"] = sum(r[c] for c in colnames)
    out.sort(key=lambda r: -r["total"])
    f = dict(dataset=dataset, start=start, end=end)
    return envelope("heatmap", dict(rows=rows, cols=cols, unit=unit, problem_only=problem_only, top_rows=top_rows, **f),
                    [render(top_sql, params), render(col_sql, params), render(sql, params)], f,
                    scope=f"{dataset}, {start or 'corpus start'} → {end or 'corpus end'}; cell = {unit}"
                          + ("; problem patterns only (Jev)" if problem_only else ""),
                    rows=out, t0=t0, total_matches=sum(r["total"] for r in out), truncated=False, columns=colnames)


def reliability_trend(
    dataset: Dataset,
    start: Start = None,
    end: End = None,
    bucket: Annotated[Literal["day", "week"], Field(description="Bucket of the series.")] = "week",
    by_team: Annotated[bool, Field(description="Also the slope per owning team.")] = True,
) -> dict:
    """Is reliability improving? Problem bursts (real-fault patterns, stored Jev judgment) per bucket over the period,
    zero-filled, with the least-squares slope (bursts per bucket per bucket, regr_slope), first-half vs second-half
    mean, and per team the same slope. `reading` = fixed rule: slope < 0 and second-half mean < first-half mean →
    'improving', both > → 'worsening', else 'no clear change'. Counts recurrences, not incidents or impact.
    """
    t0 = time.perf_counter()
    check_dataset(dataset)
    frm, ts, params = _source("bursts", True, dataset, start, end)
    span = query(f"SELECT min({ts}) AS lo, max({ts}) AS hi {frm}", params)[0]
    if not span["lo"]:
        raise ValueError("No problem bursts in that period.")
    lo = start or span["lo"]
    hi = end or span["hi"]
    step = {"day": "1 day", "week": "7 days"}[bucket]
    g = (f"generate_series(date_trunc('{bucket}', TIMESTAMP '{lo:%Y-%m-%d %H:%M:%S}'), "
         f"TIMESTAMP '{hi:%Y-%m-%d %H:%M:%S}', interval '{step}') s(b)")
    series_sql = (f"SELECT s.b AS bucket_start, count(x.t) AS bursts FROM {g} "
                  f"LEFT JOIN (SELECT {ts} AS t {frm}) x ON date_trunc('{bucket}', x.t) = s.b GROUP BY 1 ORDER BY 1")
    series = query(series_sql, params)
    n = len(series)
    stat_sql = (f"SELECT round(regr_slope(bursts, i), 3) AS slope, round(avg(bursts) FILTER (WHERE i < {n} / 2.0), 2) AS first_half_mean, "
                f"round(avg(bursts) FILTER (WHERE i >= {n} / 2.0), 2) AS second_half_mean, sum(bursts) AS total "
                f"FROM (SELECT row_number() OVER (ORDER BY bucket_start) - 1 AS i, bursts FROM ({series_sql}))")
    st = query(stat_sql, params)[0]
    sqls = [render(series_sql, params), render(stat_sql, params)]
    teams = []
    if by_team:
        team_sql = (f"SELECT team, round(regr_slope(n, i), 3) AS slope, sum(n) AS bursts FROM ("
                    f"SELECT t.team, s.i, count(x.t) AS n FROM (SELECT row_number() OVER (ORDER BY b) - 1 AS i, b FROM {g}) s "
                    f"CROSS JOIN (SELECT DISTINCT coalesce(o.team, 'unowned') AS team {frm}) t "
                    f"LEFT JOIN (SELECT {ts} AS t, coalesce(o.team, 'unowned') AS team {frm}) x "
                    f"ON date_trunc('{bucket}', x.t) = s.b AND x.team = t.team GROUP BY 1, 2) GROUP BY 1 ORDER BY bursts DESC")
        teams = query(team_sql, params)
        sqls.append(render(team_sql, params))
    sl, a, b = st["slope"] or 0, st["first_half_mean"] or 0, st["second_half_mean"] or 0
    reading = "improving" if sl < 0 and b < a else "worsening" if sl > 0 and b > a else "no clear change"
    f = dict(dataset=dataset, start=lo, end=hi)
    return envelope("reliability_trend", dict(bucket=bucket, by_team=by_team, **f), sqls, f,
                    scope=f"{dataset}, {lo} → {hi}; problem bursts (Jev real-fault patterns) per {bucket}",
                    rows=series, t0=t0, total_matches=st["total"], truncated=False, stats=st, teams=teams,
                    reading=reading,
                    reading_rule="slope < 0 and second-half mean < first-half mean → improving; both > → worsening; else no clear change")


BINS = ("CASE WHEN v < 0.1 THEN '< 0.1 s' WHEN v < 0.5 THEN '0.1-0.5 s' WHEN v < 1 THEN '0.5-1 s' WHEN v < 5 THEN '1-5 s' "
        "WHEN v < 30 THEN '5-30 s' ELSE '>= 30 s' END")


def latency_profile(
    dataset: Dataset,
    start: Start = None,
    end: End = None,
    group_by: Annotated[Literal["component", "pattern", "status"], Field(
        description="One profile per component, per pattern (each kind of timed operation) or per HTTP status.")] = "component",
    bucket: Annotated[Optional[Literal["hour", "day"]], Field(description="Optional: one profile per group and time bucket.")] = None,
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description="Rows to return, slowest p95 first.")] = 20,
) -> dict:
    """Latency and error rate: per group (and optionally per hour / day) the count of timed operations, p50 / p95 / p99
    and max duration in seconds, and the error rate (lines with problem severity or HTTP ≥ 500 among all lines of the
    group), plus a duration histogram over everything. Durations = request latency or 'Took N seconds' messages.
    """
    t0 = time.perf_counter()
    check_dataset(dataset)
    params = {"d": dataset, "s": start, "e": end}
    tw = (" AND ts >= %(s)s" if start else "") + (" AND ts < %(e)s" if end else "")
    g = {"component": "component", "pattern": "pattern_id::VARCHAR", "status": "status::VARCHAR"}[group_by]
    bk = f", date_trunc('{bucket}', ts) AS bucket_start" if bucket else ""
    gb = "1, 2" if bucket else "1"
    base = f"SELECT {g} AS grp{bk}, {VALUE} AS v, severity, status FROM logs WHERE dataset = %(d)s{tw}"
    sql = (f"SELECT grp AS {group_by}{', bucket_start' if bucket else ''}, count(v) AS timed, "
           f"round(quantile_cont(v, 0.5), 3) AS p50_s, round(quantile_cont(v, 0.95), 3) AS p95_s, "
           f"round(quantile_cont(v, 0.99), 3) AS p99_s, round(max(v), 3) AS max_s, count(*) AS lines, "
           f"round(avg(CASE WHEN severity IN ('ERROR', 'FATAL', 'CRITICAL', 'SEVERE', 'FAILURE') OR status >= 500 "
           f"THEN 1.0 ELSE 0.0 END), 4) AS error_rate FROM ({base}) GROUP BY {gb} HAVING count(v) > 0 "
           f"ORDER BY p95_s DESC NULLS LAST LIMIT {limit + 1}")
    hist_sql = f"SELECT {BINS} AS duration, count(*) AS n FROM ({base}) WHERE v IS NOT NULL GROUP BY 1 ORDER BY min(v)"
    rows, hist = query(sql, params), query(hist_sql, params)
    if group_by == "pattern" and rows:
        tpl = {str(r["pattern_id"]): r["template"] for r in query(
            "SELECT pattern_id, template FROM patterns WHERE dataset = %(d)s", {"d": dataset})}
        for r in rows:
            r["template"] = tpl.get(r["pattern"])
    f = dict(dataset=dataset, start=start, end=end)
    return envelope("latency_profile", dict(group_by=group_by, bucket=bucket, limit=limit, **f),
                    [render(sql, params), render(hist_sql, params)], f,
                    scope=f"{dataset}, {start or 'corpus start'} → {end or 'corpus end'}; duration = request latency or "
                          f"'Took N seconds'; error = problem severity or HTTP ≥ 500",
                    rows=rows[:limit], t0=t0, total_matches=sum(h["n"] for h in hist), truncated=len(rows) > limit,
                    histogram=hist)


def team_risk(
    dataset: Dataset,
    team: Annotated[str, Field(description="Owning team (see list_values field='team').")],
    start: Start = None,
    end: End = None,
) -> dict:
    """One team's risk in measured terms: its problem patterns of the period from the computed priority ranking
    (rank, score, bursts, change vs the previous period, nodes, weeks), its burst totals now vs before, and its weekly
    problem-burst trend with slope. For "which team carries the most risk / is it getting better" follow-ups.
    Says nothing about cost, downtime or customers (not in the logs).
    """
    t0 = time.perf_counter()
    from patterns import priority_table
    pt = priority_table(dataset, start, end, limit=50)
    items = [i for i in pt["items"] if i["team"] == team]
    roll = next((r for r in pt["team_rollup"] if r["team"] == team), None)
    if roll is None:
        raise ValueError(f"No problem patterns owned by {team!r} in this period; teams: "
                         + ", ".join(r["team"] for r in pt["team_rollup"]))
    s, e = datetime.fromisoformat(pt["period"]["start"]), datetime.fromisoformat(pt["period"]["end"])
    tr = reliability_trend(dataset, s, e, "week", by_team=True)
    slope = next((t for t in tr["teams"] if t["team"] == team), None)
    return envelope("team_risk", dict(dataset=dataset, team=team, start=start, end=end), pt["sql"] + tr["sql"],
                    dict(dataset=dataset, team=team, start=s, end=e),
                    scope=pt["scope"] + f"; team {team}; ranks are among the top 50 items of all teams",
                    rows=items, t0=t0, total_matches=roll["problem_patterns"], truncated=roll["problem_patterns"] > len(items),
                    rollup=roll, team_slope=slope, priority_evidence_id=pt["evidence_id"],
                    unknown="Cost, downtime, customer impact and root cause are not in these logs.")
