"""Deterministic eval metrics (plan 009). Same rules for our agent and the baseline; no model involved.

One run = {question (yaml entry), kind, role, text, card?, check?, ledger, tools_used, elapsed_s, tokens_in, tokens_out}.
`text` is the answer as a reader sees it (our card rendered without the computed-confidence line and evidence appendix;
the baseline's free text), so E1 / E2a / E5 compare like with like. A run that errored scores 0 on every quality metric (`failed_run`, plan 010).
"""
import re

from agent.checker import DATE, FORBIDDEN, NUM, _check_text, _ledger_values, _to_float


def answer_text_from_card(card: dict) -> str:
    """Our card as plain text a reader sees (no confidence line, no SQL appendix)."""
    parts = [card["answer"], "Scope: " + card["scope"]]
    parts += [f["statement"] for f in card["facts"]]
    parts += [f"{r['rank']}. {r['problem']} — owner {r['owner_team']} — {r['basis']} — {r['action']}" for r in card.get("ranked", [])]
    parts += ["Hypothesis: " + h["statement"] + " Would confirm: " + h["would_confirm"] for h in card.get("hypotheses", [])]
    parts += ["Unknown: " + u for u in card.get("unknowns", [])]
    parts += ["Next step: " + s["action"] + " — " + s["why"] for s in card.get("next_steps", [])]
    return "\n".join(parts)


def _numbers(text: str) -> set[float]:
    return {_to_float(m.group())[0] for m in NUM.finditer(DATE.sub(" ", text))}


def in_order(phrases: list[str], text: str) -> bool:
    """Every phrase present (case-insensitive) and their first occurrences in the given order."""
    pos = [text.lower().find(p.lower()) for p in phrases]
    return -1 not in pos and pos == sorted(pos)


def golden_hits(q: dict, text: str, ranked_text: str | None = None) -> tuple[int, int, list[str]]:
    """E1: how many golden facts appear in the answer (numbers exactly, dates as 'YYYY-MM-DD HH:MM' text, ranking
    order as phrases in order: E6, checked on the ranked section when the answer has one)."""
    nums, flat, miss = _numbers(text), text.replace("T", " "), []
    hits = 0
    for g in q.get("golden", []):
        v = g["value"]
        if g.get("match") == "order":
            ok = in_order(v, ranked_text or text)
        elif g.get("match") == "date":
            ok = str(v) in flat
        elif g.get("match") == "text":
            ok = str(v).lower() in text.lower()
        else:
            ok = float(v) in nums
        hits += ok
        if not ok:
            miss.append(f"{g['fact']} = {v}")
    return hits, len(q.get("golden", [])), miss


def ledger_grounding(text: str, ledger: dict) -> tuple[int, int, list[str]]:
    """E2a: numbers in the answer found in ANY tool result of the run (identical rule for both systems)."""
    nums, texts = set(), []
    for ev in ledger.values():
        _ledger_values(ev, nums, texts)
    n, bad = _check_text(text, nums, " ".join(texts).replace("T", " "))
    return n - len(bad), n, bad


def _claims_text(run: dict) -> str:
    """The answer without the parts that say what the logs do NOT show (our card's unknowns; baseline: such lines)."""
    if run.get("card"):
        return answer_text_from_card({**run["card"], "unknowns": []})
    return "\n".join(l for l in run["text"].splitlines()
                     if not re.search(r"not (?:in|available|captured|recorded|established)|unknown|can(?:no|')t (?:tell|show|establish)", l, re.I))


def forbidden_claims(run: dict) -> list[str]:
    """E5: invented money / downtime / customer impact outside the 'unknowns' (our card) or outside lines that say the
    logs do not contain it (baseline free text)."""
    return sorted({m.group() for m in FORBIDDEN.finditer(_claims_text(run))})


def must_not_hits(q: dict, run: dict) -> list[str]:
    """E5: the question's must_not terms found in the answer, same exclusion of 'not in the logs' parts."""
    text = _claims_text(run).lower()
    return [t for t in q.get("must_not", []) if t.lower() in text]


def mentions(q: dict, text: str) -> tuple[int, int]:
    must = q.get("must_mention", [])
    return sum(m.lower() in text.lower() for m in must), len(must)


def separation(run: dict) -> dict:
    """E3 (deterministic part): are facts, hypotheses / possible causes and unknowns kept apart?"""
    if run.get("card"):
        c = run["card"]
        return {"facts": bool(c["facts"]), "hypotheses_labelled": True, "unknowns": bool(c["unknowns"])}
    t = run["text"]
    return {"facts": True,
            "hypotheses_labelled": bool(re.search(r"hypothes|possible cause|may be|might|likely|suggests?", t, re.I)),
            "unknowns": bool(re.search(r"unknown|not (?:in|established|available)|can(?:no|')t (?:tell|establish)|limitation", t, re.I))}


def tool_selection(q: dict, run: dict) -> dict:
    used = run.get("tools_used", [])
    req = set(q.get("required_tools", []))
    exp = q.get("expected_first_tool")
    exp = set(exp) if isinstance(exp, list) else {exp}  # a list = several valid first tools (plan 011 atomic tools)
    return {"required_called": req <= set(used), "first_tool_ok": bool(used) and used[0] in exp,
            "tool_calls": len(used)}


def tool_seconds(ledger: dict) -> float:
    """Seconds spent inside the tools (server-side `elapsed_ms` of every distinct result: DB + Python, no transport)."""
    return round(sum(ev.get("elapsed_ms") or 0 for ev in ledger.values()) / 1000, 2)


def failed_run(q: dict, kind: str, error: str) -> dict:
    """A run that errored or returned no answer: 0 on every quality metric, so a change that breaks questions can
    never raise a mean by dropping them."""
    return {"id": q["id"], "role": q["role"], "kind": kind, "error": error,
            "E1_correct": 0.0 if q.get("golden") else None, "E1_missed": ["(run failed)"],
            "E2a_ledger_grounded": 0.0, "E2a_numbers": 0, "E2a_unverified": [],
            "E2b_citation_grounded": 0.0 if kind == "ours" else None, "E2d_jev_support": 0.0 if kind == "ours" else None,
            "E3_separation": {"facts": False, "hypotheses_labelled": False, "unknowns": False},
            "E5_forbidden": [], "E5_must_not": [], "mentions": 0.0 if q.get("must_mention") else None,
            "E7_required_tools": False, "E7_first_tool": False, "E8_tool_calls": 0, "E8_elapsed_s": None,
            "E8_tool_s": None, "E8_other_s": None, "E8_tokens_in": None, "E8_tokens_out": None,
            "judge": {k: {"score": 0.0, "comment": "run failed"} for k in
                      ("E2c_claim_support", "Q_rubric_mean", "Q_role_fit", "Q_next_step")}}


def score_run(q: dict, run: dict) -> dict:
    text = run["text"]
    card = run.get("card") or {}
    ranked = "\n".join(f"{r['problem']} {r['basis']}" for r in card.get("ranked", [])) or None
    gh, gn, gmiss = golden_hits(q, text, ranked)
    lv, ln, lbad = ledger_grounding(text, run.get("ledger", {}))
    mh, mn = mentions(q, text)
    sel = tool_selection(q, run)
    out = {
        "id": q["id"], "role": q["role"], "kind": run["kind"],
        "E1_correct": gh / gn if gn else None, "E1_missed": gmiss,
        "E2a_ledger_grounded": lv / ln if ln else 1.0, "E2a_numbers": ln, "E2a_unverified": lbad,
        "E2b_citation_grounded": (run["check"]["numbers_verified"] / run["check"]["numbers_total"]
                                  if run.get("check") and run["check"]["numbers_total"] else None),
        "E2d_jev_support": (round(sum(x for x in sup if x is not None) / len([x for x in sup if x is not None]), 3)
                            if (sup := (run.get("check") or {}).get("jev_support") or []) and any(x is not None for x in sup)
                            else None),
        "E3_separation": separation(run), "E5_forbidden": forbidden_claims(run), "E5_must_not": must_not_hits(q, run),
        "mentions": mh / mn if mn else None,
        "E7_required_tools": sel["required_called"], "E7_first_tool": sel["first_tool_ok"],
        "E8_tool_calls": sel["tool_calls"], "E8_elapsed_s": run.get("elapsed_s"),
        "E8_tool_s": tool_seconds(run.get("ledger", {})),
        "E8_other_s": round(run["elapsed_s"] - tool_seconds(run.get("ledger", {})), 1) if run.get("elapsed_s") else None,
        "E8_tokens_in": run.get("tokens_in"), "E8_tokens_out": run.get("tokens_out"),
    }
    return out


def jaccard(a: set, b: set) -> float:
    return len(a & b) / len(a | b) if a | b else 0.0


def role_distinctness(questions: list[dict], runs: dict) -> list[dict]:
    """E4: for each topic asked by several roles, mean pairwise Jaccard of tools called and of evidence ids."""
    out = []
    topics = {}
    for q in questions:
        if q.get("topic"):
            topics.setdefault(q["topic"], []).append(q["id"])
    for kind in ("ours", "baseline"):
        for topic, ids in topics.items():
            rs = [runs.get((i, kind)) for i in ids]
            rs = [r for r in rs if r]
            if len(rs) < 2:
                continue
            pairs = [(a, b) for i, a in enumerate(rs) for b in rs[i + 1:]]
            out.append({"kind": kind, "topic": topic, "roles": [r["role"] for r in rs],
                        "tools_jaccard": round(sum(jaccard(set(a["tools_used"]), set(b["tools_used"])) for a, b in pairs) / len(pairs), 3),
                        "evidence_jaccard": round(sum(jaccard(set(a["ledger"]), set(b["ledger"])) for a, b in pairs) / len(pairs), 3)})
    return out
