"""Remote huge data, queried in place (plan 011; brief: 50 billion OTel log rows as Parquet on S3, "point SereneDB at the
URL and query it where it is"). Sources are rows of `remote_sources` (data/remote_sources.csv: URL + column mapping), so
another Parquet log lake is one config row. Scans prune by Parquet row-group statistics (files are sorted by time);
remote_index builds an inverted index over a time slice of the remote files (view + CREATE INDEX: only postings are
stored locally, the rows stay in S3), and every tool reports rows / row groups touched and wall time."""
import time
from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import Field

from core import MAX_ROWS, envelope, execute, lit, query

MAX_SCAN_SECONDS = 600     # a scan window longer than this (~330M rows of the demo data) is refused: index or narrow it


def _default_source() -> str:
    try:
        r = query("SELECT name FROM remote_sources ORDER BY name LIMIT 1", {})
        return r[0]["name"] if r else "none"
    except Exception:  # noqa: BLE001
        return "none"


DEFAULT = _default_source()
Source = Annotated[str, Field(description="Remote Parquet source name (config table remote_sources; remote_describe "
                                          "describes it). Default: the first one.")]


def _src(name: str) -> dict:
    r = query("SELECT * FROM remote_sources WHERE name = %(n)s", {"n": name})
    if not r:
        names = [x["name"] for x in query("SELECT name FROM remote_sources ORDER BY 1", {})]
        raise ValueError(f"Unknown remote source {name!r}; available: {', '.join(names)}.")
    return r[0]


def _ts(t: datetime) -> str:
    return f"TIMESTAMPTZ '{t:%Y-%m-%d %H:%M:%S.%f}+00'"


def _rowgroups(s: dict, start: Optional[datetime], end: Optional[datetime]) -> dict:
    """Row groups (and rows) whose Timestamp min/max overlap the window, from the Parquet footer statistics."""
    w = []
    if end:
        w.append(f"stats_min::TIMESTAMPTZ < {_ts(end)}")
    if start:
        w.append(f"stats_max::TIMESTAMPTZ >= {_ts(start)}")
    sql = (f"SELECT count(*) AS row_groups_total, count(*) FILTER (WHERE {' AND '.join(w) or 'TRUE'}) AS row_groups_read, "
           f"sum(num_values) AS rows_total, sum(num_values) FILTER (WHERE {' AND '.join(w) or 'TRUE'}) AS rows_read "
           f"FROM parquet_metadata({lit(s['url'])}) WHERE path_in_schema = {lit(s['ts_col'])}")
    r = query(sql, {})[0]
    r["sql"] = sql
    return r


def remote_describe(
    source: Source = DEFAULT,
) -> dict:
    """What does a remote Parquet log source hold (rows, time range, columns), without scanning it?

    Use when: a question is about the huge remote log data (billions of rows queried in place, not loaded), before
    picking a time window for remote_count_by / remote_search.
    Not for: the loaded datasets (describe_corpus); a source may also have a loaded slice (said in its description):
    questions about that slice go to the normal tools.
    Returns: description, URL, rows, row groups, first / last timestamp (from row-group statistics), columns and types, seconds of
    data per row group (what a time filter can skip), and the column mapping.
    Caveats: reads only the file footers.
    Example: remote_describe()
    Next: remote_count_by / remote_search with a window of at most 10 minutes; remote_index for repeated searches.
    """
    t0 = time.perf_counter()
    s = _src(source)
    meta_sql = (f"SELECT count(*) AS row_groups, sum(num_values) AS rows, min(stats_min::TIMESTAMPTZ) AS first_ts, "
                f"max(stats_max::TIMESTAMPTZ) AS last_ts FROM parquet_metadata({lit(s['url'])}) "
                f"WHERE path_in_schema = {lit(s['ts_col'])}")
    m = query(meta_sql, {})[0]
    cols_sql = f"DESCRIBE SELECT * FROM read_parquet({lit(s['url'])})"
    cols = [{"column": r["column_name"], "type": r["column_type"]} for r in query(cols_sql, {})]
    span = (m["last_ts"] - m["first_ts"]).total_seconds() if m["first_ts"] else None
    return envelope("remote_describe", {"source": source}, [meta_sql, cols_sql], {"source": source},
                    scope=f"remote {source}: {s['url']} (Parquet footer statistics only)", rows=cols, t0=t0,
                    total_matches=m["rows"], truncated=False, row_groups=m["row_groups"],
                    first_ts=m["first_ts"], last_ts=m["last_ts"],
                    seconds_per_row_group=round(span / m["row_groups"], 3) if span and m["row_groups"] else None,
                    description=s["description"], mapping={k: s[k] for k in ("ts_col", "service_col", "severity_col",
                                                                               "body_col", "trace_col")})


def _window(s, start, end) -> str:
    if not (start and end):
        raise ValueError("Give start and end (remote data is huge: always a time window).")
    if (end - start).total_seconds() > MAX_SCAN_SECONDS:
        raise ValueError(f"Window longer than {MAX_SCAN_SECONDS} s: narrow it, or build a remote_index for repeated searches.")
    return f'"{s["ts_col"]}" >= {_ts(start)} AND "{s["ts_col"]}" < {_ts(end)}'


def remote_count_by(
    start: Annotated[datetime, Field(description="Window start (UTC, inclusive), e.g. '2025-09-23 00:10:00'.")],
    end: Annotated[datetime, Field(description="Window end (UTC, exclusive); at most 10 minutes for a scan.")],
    group_by: Annotated[Literal["service", "severity", "service_severity"], Field(description="Group by service, severity or both.")] = "service",
    contains: Annotated[Optional[str], Field(description="Optional case-insensitive substring filter on the message body.")] = None,
    source: Source = DEFAULT,
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description="Groups to return.")] = 20,
) -> dict:
    """How many remote log records per service / severity in a time window, scanned in place?

    Use when: counts over the huge remote data for a short window ("errors per service between 00:10 and 00:12"),
    or to show how much data a query touched and how long it took.
    Not for: the loaded datasets (count_by), windows longer than 10 minutes (build a remote_index or narrow it).
    Returns: counts per group, total rows matched, rows and row groups read vs the file total (pruning), scan time.
    Caveats: `contains` is a case-insensitive substring filter (no index); times are UTC.
    Example: remote_count_by(start='<window start>', end='<+2 min>', group_by='service_severity')
    Next: remote_search for example records of a large group.
    """
    t0 = time.perf_counter()
    s = _src(source)
    w = _window(s, start, end)
    g = {"service": [s["service_col"]], "severity": [s["severity_col"]],
         "service_severity": [s["service_col"], s["severity_col"]]}[group_by]
    gl = ", ".join(f'"{c}"' for c in g)
    cf = f' AND "{s["body_col"]}" ILIKE {lit("%" + contains + "%")}' if contains else ""
    sql = (f"SELECT {gl}, count(*) AS rows FROM read_parquet({lit(s['url'])}) WHERE {w}{cf} "
           f"GROUP BY ALL ORDER BY rows DESC LIMIT {limit}")
    tq = time.perf_counter()
    rows = query(sql, {})
    scan_ms = round((time.perf_counter() - tq) * 1000, 1)
    tot_sql = f"SELECT count(*) AS n FROM read_parquet({lit(s['url'])}) WHERE {w}{cf}"
    total = query(tot_sql, {})[0]["n"]
    rg = _rowgroups(s, start, end)
    return envelope("remote_count_by", dict(source=source, start=start, end=end, group_by=group_by, contains=contains,
                                            limit=limit), [sql, tot_sql, rg.pop("sql")], dict(source=source, start=start, end=end),
                    scope=f"remote {source}, {start} → {end} UTC, scanned in place over HTTPS; unit = log records",
                    rows=rows, t0=t0, total_matches=total, truncated=len(rows) >= limit, scan_ms=scan_ms, **rg)


def _index_for(source: str, start: datetime, end: datetime) -> Optional[dict]:
    from workspace import _ensure_registry
    _ensure_registry()
    for r in query("SELECT * FROM workspaces WHERE kind = 'remote' AND source = %(s)s", {"s": source}):
        if datetime.fromisoformat(r["start_ts"]) <= start and datetime.fromisoformat(r["end_ts"]) >= end:
            return r
    return None


def remote_search(
    query_text: Annotated[str, Field(description="Words to find in the message body (full-text when an index covers the "
                                                 "window, else a case-insensitive substring scan).")],
    start: Annotated[datetime, Field(description="Window start (UTC, inclusive).")],
    end: Annotated[datetime, Field(description="Window end (UTC, exclusive).")],
    service: Annotated[Optional[str], Field(description="Optional exact service name.")] = None,
    severity: Annotated[Optional[str], Field(description="Optional exact severity text.")] = None,
    source: Source = DEFAULT,
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description="Records to return.")] = 10,
) -> dict:
    """Find log records in the huge remote data: by index when one covers the window, else by an in-place scan.

    Use when: example records or exact match counts for words in the remote Parquet logs within a time window.
    Not for: the loaded datasets (search_logs).
    Returns: sample records (ts, service, severity, trace_id, body), the exact total and the time taken; path =
    'index' (remote_index covers the window: BM25-ranked full-text, milliseconds) or 'scan' (substring, seconds).
    Caveats: a scan window is limited to 10 minutes; scan and index match words slightly differently.
    Example: remote_search(query_text='timeout', start='<window start>', end='<+1 min>')
    Next: remote_index for repeated searches over the same window.
    """
    t0 = time.perf_counter()
    s = _src(source)
    idx = _index_for(source, start, end)
    tf = f'"{s["ts_col"]}" >= {_ts(start)} AND "{s["ts_col"]}" < {_ts(end)}'
    extra = (f' AND "{s["service_col"]}" = {lit(service)}' if service else "") + \
            (f' AND "{s["severity_col"]}" = {lit(severity)}' if severity else "")
    cols = f'"{s["ts_col"]}"::VARCHAR AS ts, "{s["service_col"]}" AS service, "{s["severity_col"]}" AS severity, ' \
           f'"{s["trace_col"]}" AS trace_id, left("{s["body_col"]}", 300) AS body'
    if idx:
        rel = f"rws_{idx['name']}_idx"
        w = f'WHERE "{s["body_col"]}" @@ websearch_to_tsquery({lit(query_text)}) AND {tf}{extra}'
        sql = f"SELECT {cols}, BM25({rel}.tableoid) AS score FROM {rel} {w} ORDER BY score DESC LIMIT {limit}"
        tot = f"SELECT count(*) AS n FROM {rel} {w}"
        path = "index"
    else:
        _window(s, start, end)
        w = f'WHERE {tf} AND "{s["body_col"]}" ILIKE {lit("%" + query_text + "%")}{extra}'
        sql = f"SELECT {cols} FROM read_parquet({lit(s['url'])}) {w} LIMIT {limit}"
        tot = f"SELECT count(*) AS n FROM read_parquet({lit(s['url'])}) {w}"
        path = "scan"
    tq = time.perf_counter()
    rows = query(sql, {})
    total = query(tot, {})[0]["n"]
    q_ms = round((time.perf_counter() - tq) * 1000, 1)
    return envelope("remote_search", dict(query_text=query_text, start=start, end=end, service=service, severity=severity,
                                          source=source, limit=limit), [sql, tot], dict(source=source, start=start, end=end),
                    scope=f"remote {source}, {start} → {end} UTC via {path}"
                          + (f" (workspace {idx['name']})" if idx else " (substring scan over HTTPS)"),
                    rows=rows, t0=t0, total_matches=total, truncated=total > len(rows), path=path, query_ms=q_ms)


def remote_index(
    start: Annotated[datetime, Field(description="Slice start (UTC, inclusive).")],
    end: Annotated[datetime, Field(description="Slice end (UTC, exclusive).")],
    name: Annotated[Optional[str], Field(description="Workspace name; default derived from the slice.")] = None,
    source: Source = DEFAULT,
    benchmark_text: Annotated[str, Field(description="Search used to measure scan vs index time.")] = "error",
) -> dict:
    """Build an inverted index over a time slice of the remote data without copying it, so searches there become
    index lookups.

    Use when: many searches will hit the same remote window, or the question is about index vs scan cost on huge
    data.
    Not for: one-off counts (remote_count_by).
    Returns: rows indexed, build time, the same search timed as scan vs index, and break_even_searches.
    Caveats: writes an index to the database (rows stay remote); max 30-minute slice; drop with drop_focus_index.
    Example: remote_index(start='<slice start>', end='<+1 min>')
    Next: remote_search on that window (path='index').
    """
    t0 = time.perf_counter()
    import re
    from workspace import _ensure_registry
    s = _src(source)
    _ensure_registry()
    if (end - start).total_seconds() > 3 * MAX_SCAN_SECONDS:
        raise ValueError("Slice longer than 30 minutes: keep remote indexes to small slices on this machine.")
    name = name or f"{source}_{start:%H%M%S}_{int((end - start).total_seconds())}s"
    if not re.fullmatch(r"[A-Za-z0-9_]{1,48}", name):
        raise ValueError("name: letters, digits and _ only.")
    v, idx = f"rws_{name}", f"rws_{name}_idx"
    tf = f'"{s["ts_col"]}" >= {_ts(start)} AND "{s["ts_col"]}" < {_ts(end)}'
    ddl = [f"DROP INDEX IF EXISTS {idx}", f"DROP VIEW IF EXISTS {v}",
           f'CREATE VIEW {v} AS SELECT "{s["ts_col"]}", "{s["service_col"]}", "{s["severity_col"]}", "{s["trace_col"]}", '
           f'"{s["body_col"]}" FROM read_parquet({lit(s["url"])}) WHERE {tf}',
           f'CREATE INDEX {idx} ON {v} USING inverted ("{s["ts_col"]}", "{s["service_col"]}", "{s["severity_col"]}", '
           f'"{s["trace_col"]}", "{s["body_col"]}" log_body_dict)']
    execute("DELETE FROM workspaces WHERE name = %(n)s", {"n": name})
    tb = time.perf_counter()
    for d in ddl:
        execute(d)
    build_ms = round((time.perf_counter() - tb) * 1000, 1)
    n = query(f"SELECT count(*) AS n FROM {idx}", {})[0]["n"]
    scan = (f"SELECT count(*) AS n FROM read_parquet({lit(s['url'])}) WHERE {tf} "
            f'AND "{s["body_col"]}" ILIKE {lit("%" + benchmark_text + "%")}')
    look = f'SELECT count(*) AS n FROM {idx} WHERE "{s["body_col"]}" @@ websearch_to_tsquery({lit(benchmark_text)})'
    ts_ = time.perf_counter()
    n_scan = query(scan, {})[0]["n"]
    scan_ms = round((time.perf_counter() - ts_) * 1000, 1)
    best = float("inf")
    for _ in range(5):
        tl = time.perf_counter()
        n_idx = query(look, {})[0]["n"]
        best = min(best, (time.perf_counter() - tl) * 1000)
    idx_ms = round(best, 2)
    be = round(build_ms / (scan_ms - idx_ms), 2) if scan_ms > idx_ms else None
    execute("INSERT INTO workspaces VALUES (%(n)s, 'remote', NULL, %(s)s, %(a)s, %(b)s, NULL, %(r)s, %(bm)s, %(c)s)",
          {"n": name, "s": source, "a": start.isoformat(sep=" "), "b": end.isoformat(sep=" "), "r": n, "bm": build_ms,
           "c": datetime.now().isoformat(timespec="seconds")})
    return envelope("remote_index", dict(start=start, end=end, name=name, source=source, benchmark_text=benchmark_text),
                    ddl + [scan, look], dict(source=source, start=start, end=end),
                    scope=f"remote {source}, slice {start} → {end} UTC indexed in place (view + inverted index)",
                    rows=[{"workspace": name, "rows_indexed": n, "build_ms": build_ms, "scan_ms": scan_ms,
                           "index_ms": idx_ms, "scan_matches": n_scan, "index_matches": n_idx, "break_even_searches": be}],
                    t0=t0, total_matches=n, truncated=False,
                    note="scan = case-insensitive substring; index = word tokens, so counts can differ slightly "
                         "('errors', 'error_code' match the substring but not the word)")
