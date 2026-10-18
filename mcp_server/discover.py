"""Discovery tools (plan 011): what is in the corpus, which values a filter accepts, how a search string is analyzed.
Values come from SereneDB's inverted-index term dictionary (ts_dict_*): no document scan, so they are cheap to call
before a search instead of guessing filter values."""
import re
import time
from typing import Annotated, Literal, Optional

from pydantic import Field

from core import (MATCH_HELP, MAX_ROWS, DatasetOpt, MatchMode, check_dataset, envelope, query, registry, render,
                  tsquery_sql)


def describe_corpus() -> dict:
    """What is loaded: one row per dataset with its title, description, time span, lines, patterns, bursts, owning
    teams, components and severities (most frequent first), what `location` means and which id fields exist.

    Call it first when the question does not name a dataset or period, to state the scope correctly ("the corpus
    ends 2006-01-04, so 'now' = 2006-01-04"). Every number is an exact count over the whole dataset.
    """
    t0 = time.perf_counter()
    sql = ("SELECT d.dataset, d.title, d.description, d.location_hint, d.id_fields, "
           "(SELECT count(*) FROM patterns p WHERE p.dataset = d.dataset) AS patterns, "
           "(SELECT count(*) FROM bursts b WHERE b.dataset = d.dataset) AS bursts "
           "FROM datasets d ORDER BY d.pattern_base")
    rows = query(sql, {})
    reg = registry()
    for r in rows:
        v = reg.get(r["dataset"], {})
        r.update(first_ts=v.get("first_ts"), last_ts=v.get("last_ts"), lines=v.get("lines"),
                 teams=v.get("teams", []), components=(v.get("components") or [])[:12],
                 components_total=len(v.get("components") or []), severities=v.get("severitys") or [])
    return envelope("describe_corpus", {}, [sql], {}, scope="all loaded datasets; exact counts", rows=rows, t0=t0,
                    total_matches=len(rows), truncated=False,
                    note="lines = log entries; bursts = recurrences of one pattern split by > 30 min quiet; "
                         "components lists at most 12 (components_total = all).")


FIELDS = {"component": "component", "severity": "severity", "node": "node", "location": "location",
          "request_id": "request_id", "instance_id": "instance_id", "status": "status"}


def list_values(
    dataset: DatasetOpt,
    field: Annotated[Literal["component", "severity", "node", "location", "request_id", "instance_id", "status",
                             "team", "entity"], Field(
        description="Which filter's values: component, severity, node, location (every level of the path), "
                    "request_id, instance_id, status, team (ownership) or entity (typed values like ip:…, path:…).")],
    prefix: Annotated[Optional[str], Field(
        description="Only values starting with this, e.g. 'R02' (BGL racks/midplanes), 'ip:' (entities), 'nova'.")] = None,
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description=f"Values to return, most lines first (max {MAX_ROWS}).")] = 30,
) -> dict:
    """The distinct values of one filter field with how many log lines carry each, read from the inverted index's
    term dictionary (no scan). Use it to find valid filter values (components, nodes, racks, teams, IPs) instead of
    guessing, or for "which X exist" questions. `values_total` = all distinct values (truncated when > limit).
    """
    t0 = time.perf_counter()
    check_dataset(dataset)
    params = {"d": dataset, "p": (prefix or "") + "%"}
    if field == "team":
        sql = ("SELECT coalesce(o.team, 'unowned') AS value, count(*) AS lines FROM logs "
               "LEFT JOIN ownership o ON o.dataset = logs.dataset AND o.component = logs.component "
               "WHERE TRUE" + (" AND logs.dataset = %(d)s" if dataset else "") +
               " GROUP BY 1 HAVING value LIKE %(p)s ORDER BY 2 DESC, 1")
    else:
        col = "entities" if field == "entity" else FIELDS[field]
        # term dictionary enumeration: values + live document counts, filtered by the dataset's documents
        # (a numeric column like status has no text dictionary: plain GROUP BY)
        if field == "status":
            sql = ("SELECT status::VARCHAR AS value, count(*) AS lines FROM logs WHERE status IS NOT NULL"
                   + (" AND dataset = %(d)s" if dataset else "") + " GROUP BY 1 HAVING value LIKE %(p)s ORDER BY 2 DESC, 1")
        else:
            sql = (f"SELECT value, lines FROM (SELECT unnest(ts_dict_agg({col})) AS value, "
                   f"unnest(ts_dict_count({col})) AS lines FROM logs_idx"
                   + (" WHERE dataset @@ %(d)s" if dataset else "") + ") WHERE value LIKE %(p)s ORDER BY lines DESC, value")
    allrows = query(sql, params)
    rows = allrows[:limit]
    return envelope("list_values", dict(dataset=dataset, field=field, prefix=prefix, limit=limit), [render(sql, params)],
                    {"dataset": dataset, "prefix": prefix},
                    scope=f"{dataset or 'all datasets'}, field {field}" + (" (every level of the path is a value)"
                                                                          if field == "location" else "")
                          + "; lines = log lines carrying the value",
                    rows=rows, t0=t0, total_matches=len(allrows), values_total=len(allrows),
                    truncated=len(allrows) > len(rows))


def suggest_terms(
    text: Annotated[str, Field(description="A word or a few words as you would search them (typos allowed).")],
    dataset: DatasetOpt = None,
    max_distance: Annotated[int, Field(ge=1, le=3, description="Edit distance allowed per word.")] = 2,
    per_word: Annotated[int, Field(ge=1, le=10, description="Suggestions per word.")] = 5,
) -> dict:
    """Spelling suggestions from the words that really occur in the logs: for each word of `text`, the indexed terms
    within `max_distance` edits, closest first, then by how many lines contain them. Use it when a search returns 0
    or few matches ("lustre mont" → mount; "pasword" → password) before concluding something is absent.
    """
    t0 = time.perf_counter()
    check_dataset(dataset)
    words = [w.lower() for w in re.findall(r"[\w.:\-/]+", text)][:6]
    rows, sqls = [], []
    for w in words:
        params = {"w": w, "p": w[:1] + "%", "d": dataset, "k": max_distance}
        sql = ("SELECT %(w)s AS word, term, lines, levenshtein(term, %(w)s) AS distance FROM ("
               "SELECT unnest(ts_dict_agg(body)) AS term, unnest(ts_dict_count(body)) AS lines FROM logs_idx "
               "WHERE body LIKE %(p)s" + (" AND dataset @@ %(d)s" if dataset else "") + ") "
               f"WHERE levenshtein(term, %(w)s) <= %(k)s ORDER BY distance, lines DESC LIMIT {per_word}")
        rows += query(sql, params)
        sqls.append(render(sql, params))
    return envelope("suggest_terms", dict(text=text, dataset=dataset, max_distance=max_distance, per_word=per_word),
                    sqls, {"dataset": dataset},
                    scope=f"{dataset or 'all datasets'}; terms of the message index (same first letter), lines = lines "
                          f"containing the term", rows=rows, t0=t0, total_matches=len(rows), truncated=False,
                    exact_found=sorted({r["word"] for r in rows if r["distance"] == 0}))


def explain_search(
    query_text: Annotated[str, Field(description="The search text exactly as you would pass it to search_logs.")],
    dataset: DatasetOpt = None,
    match: Annotated[MatchMode, Field(description=MATCH_HELP)] = "web",
) -> dict:
    """Why a search matches what it matches: how the message index tokenizes the text (ts_lexize), how many lines
    contain each token, the total matches of the whole query, and the query plan (whether the inverted index serves
    it: IRESEARCH_SCAN with the index filter). Use it when a search returns 0 or surprisingly many lines.
    """
    t0 = time.perf_counter()
    check_dataset(dataset)
    lex_sql = "SELECT ts_lexize('log_body_dict', %(t)s) AS tokens"
    tokens = query(lex_sql, {"t": query_text})[0]["tokens"] or []
    rows, sqls = [], [render(lex_sql, {"t": query_text})]
    for tok in tokens[:10]:
        p = {"tok": tok, "d": dataset}
        s = ("SELECT %(tok)s AS token, count(*) AS lines FROM logs WHERE TRUE" + (" AND dataset = %(d)s" if dataset else "")
             + " AND body @@ %(tok)s::tsquery")
        rows += query(s, p)
        sqls.append(render(s, p))
    expr, qp = tsquery_sql(query_text, match)
    qp["d"] = dataset
    tot_sql = "SELECT count(*) AS n FROM logs WHERE TRUE" + (" AND dataset = %(d)s" if dataset else "") + f" AND body @@ {expr}"
    total = query(tot_sql, qp)[0]["n"]
    plan = query("EXPLAIN " + render(tot_sql, qp), None)
    plan_text = "\n".join(str(list(r.values())[-1]) for r in plan)
    sqls += [render(tot_sql, qp)]
    return envelope("explain_search", dict(query_text=query_text, dataset=dataset, match=match), sqls,
                    {"dataset": dataset}, scope=f"{dataset or 'all datasets'}; dictionary log_body_dict "
                    "(lower-case word tokens; numbers and dotted ids stay whole)", rows=rows, t0=t0,
                    total_matches=total, truncated=False, tokens=tokens,
                    index_served="IRESEARCH_SCAN" in plan_text, plan=plan_text[:3000])
