"""Deterministic eval metrics (plan 009). Same rules for our agent and the baseline; no model involved.

One run = {question (yaml entry), kind, role, text, card?, check?, ledger, tools_used, elapsed_s, tokens_in, tokens_out}.
`text` is the answer as a reader sees it (our card rendered without the computed-confidence line and evidence appendix;
the baseline's free text), so E1 / E2a / E5 compare like with like.
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


def golden_hits(q: dict, text: str) -> tuple[int, int, list[str]]:
    """E1: how many golden facts appear in the answer (numbers exactly, dates as 'YYYY-MM-DD HH:MM' text)."""
    nums, flat, miss = _numbers(text), text.replace("T", " "), []
    hits = 0
    for g in q.get("golden", []):
        v = g["value"]
        if g.get("match") == "date":
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


def forbidden_claims(run: dict) -> list[str]:
    """E5: invented money / downtime / customer impact outside the 'unknowns' (our card) or outside lines that say the
    logs do not contain it (baseline free text)."""
    if run.get("card"):
        text = answer_text_from_card({**run["card"], "unknowns": []})
    else:
        text = "\n".join(l for l in run["text"].splitlines()
                         if not re.search(r"not (?:in|available|captured|recorded|established)|unknown|can(?:no|')t (?:tell|show|establish)", l, re.I))
    return sorted({m.group() for m in FORBIDDEN.finditer(text)})


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
    return {"required_called": req <= set(used), "first_tool_ok": bool(used) and used[0] == q.get("expected_first_tool"),
            "tool_calls": len(used)}


def score_run(q: dict, run: dict) -> dict:
    text = run["text"]
    gh, gn, gmiss = golden_hits(q, text)
    lv, ln, lbad = ledger_grounding(text, run.get("ledger", {}))
    mh, mn = mentions(q, text)
    sel = tool_selection(q, run)
    out = {
        "id": q["id"], "role": q["role"], "kind": run["kind"],
        "E1_correct": gh / gn if gn else None, "E1_missed": gmiss,
        "E2a_ledger_grounded": lv / ln if ln else 1.0, "E2a_numbers": ln, "E2a_unverified": lbad,
        "E2b_citation_grounded": (run["check"]["numbers_verified"] / run["check"]["numbers_total"]
                                  if run.get("check") and run["check"]["numbers_total"] else None),
        "E3_separation": separation(run), "E5_forbidden": forbidden_claims(run),
        "mentions": mh / mn if mn else None,
        "E7_required_tools": sel["required_called"], "E7_first_tool": sel["first_tool_ok"],
        "E8_tool_calls": sel["tool_calls"], "E8_elapsed_s": run.get("elapsed_s"),
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
