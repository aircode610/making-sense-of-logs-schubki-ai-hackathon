"""What Jev is asked, read from the code that asks it (no copy of any prompt), for the session report's Jev tab.

Sources: scripts/judge_patterns.sql (fault / dump / corrected / kind), scripts/judge_traits.py QUESTIONS (threat / cause /
actionable / role, + owner built per dataset), data/area_teams.csv (area per component), agent/support.py (claim
support), agent/prompts.py (route). Each entry: id, when it runs, what it is asked about, the question, its type and
its choices with their meaning, and how the answer is used.
"""
import ast
import csv
import json
import re
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]

STATE_PATTERN = "component · severity · message template (numbers and ids masked) · one real example line"
USE = {
    "fault": "p_fault: the base of p_problem",
    "dump": "p_dump: discounts register / status listings, p_problem = p_fault × (1 − p_dump)",
    "corrected": "p_corrected: stored, shown as context",
    "kind": "the kind label shown next to a problem",
    "threat": "p_threat: a security event counts as a problem too, p_problem = max(fault part, p_threat)",
    "cause": "the cause family shown next to a problem",
    "actionable": "stored as context (not used in rankings)",
    "role": "stored as context: root problem vs consequence",
    "owner": "owner hint: disputes or fills the ownership table",
    "area": "functional area → default team when the curated table has no owner",
    "support": "the Jev check on each answer card (stated / inferred / not in results)",
    "route": "our own agent picks the role when none is given",
}


def _choices(q: dict) -> list[dict]:
    """[{label, meaning, examples}] for any of the question types used here."""
    t, c = q.get("type"), q.get("criteria")
    if t == "noul":
        if isinstance(c, dict):
            return [{"label": k, "meaning": v.get("description", ""), "examples": v.get("examples", [])} for k, v in c.items()]
        return [{"label": "true", "meaning": "yes", "examples": []}, {"label": "false", "meaning": "no", "examples": []}]
    if t == "choice":
        return [{"label": k, "meaning": v, "examples": []} for k, v in (c or {}).items()]
    if t == "score":
        return [{"label": v, "meaning": "", "examples": []} for v in (c or [])]
    return []


def _entry(qid, stage, about, q, kind_note=""):
    return {"id": qid, "stage": stage, "about": about, "question": q.get("instructions", ""),
            "type": {"noul": "yes / no, with a calibrated probability", "choice": "one of the choices, with a confidence",
                     "score": "a graded score"}.get(q.get("type"), q.get("type", "")) + kind_note,
            "choices": _choices(q), "use": USE.get(qid, "")}


@lru_cache(maxsize=1)
def guide() -> dict:
    out = []
    # 1 · pattern judgments (scripts/judge_patterns.sql): the JSON literal between questions := '…'::JSON
    sql = (ROOT / "src/scripts/judge_patterns.sql").read_text()
    m = re.search(r"questions := '(\{.*?\})'::JSON", sql, re.S)
    if m:
        for qid, q in json.loads(m.group(1)).items():
            out.append(_entry(qid, "load · once per kind of message", STATE_PATTERN, q))
    # 2 · traits (scripts/judge_traits.py QUESTIONS, a literal dict) + owner (built per dataset from the ownership table)
    src = (ROOT / "src/scripts/judge_traits.py").read_text()
    node = next(n for n in ast.parse(src).body if isinstance(n, ast.Assign) and getattr(n.targets[0], "id", "") == "QUESTIONS")
    for qid, q in ast.literal_eval(node.value).items():
        out.append(_entry(qid, "load · once per kind of message", STATE_PATTERN, q))
    out.append({"id": "owner", "stage": "load · once per kind of message", "about": STATE_PATTERN,
                "question": "Which team should own the problem in `message`?", "type": "one of the choices, with a confidence",
                "choices": [{"label": "one choice per team", "meaning": "the dataset's teams in the ownership table, each with its description", "examples": []}],
                "use": USE["owner"]})
    # 3 · areas (data/area_teams.csv)
    with (ROOT / "data/config/area_teams.csv").open() as fh:
        areas = [{"label": r["area"], "meaning": r["description"].replace(" (fictional default team)", "") + f" → {r['team']}", "examples": []}
                 for r in csv.DictReader(fh)]
    out.append({"id": "area", "stage": "load · once per component", "about": "component name · dataset description",
                "question": "Which functional area of an IT system does the software `component` belong to?",
                "type": "one of the choices, with a confidence", "choices": areas, "use": USE["area"]})
    # 4 · claim support (agent/support.py) and 5 · route (agent/prompts.py)
    sup = (ROOT / "src/agent/support.py").read_text()
    qm = re.search(r'QUESTION = \((.*?)\)\n', sup, re.S)
    question = "".join(ast.literal_eval(f"[{qm.group(1)}]")) if qm else ""
    crit = re.findall(r"label: '(\w+)', description: '([^']*)'", sup)
    out.append({"id": "support", "stage": "answer · once per sentence", "about": "CLAIM (a sentence of the answer) · EVIDENCE (the tool result it matches)",
                "question": question, "type": "yes / no, with a calibrated probability",
                "choices": [{"label": l, "meaning": d, "examples": []} for l, d in crit], "use": USE["support"]})
    pr = (ROOT / "src/agent/prompts.py").read_text()
    rq = re.search(r'ROUTE_QUESTION = "([^"]*)"', pr)
    ro = re.findall(r'\{"label": "(\w+)", "description": "([^"]*)"\}', pr)
    out.append({"id": "route", "stage": "question · once (our agent only)", "about": "the user's question",
                "question": rq.group(1) if rq else "", "type": "one of the choices, with a confidence",
                "choices": [{"label": l, "meaning": d, "examples": []} for l, d in ro], "use": USE["route"]})
    return {"questions": out,
            "formula": "p_problem = max(p_fault × (1 − p_dump), p_threat). A pattern counts as a problem when it has "
                       "problem-level lines and p_problem ≥ 0.5.",
            "how": "Jev (TypeSafe) is called from SQL with ai_system_one(state, questions): it returns typed answers with "
                   "calibrated probabilities, not free text. Pattern questions run once at load time and are stored; "
                   "answering a question reads the stored values."}
