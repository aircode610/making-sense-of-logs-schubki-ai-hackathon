"""Count tools: exact full-corpus counts by group, and counts over time. Counts are log LINES, never incidents."""
import time
from datetime import datetime, timedelta
from typing import Annotated, Literal, Optional

from pydantic import Field

from core import (MAX_ROWS, Component, DatasetOpt, Entity, Location, Node, PatternIdOpt, Severity, Status, Team, envelope,
                  filter_hints, filters_sql, query, render)

TREND_ROWS = 500  # a time series is long by nature; still capped and flagged
GROUPS = {"dataset": "logs.dataset", "team": "coalesce(o.team, 'unowned')", "component": "logs.component",
          "severity": "logs.severity", "node": "logs.node", "location": "logs.location"}
# Ownership (dataset, component → team) joined only when a team grouping / filter needs it; aliased so columns don't clash.
JOIN = "LEFT JOIN (SELECT dataset AS od, component AS oc, team FROM ownership) o ON o.od = logs.dataset AND o.oc = logs.component"

Dataset = DatasetOpt
GroupBy = Literal["dataset", "team", "component", "severity", "node", "location"]


QueryText = Annotated[Optional[str], Field(
    description='Optional words the message must contain (web syntax: words, "phrase", a OR b, -word). Numbers and '
                'dotted ids are whole tokens (`503`, `10.0.0.7`).')]
Since = Annotated[Optional[datetime], Field(description="Inclusive start time, 'YYYY-MM-DD HH:MM'; omit for the data's start.")]
Until = Annotated[Optional[datetime], Field(description="Exclusive end time; omit for the data's end.")]


def _where(f: dict, query_text, team) -> tuple[str, dict, bool]:
    """Common filters → (WHERE clause on `logs`, params, needs ownership join)."""
    where, params = filters_sql({k: v for k, v in f.items() if k != "team"})
    where = where.replace(" AND ", " AND logs.")  # qualify columns (the join also has dataset / component)
    if query_text:
        where += " AND logs.body @@ websearch_to_tsquery(%(q)s)"
        params["q"] = query_text
    if team is not None:
        where += " AND coalesce(o.team, 'unowned') = %(team)s"
        params["team"] = team
    return "WHERE TRUE" + where, params, team is not None


def count_by(
    group_by: Annotated[GroupBy, Field(description="Group the counts by dataset, owning team, component, severity, node "
                                                   "or full location path.")],
    dataset: Dataset = None,
    start: Since = None,
    end: Until = None,
    team: Team = None,
    component: Component = None,
    severity: Severity = None,
    node: Node = None,
    location: Location = None,
    entity: Entity = None,
    status: Status = None,
    query_text: QueryText = None,
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description=f"Groups to return, largest first (max {MAX_ROWS}).")] = 20,
) -> dict:
    """How many log lines per team / component / severity / node / location / dataset? Exact totals, not samples.

    Use when: "how much", "which team / component / node logs the most X", comparing groups, or a total for a filter
    (e.g. how many requests failed with a status, how many ERROR lines per service).
    Not for: several breakdowns of one search at once (facet), lines per time bucket (trend), recurrences of problems
    (top_patterns: bursts, not lines), totals with subtotals (rollup).
    Returns: rows {<group>, lines}, largest first; total_lines = sum over ALL groups; groups_total = distinct groups
    (truncated when > limit).
    Caveats: lines are not incidents: one fault can log thousands of lines; use bursts (top_patterns, rollup
    unit='bursts') for how often something happened.
    Example: count_by(group_by='component', dataset=<dataset>, severity='ERROR', start='<period start>')
    Next: trend with the same filters for the time profile; search_logs for example lines of the largest group.
    """
    t0 = time.perf_counter()
    f = dict(dataset=dataset, start=start, end=end, component=component, severity=severity, node=node,
             location=location, entity=entity, status=status, team=team)
    where, params, join = _where(f, query_text, team)
    expr = GROUPS[group_by]
    join = join or group_by == "team"
    frm = f"FROM logs {JOIN if join else ''} {where}"
    rows_sql = f"SELECT {expr} AS {group_by}, count(*) AS lines {frm} GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT {limit}"
    sum_sql = f"SELECT count(*) AS total_lines, count(DISTINCT {expr}) AS groups_total {frm}"
    rows, s = query(rows_sql, params), query(sum_sql, params)[0]
    return envelope("count_by", dict(group_by=group_by, query_text=query_text, limit=limit, **f),
                    [render(rows_sql, params), render(sum_sql, params)], f,
                    scope=f"{dataset or 'all datasets'}, {start or 'corpus start'} → {end or 'corpus end'}; unit = log lines",
                    rows=rows, t0=t0, total_lines=s["total_lines"], groups_total=s["groups_total"],
                    truncated=s["groups_total"] > len(rows), **({"hints": filter_hints(f)} if not s["total_lines"] else {}))


def trend(
    bucket: Annotated[Optional[Literal["hour", "day", "week"]], Field(
        description="Time bucket. Omit to choose by the data's span (> 60 days: week, > 3 days: day, else hour); "
                    "weeks start on Monday. The bucket used is returned.")] = None,
    group_by: Annotated[Optional[GroupBy], Field(description="Optional: one series per dataset / team / component / severity / node / location.")] = None,
    dataset: Dataset = None,
    start: Since = None,
    end: Until = None,
    team: Team = None,
    component: Component = None,
    severity: Severity = None,
    node: Node = None,
    location: Location = None,
    entity: Entity = None,
    status: Status = None,
    pattern_id: PatternIdOpt = None,
    query_text: QueryText = None,
    top_groups: Annotated[int, Field(ge=1, le=20, description="With group_by: keep the N largest groups.")] = 5,
) -> dict:
    """How did the number of matching log lines change over time? Lines per hour / day / week, zero-filled.

    Use when: "is it rising", "when did it start / stop", "week over week", "at which hours / days does X peak",
    for any filter or search text, optionally one series per team / component / node.
    Not for: recurrences of one pattern over its life (pattern_history), problem bursts with a computed direction
    (reliability_trend), a team x week matrix of bursts (heatmap), whether this window is unusual (rate_vs_baseline).
    Returns: rows {bucket_start, [group], lines} with empty buckets as 0; total_lines; first_ts / last_ts of the
    matches; the bucket used.
    Caveats: lines, not incidents; direction is not computed here (compare the numbers or use reliability_trend);
    the first / last bucket can be partial.
    Example: trend(dataset=<dataset>, query_text='"failed password"', bucket='day')
    Next: rate_vs_baseline for the peak window; search_logs in the peak bucket for example lines.
    """
    t0 = time.perf_counter()
    f = dict(dataset=dataset, start=start, end=end, component=component, severity=severity, node=node,
             location=location, entity=entity, status=status, pattern_id=pattern_id, team=team)
    where, params, join = _where(f, query_text, team)
    join = join or group_by == "team"
    frm = f"FROM logs {JOIN if join else ''} {where}"
    span_sql = f"SELECT count(*) AS total_lines, min(logs.ts) AS first_ts, max(logs.ts) AS last_ts {frm}"
    span = query(span_sql, params)[0]
    sqls = [render(span_sql, params)]
    scope = f"{dataset or 'all datasets'}, {start or 'corpus start'} → {end or 'corpus end'}; unit = log lines"
    if not span["total_lines"]:
        return envelope("trend", dict(bucket=bucket, group_by=group_by, query_text=query_text, **f),
                        sqls, f, scope, [], t0, bucket=bucket, total_lines=0, truncated=False, hints=filter_hints(f))
    days = (span["last_ts"] - span["first_ts"]).days
    b = bucket or ("week" if days > 60 else "day" if days > 3 else "hour")
    step = {"hour": "1 hour", "day": "1 day", "week": "7 days"}[b]
    # bounds come from the DB, not the caller: inlined as literals (bound params in generate_series upset the wire protocol)
    lo, hi = (f"TIMESTAMP '{t:%Y-%m-%d %H:%M:%S.%f}'" for t in (span["first_ts"], span["last_ts"]))
    if group_by:
        expr = GROUPS[group_by]
        top_sql = f"SELECT {expr} AS g {frm} GROUP BY 1 ORDER BY count(*) DESC, 1 LIMIT {top_groups}"
        groups = [r["g"] for r in query(top_sql, params)]
        sqls.append(render(top_sql, params))
        glist = ", ".join("('" + str(g).replace("'", "''") + "')" for g in groups)
        rows_sql = (f"SELECT s.b AS bucket_start, g.g AS {group_by}, count(c.ts) AS lines "
                    f"FROM generate_series(date_trunc('{b}', {lo}), {hi}, interval '{step}') s(b) "
                    f"CROSS JOIN (VALUES {glist}) g(g) "
                    f"LEFT JOIN (SELECT logs.ts, {expr} AS g {frm}) c ON date_trunc('{b}', c.ts) = s.b AND c.g = g.g "
                    f"GROUP BY 1, 2 ORDER BY 2, 1 LIMIT {TREND_ROWS + 1}")
    else:
        rows_sql = (f"SELECT s.b AS bucket_start, count(c.ts) AS lines "
                    f"FROM generate_series(date_trunc('{b}', {lo}), {hi}, interval '{step}') s(b) "
                    f"LEFT JOIN (SELECT logs.ts {frm}) c ON date_trunc('{b}', c.ts) = s.b GROUP BY 1 ORDER BY 1 LIMIT {TREND_ROWS + 1}")
    rows = query(rows_sql, params)
    sqls.append(render(rows_sql, params))
    truncated = len(rows) > TREND_ROWS
    rows = rows[:TREND_ROWS]
    return envelope("trend", dict(bucket=b, group_by=group_by, query_text=query_text, top_groups=top_groups, **f),
                    sqls, f, scope, rows, t0, bucket=b, total_lines=span["total_lines"],
                    first_ts=span["first_ts"].isoformat(sep=" "), last_ts=span["last_ts"].isoformat(sep=" "),
                    groups=groups if group_by else None, truncated=truncated,
                    **({"note": f"only the {top_groups} largest groups are shown; their lines are a subset of total_lines"}
                       if group_by else {}))


def rate_vs_baseline(
    start: Annotated[datetime, Field(description="Window start (inclusive), e.g. the hour around the incident.")],
    end: Annotated[datetime, Field(description="Window end (exclusive).")],
    dataset: Dataset = None,
    days: Annotated[int, Field(ge=1, le=60, description="Baseline = up to `days` days just before `start`.")] = 7,
    query_text: QueryText = None,
    pattern_id: PatternIdOpt = None,
    component: Component = None,
    severity: Severity = None,
    node: Node = None,
    location: Location = None,
    status: Status = None,
) -> dict:
    """Is this rate unusual here? Matching lines in a window vs the same-length windows just before it.

    Use when: you have an incident window and need "how unusual is this": the rate now vs the usual rate, how many
    earlier windows reached it, or whether it never happened before (new here).
    Not for: a time series (trend), whether a pattern is new in the whole dataset (pattern_history / whats_new).
    Returns: window_lines and rate per hour; baseline_lines, baseline rate, ratio (window / usual), max per earlier
    window, how many earlier windows were at or above the window; flags new_in_baseline (0 before → new here),
    baseline_clipped (less history than asked), no_baseline_data (nothing earlier: cannot call it new or unusual).
    Caveats: lines, not incidents; the baseline is cut into windows of the SAME length as the window.
    Example: rate_vs_baseline(dataset=<dataset>, start='<incident hour start>', end='<+1 h>', severity='ERROR', days=7)
    Next: get_context / burst_timeline at the window to explain the jump.
    """
    t0 = time.perf_counter()
    if end <= start:
        raise ValueError("end must be after start.")
    w = (end - start).total_seconds()
    f = dict(dataset=dataset, component=component, severity=severity, node=node, location=location, status=status,
             pattern_id=pattern_id)
    where, params, _ = _where(f, query_text, None)
    # Baseline never starts before the data does; only whole windows count (aligned back from `start`).
    data_sql = "SELECT min(ts) AS t FROM logs" + (" WHERE dataset = %(dataset)s" if dataset else "")
    data_start = query(data_sql, {"dataset": dataset})[0]["t"]
    asked = start - timedelta(days=days)
    n_win = max(0, int((start - max(asked, data_start)).total_seconds() // w))
    bstart = start - timedelta(seconds=n_win * w)
    params.update(ws=start, we=end, bs=bstart, w=w, h=w / 3600, nw=n_win)
    now_sql = (f"SELECT count(*) AS window_lines, round(count(*) / %(h)s, 3) AS window_rate_per_h "
               f"FROM logs {where} AND logs.ts >= %(ws)s AND logs.ts < %(we)s")
    now = query(now_sql, params)[0]
    params["n"] = now["window_lines"]
    sqls = [render(data_sql, {"dataset": dataset}), render(now_sql, params)]
    row = {**now, "window_hours": round(w / 3600, 3), "baseline_start": bstart, "baseline_windows": n_win,
           "baseline_hours": round(n_win * w / 3600, 3), "baseline_clipped": bstart > asked}
    if n_win:
        # k = which earlier window (0 = just before `start`); windows without lines count as 0 lines.
        base_sql = (f"WITH b AS (SELECT floor((epoch(%(ws)s::TIMESTAMP) - epoch(logs.ts)) / %(w)s) AS k, count(*) AS n "
                    f"FROM logs {where} AND logs.ts >= %(bs)s AND logs.ts < %(ws)s GROUP BY 1) "
                    f"SELECT coalesce(sum(n), 0)::BIGINT AS baseline_lines, "
                    f"round(coalesce(sum(n), 0)::DOUBLE / (%(nw)s * %(h)s), 3) AS baseline_rate_per_h, "
                    f"round(%(n)s / nullif(sum(n)::DOUBLE / %(nw)s, 0), 1) AS ratio, "
                    f"coalesce(max(n), 0) AS baseline_max_per_window, "
                    f"count(*) FILTER (WHERE n >= %(n)s AND %(n)s > 0) AS baseline_windows_at_or_above, "
                    f"round(count(*) FILTER (WHERE n >= %(n)s AND %(n)s > 0)::DOUBLE / %(nw)s, 4) AS share_windows_at_or_above "
                    f"FROM b")
        row.update(query(base_sql, params)[0])
        sqls.append(render(base_sql, params))
    filters = {**f, "query_text": query_text}
    scope = (f"{dataset or 'all datasets'}; window {start} → {end} ({w / 3600:g} h) vs {n_win} earlier windows of the same "
             f"length, {bstart} → {start}" + (f" (clipped: data starts {data_start}, {days} days asked)" if bstart > asked else "")
             + "; unit = log lines")
    return envelope("rate_vs_baseline", dict(start=start, end=end, days=days, **filters), sqls, filters, scope,
                    rows=[row], t0=t0, total_matches=now["window_lines"], truncated=False,
                    no_baseline_data=n_win == 0,
                    new_in_baseline=bool(n_win) and row.get("baseline_lines") == 0 and now["window_lines"] > 0)
