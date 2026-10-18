"""Term and facet tools (plan 011): breakdowns of a search result, what is distinctive about a window, which extracted
values (IPs, paths, ids) dominate, and which saved watches fired. Facets and term statistics are served by SereneDB's
inverted index (GROUPING SETS / ts_dict_* over the term dictionary), counted over ALL matching lines."""
import time
from datetime import datetime, timedelta
from typing import Annotated, Literal, Optional

from pydantic import Field

from core import (MATCH_HELP, MAX_ROWS, Component, Dataset, DatasetOpt, End, Entity, Location, MatchMode, Node,
                  PatternIdOpt, Severity, Start, check_dataset, envelope, filter_hints, filters_sql, query,
                  render, tsquery_sql)
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
    query_text: Annotated[Optional[str], Field(description="Optional words the lines must contain (see match).")] = None,
    match: Annotated[MatchMode, Field(description=MATCH_HELP)] = "web",
    start: Start = None,
    end: End = None,
    component: Component = None,
    severity: Severity = None,
    node: Node = None,
    location: Location = None,
    entity: Entity = None,
    pattern_id: PatternIdOpt = None,
    dims: Annotated[list[Literal["component", "severity", "node", "location", "pattern_id", "status", "dataset"]], Field(
        description="Breakdowns to compute in ONE pass, e.g. ['component', 'severity', 'node'].")] = ["component", "severity", "node"],
    top: Annotated[int, Field(ge=1, le=20, description="Values per breakdown, most lines first.")] = 8,
    workspace: Annotated[Optional[str], Field(description="Use a focus index (create_focus_index) instead of the corpus.")] = None,
) -> dict:
    """Where do the matching lines come from? One search broken down by component, severity, node, location,
    pattern, status and dataset at once.

    Use when: you have a search or filter and want its shape in one call: "of 49,651 matching lines, 99.9 % from one
    component, all at one level, spread over 1,024 nodes; top nodes …".
    Not for: one grouping with team ownership (count_by group_by='team'), lines over time (trend), extracted values
    such as IPs or paths (top_entities).
    Returns: rows {dim, value, lines, share} for each requested breakdown (cut to `top` values); total_matches over
    all lines; `distinct` = how many values each breakdown has. Exact counts over every match.
    Caveats: lines are not incidents.
    Example: facet(dataset=<dataset>, query_text='timeout', dims=['component', 'node', 'pattern_id'])
    Next: search_logs with the dominant value as a filter; pattern_history for a dominant pattern_id.
    """
    t0 = time.perf_counter()
    where, params, f = _where(dataset, start, end, query_text, match, component, severity, node, location, pattern_id,
                              entity)
    cols = [DIMS[d] for d in dims]
    sets = ", ".join(f"({c})" for c in cols)
    dim_case = " ".join(f"WHEN grouping({c}) = 0 THEN '{d}'" for d, c in zip(dims, cols))
    val = "coalesce(" + ", ".join(f"CASE WHEN grouping({c}) = 0 THEN {c}::VARCHAR END" for c in cols) + ")"
    from workspace import source_table
    tbl = source_table(workspace)
    if len(cols) == 1:  # one grouping set is planned as a plain GROUP BY, where grouping() does not bind (SereneDB)
        sql = (f"SELECT '{dims[0]}' AS dim, {cols[0]}::VARCHAR AS value, count(*) AS lines FROM {tbl} {where} "
               f"GROUP BY {cols[0]}")
    else:
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
                    truncated=any(distinct[d] > top for d in dims), **({"hints": filter_hints(f)} if not total else {}))


def distinctive_terms(
    dataset: Dataset,
    start: Annotated[datetime, Field(description="Window start (inclusive): the incident / period of interest.")],
    end: Annotated[datetime, Field(description="Window end (exclusive).")],
    baseline: Annotated[Literal["before", "rest", "none"], Field(
        description="'before' = the `baseline_days` just before the window (what changed?), 'rest' = the whole dataset "
                    "outside the window, 'none' = just the loudest words of the window (tag cloud).")] = "before",
    baseline_days: Annotated[int, Field(ge=1, le=90, description="Length of the 'before' baseline in days.")] = 7,
    node: Node = None,
    component: Component = None,
    min_lines: Annotated[int, Field(ge=1, description="A term must appear in at least this many window lines.")] = 5,
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description="Terms to return.")] = 20,
) -> dict:
    """What is different about this time window? Words over-represented in the window compared with a baseline.

    Use when: an incident window or a period looks odd and you do not yet know what to search for ("what changed?",
    "what's unusual this week?"); the words point to the messages worth searching.
    Not for: new kinds of messages (whats_new: patterns first seen), counts of a known search (count_by / trend).
    Returns: per term: window_lines, baseline_lines (lines containing it), lift = window_lines minus the expected
    from the baseline rate, ratio of rates, new_term (absent from the baseline). From the index's term dictionary,
    no scan.
    Caveats: words, not causes: label any reading as a hypothesis; very common words are filtered by lift, not by a
    stop list.
    Example: distinctive_terms(dataset=<dataset>, start='<incident start>', end='<incident end>', baseline='before')
    Next: search_logs(query_text=<term>) in the window for the lines behind the top terms.
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
    entity_type: Annotated[str, Field(
        description="Which kind of extracted value: ip, path, uuid, url, … or 'any' (kinds per dataset: field guide).")] = "any",
    query_text: Annotated[Optional[str], Field(description="Optional words the lines must contain (see match).")] = None,
    match: Annotated[MatchMode, Field(description=MATCH_HELP)] = "web",
    start: Start = None,
    end: End = None,
    pattern_id: PatternIdOpt = None,
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description="Values to return, most lines first.")] = 15,
) -> dict:
    """Which IPs / paths / ids / URLs appear most in these lines? Who or what is behind the messages.

    Use when: "which IP addresses / clients / files / VMs / users drive X", attacks, scans, a noisy client, or which
    object ids are involved; values were extracted from every message at load time (column `entities`).
    Not for: grouping by component / node / severity (count_by / facet), the values of a structured field
    (list_values).
    Returns: per value: lines, first / last time, nodes, patterns; total_matches = distinct values; mentions = all
    mentions. Exact counts over every matching line.
    Caveats: a value appears only if the message text contains it; lines are not incidents.
    Example: top_entities(dataset=<dataset>, entity_type='ip', query_text='"authentication failure"')
    Next: search_logs(entity='ip:…') to drill into one value; trend(entity='ip:…') for its time profile.
    """
    t0 = time.perf_counter()
    where, params, f = _where(dataset, start, end, query_text, match, pattern_id=pattern_id)
    if not entity_type.replace("_", "").isalnum():
        raise ValueError("entity_type: a kind such as ip, path, uuid, url, or 'any'.")
    pref = "" if entity_type == "any" else entity_type.rstrip(":") + ":"
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
    """Did any of the known, saved problem searches fire in this window? A quick health check against a watchlist.

    Use when: "did any of the known problems come back", "anything from our usual suspects this week", a routine check
    of a period; watches are fixed searches configured per dataset (data/watchlist.csv).
    Not for: problems nobody has saved yet (top_patterns, whats_new), a single search (search_logs).
    Returns: one row per watch (name, query, match mode): window_lines, previous_lines (previous window of the same
    length), first_ts, fired; total_matches = watches that fired. Quiet watches are listed too.
    Caveats: datasets without configured watches return no rows; lines, not incidents.
    Example: check_watchlist(dataset=<dataset>, start='<week start>', end='<week end>')
    Next: search_logs(query_text=<watch query>) for a fired watch; trend for its profile.
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
