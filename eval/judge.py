"""LLM-as-judge (plan 009), only where code cannot decide. A different, stronger model than the agent; structured
output; sees the question, the role's rubric and the run's evidence (SQL + results); never told which system wrote the
answer. Every score comes with written reasons (stored as LangSmith feedback comments).

- claim_support: each sentence → supported / unsupported / not a factual claim, against that run's evidence (E2c, E3)
- rubric: role-specific 1-5 scales with anchors (Q) + causes stated as fact + invented impact (E3, E5)
- pairwise: which answer serves the role better; asked in both orders, only consistent wins count (Q)
"""
import os
from typing import Literal

from langchain.chat_models import init_chat_model
from langchain_core.messages import HumanMessage, SystemMessage
from pydantic import BaseModel, Field

from agent.checker import ledger_json

JUDGE_MODEL = os.environ.get("JUDGE_MODEL", "anthropic:claude-opus-5-5")

ROLE_NEEDS = {
    "engineer": "investigate one failure: the error lines, component and node, what happened just before and after, "
                "whether it is local or widespread and new or recurring, a possible cause labelled as a hypothesis, and a "
                "concrete next check (a query to run, a component to inspect).",
    "lead": "see recurring problems over a stated period: counts and trend over time, by component and owning team, "
            "recurrences (not raw lines) and spread, and which one problem the team should investigate first, with a "
            "measured reason.",
    "manager": "decide priorities: a short ranked list of problems with owner team, the measured basis (frequency, "
               "spread, trend), an action to decide or fund per item, and an honest statement of what the logs do not "
               "show. Must not invent money, downtime or customer impact.",
}


def _model():
    return init_chat_model(JUDGE_MODEL, max_tokens=8000)


class Claim(BaseModel):
    sentence: str = Field(description="The sentence or clause, quoted from the answer.")
    verdict: Literal["supported", "unsupported", "not_factual"] = Field(
        description="supported: the evidence shows it (numbers match, or it follows directly); unsupported: a factual "
                    "claim the evidence does not show or contradicts (including rounded or derived numbers not in the "
                    "evidence, and causes stated as fact); not_factual: a recommendation, hypothesis clearly labelled "
                    "as such, a question, or a statement of what is unknown.")
    reason: str


class ClaimReport(BaseModel):
    claims: list[Claim]


class Rubric(BaseModel):
    role_fit: int = Field(ge=1, le=5, description="1 = generic or wrong role; 3 = partly what this role needs; "
                                                  "5 = exactly the evidence and decision this role needs.")
    next_step: int = Field(ge=1, le=5, description="1 = none or vague ('investigate further'); 3 = plausible but "
                                                   "generic; 5 = concrete, runnable, tied to the evidence, with owner.")
    evidence_use: int = Field(ge=1, le=5, description="1 = claims without evidence; 3 = some numbers with scope; "
                                                      "5 = every key claim backed by stated counts, period and scope.")
    separation: int = Field(ge=1, le=5, description="1 = causes stated as facts; 3 = mixed; 5 = facts, hypotheses "
                                                    "and unknowns clearly separated and labelled.")
    clarity: int = Field(ge=1, le=5, description="1 = hard to act on; 5 = short, ordered, easy to act on for this role.")
    causes_as_fact: int = Field(ge=0, description="How many causes or explanations are stated as established fact "
                                                  "without evidence in the answer.")
    invented_impact: bool = Field(description="Does the answer claim money, downtime or customer impact that logs "
                                              "cannot show (saying they are unknown is fine)?")
    reasons: str = Field(description="2-4 sentences justifying the scores.")


class Preference(BaseModel):
    winner: Literal["A", "B", "tie"]
    reasons: str


async def claim_support(question: str, role: str, answer: str, ledger: dict) -> dict:
    sys = ("You check whether an answer about system logs is supported by the evidence: the tool results (SQL that ran "
           "and its results) the system gathered. Split the answer into its factual sentences or clauses and judge each. "
           "Be strict with numbers: a number is supported only if the same value appears in the evidence (a rounded or "
           "derived value is unsupported). Do not use outside knowledge.")
    msg = f"Role: {role}\nQuestion: {question}\n\nEVIDENCE (JSON):\n{ledger_json(ledger, max_rows=8)}\n\nANSWER:\n{answer}"
    r = await _model().with_structured_output(ClaimReport, method="json_schema").ainvoke([SystemMessage(sys), HumanMessage(msg)])
    sup = sum(c.verdict == "supported" for c in r.claims)
    uns = [c for c in r.claims if c.verdict == "unsupported"]
    return {"score": sup / (sup + len(uns)) if sup + len(uns) else 1.0, "supported": sup, "unsupported": len(uns),
            "unsupported_claims": [{"sentence": c.sentence, "reason": c.reason} for c in uns]}


async def rubric(question: str, role: str, answer: str) -> dict:
    sys = (f"You grade an answer written for a {role.upper()} who asked a question about system logs. This role needs to "
           f"{ROLE_NEEDS[role]} Score each scale using its anchors. Judge content, not length or formatting.")
    r = await _model().with_structured_output(Rubric, method="json_schema").ainvoke(
        [SystemMessage(sys), HumanMessage(f"Question: {question}\n\nANSWER:\n{answer}")])
    d = r.model_dump()
    d["mean"] = round(sum(d[k] for k in ("role_fit", "next_step", "evidence_use", "separation", "clarity")) / 5, 2)
    return d


async def _prefer(question: str, role: str, a: str, b: str) -> Preference:
    sys = (f"Two answers to the same question, written for a {role.upper()} (who needs to {ROLE_NEEDS[role]}). Which "
           f"answer serves this person better: correct, grounded in measured evidence, specific, honest about unknowns? "
           f"Ignore length and formatting. Answer A, B or tie.")
    return await _model().with_structured_output(Preference, method="json_schema").ainvoke(
        [SystemMessage(sys), HumanMessage(f"Question: {question}\n\nANSWER A:\n{a}\n\nANSWER B:\n{b}")])


async def pairwise(question: str, role: str, ours: str, baseline: str) -> dict:
    """Ask in both orders; 'ours' / 'baseline' only if both orders agree, else 'inconsistent' (or 'tie')."""
    p1 = await _prefer(question, role, ours, baseline)        # A = ours
    p2 = await _prefer(question, role, baseline, ours)        # A = baseline
    first = {"A": "ours", "B": "baseline", "tie": "tie"}[p1.winner]
    second = {"A": "baseline", "B": "ours", "tie": "tie"}[p2.winner]
    result = first if first == second else "inconsistent"
    return {"result": result, "order1": first, "order2": second, "reasons": [p1.reasons, p2.reasons]}
