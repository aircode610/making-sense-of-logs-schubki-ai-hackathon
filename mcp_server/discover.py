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
    """What logs are loaded, over which period, and what does each field mean in each dataset? Start here.

    Use when: starting on a question, the question does not name a dataset or period, or you need to know what a
    field means (node, location, request_id, object_id, status, duration) in a given dataset before filtering on it.
    Not for: the values of one field (list_values), counts (count_by).
    Returns: one row per dataset: title, description, first_ts / last_ts (each dataset has its own clock: "now" = its
    last line), lines, patterns, bursts, owning teams, components and log levels (most frequent first), entity kinds,
    and per field its meaning here with a real example value (NULL = the dataset does not log it).
    Caveats: exact counts over the whole dataset; descriptions are written by whoever loaded the data.
    Example: describe_corpus()
    Next: list_values(dataset, field) for valid filter values; search_logs / top_patterns with the dataset and period.
    """
    t0 = time.perf_counter()
    sql = ("SELECT d.dataset, d.title, d.description, d.node_meaning, d.location_meaning, d.request_meaning, "
           "d.object_meaning, d.status_meaning, d.duration_meaning, "
           "(SELECT count(*) FROM patterns p WHERE p.dataset = d.dataset) AS patterns, "
           "(SELECT count(*) FROM bursts b WHERE b.dataset = d.dataset) AS bursts "
           "FROM datasets d ORDER BY d.pattern_base")
    rows = query(sql, {})
    reg = registry()
    for r in rows:
        v = reg.get(r["dataset"], {})
        r.update(first_ts=v.get("first_ts"), last_ts=v.get("last_ts"), lines=v.get("lines"),
                 teams=v.get("teams", []), components=(v.get("components") or [])[:12],
                 components_total=len(v.get("components") or []), severities=v.get("severitys") or [],
                 entity_kinds=v.get("entity_kinds", []), examples=v.get("examples", {}))
    return envelope("describe_corpus", {}, [sql], {}, scope="all loaded datasets; exact counts", rows=rows, t0=t0,
                    total_matches=len(rows), truncated=False,
                    note="lines = log entries; bursts = recurrences of one pattern split by > 30 min quiet; "
                         "components lists at most 12 (components_total = all); a NULL *_meaning = field not logged; "
                         "severities empty = the format has no log level.")


FIELDS = {"component": "component", "severity": "severity", "node": "node", "location": "location",
          "request_id": "request_id", "object_id": "object_id", "status": "status"}


def list_values(
    dataset: DatasetOpt,
    field: Annotated[Literal["component", "severity", "node", "location", "request_id", "object_id", "status",
                             "team", "entity"], Field(
        description="Which field's values: component, severity, node, location (every level of the path is a value), "
                    "request_id, object_id, status, team (ownership) or entity (typed values like ip:…, path:…).")],
    prefix: Annotated[Optional[str], Field(
        description="Only values starting with this, e.g. a location's first level, 'ip:' for entities, or the start "
                    "of a component name.")] = None,
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description=f"Values to return, most lines first (max {MAX_ROWS}).")] = 30,
) -> dict:
    """Which values does this field take (and how many lines carry each)? Valid filter values instead of guesses.

    Use when: you need the exact spelling of a component, node, location level, team or entity before filtering, or
    the question is "which X exist / which X logs the most".
    Not for: values of matching lines only (facet: breakdown of a search), ranked entities with first / last time
    (top_entities).
    Returns: rows {value, lines}, most lines first; values_total = all distinct values (truncated when > limit).
    Read from the inverted index's term dictionary: no scan, cheap to call.
    Caveats: lines are log lines, not incidents.
    Example: list_values(dataset=<dataset>, field='component')
    Next: use a value as the filter of search_logs / count_by / trend.
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
    """Which words really occur in the logs close to this spelling? Fixes a search that found nothing.

    Use when: search_logs returned 0 or very few matches, or you are unsure of the log's wording or spelling
    ("pasword" → password, "mont" → mount), before concluding that something is absent.
    Not for: finding messages by meaning in other words (find_patterns), why a search matches (explain_search).
    Returns: per word of `text`, indexed terms within `max_distance` edits, closest first then most lines, with the
    lines containing each; exact_found = words that do occur as typed.
    Caveats: candidates share the first letter; terms are lower-case word tokens.
    Example: suggest_terms(text='conection refused', dataset=<dataset>)
    Next: search_logs with the corrected words (or match='fuzzy').
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
    """Why does this search match what it matches? Tokens, per-token line counts and whether the index serves it.

    Use when: a search returns 0 or surprisingly many lines and you need to see how the text is tokenized (numbers,
    dotted ids and punctuation) and which token is rare or common.
    Not for: spelling fixes (suggest_terms), the matching lines themselves (search_logs).
    Returns: tokens of the text, lines containing each token, total matches of the whole query, and the query plan
    (index_served = the inverted index answers it).
    Caveats: diagnostic only; nothing about the incident itself.
    Example: explain_search(query_text='"status: 503"', dataset=<dataset>)
    Next: search_logs with an adjusted query or match mode.
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
