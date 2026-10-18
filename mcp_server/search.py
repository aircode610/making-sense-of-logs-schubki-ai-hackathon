"""Search tools: full-text search with filters, and the events around one log line."""
import time
from datetime import datetime, timedelta
from typing import Annotated, Literal, Optional

from pydantic import Field

from core import (MATCH_HELP, MAX_ROWS, Dataset as DatasetReq, DatasetOpt, MatchMode, clean_row, envelope, filters_sql,
                  query, registry, render, team_scoped, tsquery_sql, vocab_text)

COLS = "line_id, dataset, ts, component, severity, node, request_id, instance_id, status, latency_ms, pattern_id, body"

Dataset = DatasetOpt


def search_logs(
    query_text: Annotated[Optional[str], Field(
        description='Full-text query on the log message, web-search syntax: words = all must appear (`parity corrected`), '
                    '`"exact phrase"`, `a OR b`, `-word` excludes. Case-insensitive; numbers, dotted ids and hex '
                    'inside messages are searchable as whole tokens (`503`, `172.16.96.116`); for exact ids prefer the '
                    'node / request_id / instance_id / entity filters. '
                    'Omit to list lines by filters only.')] = None,
    dataset: Dataset = None,
    start: Annotated[Optional[datetime], Field(description="Inclusive start time, e.g. '2005-11-02 00:00'.")] = None,
    end: Annotated[Optional[datetime], Field(description="Exclusive end time.")] = None,
    component: Annotated[Optional[str], Field(
        description="Exact component (most frequent first): " + vocab_text("components") + ".")] = None,
    severity: Annotated[Optional[str], Field(
        description="Exact severity (upper case): " + vocab_text("severitys") + ".")] = None,
    node: Annotated[Optional[str], Field(description="Exact node / host, e.g. BGL 'R02-M1-N0-C:J12-U11', SSH 'LabSZ'.")] = None,
    location: Annotated[Optional[str], Field(
        description="Location path at ANY level ('/'-separated, coarse → fine): BGL 'R02' (rack), 'R02/R02-M1' "
                    "(midplane), full 'R02/R02-M1/R02-M1-N0-C:J12-U11'; Zookeeper 'ClassName' or 'ClassName/thread'.")] = None,
    entity: Annotated[Optional[str], Field(
        description="A value extracted from the message, typed: 'ip:173.234.31.186', 'path:/var/www/cgi-bin/awstats', "
                    "'uuid:…', 'url:…' (see top_entities).")] = None,
    midplane: Annotated[Optional[str], Field(description="BGL midplane, e.g. 'R02-M1'.")] = None,
    rack: Annotated[Optional[str], Field(description="BGL rack, e.g. 'R02'.")] = None,
    request_id: Annotated[Optional[str], Field(description="OpenStack request id (req-…).")] = None,
    instance_id: Annotated[Optional[str], Field(description="OpenStack VM instance uuid.")] = None,
    pattern_id: Annotated[Optional[int], Field(
        description="Log template id (every row carries one; same id = same message with numbers/ids masked). "
                    "Use it to fetch all lines of one recurring message, e.g. from a previous result row.")] = None,
    match: Annotated[MatchMode, Field(description=MATCH_HELP)] = "web",
    slop: Annotated[int, Field(ge=0, le=20, description="match='near': max positions between the words.")] = 2,
    distance: Annotated[int, Field(ge=1, le=2, description="match='fuzzy': typos allowed per word.")] = 1,
    min_match: Annotated[int, Field(ge=1, le=10, description="match='at_least': how many of the words must appear.")] = 2,
    exclude_text: Annotated[Optional[str], Field(
        description="Drop lines that match this (web-search syntax), e.g. 'heartbeat OR healthcheck'.")] = None,
    highlight: Annotated[bool, Field(
        description="Add `snippet` to each row: the best passage with the matched words wrapped in «…» "
                    "(needs query_text).")] = False,
    order: Annotated[Literal["time", "recent", "relevance", "relevance_recent"], Field(
        description="'time' = earliest first (where/when did it start), 'recent' = latest first, "
                    "'relevance' = best BM25 match first, 'relevance_recent' = BM25 × recency decay (30-day "
                    "half-life from the dataset's last line): relevant AND recent first.")] = "time",
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description=f"Lines to return (max {MAX_ROWS}).")] = 20,
    workspace: Annotated[Optional[str], Field(
        description="Search a focus index made with create_focus_index instead of the whole corpus.")] = None,
) -> dict:
    """Find log lines by message text and/or filters (time range, dataset, component, severity, node, location,
    entity, ids), with exact, phrase, proximity, fuzzy, prefix, k-of-n or synonym matching.

    Use it to locate an error, see where and when it happened, and pick a line_id for get_context.
    Returns up to `limit` matching lines plus, computed over ALL matches with the same filters:
    total_matches, first_ts, last_ts and distinct_nodes. Use those for "how many / since when / how widespread";
    the returned lines are only a sample (truncated=true when total_matches > lines returned).
    0 matches? try match='fuzzy' / 'synonyms', or suggest_terms. Counts are log lines, not incidents.
    """
    t0 = time.perf_counter()
    f = dict(dataset=dataset, start=start, end=end, component=component, severity=severity, node=node,
             midplane=midplane, rack=rack, location=location, entity=entity, request_id=request_id,
             instance_id=instance_id, pattern_id=pattern_id)
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
                    distinct_nodes=s["distinct_nodes"], **({"note": note} if note else {}))


SCOPE_COL = {"node": "node", "midplane": "midplane", "rack": "rack", "location": "location", "component": "component",
             "request": "request_id", "instance": "instance_id", "all": None}


def get_context(
    dataset: DatasetReq,
    line_id: Annotated[int, Field(description="line_id of the anchor line (from search_logs).")],
    before_s: Annotated[int, Field(ge=0, le=86400, description="Seconds before the anchor to include.")] = 300,
    after_s: Annotated[int, Field(ge=0, le=86400, description="Seconds after the anchor to include.")] = 300,
    scope: Annotated[Literal["node", "midplane", "rack", "location", "component", "request", "instance", "all"], Field(
        description="Which neighbours: same 'node' / 'midplane' / 'rack' (BGL), same full 'location' path, same "
                    "'component', same 'request' (OpenStack request, SSH connection) / 'instance' (OpenStack VM, follows "
                    "it across services), or 'all' lines of the dataset.")] = "node",
    severity: Annotated[Optional[str], Field(
        description="Only neighbours with this exact severity (e.g. 'FATAL'); omit for all.")] = None,
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description=f"Max lines per side (max {MAX_ROWS}).")] = 20,
) -> dict:
    """Show what happened just before and just after one log line, on the same node / midplane / rack / request / VM.

    Use it after search_logs to build a timeline around an error. Returns the anchor line, `before` (nearest first)
    and `after` (nearest first), each with its total count in the window and a truncated flag, so you know how many
    events were not shown. Order in time does not prove cause: label any causal reading as a hypothesis.
    """
    t0 = time.perf_counter()
    anchor_rows = query(f"SELECT {COLS}, midplane, rack, location FROM logs WHERE dataset = %(d)s AND line_id = %(l)s",
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
    if col == "location":
        f["location"] = a["location"]  # exact path (keyword) = same full location
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
                                       scope=scope, severity=severity, limit=limit),
                   [render(s, params) for s in sqls], f,
                   scope=f"{dataset}, {scope}{'=' + str(a[col]) if col else ''}, "
                         f"{f['start']} → {a['ts'] + timedelta(seconds=after_s)}",
                   rows=[], t0=t0, total_matches=nb + na, truncated=nb > len(before) or na > len(after))
    del env["rows"]
    env.update(anchor=clean_row({k: v for k, v in a.items() if k not in ("midplane", "rack", "location")}),
               before=[clean_row(r) for r in before], before_total=nb, before_truncated=nb > len(before),
               after=[clean_row(r) for r in after], after_total=na, after_truncated=na > len(after))
    return env
