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

## Harness (plan 009) — how to run and what each number means
`.venv/bin/python -m eval.run_eval [--ids …] [--no-judge]` runs **ours** and the **baseline** (`create_agent`, same MCP
tools, plain role prompt) on `eval/dev_questions.yaml` (18 questions, 6 per role, golden facts from hand-written SQL
stored by `eval/build_golden.py`) as LangSmith experiments `ours-<sha>` / `baseline-<sha>` on dataset `logs-dev-<hash>`;
report in `eval/results/<time>.md/.json`. The held-out set runs through the same suite via the held-out runner (humans
only, aggregates only).

| Metric | Deterministic (code) | LLM judge (`claude-opus-5-5`, structured, reasons stored as feedback) |
|---|---|---|
| E1 correctness | golden fact values appear in the answer (numbers exact, dates `YYYY-MM-DD HH:MM`) | — |
| E2 groundedness | **E2a** numbers in the answer found in any tool result of the run (same rule both systems; years / day-of-month in prose and integers ≤ 10 skipped) · **E2b** ours: found in the result the fact *cites* | **E2c** every sentence → supported / unsupported / not factual against the run's evidence (rounded or derived numbers = unsupported) |
| E3 separation | facts / hypotheses / unknowns sections present | causes stated as fact (count) |
| E4 role distinctness | topic triples: Jaccard of tools and evidence ids between roles (lower = more distinct) | — |
| E5 forbidden claims | money / downtime / customer-impact regex outside "unknowns" | invented impact (bool) |
| E7 tool selection | required tools called; expected first tool | — |
| E8 cost / latency | seconds, tool calls, input / output tokens | — |
| Q answer quality | must-mention terms | role rubric 1-5 (role fit, next step, evidence use, separation, clarity) with anchors; **pairwise** ours vs baseline in both orders, only consistent wins count |

Judge caveats: our answers carry `[ev-…]` citations, so the judge can tell the systems apart; pairwise is asked in both
orders to cancel position bias; a human spot check of 6 answers is part of plan 009.
