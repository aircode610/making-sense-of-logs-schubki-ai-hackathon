"""Agent-managed index workspace (plan 011; brief: "create an index for a selected time range and remove it after an
investigation … compare the time with and without the index"). A focus index is a copy of one investigation window
(dataset, time range, optional filters) in its own SereneDB search table with its own inverted index; search_logs and
facet accept workspace=<name>. Building it is timed and compared with the same queries on the full corpus, so every
workspace reports its break-even ("pays off after N repeated queries"). Plus index statistics and query plans."""
import json
import re
import time
from datetime import datetime
from typing import Annotated, Optional

from pydantic import Field

from core import Component, Dataset, Node, check_dataset, envelope, execute, filters_sql, query, render, tsquery_sql

MAX_ROWS_WS = 2_000_000
COLS = ("dataset, line_id, ts, component, severity, node, location, request_id, object_id, status, duration_ms, "
        "entities, body, pattern_id")


def _ensure_registry() -> None:
    execute("CREATE TABLE IF NOT EXISTS workspaces (name VARCHAR, kind VARCHAR, dataset VARCHAR, source VARCHAR, "
          "start_ts VARCHAR, end_ts VARCHAR, filters VARCHAR, rows BIGINT, build_ms DOUBLE, created VARCHAR)", {})


def source_table(workspace: Optional[str]) -> str:
    """Table a tool reads: `logs`, or the workspace's own table (validated against the workspaces registry)."""
    if not workspace:
        return "logs"
    _ensure_registry()
    r = query("SELECT name FROM workspaces WHERE name = %(n)s AND kind = 'local'", {"n": workspace})
    if not r:
        raise ValueError(f"Unknown workspace {workspace!r}; see index_stats.")
    return "ws_" + workspace


def _timed(sql: str, params: dict, reps: int = 5) -> float:
    best = float("inf")
    for _ in range(reps):
        t = time.perf_counter()
        query(sql, params)
        best = min(best, (time.perf_counter() - t) * 1000)
    return round(best, 2)


def create_focus_index(
    dataset: Dataset,
    start: Annotated[datetime, Field(description="Window start (inclusive).")],
    end: Annotated[datetime, Field(description="Window end (exclusive).")],
    name: Annotated[Optional[str], Field(description="Short name (letters, digits, _); default derived from the window.")] = None,
    component: Component = None,
    node: Node = None,
    benchmark_text: Annotated[Optional[str], Field(
        description="A search you expect to repeat (used to measure the speed-up); default 'error'.")] = None,
) -> dict:
    """Create a temporary, indexed copy of one investigation window (a workspace) to search it repeatedly and fast.

    Use when: you will run many searches / facets over the same window of a large dataset during one investigation,
    or the question is about the speed trade-off of building an index for a time range.
    Not for: one-off searches (search_logs already uses the corpus index).
    Returns: rows copied, build time, and the measured time of a typical search and count on the full corpus vs on the
    workspace, with break_even_queries = build time / time saved per query.
    Caveats: writes to the database (a new table); drop it with drop_focus_index when done. Max 2M lines.
    Example: create_focus_index(dataset=<dataset>, start='<window start>', end='<window end>', name='incident1')
    Next: search_logs(workspace='incident1') / facet(workspace='incident1'); then drop_focus_index('incident1').
    """
    t0 = time.perf_counter()
    check_dataset(dataset)
    _ensure_registry()
    name = name or f"{dataset}_{start:%Y%m%d%H%M}_{int((end - start).total_seconds() // 60)}m"
    if not re.fullmatch(r"[A-Za-z0-9_]{1,48}", name):
        raise ValueError("name: letters, digits and _ only (max 48).")
    f = dict(dataset=dataset, start=start, end=end, component=component, node=node)
    where, params = filters_sql(f)
    n = query(f"SELECT count(*) AS n FROM logs WHERE TRUE{where}", params)[0]["n"]
    if n == 0:
        raise ValueError("No lines in that window.")
    if n > MAX_ROWS_WS:
        raise ValueError(f"{n} lines: narrow the window (max {MAX_ROWS_WS:,}).")
    t = "ws_" + name
    execute(f"DROP TABLE IF EXISTS {t} CASCADE", {})
    execute("DELETE FROM workspaces WHERE name = %(n)s", {"n": name})
    ddl = [f"CREATE TABLE {t} (dataset VARCHAR, line_id BIGINT, ts TIMESTAMP, component VARCHAR, severity VARCHAR, "
           f"node VARCHAR, location VARCHAR, request_id VARCHAR, object_id VARCHAR, status INTEGER, duration_ms DOUBLE, "
           f"entities VARCHAR[], body VARCHAR, pattern_id INTEGER) "
           f"WITH (storage = 'search', optimize_top_k = 'bm25(1.2, 0.75)')",
           f"CREATE INDEX {t}_idx ON {t} USING inverted (ts, body log_body_dict, dataset, component, severity, node, "
           f"location location_dict, request_id, object_id, status, duration_ms, entities, pattern_id)"]
    tb = time.perf_counter()
    for d in ddl:
        execute(d)
    ins = f"INSERT INTO {t} SELECT {COLS} FROM logs WHERE TRUE{where} ORDER BY ts, line_id"
    execute(ins, params)
    execute(f"VACUUM (REFRESH_TABLE) {t}", {})
    build_ms = round((time.perf_counter() - tb) * 1000, 1)
    bench = benchmark_text or "error"
    expr, qp = tsquery_sql(bench, "web")
    q_full = f"SELECT line_id, ts, body FROM logs WHERE TRUE{where} AND body @@ {expr} ORDER BY BM25(logs.tableoid) DESC LIMIT 20"
    q_ws = f"SELECT line_id, ts, body FROM {t} WHERE body @@ {expr} ORDER BY BM25({t}.tableoid) DESC LIMIT 20"
    c_full = f"SELECT component, count(*) FROM logs WHERE TRUE{where} AND body @@ {expr} GROUP BY 1"
    c_ws = f"SELECT component, count(*) FROM {t} WHERE body @@ {expr} GROUP BY 1"
    p2 = {**params, **qp}
    times = {"search_full_ms": _timed(q_full, p2), "search_workspace_ms": _timed(q_ws, qp),
             "count_full_ms": _timed(c_full, p2), "count_workspace_ms": _timed(c_ws, qp)}
    saved = (times["search_full_ms"] - times["search_workspace_ms"]) + (times["count_full_ms"] - times["count_workspace_ms"])
    be = round(build_ms / saved, 1) if saved > 0 else None
    execute("INSERT INTO workspaces VALUES (%(n)s, 'local', %(d)s, 'logs', %(s)s, %(e)s, %(f)s, %(r)s, %(b)s, %(c)s)",
          {"n": name, "d": dataset, "s": str(start), "e": str(end), "f": json.dumps({"component": component, "node": node}),
           "r": n, "b": build_ms, "c": datetime.now().isoformat(timespec="seconds")})
    return envelope("create_focus_index", dict(name=name, benchmark_text=bench, **f),
                    ddl + [render(ins, params), render(q_full, p2), q_ws], f,
                    scope=f"workspace {name}: {dataset} {start} → {end}; benchmark = BM25 top-20 search + component "
                          f"count for {bench!r}, best of 5 runs each",
                    rows=[{"workspace": name, "rows": n, "build_ms": build_ms, **times,
                           "saved_per_query_pair_ms": round(saved, 2), "break_even_queries": be}],
                    t0=t0, total_matches=n, truncated=False,
                    reading=(f"pays off after about {be} repeated search+count pairs" if be
                             else "no speed-up measured: the corpus index already serves this window fast; keep it only "
                                  "for isolation or richer analysis"))


def drop_focus_index(
    name: Annotated[str, Field(description="Workspace name (see index_stats).")],
) -> dict:
    """Remove a workspace (a focus index or a remote-data index) when the investigation is over.

    Use when: a create_focus_index / remote_index workspace is no longer needed.
    Not for: anything else: this deletes the workspace's table / view and index.
    Returns: the removed workspace's name, kind, dataset, rows and build time.
    Caveats: destructive for the workspace only (never touches the corpus).
    Example: drop_focus_index(name='incident1')
    Next: index_stats to confirm it is gone.
    """
    t0 = time.perf_counter()
    _ensure_registry()
    r = query("SELECT * FROM workspaces WHERE name = %(n)s", {"n": name})
    if not r:
        raise ValueError(f"Unknown workspace {name!r}.")
    sqls = []
    if r[0]["kind"] == "local":
        sqls.append(f"DROP TABLE IF EXISTS ws_{name} CASCADE")
    else:
        sqls += [f"DROP INDEX IF EXISTS rws_{name}_idx", f"DROP VIEW IF EXISTS rws_{name}"]
    for s in sqls:
        execute(s)
    execute("DELETE FROM workspaces WHERE name = %(n)s", {"n": name})
    return envelope("drop_focus_index", {"name": name}, sqls, {"name": name}, scope=f"workspace {name} removed",
                    rows=[{k: r[0][k] for k in ("name", "kind", "dataset", "rows", "build_ms")}], t0=t0,
                    total_matches=1, truncated=False)


def index_stats() -> dict:
    """Which indexes and workspaces exist right now, and how big / healthy are they?

    Use when: checking that a workspace exists, reporting index cost (documents, size, segments, commit time), or when
    counts look stale (buffered_docs > 0 = recent writes not yet searchable).
    Not for: anything about the log contents.
    Returns: one row per inverted index (docs, live docs, buffered docs, segments, bytes, avg commit ms) and the
    workspace registry (window, rows, build time).
    Caveats: operator information only.
    Example: index_stats()
    Next: drop_focus_index for workspaces no longer needed.
    """
    t0 = time.perf_counter()
    _ensure_registry()
    sql = ("SELECT i.index_name, i.table_name, max(m.value) FILTER (WHERE m.metric = 'num_docs') AS docs, "
           "max(m.value) FILTER (WHERE m.metric = 'num_live_docs') AS live_docs, "
           "max(m.value) FILTER (WHERE m.metric = 'num_buffered_docs') AS buffered_docs, "
           "max(m.value) FILTER (WHERE m.metric = 'num_segments') AS segments, "
           "max(m.value) FILTER (WHERE m.metric = 'index_size') AS index_bytes, "
           "max(m.value) FILTER (WHERE m.metric = 'avg_commit_time_ms') AS avg_commit_ms "
           "FROM sdb_indexes() i LEFT JOIN pg_class ci ON ci.relname = i.index_name "
           "LEFT JOIN pg_class ct ON ct.relname = i.table_name "
           "LEFT JOIN sdb_metrics m ON m.relation_id IN (ci.oid, ct.oid) GROUP BY 1, 2 ORDER BY docs DESC NULLS LAST")
    rows = query(sql, {})
    ws = query("SELECT * FROM workspaces ORDER BY created", {})
    return envelope("index_stats", {}, [sql, "SELECT * FROM workspaces"], {}, scope="all inverted indexes of this database",
                    rows=rows, t0=t0, total_matches=len(rows), truncated=False, workspaces=ws)


def explain_tool(
    tool: Annotated[str, Field(description="Tool name, e.g. 'search_logs', 'facet', 'top_patterns'.")],
    args: Annotated[dict, Field(description="The tool's arguments as you would pass them.")],
    analyze: Annotated[bool, Field(description="Also run it (EXPLAIN ANALYZE) for per-operator timings.")] = False,
) -> dict:
    """How does the database execute this tool call? The query plan of a tool's main SQL, with index-usage flags.

    Use when: a performance question ("is this served by the index or a scan?", "why is this slow?") or to show how
    a result was computed.
    Not for: the result itself (call the tool).
    Returns: the plan (EXPLAIN, or EXPLAIN ANALYZE with timings when analyze=True) of the tool's first SQL statement
    and flags: inverted_index_scan, term_dictionary_facets, wand_top_k, vector_knn, full_scan.
    Caveats: analyze=True runs the query.
    Example: explain_tool(tool='search_logs', args={'dataset': <dataset>, 'query_text': 'timeout'})
    Next: create_focus_index if a repeated query scans a lot.
    """
    t0 = time.perf_counter()
    import server
    fn = server.TOOLS.get(tool)
    if fn is None or tool == "explain_tool":
        raise ValueError(f"Unknown tool {tool!r}; one of: {', '.join(sorted(server.TOOLS))}.")
    from pydantic import validate_call
    from core import pinned
    if pinned():  # pinned server: the wrapped tool injects the dataset itself
        args = {k: v for k, v in args.items() if k != "dataset"}
    env = validate_call(fn)(**args)  # same coercion as an MCP call (ISO strings → datetime, …)
    first = env["sql"][0]
    import re as _re
    # vector tools show '<embedding of …>' instead of 768 numbers; a zero vector of the same type gives the same plan
    first = _re.sub(r"<embedding[^>]*>", "[" + ",".join(["0"] * 768) + "]::FLOAT[768]", first)
    plan = query(("EXPLAIN ANALYZE " if analyze else "EXPLAIN ") + first, None)  # rendered SQL: no placeholders
    text = "\n".join(str(list(r.values())[-1]) for r in plan)
    flags = {"inverted_index_scan": "IRESEARCH_SCAN" in text, "term_dictionary_facets": "TsDict" in text,
             "wand_top_k": "optimized" in text, "vector_knn": any(op in first for op in ("<=>", "<->", "<#>", "<+>")),
             "full_scan": "SEQ_SCAN" in text or "READ_PARQUET" in text}
    return envelope("explain_tool", dict(tool=tool, args=args, analyze=analyze), [first], {}, scope=f"plan of {tool}'s first query",
                    rows=[], t0=t0, total_matches=0, truncated=len(text) > 6000, plan=text[:6000], flags=flags,
                    tool_elapsed_ms=env.get("elapsed_ms"))
