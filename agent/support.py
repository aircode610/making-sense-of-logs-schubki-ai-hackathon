"""Jev claim support (plan 011, idea G2): for every fact of a card, a calibrated probability that the cited evidence
supports it, asked in ONE SQL query inside SereneDB (ai_system_one, yes/no question, batch_size 1 = per-fact isolation).
A computed signal next to the deterministic number check: numbers can match while the meaning does not. Returns None per
fact when Jev is unavailable (no key, no database); never blocks an answer."""
import json
import os
from typing import Optional

import psycopg

QUESTION = ("Is the CLAIM fully supported by the EVIDENCE: same numbers, same meaning, same scope, nothing added "
            "that the evidence does not show?")
CRITERIA = ("{label: 'true', description: 'every part of the claim is shown by the evidence'}, "
            "{label: 'false', description: 'some part is not shown, contradicted, or overstated (e.g. lines called incidents, a cause stated as fact)'}")


def _relevant(rows: list, claim: str, n: int = 6) -> list:
    """The rows that share the most numbers / dates / words with the claim (a long series' relevant row is often not
    among the first ones), in their original order."""
    import re
    toks = set(re.findall(r"[\w.:\-]+", claim.lower()))
    scored = sorted(range(len(rows)), key=lambda i: -len(toks & set(re.findall(r"[\w.:\-]+", json.dumps(rows[i], default=str).lower()))))
    return [rows[i] for i in sorted(scored[:n])]


def _brief(ev: dict, claim: str = "", limit: int = 2400) -> str:
    """What a reader of the evidence sees: tool, scope, totals and the rows most relevant to the claim, compact JSON."""
    keep = {k: v for k, v in ev.items() if k not in ("sql", "params", "filters", "evidence_id", "elapsed_ms", "rows",
                                                       "items", "before", "after", "model_summary")}
    for k in ("rows", "items", "before", "after"):
        v = ev.get(k)
        if v:
            keep[k] = _relevant(v, claim) if isinstance(v, list) else v
    return json.dumps(keep, default=str, ensure_ascii=False)[:limit]


def _lit(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


def jev_support(card: dict, ledger: dict) -> list[Optional[float]]:
    try:
        return _jev_support(card, ledger)
    except Exception:  # noqa: BLE001  (a support score must never block an answer)
        return [None] * len(card.get("facts", []))


def _jev_support(card: dict, ledger: dict) -> list[Optional[float]]:
    facts = card.get("facts", [])
    if not facts or os.getenv("AGENT_JEV_SUPPORT", "1") == "0":
        return [None] * len(facts)
    states = []
    for f in facts:
        ev = " | ".join(_brief(ledger[i], f["statement"]) for i in f.get("evidence_ids", []) if i in ledger)[:4800]
        states.append(f"CLAIM: {f['statement']}\nEVIDENCE: {ev or '(none cited)'}")
    values = ", ".join(f"({i}, {_lit(s)})" for i, s in enumerate(states))
    sql = (f"SELECT i, round(ai_system_one(s, {_lit(QUESTION)}, noul := [{CRITERIA}], batch_size := 1), 3) AS p "
           f"FROM (VALUES {values}) t(i, s) ORDER BY i")
    try:
        with psycopg.connect(host=os.getenv("PGHOST", "localhost"), port=os.getenv("PGPORT", "7890"),
                             user=os.getenv("PGUSER", "postgres"), dbname=os.getenv("PGDATABASE", "postgres"),
                             autocommit=True) as c:
            got = {i: p for i, p in c.execute(sql).fetchall()}
    except Exception:  # noqa: BLE001
        return [None] * len(facts)
    return [got.get(i) for i in range(len(facts))]
