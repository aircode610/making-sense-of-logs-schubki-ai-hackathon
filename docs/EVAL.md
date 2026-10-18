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
| E1 correctness | golden fact values appear in the answer (numbers exact, dates `YYYY-MM-DD HH:MM`); **E6 ranking** (plan 010): manager questions' computed `priority_table` top items, as phrases in rank order (checked on our ranked section) | — |
| E2 groundedness | **E2a** numbers in the answer found in any tool result of the run (same rule both systems; years / day-of-month in prose and integers ≤ 10 skipped) · **E2b** ours: found in the result the fact *cites* | **E2c** every sentence → supported / unsupported / not factual against the run's evidence (rounded or derived numbers = unsupported) |
| E3 separation | facts / hypotheses / unknowns sections present | causes stated as fact (count) |
| E4 role distinctness | topic triples: Jaccard of tools and evidence ids between roles (lower = more distinct) | — |
| E5 forbidden claims | money / downtime / customer-impact regex outside "unknowns"; the question's `must_not` terms | invented impact (bool) |
| E7 tool selection | required tools called; expected first tool | — |
| E8 cost / latency | seconds (split: inside tools = DB, vs LLM + overhead), tool calls, input / output tokens | — |
| failures | a run that errors scores 0 on every quality metric (never dropped); `runs failed` row | — |
| Q answer quality | must-mention terms | role rubric 1-5 (role fit, next step, evidence use, separation, clarity) with anchors; **pairwise** ours vs baseline in both orders, only consistent wins count |

Judge caveats: our answers carry `[ev-…]` citations, so the judge can tell the systems apart; pairwise is asked in both
orders to cancel position bias; a human spot check of 6 answers is part of plan 009. Since plan 010 the claim judge
sees every tool result in full (it saw 8 rows per result before, while the composer saw all: correct claims about
rows 9+ were marked unsupported).

## How to iterate (plan 010): is my change better, beyond noise, with no regressions?
1. **Tools / DB only** (new backend, rewritten query, new index): `.venv/bin/python bench/replay_tools.py
   eval/results/<last>.json` replays every recorded tool call: must be 100 % identical-or-same-rows; prints p50/p95 per
   tool. No LLM cost. (End-to-end latency is dominated by the LLM: tools are ~1 % of seconds per answer, row "inside tools".)
2. **Agent / prompts / new tools, fast check** (no judge, baseline reused):
   `.venv/bin/python -m eval.run_eval --systems ours --no-judge --reuse-baseline eval/results/<ref>.json --compare eval/results/<ref>.json`
3. **Full check** (judge + pairwise new vs old): same without `--no-judge`. Keep the change if the deltas beat the
   noise below and the regression list is empty (or explained).
- Judge or golden facts changed? `--rejudge <x>.json` re-scores stored answers without running the agent; `--compare`
  always re-scores the old answers with the current golden facts.
- Every run writes `<stamp>.runs.json` (answers + evidence), which is what reuse / compare / replay read; older results
  are fetched from LangSmith.
- **Noise** (`--repeat 3`, same code, max − min of the overall mean over 20 dev questions, run `20261018-025819`):
  E1 0.05 · E2a 0.001 · E2c 0.01 · rubric mean 0.06 · role fit 0.2 · next-step 0.15 · E7 first tool 0.05 ·
  causes-as-fact 0.15 · seconds ±5 · input tokens ±8k. So a change must beat e.g. **E1 by > 0.05** or **rubric by
  > 0.06** to count; per-question changes are noisier than these means (a 3-rep mean can still drop on one question).
- Dev questions were written after seeing the data: tuning on them overfits. The human-written private set is the
  real test; write it before heavy tuning.

## Blind A/B with answer keys (plan 013)
`.venv/bin/python -m eval.ab [--ids ...] [--reuse <runs.json>] [--concurrency 1]` compares two toolsets of the same
agent. Ground truth = `eval/answer_keys/<id>.yaml` (frozen; rules in its README). Judge = Opus agent + read-only `sql`
(DB role `logs_manager`), blinded answers, X/Y seeded, both orders; only order-consistent wins count. Per arm: claim
accuracy, found_problem (0-2), rubric, E1, and **time split** wall = llm + tool (client) + other, plus tool db (server
`elapsed_ms`) and per-tool calls / ms. Shell note: unset `ANTHROPIC_BASE_URL` / `ANTHROPIC_AUTH_TOKEN` if a proxy is
exported (401 otherwise). First result: `eval/results/ab-20261018-144958.md`.

## Claude Code with our MCP vs plain Claude Code (plan 018) — the headline comparison
`.venv/bin/python -m eval.cc_ab` runs headless Claude Code (`--bare`, Sonnet 5.5, empty temp dir) twice per question:
with only our MCP server (pinned to the dataset), and with nothing but Bash / Read / Grep / Glob over the dataset's raw
log files (BGL's inline ground-truth label column cut, OpenStack files renamed, label files left out). Same 50 keys,
same blind both-orders Opus judge as `eval/ab.py`. Result `eval/results/cc-20261018-205503.md`:

| | Claude Code + our MCP | plain Claude Code (raw files, Bash/grep) |
|---|---|---|
| blind judge wins (order-consistent) | **30** | 15 (tie 1, inconsistent 4) |
| wins, base corpus (BGL + OpenStack) | **18** | 4 |
| wins by role: engineer / lead / manager | 8 / **13** / **9** | **9** / 2 / 4 |
| claim accuracy (judge + SQL) | **0.87** | 0.80 |
| wrong claims (50 answers) | **116** | 186 |
| found the real problem (0-2) | **1.51** | 1.22 |
| rubric (1-5) | **3.50** | 3.23 |
| E1 golden facts in the answer | **0.64** | 0.46 |
| seconds per answer, median / mean / max | **14.6 / 14.3 / 27** | 33.4 / 86.0 / 1500 (timeout) |
| seconds, large datasets (BGL 4.7M, HDFS 11M lines; 21 q) median / mean | **13.8 / 14.0** | 77.7 / 168.1 |
| failed runs | 0 | 1 (D-X17, HDFS, 25 min timeout) |
| tool errors | 2 | 14 |
| $ per answer (Claude Code's own count) | 0.049 | 0.038 |

