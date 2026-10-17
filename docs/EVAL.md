# Evaluation: prove it against the rubric (and against the baseline)

The side-quest eval (macro-F1 on fault labels, held-out splits, Jev vs LLM fairness) answered "is Jev a good fit".
The hackathon is judged on something else: **correct numbers, grounded answers, distinct roles, useful next steps.**
So the eval changes to that. Every metric below runs for **our agent** and the **baseline ReAct agent** (same LLM,
same base tools), on the same question set. Small, scripted, re-runnable (`eval/`), results in LangSmith + a table here.

| ID | Measures | Rubric line | How | Target |
|---|---|---|---|---|
| E1 | **Query correctness** | 25% search+analytics | ~15 golden questions with hand-checked reference SQL (counts by dataset/team/component, trends, a full-text count); compare tool output exactly | 100% |
| E2 | **Groundedness** | 25% recommendation, "shows its work" | parse numbers in the final answer; each must equal a value in a cited evidence result; % sentences with citations; claims flagged by the checker | ≥ 95% numbers verified; baseline measured |
| E3 | **Fact / hypothesis / unknown separation** | 25% recommendation | answer card sections present; no hypothesis phrased as fact (Jev Noul per sentence + spot check) | 100% sections; 0 forbidden claims |
| E4 | **Role distinctness** | 30% role insight | same topic, three roles: overlap of tools called + evidence ids (Jaccard, lower = more distinct); per-role checklist (engineer: error lines + before/after + next check; lead: period + counts + trend + teams; manager: ranked list + measured basis + action) | checklist 100%; overlap < baseline |
| E5 | **Forbidden claims** (manager) | brief rule | no money / downtime / customer-impact claims (regex + judge) | 0 |
| E6 | **Finds the real problems** | 30% / 25% | BGL alert labels: pattern-level precision/recall of "problem" patterns (Jev columns vs severity-only vs LLM); OpenStack: does the engineer flow reach the 3 anomalous instances; does the manager's top-k cover the largest alert categories | report numbers; beat severity-only |
| E7 | **Tool selection** | Best MCP award | expected first tool per question; % correct; results within limits | ≥ 90% |
| E8 | **Cost / latency** | 20% execution | per answer: wall time, LLM tokens, Jev calls, $; index on/off timing if we build it | report |
| E9 | **Clean checkout** | 20% execution | fresh clone → README steps → demo question answered (Konark runs it on his machine) | passes |

Rules
- Held-out questions and a held-out BGL time slice are scored only by `eval/run_heldout.py` (`HELDOUT.md`).
- Per-tool p50/p95 latency comes from `bench/` (`PERFORMANCE.md`) and is reported with E8.
- Labels (BGL alert category, OpenStack anomaly ids) are for evaluation only; tools must not hand them to the agent as answers.
- Golden SQL answers are written and checked by hand once, stored in `eval/golden.yaml`.
- Keep it cheap: question set ≤ 30 (10 per role); re-run after each milestone; record the table in `STATUS.md`.
- Honest reporting: if the baseline wins on something, we say so.
