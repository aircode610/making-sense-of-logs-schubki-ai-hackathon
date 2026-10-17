"""Deterministic claim checker (no model): numbers in the answer card must come from the tool results it cites.

- Every number in a fact / ranked item must equal a value in one of its cited evidence results (a value written with
  fewer decimals matches its rounding; "35%" also matches 0.35). Dates and times are matched as text.
- Numbers in the answer / next steps must appear somewhere in the ledger (they carry no citation).
- Integers 0-10 are not checked (ranks, "top 3", list counts) and identifiers (R02-M1, J18-U11, ev-…) are skipped.
- Forbidden claims (brief: no invented money, downtime or customer impact) outside the `unknowns` section.
- Role checklist (ROLES.md acceptance): which tools must have run and which card sections must be filled.
- confidence = verified-number rate, halved if the role checklist is incomplete. Computed, never self-reported.
"""
import json
import re
from decimal import ROUND_HALF_UP, Decimal

DATE = re.compile(r"\b\d{4}-\d{2}-\d{2}(?:[ T]\d{2}:\d{2}(?::\d{2})?)?")
NUM = re.compile(r"(?<![\w.:/#@-])-?\d{1,3}(?:,\d{3})+(?:\.\d+)?%?(?![\w:/-])|(?<![\w.:/#@-])-?\d+(?:\.\d+)?%?(?![\w:/-])")
FORBIDDEN = re.compile(
    r"[$€£]\s?\d|\b(?:usd|eur|dollars?|euros?|revenue|cost(?:s|ing)? (?:us|the company)|financial (?:loss|impact)|"
    r"hours? of downtime|downtime of|minutes? of (?:downtime|outage)|customers? (?:were |are )?(?:affected|impacted|lost)|"
    r"sla (?:breach|violation)|lost sales)\b", re.I)

# What each role must have gathered before composing (coverage) and what its card must contain (ROLES.md).
REQUIRED_TOOLS = {
    "engineer": [{"search_logs"}, {"get_context"}],
    "lead": [{"top_patterns"}, {"trend", "count_by"}],
    "manager": [{"priority_table"}],
}


def missing_tools(role: str, tools_used: set[str]) -> list[str]:
    return [" or ".join(sorted(g)) for g in REQUIRED_TOOLS[role] if not g & tools_used]


def _ledger_values(obj, nums: set, texts: list):
    if isinstance(obj, bool) or obj is None:
        return
    if isinstance(obj, (int, float)):
        nums.add(float(obj))
    elif isinstance(obj, str):
        texts.append(obj)
        for m in NUM.finditer(obj):
            nums.add(_to_float(m.group())[0])
    elif isinstance(obj, dict):
        for v in obj.values():
            _ledger_values(v, nums, texts)
    elif isinstance(obj, list):
        for v in obj:
            _ledger_values(v, nums, texts)


def _to_float(tok: str) -> tuple[float, int, bool]:
    pct = tok.endswith("%")
    t = tok.rstrip("%").replace(",", "")
    dec = len(t.split(".")[1]) if "." in t else 0
    return float(t), dec, pct


def _round(x: float, d: int) -> float:
    return float(Decimal(repr(x)).quantize(Decimal(1).scaleb(-d), rounding=ROUND_HALF_UP))


def _matches(tok: str, nums: set) -> bool:
    x, d, pct = _to_float(tok)
    cands = {x} | ({x / 100} if pct else set())
    for v in nums:
        for c in cands:
            dd = d + (2 if pct and c != x else 0)
            if v == c or _round(v, dd) == c or (abs(v) >= 1 and _round(v, d) == c and not pct):
                return True
    return False


def _check_text(text: str, nums: set, ledger_text: str) -> tuple[int, list[str]]:
    """Return (numbers checked, unverified tokens) for one piece of text."""
    checked, bad = 0, []
    for m in DATE.finditer(text):
        checked += 1
        if m.group().replace("T", " ") not in ledger_text:
            bad.append(m.group())
    rest = DATE.sub(" ", text)
    for m in NUM.finditer(rest):
        tok = m.group()
        x, d, pct = _to_float(tok)
        if not pct and d == 0 and 0 <= x <= 10:
            continue
        checked += 1
        if not _matches(tok, nums):
            bad.append(tok)
    return checked, bad


def check_card(card: dict, ledger: dict, role: str, tools_used: set[str]) -> dict:
    per_ev = {}
    for eid, ev in ledger.items():
        nums, texts = set(), []
        _ledger_values(ev, nums, texts)
        per_ev[eid] = (nums, " ".join(texts).replace("T", " "))
    all_nums = set().union(*(v[0] for v in per_ev.values())) if per_ev else set()
    all_text = " ".join(v[1] for v in per_ev.values())

    total, unverified, unverified_facts, bad_citations = 0, [], [], []

    def cited(ids):
        ok = [i for i in ids if i in per_ev]
        bad_citations.extend(i for i in ids if i not in per_ev)
        nums = set().union(*(per_ev[i][0] for i in ok)) if ok else set()
        return ok, nums, " ".join(per_ev[i][1] for i in ok)

    for i, f in enumerate(card.get("facts", [])):
        ok, nums, txt = cited(f.get("evidence_ids", []))
        n, bad = _check_text(f["statement"], nums, txt)
        total += n
        if not ok or bad:
            unverified_facts.append(i)
            unverified.append({"where": f"fact {i + 1}", "tokens": bad or ["no valid evidence id"], "text": f["statement"]})
    for r in card.get("ranked", []):
        ok, nums, txt = cited(r.get("evidence_ids", []))
        n, bad = _check_text(r["basis"], nums, txt)
        total += n
        if not ok or bad:
            unverified.append({"where": f"ranked {r['rank']}", "tokens": bad or ["no valid evidence id"], "text": r["basis"]})
    for where, text in [("answer", card.get("answer", ""))] + [(f"next step {i + 1}", s["action"] + " " + s["why"])
                                                               for i, s in enumerate(card.get("next_steps", []))]:
        n, bad = _check_text(text, all_nums, all_text)
        total += n
        if bad:
            unverified.append({"where": where, "tokens": bad, "text": text})
    n_bad = sum(len(u["tokens"]) for u in unverified if u["tokens"] != ["no valid evidence id"])

    claim_text = " ".join([card.get("answer", "")] + [f["statement"] for f in card.get("facts", [])]
                          + [r["problem"] + " " + r["basis"] + " " + r["action"] for r in card.get("ranked", [])]
                          + [s["action"] + " " + s["why"] for s in card.get("next_steps", [])])
    forbidden = sorted({m.group() for m in FORBIDDEN.finditer(claim_text)})

    missing = missing_tools(role, tools_used)
    if not card.get("next_steps"):
        missing.append("next step")
    if not card.get("unknowns"):
        missing.append("unknowns")
    if role == "engineer" and len(card.get("facts", [])) < 2:
        missing.append("≥ 2 facts (error lines + context)")
    if role in ("lead", "manager"):
        if not card.get("ranked"):
            missing.append("ranked problems")
        elif any(not r.get("owner_team") or not r.get("action") for r in card["ranked"]):
            missing.append("owner + action per ranked item")
        if not DATE.search(card.get("scope", "")):
            missing.append("absolute period in scope")

    verified = total - n_bad
    rate = verified / total if total else 1.0
    return {
        "numbers_total": total, "numbers_verified": verified, "unverified": unverified,
        "unverified_facts": unverified_facts, "bad_citations": sorted(set(bad_citations)), "forbidden": forbidden,
        "checklist_missing": missing, "confidence": round(rate * (0.5 if missing else 1.0), 3),
        "passed": not unverified and not forbidden and not missing,
    }


def feedback(report: dict) -> str:
    """Instructions for the one revision round."""
    lines = []
    for u in report["unverified"]:
        lines.append(f"- {u['where']}: {', '.join(u['tokens'])} not found in its cited results → copy the exact value "
                     f"from a cited result, cite the right evidence_id, or drop the number. Text: {u['text']!r}")
    if report["bad_citations"]:
        lines.append(f"- unknown evidence ids {report['bad_citations']}: only cite ids from the ledger")
    if report["forbidden"]:
        lines.append(f"- remove claims about money / downtime / customer impact {report['forbidden']} (not in the logs; "
                     f"they may only appear in `unknowns`)")
    if report["checklist_missing"]:
        lines.append(f"- missing for this role: {', '.join(report['checklist_missing'])}")
    return "\n".join(lines)


def ledger_json(ledger: dict) -> str:
    """Ledger for the compose prompt: every tool result in full (tools already cap rows at 50, plan 054)."""
    return json.dumps(ledger, default=str, ensure_ascii=False)
