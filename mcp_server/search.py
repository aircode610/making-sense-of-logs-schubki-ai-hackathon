"""Engineer tools: full-text search with filters, and the events around one log line."""
import time
from datetime import datetime, timedelta
from typing import Annotated, Literal, Optional

from pydantic import Field

from core import MAX_ROWS, clean_row, envelope, filters_sql, query, render

COLS = "line_id, dataset, ts, component, severity, node, request_id, instance_id, status, latency_ms, pattern_id, body"

Dataset = Annotated[Optional[Literal["bgl", "openstack"]], Field(description="Restrict to one dataset; omit for both.")]


def search_logs(
    query_text: Annotated[Optional[str], Field(
        description='Full-text query on the log message, web-search syntax: words = all must appear (`parity corrected`), '
                    '`"exact phrase"`, `a OR b`, `-word` excludes. Case-insensitive, letters only: numbers, hex and ids '
                    'inside messages are not searchable (filter by node / request_id / instance_id instead). '
                    'Omit to list lines by filters only.')] = None,
    dataset: Dataset = None,
    start: Annotated[Optional[datetime], Field(description="Inclusive start time, e.g. '2005-11-02 00:00'.")] = None,
    end: Annotated[Optional[datetime], Field(description="Exclusive end time.")] = None,
    component: Annotated[Optional[str], Field(
        description="Exact component: BGL KERNEL, APP, DISCOVERY, MMCS, HARDWARE, MONITOR, LINKCARD, CMCS, BGLMASTER, "
                    "SERV_NET; OpenStack nova-api, nova-compute, nova-scheduler.")] = None,
    severity: Annotated[Optional[str], Field(
        description="Exact severity: BGL INFO, WARNING, ERROR, SEVERE, FATAL, FAILURE; OpenStack INFO, WARNING, ERROR.")] = None,
    node: Annotated[Optional[str], Field(description="Exact node / host, e.g. BGL 'R02-M1-N0-C:J12-U11'.")] = None,
    midplane: Annotated[Optional[str], Field(description="BGL midplane, e.g. 'R02-M1'.")] = None,
    rack: Annotated[Optional[str], Field(description="BGL rack, e.g. 'R02'.")] = None,
    request_id: Annotated[Optional[str], Field(description="OpenStack request id (req-…).")] = None,
    instance_id: Annotated[Optional[str], Field(description="OpenStack VM instance uuid.")] = None,
    pattern_id: Annotated[Optional[int], Field(
        description="Log template id (every row carries one; same id = same message with numbers/ids masked). "
                    "Use it to fetch all lines of one recurring message, e.g. from a previous result row.")] = None,
    order: Annotated[Literal["time", "recent", "relevance"], Field(
        description="'time' = earliest first (where/when did it start), 'recent' = latest first, "
                    "'relevance' = best BM25 match first.")] = "time",
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description=f"Lines to return (max {MAX_ROWS}).")] = 20,
) -> dict:
    """Find log lines by message text and/or filters (time range, dataset, component, severity, node, ids).

    Use it to locate an error, see where and when it happened, and pick a line_id for get_context.
    Returns up to `limit` matching lines plus, computed over ALL matches with the same filters:
    total_matches, first_ts, last_ts and distinct_nodes. Use those for "how many / since when / how widespread";
    the returned lines are only a sample (truncated=true when total_matches > lines returned).
    Counts are log lines, not incidents: one fault can log thousands of lines.
    """
    t0 = time.perf_counter()
    f = dict(dataset=dataset, start=start, end=end, component=component, severity=severity, node=node,
             midplane=midplane, rack=rack, request_id=request_id, instance_id=instance_id, pattern_id=pattern_id)
    where, params = filters_sql(f)
    if query_text:
        where = " AND body @@ websearch_to_tsquery(%(q)s)" + where
        params["q"] = query_text
    elif not where:
        raise ValueError("Give query_text or at least one filter (e.g. dataset + start/end).")
    where = "WHERE TRUE" + where
    order_by = {"time": "ts, line_id", "recent": "ts DESC, line_id DESC",
                "relevance": "BM25(logs.tableoid) DESC, ts" if query_text else "ts, line_id"}[order]
    rows_sql = f"SELECT {COLS} FROM logs {where} ORDER BY {order_by} LIMIT {limit}"
    sum_sql = (f"SELECT count(*) AS total_matches, min(ts) AS first_ts, max(ts) AS last_ts, "
               f"count(DISTINCT node) AS distinct_nodes FROM logs {where}")
    rows = query(rows_sql, params)
    s = query(sum_sql, params)[0]
    return envelope("search_logs", dict(query_text=query_text, order=order, limit=limit, **f),
                    [render(rows_sql, params), render(sum_sql, params)], f,
                    scope=f"{dataset or 'all datasets'}, {start or 'corpus start'} → {end or 'corpus end'}",
                    rows=rows, t0=t0, total_matches=s["total_matches"],
                    truncated=s["total_matches"] > len(rows),
                    first_ts=s["first_ts"] and s["first_ts"].isoformat(sep=" "),
                    last_ts=s["last_ts"] and s["last_ts"].isoformat(sep=" "),
                    distinct_nodes=s["distinct_nodes"])


SCOPE_COL = {"node": "node", "midplane": "midplane", "rack": "rack",
             "request": "request_id", "instance": "instance_id", "all": None}


def get_context(
    dataset: Annotated[Literal["bgl", "openstack"], Field(description="Dataset of the anchor line.")],
    line_id: Annotated[int, Field(description="line_id of the anchor line (from search_logs).")],
    before_s: Annotated[int, Field(ge=0, le=86400, description="Seconds before the anchor to include.")] = 300,
    after_s: Annotated[int, Field(ge=0, le=86400, description="Seconds after the anchor to include.")] = 300,
    scope: Annotated[Literal["node", "midplane", "rack", "request", "instance", "all"], Field(
        description="Which neighbours: same 'node' / 'midplane' / 'rack' (BGL), same 'request' / 'instance' "
                    "(OpenStack, follows one request or VM across services), or 'all' lines of the dataset.")] = "node",
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
    anchor_rows = query(f"SELECT {COLS}, midplane, rack FROM logs WHERE dataset = %(d)s AND line_id = %(l)s",
                        {"d": dataset, "l": line_id})
    if not anchor_rows:
        raise ValueError(f"No {dataset} line with line_id={line_id}; take line_id from search_logs results.")
    a = anchor_rows[0]
    col = SCOPE_COL[scope]
    if col and a.get(col) is None:
        raise ValueError(f"Anchor line has no {col}; use scope='all' or a scope this dataset has "
                         f"(BGL: node/midplane/rack, OpenStack: request/instance).")
    f = {"dataset": dataset, "start": a["ts"] - timedelta(seconds=before_s),
         "end": a["ts"] + timedelta(seconds=after_s, microseconds=1), "severity": severity}
    if col:
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
    env.update(anchor=clean_row({k: v for k, v in a.items() if k not in ("midplane", "rack")}),
               before=[clean_row(r) for r in before], before_total=nb, before_truncated=nb > len(before),
               after=[clean_row(r) for r in after], after_total=na, after_truncated=na > len(after))
    return env
