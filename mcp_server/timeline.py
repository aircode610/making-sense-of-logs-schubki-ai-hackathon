"""Timeline and correlation tools (plan 011): one pattern's history, the sequence inside a burst, how widespread a
problem is, what is new, what tends to come before / together with a problem, how regular it is, and one request's
path. All computed in SQL over the patterns / bursts / episodes tables (plan 004) with window functions, ASOF joins and
statistical aggregates; association is never presented as cause."""
import time
from datetime import datetime, timedelta
from typing import Annotated, Literal, Optional

from pydantic import Field

from core import (MAX_ROWS, Dataset, ObjectId, RequestId, check_dataset, envelope, filters_sql, query, render,
                  tsquery_sql)

PatternId = Annotated[int, Field(description="Log pattern id: a kind of message (from search_logs rows, top_patterns, "
                                             "priority_table, find_patterns, …).")]
TEAM = "LEFT JOIN ownership o ON o.dataset = p.dataset AND o.component = p.component"
JUDGE = "LEFT JOIN pattern_judgments j ON j.dataset = p.dataset AND j.pattern_id = p.pattern_id"


def _pattern(dataset: str, pattern_id: int) -> dict:
    rows = query(f"SELECT p.*, coalesce(o.team, 'unowned') AS team, round(j.p_problem, 3) AS p_problem, "
                 f"j.kind FROM patterns p {TEAM} {JUDGE} WHERE p.dataset = %(d)s AND p.pattern_id = %(p)s",
                 {"d": dataset, "p": pattern_id})
    if not rows:
        raise ValueError(f"No pattern {pattern_id} in {dataset}; take pattern_id from search_logs / top_patterns rows.")
    return rows[0]


def pattern_history(
    dataset: Dataset,
    pattern_id: PatternId,
    bucket: Annotated[Literal["day", "week", "month"], Field(description="Bucket of the bursts-over-time series.")] = "week",
    as_of: Annotated[Optional[datetime], Field(
        description="Optional 'now' for the new-vs-recurring question: counts before this time are returned too.")] = None,
) -> dict:
    """Is this kind of message new or recurring, and how has it behaved over the whole dataset?

    Use when: you have one pattern (a kind of error) and need its life: first / last seen, how many bursts over time,
    longest quiet gap, and with `as_of` whether it had ever happened before an incident ("new or recurring?").
    Not for: many patterns at once (top_patterns), lines of any search over time (trend), schedule / time-of-day
    regularity (periodicity).
    Returns: the pattern (template, component, team, lines, bursts, nodes, weeks_active, first_ts, last_ts,
    p_problem), bursts and lines per bucket over the whole dataset (zero-filled), gap statistics, and `before`
    (bursts / lines before as_of, new_as_of).
    Caveats: bursts = recurrences split by > 30 min quiet, not confirmed incidents.
    Example: pattern_history(dataset=<dataset>, pattern_id=<id>, bucket='week', as_of='<incident time>')
    Next: spread(pattern_id) for how widespread; precursors(pattern_id) for what comes before it.
    """
    t0 = time.perf_counter()
    check_dataset(dataset)
    p = _pattern(dataset, pattern_id)
    params = {"d": dataset, "p": pattern_id}
    span = query("SELECT min(ts) AS lo, max(ts) AS hi FROM logs WHERE dataset = %(d)s", {"d": dataset})[0]
    lo, hi = (f"TIMESTAMP '{t:%Y-%m-%d %H:%M:%S}'" for t in (span["lo"], span["hi"]))
    step = {"day": "1 day", "week": "7 days", "month": "1 month"}[bucket]
    series_sql = (f"SELECT s.b AS bucket_start, count(b.burst_no) AS bursts, coalesce(sum(b.lines), 0) AS lines "
                  f"FROM generate_series(date_trunc('{bucket}', {lo}), {hi}, interval '{step}') s(b) "
                  f"LEFT JOIN bursts b ON b.dataset = %(d)s AND b.pattern_id = %(p)s AND date_trunc('{bucket}', b.start_ts) = s.b "
                  f"GROUP BY 1 ORDER BY 1")
    gap_sql = ("SELECT max(gap) AS longest_gap, median(gap) AS median_gap, count(*) AS gaps FROM ("
               "SELECT start_ts - lag(end_ts) OVER (ORDER BY start_ts) AS gap FROM bursts "
               "WHERE dataset = %(d)s AND pattern_id = %(p)s) WHERE gap IS NOT NULL")
    series, gaps = query(series_sql, params), query(gap_sql, params)[0]
    sqls = [render(series_sql, params), render(gap_sql, params)]
    before = None
    if as_of:
        params["t"] = as_of
        b_sql = ("SELECT (SELECT count(*) FROM bursts WHERE dataset = %(d)s AND pattern_id = %(p)s AND start_ts < %(t)s) AS bursts_before, "
                 "(SELECT count(*) FROM logs WHERE dataset = %(d)s AND pattern_id = %(p)s AND ts < %(t)s) AS lines_before")
        before = query(b_sql, params)[0]
        before["new_as_of"] = before["lines_before"] == 0
        sqls.append(render(b_sql, params))
    gaps = {k: (str(v) if isinstance(v, timedelta) else v) for k, v in gaps.items()}
    return envelope("pattern_history", dict(dataset=dataset, pattern_id=pattern_id, bucket=bucket, as_of=as_of), sqls,
                    dict(dataset=dataset, pattern_id=pattern_id),
                    scope=f"{dataset}, whole dataset {span['lo']} → {span['hi']}; bursts = recurrences (30-min gap)",
                    rows=series, t0=t0, total_matches=p["bursts"], truncated=False,
                    pattern={k: p[k] for k in ("pattern_id", "template", "component", "team", "severity", "lines", "bursts",
                                               "nodes", "weeks_active", "first_ts", "last_ts", "p_problem", "kind")},
                    gaps=gaps, before=before)


def burst_timeline(
    dataset: Dataset,
    pattern_id: PatternId,
    at: Annotated[Optional[datetime], Field(
        description="A time inside (or just before) the burst; omit to take the pattern's largest burst.")] = None,
    before_s: Annotated[int, Field(ge=0, le=86400, description="Also look this many seconds before the burst start.")] = 600,
    same_nodes: Annotated[bool, Field(description="Only lines on the burst's own nodes (else the whole dataset).")] = True,
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description="Patterns in the sequence to return.")] = 20,
) -> dict:
    """Which error came first? The order in which kinds of messages appeared around one burst of a problem.

    Use when: an incident involves several errors and you need the sequence: what showed up first on the affected
    nodes, from `before_s` before the burst to its end.
    Not for: the raw lines around one line (get_context), what usually precedes this problem across all its
    occurrences (precursors).
    Returns: the burst (start, end, lines, nodes, its first line) and one row per pattern seen in the window (first
    time, lines, nodes, level, owner, template), earliest first; first_problem = the earliest pattern with
    problem-level lines.
    Caveats: earlier is not cause: label a causal reading as a hypothesis. Without a node in the dataset, "same
    nodes" means the same component.
    Example: burst_timeline(dataset=<dataset>, pattern_id=<id>, at='<incident time>')
    Next: get_context(line_id of the first problem line) for the raw lines; precursors(pattern_id) for the general
    pattern.
    """
    t0 = time.perf_counter()
    check_dataset(dataset)
    p = _pattern(dataset, pattern_id)
    params = {"d": dataset, "p": pattern_id, "at": at}
    b_sql = ("SELECT * FROM bursts WHERE dataset = %(d)s AND pattern_id = %(p)s "
             + ("AND end_ts >= %(at)s ORDER BY start_ts LIMIT 1" if at else "ORDER BY lines DESC, start_ts LIMIT 1"))
    bs = query(b_sql, params)
    if not bs:
        raise ValueError("No burst of this pattern at or after that time.")
    b = bs[0]
    params.update(s=b["start_ts"] - timedelta(seconds=before_s), e=b["end_ts"] + timedelta(microseconds=1),
                  bs=b["start_ts"], be=b["end_ts"] + timedelta(microseconds=1))
    first_sql = "SELECT line_id, ts, node, component, severity, body FROM logs WHERE dataset = %(d)s AND line_id = %(l)s"
    first = query(first_sql, {"d": dataset, "l": b["first_line_id"]})
    nodes_f = ("AND coalesce(l.node, l.component) IN (SELECT DISTINCT coalesce(node, component) FROM logs "
               "WHERE dataset = %(d)s AND pattern_id = %(p)s AND ts >= %(bs)s AND ts < %(be)s)") if same_nodes else ""
    seq_sql = (f"SELECT l.pattern_id, min(l.ts) AS first_ts, count(*) AS lines, count(DISTINCT l.node) AS nodes, "
               f"mode(l.severity) AS severity, any_value(p.template) AS template, any_value(coalesce(o.team, 'unowned')) AS team, "
               f"bool_or(l.severity IN ('FATAL', 'FAILURE', 'SEVERE', 'ERROR', 'CRITICAL', 'WARN', 'WARNING') OR l.status >= 500) AS problem_level "
               f"FROM logs l JOIN patterns p ON p.dataset = l.dataset AND p.pattern_id = l.pattern_id {TEAM} "
               f"WHERE l.dataset = %(d)s AND l.ts >= %(s)s AND l.ts < %(e)s {nodes_f} "
               f"GROUP BY 1 ORDER BY 2, 1")
    seq = query(seq_sql, params)
    first_problem = next((r for r in seq if r["problem_level"]), None)
    return envelope("burst_timeline", dict(dataset=dataset, pattern_id=pattern_id, at=at, before_s=before_s,
                                           same_nodes=same_nodes, limit=limit),
                    [render(b_sql, params), render(first_sql, {"d": dataset, "l": b["first_line_id"]}), render(seq_sql, params)],
                    dict(dataset=dataset, pattern_id=pattern_id),
                    scope=f"{dataset}, burst {b['burst_no']} of pattern {pattern_id}: {b['start_ts']} → {b['end_ts']}; "
                          f"sequence from {params['s']} on {'the burst nodes' if same_nodes else 'all nodes'}",
                    rows=seq[:limit], t0=t0, total_matches=len(seq), truncated=len(seq) > limit,
                    burst={k: b[k] for k in ("burst_no", "start_ts", "end_ts", "lines", "nodes")},
                    burst_first_line=first[0] if first else None,
                    first_problem=first_problem and {k: first_problem[k] for k in ("pattern_id", "first_ts", "template")},
                    pattern={"template": p["template"], "team": p["team"]})


def spread(
    dataset: Dataset,
    pattern_id: Annotated[Optional[int], Field(description="Pattern to measure (or give query_text).")] = None,
    query_text: Annotated[Optional[str], Field(description="Full-text search instead of a pattern (web syntax).")] = None,
    start: Annotated[Optional[datetime], Field(description="Inclusive start time.")] = None,
    end: Annotated[Optional[datetime], Field(description="Exclusive end time.")] = None,
) -> dict:
    """Is it one bad node or fleet-wide? How the matching lines spread over nodes and top-level locations.

    Use when: "local or systemic?", "how many machines are affected", "is it one host / rack / pod".
    Not for: lines per node as a ranking only (count_by group_by='node'), spread over time (trend).
    Returns: nodes, top nodes with lines, top_node_share (1.0 = one node only), entropy_norm (0 = all on one node,
    1 = perfectly even), lines and nodes per top-level location, and `reading` (concentrated / mixed / widespread)
    with the fixed rule that produced it.
    Caveats: datasets without a node use the component as the unit (said in `scope`); lines, not incidents.
    Example: spread(dataset=<dataset>, pattern_id=<id>, start='<period start>')
    Next: search_logs(node=<top node>) or get_context on that node; pattern_history for whether it is new.
    """
    t0 = time.perf_counter()
    if pattern_id is None and not query_text:
        raise ValueError("Give pattern_id or query_text.")
    f = dict(dataset=dataset, start=start, end=end, pattern_id=pattern_id)
    where, params = filters_sql(f)
    if query_text:
        expr, qp = tsquery_sql(query_text, "web")
        where += f" AND body @@ {expr}"
        params.update(qp)
    sum_sql = (f"SELECT count(*) AS lines, count(DISTINCT coalesce(node, component)) AS nodes, "
               f"approx_top_k(coalesce(node, component), 5) AS top_nodes, entropy(coalesce(node, component)) AS entropy_bits "
               f"FROM logs WHERE TRUE{where}")
    s = query(sum_sql, params)[0]
    top_sql = (f"SELECT coalesce(node, component) AS node, count(*) AS lines FROM logs WHERE TRUE{where} "
               f"GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT 5")
    loc_sql = (f"SELECT split_part(location, '/', 1) AS location_top, count(*) AS lines, count(DISTINCT node) AS nodes "
               f"FROM logs WHERE TRUE{where} AND location IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT 20")
    top, locs = query(top_sql, params), query(loc_sql, params)
    import math
    n = s["nodes"] or 0
    norm = round(s["entropy_bits"] / math.log2(n), 3) if n > 1 and s["entropy_bits"] is not None else 0.0
    share = round(top[0]["lines"] / s["lines"], 3) if top and s["lines"] else None
    rule = "top_node_share ≥ 0.5 → 'concentrated'; nodes ≥ 10 and entropy_norm ≥ 0.8 → 'widespread'; else 'mixed'"
    reading = ("no lines" if not s["lines"] else "concentrated on one node" if share >= 0.5
               else "widespread" if n >= 10 and norm >= 0.8 else "mixed")
    return envelope("spread", dict(query_text=query_text, **f),
                    [render(sum_sql, params), render(top_sql, params), render(loc_sql, params)], f,
                    scope=f"{dataset}, {start or 'corpus start'} → {end or 'corpus end'}; node = emitting node (component "
                          f"when the dataset has none); unit = log lines",
                    rows=locs, t0=t0, total_matches=s["lines"], truncated=False, nodes=n, top_nodes=top,
                    top_node_share=share, entropy_norm=norm, reading=reading, reading_rule=rule)


def whats_new(
    dataset: Dataset,
    start: Annotated[datetime, Field(description="Period start (inclusive).")],
    end: Annotated[datetime, Field(description="Period end (exclusive).")],
    problem_only: Annotated[bool, Field(description="Only patterns the stored Jev judgment calls a real fault.")] = True,
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description="Patterns to return, most bursts first.")] = 20,
) -> dict:
    """What is new this period? Kinds of messages whose first appearance in the whole dataset falls inside it.

    Use when: "anything new this week", "did a new error appear after the change", a period review.
    Not for: problems that existed before and grew (top_patterns rank_by='growth'), unusual words (distinctive_terms).
    Returns: per new pattern: template, component, team, first_ts, bursts / lines / nodes up to the period end,
    p_problem and kind (stored Jev judgment); total_matches = all new patterns in the period.
    Caveats: a new pattern is a new kind of message, not necessarily a new problem (problem_only=True keeps only
    those judged real faults or security events).
    Example: whats_new(dataset=<dataset>, start='<week start>', end='<week end>')
    Next: pattern_history / spread(pattern_id) for a new pattern; search_logs(pattern_id=…) for its lines.
    """
    t0 = time.perf_counter()
    check_dataset(dataset)
    params = {"d": dataset, "s": start, "e": end}
    pf = "AND j.p_problem >= 0.5" if problem_only else ""
    sql = (f"SELECT p.pattern_id, p.template, p.component, coalesce(o.team, 'unowned') AS team, p.first_ts, "
           f"(SELECT count(*) FROM bursts b WHERE b.dataset = p.dataset AND b.pattern_id = p.pattern_id AND b.start_ts < %(e)s) AS bursts, "
           f"(SELECT count(*) FROM logs l WHERE l.dataset = p.dataset AND l.pattern_id = p.pattern_id AND l.ts < %(e)s) AS lines, "
           f"(SELECT count(DISTINCT node) FROM logs l WHERE l.dataset = p.dataset AND l.pattern_id = p.pattern_id AND l.ts < %(e)s) AS nodes, "
           f"round(j.p_problem, 3) AS p_problem, j.kind "
           f"FROM patterns p {TEAM} {JUDGE} WHERE p.dataset = %(d)s AND p.first_ts >= %(s)s AND p.first_ts < %(e)s {pf} "
           f"ORDER BY bursts DESC, lines DESC, p.pattern_id")
    rows = query(sql, params)
    return envelope("whats_new", dict(dataset=dataset, start=start, end=end, problem_only=problem_only, limit=limit),
                    [render(sql, params)], dict(dataset=dataset, start=start, end=end),
                    scope=f"{dataset}, patterns first seen {start} → {end} (first occurrence in the whole dataset); "
                          f"counts within the period", rows=rows[:limit], t0=t0, total_matches=len(rows),
                    truncated=len(rows) > limit)


def _episodes_key(scope: str) -> tuple[str, str]:
    """(table, key column) for co-occurrence / precursor scopes."""
    return ("episodes", "node") if scope == "node" else ("bursts", "dataset")


def precursors(
    dataset: Dataset,
    pattern_id: PatternId,
    window_s: Annotated[int, Field(ge=10, le=86400, description="How far before each occurrence to look (seconds).")] = 600,
    scope: Annotated[Literal["node", "dataset"], Field(
        description="'node' = before it on the SAME node (per-node episodes), 'dataset' = anywhere (bursts).")] = "node",
    start: Annotated[Optional[datetime], Field(description="Only occurrences from this time.")] = None,
    end: Annotated[Optional[datetime], Field(description="Only occurrences before this time.")] = None,
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description="Preceding patterns to return.")] = 10,
) -> dict:
    """What tends to happen just BEFORE this problem? Other kinds of messages that start shortly before it, across
    all its occurrences, compared with a control.

    Use when: "what leads up to X", "is there an early warning sign", looking for a candidate cause or precursor of a
    recurring problem.
    Not for: the lines around one occurrence (get_context), the order inside one burst (burst_timeline), what happens
    at the same time (co_occurrence).
    Returns: per preceding pattern: occurrences preceded, share, median lead time (s), control share (same look-back
    one day earlier) and lift = share / control; `nearest` = the immediately preceding pattern per occurrence.
    Caveats: association in time, not cause: report candidates with lift and share, never as "the cause". scope='node'
    needs a node in the dataset; otherwise use scope='dataset'.
    Example: precursors(dataset=<dataset>, pattern_id=<id>, window_s=600)
    Next: search_logs(pattern_id=<precursor>) for its lines; burst_timeline to see one occurrence in order.
    """
    t0 = time.perf_counter()
    check_dataset(dataset)
    tbl, key = _episodes_key(scope)
    params = {"d": dataset, "p": pattern_id, "w": window_s, "s": start, "e": end}
    tw = (" AND start_ts >= %(s)s" if start else "") + (" AND start_ts < %(e)s" if end else "")
    tgt = f"SELECT {key} AS k, start_ts AS t FROM {tbl} WHERE dataset = %(d)s AND pattern_id = %(p)s{tw}"
    n = query(f"SELECT count(*) AS n FROM ({tgt})", params)[0]["n"]
    if not n:
        raise ValueError("No occurrences of this pattern in that period.")
    pre = (f"WITH t AS ({tgt}), o AS (SELECT {key} AS k, start_ts AS t, pattern_id FROM {tbl} "
           f"WHERE dataset = %(d)s AND pattern_id <> %(p)s), "
           f"hit AS (SELECT o.pattern_id, t.k, t.t, min(epoch(t.t) - epoch(o.t)) AS lead_s FROM t JOIN o ON o.k = t.k "
           f"AND o.t < t.t AND o.t >= t.t - to_seconds(%(w)s) GROUP BY 1, 2, 3), "
           f"ctl AS (SELECT DISTINCT o.pattern_id, t.k, t.t FROM t JOIN o ON o.k = t.k "
           f"AND o.t < t.t - INTERVAL 1 DAY AND o.t >= t.t - INTERVAL 1 DAY - to_seconds(%(w)s)) "
           f"SELECT h.pattern_id, count(*) AS preceded, round(count(*) / {n}::DOUBLE, 3) AS share, "
           f"round(median(h.lead_s), 1) AS median_lead_s, "
           f"round(coalesce((SELECT count(*) FROM ctl WHERE ctl.pattern_id = h.pattern_id), 0) / {n}::DOUBLE, 3) AS control_share "
           f"FROM hit h GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT {limit}")
    rows = query(pre, params)
    ids = [r["pattern_id"] for r in rows]
    if ids:
        meta = {r["pattern_id"]: r for r in query(
            f"SELECT p.pattern_id, p.template, coalesce(o.team, 'unowned') AS team, p.severity FROM patterns p {TEAM} "
            f"WHERE p.dataset = %(d)s AND p.pattern_id IN ({', '.join(map(str, ids))})", {"d": dataset})}
        for r in rows:
            r.update(meta.get(r["pattern_id"], {}))
            r["lift"] = round(r["share"] / max(r["control_share"], 1 / n), 1)
    near = (f"WITH t AS ({tgt}), o AS (SELECT {key} AS k, start_ts AS t, pattern_id FROM {tbl} "
            f"WHERE dataset = %(d)s AND pattern_id <> %(p)s) "
            f"SELECT o.pattern_id, count(*) AS times_nearest FROM t ASOF JOIN o ON o.k = t.k AND o.t < t.t "
            f"WHERE t.t - o.t <= to_seconds(%(w)s) GROUP BY 1 ORDER BY 2 DESC LIMIT 5")
    nearest = query(near, params)
    p = _pattern(dataset, pattern_id)
    return envelope("precursors", dict(dataset=dataset, pattern_id=pattern_id, window_s=window_s, scope=scope,
                                       start=start, end=end, limit=limit),
                    [render(pre, params), render(near, params)], dict(dataset=dataset, pattern_id=pattern_id),
                    scope=f"{dataset}, {n} occurrences of pattern {pattern_id} ({'node episodes' if scope == 'node' else 'bursts'}); "
                          f"look-back {window_s} s; control = same look-back one day earlier",
                    rows=rows, t0=t0, total_matches=len(rows), truncated=len(rows) >= limit, occurrences=n,
                    nearest=nearest, target={"template": p["template"], "team": p["team"]})


def co_occurrence(
    dataset: Dataset,
    pattern_a: PatternId,
    pattern_b: Annotated[Optional[int], Field(description="Second pattern; omit to list the patterns that co-occur most with A.")] = None,
    window_s: Annotated[int, Field(ge=10, le=86400, description="Within how many seconds (either side) counts as together.")] = 300,
    scope: Annotated[Literal["node", "dataset"], Field(
        description="'node' = on the SAME node (episodes), 'dataset' = anywhere (bursts).")] = "node",
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description="Patterns to return when pattern_b is omitted.")] = 10,
) -> dict:
    """Do these kinds of messages occur together? What shows up around a problem, compared with a control.

    Use when: "does X happen together with Y", "what else goes wrong at the same time as X", grouping symptoms of one
    problem.
    Not for: what comes BEFORE (precursors), the order inside one burst (burst_timeline).
    Returns: share of A's occurrences with a B occurrence within ±window_s (same node or anywhere), the control share
    (A shifted one day) and lift; without pattern_b: the patterns most often found around A.
    Caveats: association, not cause.
    Example: co_occurrence(dataset=<dataset>, pattern_a=<id>, window_s=300, scope='dataset')
    Next: search_logs(pattern_id=…) for the companion pattern's lines.
    """
    t0 = time.perf_counter()
    check_dataset(dataset)
    tbl, key = _episodes_key(scope)
    params = {"d": dataset, "a": pattern_a, "b": pattern_b, "w": window_s}
    n = query(f"SELECT count(*) AS n FROM {tbl} WHERE dataset = %(d)s AND pattern_id = %(a)s", params)[0]["n"]
    if not n:
        raise ValueError("Pattern A has no occurrences.")
    bf = "AND pattern_id = %(b)s" if pattern_b is not None else "AND pattern_id <> %(a)s"
    sql = (f"WITH a AS (SELECT {key} AS k, start_ts AS t FROM {tbl} WHERE dataset = %(d)s AND pattern_id = %(a)s), "
           f"o AS (SELECT {key} AS k, start_ts AS t, pattern_id FROM {tbl} WHERE dataset = %(d)s {bf}), "
           f"hit AS (SELECT DISTINCT o.pattern_id, a.k, a.t FROM a JOIN o ON o.k = a.k "
           f"AND abs(epoch(o.t) - epoch(a.t)) <= %(w)s), "
           f"ctl AS (SELECT DISTINCT o.pattern_id, a.k, a.t FROM a JOIN o ON o.k = a.k "
           f"AND abs(epoch(o.t) - epoch(a.t) + 86400) <= %(w)s) "
           f"SELECT h.pattern_id, count(*) AS a_with_b, round(count(*) / {n}::DOUBLE, 3) AS share, "
           f"round(coalesce((SELECT count(*) FROM ctl WHERE ctl.pattern_id = h.pattern_id), 0) / {n}::DOUBLE, 3) AS control_share "
           f"FROM hit h GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT {limit if pattern_b is None else 1}")
    rows = query(sql, params)
    if pattern_b is not None and not rows:
        rows = [{"pattern_id": pattern_b, "a_with_b": 0, "share": 0.0, "control_share": 0.0}]
    ids = [r["pattern_id"] for r in rows]
    meta = {r["pattern_id"]: r for r in query(
        f"SELECT p.pattern_id, p.template, coalesce(o.team, 'unowned') AS team FROM patterns p {TEAM} "
        f"WHERE p.dataset = %(d)s AND p.pattern_id IN ({', '.join(map(str, ids or [-1]))})", {"d": dataset})}
    for r in rows:
        r.update(meta.get(r["pattern_id"], {}))
        r["lift"] = round(r["share"] / max(r["control_share"], 1 / n), 1)
    a = _pattern(dataset, pattern_a)
    return envelope("co_occurrence", dict(dataset=dataset, pattern_a=pattern_a, pattern_b=pattern_b, window_s=window_s,
                                          scope=scope, limit=limit), [render(sql, params)],
                    dict(dataset=dataset, pattern_a=pattern_a, pattern_b=pattern_b),
                    scope=f"{dataset}, {n} occurrences of pattern {pattern_a} ({'node episodes' if scope == 'node' else 'bursts'}); "
                          f"together = within ±{window_s} s{' on the same node' if scope == 'node' else ''}; control = A shifted one day",
                    rows=rows, t0=t0, total_matches=len(rows), truncated=pattern_b is None and len(rows) >= limit,
                    occurrences_a=n, pattern_a_template=a["template"])


def periodicity(
    dataset: Dataset,
    pattern_id: PatternId,
) -> dict:
    """Does this problem recur on a schedule or at certain hours / weekdays?

    Use when: "is it periodic", "does it happen every night / every hour", "at what time of day does it peak",
    cron-like or shift-like faults.
    Not for: lines of a search per hour across days (trend bucket='hour'), whether it is new (pattern_history).
    Returns: gap statistics between bursts (count, median, MAD, regular_share = gaps within ±20 % of the median),
    a gap histogram (< 1 h … > 7 d), bursts by hour of day and by weekday, and `reading` with its fixed rule.
    Caveats: counts burst starts of one pattern, not lines.
    Example: periodicity(dataset=<dataset>, pattern_id=<id>)
    Next: trend(pattern_id=…, bucket='hour') for the raw hourly volume.
    """
    t0 = time.perf_counter()
    check_dataset(dataset)
    params = {"d": dataset, "p": pattern_id}
    g = ("SELECT epoch(start_ts) - epoch(lag(start_ts) OVER (ORDER BY start_ts)) AS gap_s, start_ts FROM bursts "
         "WHERE dataset = %(d)s AND pattern_id = %(p)s")
    st_sql = (f"SELECT count(gap_s) AS gaps, round(median(gap_s)) AS median_gap_s, round(mad(gap_s)) AS mad_gap_s, "
              f"round(avg(CASE WHEN abs(gap_s - m) <= 0.2 * m THEN 1.0 ELSE 0.0 END), 3) AS regular_share "
              f"FROM ({g}) x, (SELECT median(gap_s) AS m FROM ({g}) WHERE gap_s IS NOT NULL) med WHERE gap_s IS NOT NULL")
    hist_sql = (f"SELECT CASE WHEN gap_s < 3600 THEN '< 1 h' WHEN gap_s < 21600 THEN '1-6 h' WHEN gap_s < 86400 THEN '6-24 h' "
                f"WHEN gap_s < 604800 THEN '1-7 d' ELSE '> 7 d' END AS gap, count(*) AS n FROM ({g}) WHERE gap_s IS NOT NULL "
                f"GROUP BY 1 ORDER BY min(gap_s)")
    hod_sql = ("SELECT hour(start_ts) AS hour, count(*) AS bursts FROM bursts WHERE dataset = %(d)s AND pattern_id = %(p)s "
               "GROUP BY 1 ORDER BY 1")
    dow_sql = ("SELECT dayname(start_ts) AS weekday, count(*) AS bursts FROM bursts WHERE dataset = %(d)s AND pattern_id = %(p)s "
               "GROUP BY 1, isodow(start_ts) ORDER BY isodow(start_ts)")
    st, hist, hod, dow = (query(x, params) for x in (st_sql, hist_sql, hod_sql, dow_sql))
    st = st[0] if st else {}
    rule = "gaps ≥ 5 and regular_share ≥ 0.5 → 'regular'; top hour holds ≥ 30 % of bursts (and ≥ 5 bursts) → 'time-of-day pattern'"
    tot = sum(r["bursts"] for r in hod)
    top_h = max(hod, key=lambda r: r["bursts"]) if hod else None
    reading = []
    if (st.get("gaps") or 0) >= 5 and (st.get("regular_share") or 0) >= 0.5:
        reading.append(f"regular (about every {int(st['median_gap_s'])} s)")
    if top_h and tot >= 5 and top_h["bursts"] / tot >= 0.3:
        reading.append(f"time-of-day pattern (hour {top_h['hour']}: {top_h['bursts']} of {tot} bursts)")
    return envelope("periodicity", dict(dataset=dataset, pattern_id=pattern_id),
                    [render(x, params) for x in (st_sql, hist_sql, hod_sql, dow_sql)], dict(dataset=dataset, pattern_id=pattern_id),
                    scope=f"{dataset}, all bursts of pattern {pattern_id} ({tot}); gap = time between burst starts",
                    rows=hist, t0=t0, total_matches=tot, truncated=False, gap_stats=st, by_hour=hod, by_weekday=dow,
                    reading=reading or ["no regular schedule"], reading_rule=rule)


def request_timeline(
    dataset: Dataset,
    request_id: RequestId = None,
    object_id: ObjectId = None,
    at: Annotated[Optional[datetime], Field(
        description="Pick the session containing (or starting after) this time; ids such as process ids get reused.")] = None,
    max_gap_s: Annotated[int, Field(ge=1, description="A quiet gap longer than this starts a new session of the same id.")] = 3600,
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description="Steps to return.")] = 50,
) -> dict:
    """What happened to this one request / session / trace / object, step by step, end to end?

    Use when: the question names one id (a request, connection, trace, block, VM …) and asks what happened to it,
    where it spent its time or where it failed (what request_id / object_id are in each dataset: field guide).
    Not for: the neighbours of one line on a machine (get_context), all slow operations (value_outliers).
    Returns: the id's lines in time order with seconds since the previous step and since the start; per component
    first / last time, lines, statuses, max duration; total duration and problem lines. Reused ids are split into
    sessions at quiet gaps > max_gap_s (`sessions`; `at` picks one).
    Caveats: steps are log lines; a missing step is not proof it did not happen.
    Example: request_timeline(dataset=<dataset>, request_id=<id from a search row>)
    Next: get_context(line_id of the failing step, scope='node') for what else happened on that machine.
    """
    t0 = time.perf_counter()
    if not (request_id or object_id):
        raise ValueError("Give request_id or object_id (describe_corpus says what they are in each dataset).")
    f = dict(dataset=dataset, request_id=request_id, object_id=object_id)
    where, params = filters_sql(f)
    sess = (f"SELECT *, sum(new_s) OVER (ORDER BY ts, line_id) AS session FROM ("
            f"SELECT line_id, ts, component, severity, node, status, duration_ms, pattern_id, body, "
            f"CASE WHEN epoch(ts) - epoch(lag(ts) OVER (ORDER BY ts, line_id)) <= {int(max_gap_s)} THEN 0 ELSE 1 END AS new_s "
            f"FROM logs WHERE TRUE{where})")
    list_sql = (f"SELECT session, count(*) AS lines, min(ts) AS first_ts, max(ts) AS last_ts FROM ({sess}) "
                f"GROUP BY 1 ORDER BY 1")
    sessions = query(list_sql, params)
    if not sessions:
        raise ValueError("No lines with that id.")
    pick = next((x for x in sessions if at is None or x["last_ts"] >= at), sessions[-1])
    # integers inlined: bound parameters inside these window queries hit a SereneDB internal error (plan 011)
    one = f"SELECT * EXCLUDE (new_s, session) FROM ({sess}) WHERE session = {int(pick['session'])}"
    steps_sql = (f"SELECT *, round(epoch(ts) - epoch(lag(ts) OVER (ORDER BY ts, line_id)), 3) AS since_prev_s, "
                 f"round(epoch(ts) - epoch(first_value(ts) OVER (ORDER BY ts, line_id)), 3) AS since_start_s "
                 f"FROM ({one}) ORDER BY ts, line_id LIMIT {limit}")
    comp_sql = (f"SELECT component, count(*) AS lines, min(ts) AS first_ts, max(ts) AS last_ts, "
                f"round(epoch(max(ts)) - epoch(min(ts)), 3) AS span_s, list(DISTINCT status) FILTER (WHERE status IS NOT NULL) AS statuses, "
                f"round(max(duration_ms), 1) AS max_duration_ms FROM ({one}) GROUP BY 1 ORDER BY 3")
    tot_sql = (f"SELECT count(*) AS lines, min(ts) AS first_ts, max(ts) AS last_ts, round(epoch(max(ts)) - epoch(min(ts)), 3) AS duration_s, "
               f"count(*) FILTER (WHERE severity IN ('ERROR', 'FATAL', 'CRITICAL', 'SEVERE', 'FAILURE') OR status >= 500) AS problem_lines "
               f"FROM ({one})")
    steps, comps, tot = query(steps_sql, params), query(comp_sql, params), query(tot_sql, params)[0]
    return envelope("request_timeline", dict(at=at, max_gap_s=max_gap_s, limit=limit, **f),
                    [render(list_sql, params), render(steps_sql, params), render(comp_sql, params), render(tot_sql, params)], f,
                    scope=f"{dataset}, " + (f"request {request_id}" if request_id else f"object {object_id}")
                          + f", session {pick['session']} of {len(sessions)} (split at quiet gaps > {max_gap_s} s)",
                    rows=steps, t0=t0, total_matches=tot["lines"], truncated=tot["lines"] > len(steps),
                    components=comps, summary=tot, sessions=len(sessions),
                    other_sessions=[{k: x[k] for k in ("session", "lines", "first_ts")} for x in sessions[:10]])
