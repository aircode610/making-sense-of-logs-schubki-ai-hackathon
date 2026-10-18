"""Semantic tools (plan 011): patterns that mean the same thing, patterns found by meaning, and a model summary of a
burst. Pattern templates were embedded INSIDE SereneDB with ai_embed (scripts/embed_patterns.py) and live in the
`pattern_index` search table: one inverted index holds the template text (BM25) and the vector (IVF, cosine), so
lexical, semantic and hybrid (reciprocal rank fusion) search run in SQL. Model text is labelled and never evidence."""
import time
from datetime import datetime, timedelta
from typing import Annotated, Literal, Optional

from pydantic import Field

from core import MAX_ROWS, Dataset, DatasetOpt, check_dataset, envelope, lit, query, render

EMBED_MODEL, DIM = "gemini-embedding-001", 768
META = ("SELECT p.dataset, p.pattern_id, p.template, p.component, coalesce(o.team, 'unowned') AS team, p.lines, p.bursts, "
        "p.nodes, p.first_ts, p.last_ts, round(j.p_problem, 3) AS p_problem, t.cause, round(t.actionable, 2) AS actionable "
        "FROM patterns p LEFT JOIN ownership o ON o.dataset = p.dataset AND o.component = p.component "
        "LEFT JOIN pattern_judgments j ON j.dataset = p.dataset AND j.pattern_id = p.pattern_id "
        "LEFT JOIN pattern_traits t ON t.dataset = p.dataset AND t.pattern_id = p.pattern_id")


def _vec_literal(v) -> str:
    return "[" + ",".join(f"{x:.7g}" for x in v) + f"]::FLOAT[{DIM}]"


def _meta(keys: list[tuple[str, int]]) -> dict:
    if not keys:
        return {}
    cond = " OR ".join(f"(p.dataset = {lit(d)} AND p.pattern_id = {int(p)})" for d, p in keys)
    return {(r["dataset"], r["pattern_id"]): r for r in query(f"{META} WHERE {cond}", {})}


def similar_patterns(
    dataset: Dataset,
    pattern_id: Annotated[int, Field(description="The pattern to find look-alikes for.")],
    k: Annotated[int, Field(ge=1, le=MAX_ROWS, description="Neighbours to return.")] = 8,
    any_dataset: Annotated[bool, Field(description="Also search the other datasets (same problem in another system?).")] = False,
) -> dict:
    """Patterns that MEAN the same as one pattern (nearest template embeddings, cosine distance), even when worded
    differently: variants of one fault, the same failure in another component, or another dataset's equivalent.
    Per neighbour: distance (0 = same meaning), template, owner, lines, bursts, nodes, Jev p_problem and cause family.
    Use it to group a problem's variants before counting, or to ask "has something like this happened elsewhere?".
    Similarity of wording, not proof of a shared cause.
    """
    t0 = time.perf_counter()
    check_dataset(dataset)
    # pattern_id is selected with emb on purpose: projecting the vector column alone returned no rows (plan 011)
    src = query("SELECT pattern_id, emb FROM pattern_index WHERE dataset = %(d)s AND pattern_id = %(p)s",
                {"d": dataset, "p": pattern_id})
    if not src or src[0]["emb"] is None:
        raise ValueError("No stored embedding for this pattern (scripts/embed_patterns.py).")
    v = _vec_literal(src[0]["emb"])
    filt = "" if any_dataset else f"WHERE dataset @@ {lit(dataset)}"
    # two steps (vector first, then a constant probe) so the IVF index serves the kNN
    sql = (f"SELECT dataset, pattern_id, round(emb <=> {v}, 4) AS distance FROM pattern_index_idx {filt} "
           f"ORDER BY emb <=> {v} LIMIT {k + 1}")
    hits = [h for h in query(sql, {}) if not (h["dataset"] == dataset and h["pattern_id"] == pattern_id)][:k]
    meta = _meta([(h["dataset"], h["pattern_id"]) for h in hits])
    rows = [{**h, **{kk: vv for kk, vv in meta.get((h["dataset"], h["pattern_id"]), {}).items() if kk not in h}} for h in hits]
    probe = _meta([(dataset, pattern_id)]).get((dataset, pattern_id), {})
    return envelope("similar_patterns", dict(dataset=dataset, pattern_id=pattern_id, k=k, any_dataset=any_dataset),
                    [sql.replace(v, "<embedding of the pattern>")], dict(dataset=dataset, pattern_id=pattern_id),
                    scope=f"{'all datasets' if any_dataset else dataset}; template embeddings ({EMBED_MODEL}, {DIM} dims), "
                          f"cosine distance through the IVF index", rows=rows, t0=t0, total_matches=len(rows),
                    truncated=False, probe={k2: probe.get(k2) for k2 in ("template", "team", "lines", "bursts")})


def find_patterns(
    text: Annotated[str, Field(description="What you are looking for in plain words, e.g. 'network connection lost', "
                                           "'memory hardware errors', 'brute force login attempts'.")],
    dataset: DatasetOpt = None,
    mode: Annotated[Literal["hybrid", "semantic", "lexical"], Field(
        description="'semantic' = by meaning (embeds the text, needs the embedding key), 'lexical' = BM25 on the "
                    "template words, 'hybrid' (default) = both fused with reciprocal rank fusion (falls back to "
                    "lexical without a key).")] = "hybrid",
    k: Annotated[int, Field(ge=1, le=MAX_ROWS, description="Patterns to return.")] = 10,
) -> dict:
    """Find log patterns (message templates) by what they are about, when you do not know the exact log wording: the
    agent's vocabulary → the log's vocabulary. Returns pattern ids with template, owner, lines, bursts, nodes, Jev
    p_problem and cause, ranked; then count / trend them with top_patterns, search_logs(pattern_id=…), trend.
    `rank_source` says which ranking produced each hit.
    """
    t0 = time.perf_counter()
    check_dataset(dataset)
    filt = f"AND dataset @@ {lit(dataset)}" if dataset else ""
    sqls, note = [], None
    lex_sql = (f"SELECT dataset, pattern_id, BM25(pattern_index_idx.tableoid) AS s FROM pattern_index_idx "
               f"WHERE template @@ {lit(text)}::tsquery {filt} ORDER BY s DESC LIMIT 50")
    lex = query(lex_sql, {})
    sqls.append(lex_sql)
    sem = []
    if mode in ("semantic", "hybrid"):
        try:
            v = query(f"SELECT ai_embed({lit(text)}, '{EMBED_MODEL}', 'gemini', {DIM}) AS v", {})[0]["v"]
            vl = _vec_literal(v)
            sem_sql = (f"SELECT dataset, pattern_id, round(emb <=> {vl}, 4) AS distance FROM pattern_index_idx "
                       f"{'WHERE dataset @@ ' + lit(dataset) if dataset else ''} ORDER BY emb <=> {vl} LIMIT 50")
            sem = query(sem_sql, {})
            sqls.append(sem_sql.replace(vl, "<embedding of the text>"))
        except Exception as e:  # noqa: BLE001  (no embedding key / provider down)
            if mode == "semantic":
                raise ValueError(f"Semantic search needs the embedding secret (./docker/secrets.sh): {e}")
            note = "semantic branch unavailable (no embedding secret): lexical ranking only"
    if mode == "lexical":
        ranked = [((r["dataset"], r["pattern_id"]), {"bm25": round(r["s"], 3), "rank_source": "lexical"}) for r in lex]
    elif mode == "semantic":
        ranked = [((r["dataset"], r["pattern_id"]), {"distance": r["distance"], "rank_source": "semantic"}) for r in sem]
    else:  # reciprocal rank fusion, k = 60
        score, info = {}, {}
        for src, lst in (("lexical", lex), ("semantic", sem)):
            for i, r in enumerate(lst):
                key = (r["dataset"], r["pattern_id"])
                score[key] = score.get(key, 0) + 1 / (60 + i + 1)
                info.setdefault(key, {"rank_source": []})["rank_source"].append(src)
                if "distance" in r:
                    info[key]["distance"] = r["distance"]
        ranked = sorted(((key, {**info[key], "rrf": round(s, 5), "rank_source": "+".join(info[key]["rank_source"])})
                         for key, s in score.items()), key=lambda x: -x[1]["rrf"])
    ranked = ranked[:k]
    meta = _meta([key for key, _ in ranked])
    rows = [{**{"dataset": key[0], "pattern_id": key[1]}, **extra, **{kk: vv for kk, vv in meta.get(key, {}).items()
                                                                     if kk not in ("dataset", "pattern_id")}}
            for key, extra in ranked]
    return envelope("find_patterns", dict(text=text, dataset=dataset, mode=mode, k=k), sqls, dict(dataset=dataset),
                    scope=f"{dataset or 'all datasets'}; pattern templates; "
                          + {"lexical": "BM25 on template words", "semantic": f"cosine distance of {EMBED_MODEL} embeddings",
                             "hybrid": "reciprocal rank fusion of BM25 and embedding ranks (k = 60, top 50 each)"}[mode],
                    rows=rows, t0=t0, total_matches=len(rows), truncated=False, **({"note": note} if note else {}))


def summarize_burst(
    dataset: Dataset,
    pattern_id: Annotated[int, Field(description="Pattern whose burst to summarize.")],
    at: Annotated[Optional[datetime], Field(description="A time inside the burst; omit for the pattern's largest burst.")] = None,
    window_s: Annotated[int, Field(ge=0, le=3600, description="Also include other messages this many seconds around it.")] = 300,
) -> dict:
    """A short MODEL-WRITTEN summary of what the logs say during one burst (the distinct messages of the burst and
    `window_s` around it, in time order), written by SereneDB's ai_summarize_agg. Stored summaries are reused
    (burst_summaries); otherwise it is generated live (needs the chat secret). It is context for reading, NOT evidence:
    never cite numbers from it; take counts from the other tools. `model_summary` carries the text.
    """
    t0 = time.perf_counter()
    check_dataset(dataset)
    params = {"d": dataset, "p": pattern_id, "at": at}
    b_sql = ("SELECT * FROM bursts WHERE dataset = %(d)s AND pattern_id = %(p)s "
             + ("AND end_ts >= %(at)s ORDER BY start_ts LIMIT 1" if at else "ORDER BY lines DESC, start_ts LIMIT 1"))
    bs = query(b_sql, params)
    if not bs:
        raise ValueError("No burst of this pattern at or after that time.")
    b = bs[0]
    stored = query("SELECT summary, model, created FROM burst_summaries WHERE dataset = %(d)s AND pattern_id = %(p)s "
                   "AND burst_no = %(b)s", {"d": dataset, "p": pattern_id, "b": b["burst_no"]})
    lo, hi = b["start_ts"] - timedelta(seconds=window_s), b["end_ts"] + timedelta(seconds=window_s)
    src_sql = (f"SELECT body, ts FROM (SELECT DISTINCT ON (pattern_id) pattern_id, ts, body FROM logs "
               f"WHERE dataset = {lit(dataset)} AND ts >= TIMESTAMP '{lo:%Y-%m-%d %H:%M:%S.%f}' "
               f"AND ts <= TIMESTAMP '{hi:%Y-%m-%d %H:%M:%S.%f}' ORDER BY pattern_id, ts) ORDER BY ts LIMIT 40")
    if stored:
        summary, source = stored[0]["summary"], f"stored ({stored[0]['model']}, {stored[0]['created']})"
    else:
        sql = f"SELECT ai_summarize_agg(body, max_tokens := 6000 ORDER BY ts) AS s FROM ({src_sql})"
        try:
            summary, source = query(sql, {})[0]["s"], "generated live by ai_summarize_agg"
        except Exception as e:  # noqa: BLE001
            raise ValueError(f"No stored summary and live generation failed (chat secret?): {e}")
    n = query(f"SELECT count(*) AS n FROM ({src_sql})", {})[0]["n"]
    return envelope("summarize_burst", dict(dataset=dataset, pattern_id=pattern_id, at=at, window_s=window_s),
                    [render(b_sql, params), src_sql], dict(dataset=dataset, pattern_id=pattern_id),
                    scope=f"{dataset}, burst {b['burst_no']} of pattern {pattern_id} ({b['start_ts']} → {b['end_ts']}) "
                          f"± {window_s} s; {n} distinct messages summarized",
                    rows=[], t0=t0, total_matches=n, truncated=False,
                    burst={k: b[k] for k in ("burst_no", "start_ts", "end_ts", "lines", "nodes")},
                    model_summary=summary, summary_source=source,
                    warning="Model-written text: context only, not evidence. Do not cite numbers from it.")
