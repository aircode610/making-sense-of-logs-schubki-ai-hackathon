"""Answer card: the structured output the agent must produce (ROLES.md "Answer card"), and its Markdown rendering.

The LLM fills the card from the evidence ledger only; numbers, the confidence and the verification marks are added
by code (agent/checker.py), never self-reported by the model.
"""
from typing import Literal, Optional

from pydantic import BaseModel, Field

Role = Literal["engineer", "lead", "manager"]


class Fact(BaseModel):
    """An observed fact. Every number in `statement` must appear in a cited tool result."""
    statement: str = Field(description="One measured fact in plain words, numbers copied exactly from the cited results.")
    evidence_ids: list[str] = Field(description="evidence_id values (ev-…) of the tool results that show this fact.")


class Hypothesis(BaseModel):
    """A possible explanation: never stated as fact."""
    statement: str = Field(description="A possible cause or explanation, phrased as a possibility.")
    supported_by: list[str] = Field(default_factory=list, description="evidence_ids that make it plausible.")
    would_confirm: str = Field(description="What check or data would confirm or rule it out.")


class RankedItem(BaseModel):
    """A ranked problem (team lead: what to investigate first; manager: what to prioritise)."""
    rank: int
    problem: str = Field(description="The problem in plain words (the log pattern, explained).")
    owner_team: str = Field(description="Owning team from the tool results (ownership table), or 'unowned'.")
    basis: str = Field(description="Measured basis, numbers copied from the results: bursts, nodes, weeks, change.")
    action: str = Field(description="What the owner should check, decide or fix next.")
    evidence_ids: list[str]


class NextStep(BaseModel):
    action: str = Field(description="A concrete, runnable next step suited to the role.")
    owner: Optional[str] = Field(default=None, description="Who should do it (team or role), if known.")
    why: str = Field(description="Why this step, with reference to the evidence.")


class AnswerCard(BaseModel):
    answer: str = Field(description="1-3 sentences that directly answer the question for this role.")
    scope: str = Field(description="Datasets, absolute time period, filters, and whether results were truncated.")
    facts: list[Fact]
    ranked: list[RankedItem] = Field(default_factory=list,
                                     description="Team lead / manager: ranked problems. Engineer: leave empty.")
    hypotheses: list[Hypothesis] = Field(default_factory=list)
    unknowns: list[str] = Field(description="What these logs cannot establish (e.g. root cause, cost, customer impact).")
    next_steps: list[NextStep]


def render(card: dict, check: Optional[dict] = None, ledger: Optional[dict] = None, role: str = "") -> str:
    """Markdown answer card; facts that failed verification are marked; evidence appendix with the SQL."""
    bad = set((check or {}).get("unverified_facts", []))
    out = [f"## Answer ({role})" if role else "## Answer", card["answer"], "", f"**Scope:** {card['scope']}", ""]
    if check:
        out += [f"**Confidence (computed):** {check['confidence']:.0%} · numbers verified "
                f"{check['numbers_verified']}/{check['numbers_total']} · checklist "
                f"{'passed' if not check['checklist_missing'] else 'missing: ' + ', '.join(check['checklist_missing'])}", ""]
    out.append("### Facts")
    support = (check or {}).get("jev_support") or []
    for i, f in enumerate(card["facts"]):
        mark = " ⚠ unverified" if i in bad else ""
        if i < len(support) and support[i] is not None:
            mark += f" · Jev support {support[i]:.2f}"
        out.append(f"- {f['statement']} `[{', '.join(f['evidence_ids'])}]`{mark}")
    if card.get("ranked"):
        out += ["", "### Ranked"]
        for r in card["ranked"]:
            out.append(f"{r['rank']}. **{r['problem']}** · owner `{r['owner_team']}` · {r['basis']} → {r['action']} "
                       f"`[{', '.join(r['evidence_ids'])}]`")
    if card.get("hypotheses"):
        out += ["", "### Hypotheses (not established by the logs)"]
        for h in card["hypotheses"]:
            out.append(f"- {h['statement']} (supported by {', '.join(h['supported_by']) or '—'}; "
                       f"would confirm: {h['would_confirm']})")
    out += ["", "### Unknown"] + [f"- {u}" for u in card["unknowns"]]
    out += ["", "### Next steps"] + [f"- {s['action']}" + (f" (owner: {s['owner']})" if s.get("owner") else "")
                                      + f" — {s['why']}" for s in card["next_steps"]]
    if ledger:
        cited = {e for f in card["facts"] for e in f["evidence_ids"]} | {e for r in card.get("ranked", []) for e in r["evidence_ids"]}
        out += ["", "### Evidence"]
        for eid, ev in ledger.items():
            if eid not in cited:
                continue
            tot = ev.get("total_matches", ev.get("total_lines"))
            out.append(f"- `{eid}` **{ev['tool']}** · {ev.get('scope', '')} · total {tot} · truncated {ev.get('truncated')} "
                       f"· {ev.get('elapsed_ms')} ms")
            for sql in ev.get("sql", [])[:2]:
                out.append(f"  - `{sql[:400]}`")
    return "\n".join(out)
