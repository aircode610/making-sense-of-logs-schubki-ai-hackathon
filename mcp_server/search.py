"""Search tools: full-text search with filters, and the events around one log line."""
import time
from datetime import datetime, timedelta
from typing import Annotated, Literal, Optional

from pydantic import Field

from core import (MATCH_HELP, MAX_ROWS, Component, Dataset as DatasetReq, DatasetOpt, End, Entity, Location, MatchMode,
                  Node, ObjectId, PatternIdOpt, RequestId, Severity, Start, Status, clean_row, envelope, filters_sql,
                  query, registry, render, search_hints, team_scoped, tsquery_sql)

COLS = "line_id, dataset, ts, component, severity, severity_number, node, location, request_id, object_id, status, duration_ms, pattern_id, body"

Dataset = DatasetOpt


def search_logs(
    query_text: Annotated[Optional[str], Field(
        description='Words to find in the log message. Default syntax (match="web"): all words must appear, '
                    '"exact phrase" in double quotes, a OR b, -word to exclude. Case-insensitive; numbers, dotted ids '
                    'and hex inside messages are whole tokens (`503`, `10.0.0.7`). Omit to list lines by filters only.')] = None,
    dataset: Dataset = None,
    start: Start = None,
    end: End = None,
    component: Component = None,
    severity: Severity = None,
    node: Node = None,
    location: Location = None,
    entity: Entity = None,
    request_id: RequestId = None,
    object_id: ObjectId = None,
    status: Status = None,
    pattern_id: PatternIdOpt = None,
    match: Annotated[MatchMode, Field(description=MATCH_HELP)] = "web",
    slop: Annotated[int, Field(ge=0, le=20, description="match='near': max positions between the words.")] = 2,
    distance: Annotated[int, Field(ge=1, le=2, description="match='fuzzy': typos allowed per word.")] = 1,
    min_match: Annotated[int, Field(ge=1, le=10, description="match='at_least': how many of the words must appear.")] = 2,
    exclude_text: Annotated[Optional[str], Field(
        description="Drop lines that match this (same web syntax), e.g. 'heartbeat OR healthcheck'.")] = None,
    highlight: Annotated[bool, Field(
        description="Add `snippet` to each row: the best passage with the matched words wrapped in «…» "
                    "(needs query_text).")] = False,
    order: Annotated[Literal["time", "recent", "relevance", "relevance_recent"], Field(
        description="'time' = earliest first (where / when did it start), 'recent' = latest first, "
                    "'relevance' = best BM25 match first, 'relevance_recent' = BM25 x recency (30-day half-life from "
                    "the dataset's last line).")] = "time",
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description=f"Sample lines to return (max {MAX_ROWS}); totals are "
                                                               f"always over all matches.")] = 20,
    workspace: Annotated[Optional[str], Field(
        description="Search a focus index made with create_focus_index instead of the whole corpus.")] = None,
) -> dict:
    """Find log lines: which lines say X, where, and when did it start? The main entry point into the raw logs.

    Use when: you need the log lines for an error / message / id, its first and last time, how many lines match, or a
    line_id / pattern_id to drill into. Filters work with or without query_text.
    Not for: counts per group (count_by / facet), counts over time (trend), ranking recurring problems (top_patterns),
    one request end to end (request_timeline).
    Returns: up to `limit` sample lines (line_id, ts, component, severity, node, ids, pattern_id, body) plus, over ALL
    matches: total_matches, first_ts, last_ts, distinct_nodes (cite these for "how many / since when / how widespread").
    Caveats: counts are log lines, not incidents. 0 matches is not proof of absence: try match='fuzzy' or 'synonyms',
    or suggest_terms for the real wording.
    Example: search_logs(dataset=<dataset>, query_text='"connection refused"', start='<period start>', order='time')
    Next: get_context(line_id) for what happened around a line; pattern_history / spread / precursors(pattern_id) for
    that kind of message; top_entities for the IPs / paths behind the matches.
    """
    t0 = time.perf_counter()
    f = dict(dataset=dataset, start=start, end=end, component=component, severity=severity, node=node,
             location=location, entity=entity, request_id=request_id, object_id=object_id, status=status,
             pattern_id=pattern_id)
    where, params = filters_sql(f)
    if query_text:  # text predicate after the filters (text-before-timestamp parameter bug, see filters_sql)
        expr, qp = tsquery_sql(query_text, match, slop, distance, min_match, exclude_text)
        where += f" AND body @@ {expr}"
        params.update(qp)
    elif not where:
        raise ValueError("Give query_text or at least one filter (e.g. dataset + start/end).")
    where = "WHERE TRUE" + where
    from workspace import source_table
    tbl = source_table(workspace)
    note = None
    if team_scoped() and order in ("relevance", "relevance_recent"):  # BM25 needs the index relation, not a team view
        order, note = "time", "team-scoped access: relevance ranking unavailable, ordered by time"
    last = max((v["last_ts"] for d, v in registry().items() if v.get("last_ts") and (dataset in (None, d))), default=None)
    decay = (f"BM25({tbl}.tableoid) * exp(-(epoch(TIMESTAMP '{last:%Y-%m-%d %H:%M:%S}') - epoch(ts)) / (86400 * 30.0 / ln(2)))"
             if last else f"BM25({tbl}.tableoid)")
    order_by = {"time": "ts, line_id", "recent": "ts DESC, line_id DESC",
                "relevance": f"BM25({tbl}.tableoid) DESC, ts" if query_text else "ts, line_id",
                "relevance_recent": f"{decay} DESC, ts DESC" if query_text else "ts DESC, line_id DESC"}[order]
    snip = (", ts_highlight(body, ts_offsets(body), 'StartSel=«, StopSel=», MaxWords=30') AS snippet"
            if highlight and query_text else "")
    rows_sql = f"SELECT {COLS}{snip} FROM {tbl} {where} ORDER BY {order_by} LIMIT {limit}"
    sum_sql = (f"SELECT count(*) AS total_matches, min(ts) AS first_ts, max(ts) AS last_ts, "
               f"count(DISTINCT node) AS distinct_nodes FROM {tbl} {where}")
    rows = query(rows_sql, params)
    s = query(sum_sql, params)[0]
    return envelope("search_logs", dict(query_text=query_text, match=match if query_text else None,
                                        exclude_text=exclude_text, highlight=highlight or None, order=order,
                                        limit=limit, workspace=workspace, **f),
                    [render(rows_sql, params), render(sum_sql, params)], f,
                    scope=f"{dataset or 'all datasets'}, {start or 'corpus start'} → {end or 'corpus end'}"
                          + (f", workspace {workspace}" if workspace else ""),
                    rows=rows, t0=t0, total_matches=s["total_matches"],
                    truncated=s["total_matches"] > len(rows),
                    first_ts=s["first_ts"] and s["first_ts"].isoformat(sep=" "),
                    last_ts=s["last_ts"] and s["last_ts"].isoformat(sep=" "),
                    distinct_nodes=s["distinct_nodes"], **({"note": note} if note else {}),
                    hints=search_hints(s["total_matches"], s["total_matches"] > len(rows), f, query_text, rows))


SCOPE_COL = {"node": "node", "location": "location", "component": "component", "request": "request_id",
             "object": "object_id", "all": None}


def get_context(
    dataset: DatasetReq,
    line_id: Annotated[int, Field(description="line_id of the anchor line (from search_logs or any row with a line_id).")],
    before_s: Annotated[int, Field(ge=0, le=86400, description="Seconds before the anchor to include.")] = 300,
    after_s: Annotated[int, Field(ge=0, le=86400, description="Seconds after the anchor to include.")] = 300,
    scope: Annotated[Literal["node", "location", "component", "request", "object", "all"], Field(
        description="Which neighbours: same 'node' (machine / host), same 'location' path (with location_level: a "
                    "coarser group such as a rack or a namespace), same 'component', same 'request' (request / session "
                    "/ trace id), same 'object' (object id, followed across requests), or 'all' lines of the dataset. "
                    "A scope the anchor has no value for is refused with the scopes it does have.")] = "node",
    location_level: Annotated[Optional[int], Field(
        ge=1, le=10, description="scope='location' only: keep the first N levels of the anchor's path (1 = coarsest); "
                                 "omit for the full path.")] = None,
    severity: Severity = None,
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description=f"Max lines per side (max {MAX_ROWS}).")] = 20,
) -> dict:
    """What happened just before and just after this log line on the same node / location / request / object?

    Use when: you have one line (an error) and need its timeline: the events leading up to it and what followed, on
    the same machine, group of machines, component, request or object.
    Not for: finding the line in the first place (search_logs), a whole request or object end to end
    (request_timeline), which kinds of messages tend to precede a problem across all its occurrences (precursors).
    Returns: the anchor line, `before` (nearest first) and `after` (nearest first) lines, each side with its total
    count in the window and a truncated flag.
    Caveats: earlier is not cause: label any causal reading as a hypothesis. A flooded window: narrow before_s /
    after_s or filter by severity.
    Example: get_context(dataset=<dataset>, line_id=<line_id from search_logs>, scope='node', before_s=600)
    Next: search_logs(pattern_id=…) for a preceding message seen here; burst_timeline(pattern_id, at=anchor time) for
    the order of first appearance across the affected nodes.
    """
    t0 = time.perf_counter()
    anchor_rows = query(f"SELECT {COLS} FROM logs WHERE dataset = %(d)s AND line_id = %(l)s",
                        {"d": dataset, "l": line_id})
    if not anchor_rows:
        raise ValueError(f"No {dataset} line with line_id={line_id}; take line_id from search_logs results.")
    a = anchor_rows[0]
    col = SCOPE_COL[scope]
    if col and a.get(col) is None:
        raise ValueError(f"Anchor line has no {col}; use scope='all' or one of the anchor's non-empty fields: "
                         + ", ".join(k for k, c in SCOPE_COL.items() if c and a.get(c) is not None) + ".")
    f = {"dataset": dataset, "start": a["ts"] - timedelta(seconds=before_s),
         "end": a["ts"] + timedelta(seconds=after_s, microseconds=1), "severity": severity}
    if col == "location":  # exact path (keyword) at the chosen level = same location or the same group of locations
        parts = a["location"].split("/")
        f["location"] = "/".join(parts[:location_level]) if location_level else a["location"]
    elif col:
        f[col] = a[col]
    where, params = filters_sql(f)
    params.update(ats=a["ts"], aid=line_id)
    before_w = f"WHERE (ts < %(ats)s OR (ts = %(ats)s AND line_id < %(aid)s)){where}"
    after_w = f"WHERE (ts > %(ats)s OR (ts = %(ats)s AND line_id > %(aid)s)){where}"
    sqls = [f"SELECT {COLS} FROM logs {before_w} ORDER BY ts DESC, line_id DESC LIMIT {limit}",
            f"SELECT {COLS} FROM logs {after_w} ORDER BY ts, line_id LIMIT {limit}",
            f"SELECT count(*) AS n FROM logs {before_w}",
            f"SELECT count(*) AS n FROM logs {after_w}"]
    before, after = query(sqls[0], params), query(sqls[1], params)
    nb, na = query(sqls[2], params)[0]["n"], query(sqls[3], params)[0]["n"]
    env = envelope("get_context", dict(dataset=dataset, line_id=line_id, before_s=before_s, after_s=after_s,
                                       scope=scope, location_level=location_level, severity=severity, limit=limit),
                   [render(s, params) for s in sqls], f,
                   scope=f"{dataset}, {scope}{'=' + str(f.get(col)) if col else ''}, "
                         f"{f['start']} → {a['ts'] + timedelta(seconds=after_s)}",
                   rows=[], t0=t0, total_matches=nb + na, truncated=nb > len(before) or na > len(after))
    del env["rows"]
    env.update(anchor=clean_row(a),
               before=[clean_row(r) for r in before], before_total=nb, before_truncated=nb > len(before),
               after=[clean_row(r) for r in after], after_total=na, after_truncated=na > len(after))
    return env
