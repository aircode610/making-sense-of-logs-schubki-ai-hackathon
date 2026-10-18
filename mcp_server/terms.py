"""Term and facet tools (plan 011): breakdowns of a search result, what is distinctive about a window, which extracted
values (IPs, paths, ids) dominate, and which saved watches fired. Facets and term statistics are served by SereneDB's
inverted index (GROUPING SETS / ts_dict_* over the term dictionary), counted over ALL matching lines."""
import time
from datetime import datetime, timedelta
from typing import Annotated, Literal, Optional

from pydantic import Field

from core import (MATCH_HELP, MAX_ROWS, Dataset, DatasetOpt, MatchMode, check_dataset, envelope, filters_sql, query,
                  render, tsquery_sql)

Start = Annotated[Optional[datetime], Field(description="Inclusive start time.")]
End = Annotated[Optional[datetime], Field(description="Exclusive end time.")]
DIMS = {"component": "component", "severity": "severity", "node": "node", "location": "location",
        "pattern_id": "pattern_id", "status": "status", "dataset": "dataset"}


def _where(dataset, start, end, query_text, match, component=None, severity=None, node=None, location=None,
           pattern_id=None, entity=None):
    f = dict(dataset=dataset, start=start, end=end, component=component, severity=severity, node=node,
             location=location, pattern_id=pattern_id, entity=entity)
    where, params = filters_sql(f)
    if query_text:
        expr, qp = tsquery_sql(query_text, match)
        where += f" AND body @@ {expr}"
        params.update(qp)
    return "WHERE TRUE" + where, params, f


def facet(
    dataset: DatasetOpt = None,
    query_text: Annotated[Optional[str], Field(description="Optional full-text filter (see match).")] = None,
    match: Annotated[MatchMode, Field(description=MATCH_HELP)] = "web",
    start: Start = None,
    end: End = None,
    component: Annotated[Optional[str], Field(description="Exact component filter.")] = None,
    severity: Annotated[Optional[str], Field(description="Exact severity filter.")] = None,
    location: Annotated[Optional[str], Field(description="Location path at any level, e.g. 'R02/R02-M1'.")] = None,
    dims: Annotated[list[Literal["component", "severity", "node", "location", "pattern_id", "status", "dataset"]], Field(
        description="Breakdowns to compute in ONE pass, e.g. ['component', 'severity', 'node'].")] = ["component", "severity", "node"],
    top: Annotated[int, Field(ge=1, le=20, description="Values per breakdown, most lines first.")] = 8,
    workspace: Annotated[Optional[str], Field(description="Use a focus index (create_focus_index) instead of the corpus.")] = None,
) -> dict:
    """Breakdown of all lines matching a search / filter by several dimensions at once: "of 49,651 matching lines,
    99.9 % APP, all FAILURE, 1,024 nodes; top nodes …". One GROUPING SETS query over the inverted index (exact
    counts over every match, not a sample). rows = {dim, value, lines, share}; `distinct` = how many values each
    dimension has (a value list is cut to `top`). Lines are not incidents.
    """
    t0 = time.perf_counter()
    where, params, f = _where(dataset, start, end, query_text, match, component, severity, location=location)
    cols = [DIMS[d] for d in dims]
    sets = ", ".join(f"({c})" for c in cols)
    dim_case = " ".join(f"WHEN grouping({c}) = 0 THEN '{d}'" for d, c in zip(dims, cols))
    val = "coalesce(" + ", ".join(f"CASE WHEN grouping({c}) = 0 THEN {c}::VARCHAR END" for c in cols) + ")"
    from workspace import source_table
    tbl = source_table(workspace)
    sql = (f"SELECT CASE {dim_case} END AS dim, {val} AS value, count(*) AS lines FROM {tbl} {where} "
           f"GROUP BY GROUPING SETS ({sets})")
    allrows = query(sql, params)
    tot_sql = f"SELECT count(*) AS n FROM {tbl} {where}"
    total = query(tot_sql, params)[0]["n"]
    rows, distinct = [], {}
    for d in dims:
        g = sorted((r for r in allrows if r["dim"] == d), key=lambda r: -r["lines"])
        distinct[d] = len(g)
        rows += [{**r, "share": round(r["lines"] / total, 4) if total else None} for r in g[:top]]
    return envelope("facet", dict(query_text=query_text, match=match if query_text else None, dims=dims, top=top,
                                  workspace=workspace, **f),
                    [render(sql, params), render(tot_sql, params)], f,
                    scope=f"{dataset or 'all datasets'}, {start or 'corpus start'} → {end or 'corpus end'}; unit = log lines",
                    rows=rows, t0=t0, total_matches=total, distinct=distinct,
                    truncated=any(distinct[d] > top for d in dims))


def distinctive_terms(
    dataset: Dataset,
    start: Annotated[datetime, Field(description="Window start (inclusive): the incident / period of interest.")],
    end: Annotated[datetime, Field(description="Window end (exclusive).")],
    baseline: Annotated[Literal["before", "rest", "none"], Field(
        description="'before' = the `baseline_days` just before the window (what changed?), 'rest' = the whole dataset "
                    "outside the window, 'none' = just the loudest words of the window (tag cloud).")] = "before",
    baseline_days: Annotated[int, Field(ge=1, le=90, description="Length of the 'before' baseline in days.")] = 7,
    node: Annotated[Optional[str], Field(description="Optional: only this node / host (both sides).")] = None,
    component: Annotated[Optional[str], Field(description="Optional: only this component (both sides).")] = None,
    min_lines: Annotated[int, Field(ge=1, description="A term must appear in at least this many window lines.")] = 5,
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description="Terms to return.")] = 20,
) -> dict:
    """Significant terms: the words that are over-represented in a time window compared with a baseline, read from the
    inverted index's term dictionary (document counts per term, no scan). Answers "what is different about this
    incident window?" / "what's new this period?" without an LLM: e.g. 'severed', 'ciod' 30× more frequent than usual.
    Per term: window_lines, baseline_lines (lines containing it), lift = window_lines − expected from the baseline
    rate, ratio of rates, new_term (absent from the baseline). Words, not causes: label any reading as a hypothesis.
    """
    t0 = time.perf_counter()
    check_dataset(dataset)
    if end <= start:
        raise ValueError("end must be after start.")
    extra = (" AND node = %(node)s" if node else "") + (" AND component = %(comp)s" if component else "")
    params = {"d": dataset, "s": start, "e": end, "bs": start - timedelta(days=baseline_days), "node": node,
              "comp": component, "k": min_lines}
    fg_w = f"WHERE dataset = %(d)s AND ts >= %(s)s AND ts < %(e)s{extra}"
    bg_w = {"before": f"WHERE dataset = %(d)s AND ts >= %(bs)s AND ts < %(s)s{extra}",
            "rest": f"WHERE dataset = %(d)s AND (ts < %(s)s OR ts >= %(e)s){extra}", "none": None}[baseline]
    dict_q = "SELECT unnest(ts_dict_agg(body)) AS term, unnest(ts_dict_count(body)) AS n FROM logs_idx {w}"
    tot_q = "SELECT count(*) AS n FROM logs {w}"
    fg_total = query(tot_q.format(w=fg_w), params)[0]["n"]
    sqls = [render(tot_q.format(w=fg_w), params)]
    if bg_w:
        bg_total = query(tot_q.format(w=bg_w), params)[0]["n"]
        sql = (f"WITH fg AS ({dict_q.format(w=fg_w)}), bg AS ({dict_q.format(w=bg_w)}) "
               f"SELECT fg.term, fg.n AS window_lines, coalesce(bg.n, 0) AS baseline_lines, "
               f"round(fg.n - coalesce(bg.n, 0) * {fg_total}::DOUBLE / {max(bg_total, 1)}, 1) AS lift, "
               f"round((fg.n::DOUBLE / {max(fg_total, 1)}) / ((coalesce(bg.n, 0) + 1)::DOUBLE / {max(bg_total, 1)}), 1) AS ratio, "
               f"bg.n IS NULL AS new_term "
               f"FROM fg LEFT JOIN bg USING (term) WHERE fg.n >= %(k)s AND regexp_matches(fg.term, '[a-z]') "
               f"ORDER BY lift DESC, fg.term LIMIT {limit}")
        sqls += [render(tot_q.format(w=bg_w), params)]
    else:
        bg_total = None
        sql = (f"SELECT term, n AS window_lines FROM ({dict_q.format(w=fg_w)}) WHERE n >= %(k)s "
               f"AND regexp_matches(term, '[a-z]') ORDER BY n DESC, term LIMIT {limit}")
    rows = query(sql, params)
    sqls.insert(0, render(sql, params))
    f = dict(dataset=dataset, start=start, end=end, node=node, component=component)
    return envelope("distinctive_terms", dict(baseline=baseline, baseline_days=baseline_days, min_lines=min_lines,
                                              limit=limit, **f), sqls, f,
                    scope=f"{dataset}, window {start} → {end} ({fg_total} lines) vs "
                          + {"before": f"the {baseline_days} days before ({bg_total} lines)",
                             "rest": f"the rest of the dataset ({bg_total} lines)", "none": "no baseline"}[baseline]
                          + "; per term: lines containing it (term dictionary of the message index)",
                    rows=rows, t0=t0, total_matches=len(rows), truncated=len(rows) >= limit,
                    window_lines=fg_total, baseline_lines_total=bg_total)


def top_entities(
    dataset: Dataset,
    entity_type: Annotated[Literal["ip", "path", "uuid", "url", "any"], Field(
        description="Which extracted values: IPv4 addresses, file paths, UUIDs, URLs, or any.")] = "ip",
    query_text: Annotated[Optional[str], Field(description="Optional full-text filter on the message (see match).")] = None,
    match: Annotated[MatchMode, Field(description=MATCH_HELP)] = "web",
    start: Start = None,
    end: End = None,
    pattern_id: Annotated[Optional[int], Field(description="Optional: only lines of this pattern.")] = None,
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description="Values to return, most lines first.")] = 15,
) -> dict:
    """Which concrete values (IP addresses, file paths, VM / request UUIDs, URLs) appear most in the matching lines,
    with lines, first / last time, nodes and patterns per value. The values were extracted from every message at load
    time (column `entities`), so this is an exact count, e.g. "59.63.188.30 appears in 57,539 failed-login lines".
    Use the value with search_logs(entity='ip:…') to drill down.
    """
    t0 = time.perf_counter()
    where, params, f = _where(dataset, start, end, query_text, match, pattern_id=pattern_id)
    pref = "" if entity_type == "any" else entity_type + ":"
    params["pref"] = pref + "%"
    sql = (f"SELECT e AS entity, count(*) AS lines, min(ts) AS first_ts, max(ts) AS last_ts, "
           f"count(DISTINCT node) AS nodes, count(DISTINCT pattern_id) AS patterns "
           f"FROM (SELECT unnest(entities) AS e, ts, node, pattern_id FROM logs {where}) WHERE e LIKE %(pref)s "
           f"GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT {limit}")
    tot_sql = (f"SELECT count(DISTINCT e) AS values_total, count(*) AS mentions FROM "
               f"(SELECT unnest(entities) AS e FROM logs {where}) WHERE e LIKE %(pref)s")
    rows, tot = query(sql, params), query(tot_sql, params)[0]
    return envelope("top_entities", dict(entity_type=entity_type, query_text=query_text, limit=limit, **f),
                    [render(sql, params), render(tot_sql, params)], f,
                    scope=f"{dataset}, {start or 'corpus start'} → {end or 'corpus end'}; entities extracted from the "
                          f"message text at load time; lines = lines mentioning the value",
                    rows=rows, t0=t0, total_matches=tot["values_total"], mentions=tot["mentions"],
                    truncated=tot["values_total"] > len(rows))


def check_watchlist(
    dataset: Dataset,
    start: Annotated[datetime, Field(description="Window start (inclusive).")],
    end: Annotated[datetime, Field(description="Window end (exclusive).")],
) -> dict:
    """Saved searches ("watches", table watchlist, data/watchlist.csv): which of them fired in the window, with lines
    in the window vs the previous window of the same length. Use it for "did any of the known problems come back?" /
    a quick health check of a period. A watch is a fixed query (name, text, match mode); quiet watches are listed too.
    """
    t0 = time.perf_counter()
    check_dataset(dataset)
    watches = query("SELECT name, query_text, match FROM watchlist WHERE dataset = %(d)s ORDER BY name", {"d": dataset})
    rows, sqls = [], []
    w = end - start
    for wt in watches:
        expr, qp = tsquery_sql(wt["query_text"], wt["match"] or "web")
        params = {"d": dataset, "s": start, "e": end, "ps": start - w, **qp}
        sql = (f"SELECT count(*) FILTER (WHERE ts >= %(s)s) AS window_lines, "
               f"count(*) FILTER (WHERE ts < %(s)s) AS previous_lines, min(ts) FILTER (WHERE ts >= %(s)s) AS first_ts "
               f"FROM logs WHERE dataset = %(d)s AND ts >= %(ps)s AND ts < %(e)s AND body @@ {expr}")
        r = query(sql, params)[0]
        rows.append({"watch": wt["name"], "query": wt["query_text"], "match": wt["match"], **r,
                     "fired": r["window_lines"] > 0})
        sqls.append(render(sql, params))
    rows.sort(key=lambda r: (not r["fired"], -r["window_lines"]))
    return envelope("check_watchlist", dict(dataset=dataset, start=start, end=end), sqls, dict(dataset=dataset),
                    scope=f"{dataset}, window {start} → {end} vs previous {start - w} → {start}; unit = log lines",
                    rows=rows, t0=t0, total_matches=sum(r["fired"] for r in rows), truncated=False,
                    watches=len(rows))
