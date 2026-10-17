# 009: Eval harness: ours vs baseline, deterministic metrics + LLM judge, LangSmith experiments

- **Status:** done (2026-10-17); human judge check pending (Amirali / Konark)
- **Owner:** Amirali · **Branch:** `feat/009-eval` · **Date:** 2026-10-17
- **PLAN.md block / slice:** B4 · eval (`docs/EVAL.md` E1–E8) + held-out runner (`docs/HELDOUT.md` step 1)

## 1. Goal
Prove with numbers, on a question set and not one question, that our agent's answers are (a) **grounded** in the queries
and evidence that ran, (b) **correct** against hand-checked SQL, and (c) **better answers** for each role than the
brief's reference design (baseline ReAct, same tools). Every metric runs for both. Moves all rubric lines; it is our
evidence for "novelty" and the slides.

## 2. Done when
- `eval/dev_questions.yaml`: **18 dev questions** (6 per role; BGL tune part `< 2005-12-05` + OpenStack), same format as
  `HELDOUT_BRIEF.md`, each with golden facts (value + the SQL that produced it, written by me and run once), required /
  expected-first tools, and 2 **topic triples** (one topic asked as engineer, lead, manager) for role distinctness.
- `eval/run_eval.py`: runs ours + baseline on every question as **LangSmith experiments** (dataset `logs-dev`,
  experiments `ours-<sha>`, `baseline-<sha>`, comparable in the UI) and writes `eval/results/<date>.md` + JSON.
- The metric table below is filled for both systems, with per-role breakdown; results in `STATUS.md`, `EVAL.md`.
- The held-out runner (`eval/` script named in `HELDOUT.md`) runs the same metrics on the human-written held-out file and
  prints aggregates only (tested against the dev file; never run on held-out by Claude).

## 3. Metrics (deterministic first; the judge only where code cannot decide)
| ID | Metric | How | Kind |
|---|---|---|---|
| E1 | **Answer correctness** | share of golden facts whose value appears in the answer (number match with the checker's rules) | deterministic |
| E2a | **Number groundedness (ledger)** | share of numbers in the answer found in *any* tool result of that run (same rule for both systems) | deterministic |
| E2b | **Citation groundedness** | ours only: share of numbers found in the result the fact *cites* (the checker) | deterministic |
| E2c | **Claim support** | judge: each sentence of the answer → supported / not supported / not a factual claim, given the evidence ledger (SQL + results); score = supported / factual | LLM judge |
| E3 | **Fact vs hypothesis** | judge: causes stated as fact (count); deterministic: answer has separate facts / hypotheses / unknowns | judge + deterministic |
| E4 | **Role distinctness** | topic triples: Jaccard overlap of tools called and of evidence ids between roles (lower = more distinct); per-role checklist pass (ROLES.md) | deterministic |
| E5 | **Forbidden claims** | money / downtime / customer-impact regex outside "unknowns" (+ judge double-check on manager answers) | deterministic + judge |
| E6 | Finds the real problems | already measured in plans 005–006 (top-10 alert share); cited, not re-run | — |
| E7 | **Tool selection** | required tools called; expected first tool | deterministic |
| E8 | **Cost / latency** | wall time, LLM input/output tokens (usage metadata), tool calls, $ | deterministic |
| Q | **Answer quality** | judge rubric per role, 1–5 with written reasons: role fit, specificity of next step, evidence use, clarity; plus **pairwise preference** ours vs baseline, asked in both orders (position-bias check: only consistent wins count) | LLM judge |

**Judge design:** a different, stronger model than the agent (`claude-opus-5-5` vs Sonnet), structured output, sees the
question, role, the role's rubric (ROLES.md acceptance) and the evidence ledger (SQL + results); never sees which system
wrote the answer; both answers rendered to the same plain Markdown (our confidence line removed). Every judgment is a
LangSmith feedback with its reasoning. **Judge sanity:** Amirali/Konark rate 6 answers by hand; agreement with the
judge reported (if low, the judge numbers are reported as indicative only).

## 4. How we check it
The harness itself: golden SQL run once and stored; one dry run on 3 questions; numbers spot-checked by hand.
Held-out untouched (only the runner, by the humans).

## 5. Out of scope / risks
- Out: held-out questions (humans), UI, prompt tuning on the eval (results are reported; any later change re-runs all).
- Risk: dev questions written by me after seeing the data → only used as dev; the held-out set is the honest test.
- Risk: judge bias (length, style) → same rendering, both orders, consistent wins only, human sanity check.
- Cost: 18 × (ours + baseline + judge) ≈ 18 × ~$0.5 → ≈ $10 per full run; run sparingly.

## 6. Steps
- [x] dev questions + golden SQL (run once, values stored)
- [x] `eval/metrics.py` (deterministic), `eval/judge.py` (rubric + claim support + pairwise), `eval/run_eval.py` (LangSmith experiments)
- [x] dry run (3 questions) → full run → results table; held-out runner on the dev file
- [x] EVAL.md, STATUS, README results, QA_JURY; push branch

## 7. Results (filled after)
Done 2026-10-17. Full run `eval/results/20261017-174933.md` (LangSmith dataset `logs-dev-473337f9`, experiments
`ours-151ec54-e4328711` vs `baseline-151ec54-2230bd25`, judge `claude-opus-5-5`):

| Metric (18 dev questions, 6 per role) | ours | baseline |
|---|---|---|
| E1 golden facts in the answer | **0.79** | 0.59 |
| E2a numbers found in the run's own tool results | **0.99** | 0.85 |
| E2b numbers found in the result the fact cites (ours) | **1.00** | — |
| E2c claims supported by the evidence (judge) | **0.89** | 0.59 |
| E3 causes stated as fact, per answer (judge) ↓ | **0.11** | 0.39 |
| E3 states what the logs cannot establish | **1.00** | 0.11 |
| E5 invented money / downtime / impact (regex + judge) | 0 | 0 |
| E7 required tools called | **1.00** | 0.83 |
| Q rubric mean 1-5 (judge) | **4.53** | 3.91 |
| Q role fit 1-5 (judge) | **4.83** | 4.17 |
| Q next-step specificity 1-5 (judge) | **4.28** | 2.56 |
| Q pairwise, both orders, consistent wins | **10** | 4 (4 inconsistent) |
| E4 evidence overlap between roles on the same topic ↓ | **0.02** | 0.04 |
| E4 tool overlap between roles on the same topic ↓ | 0.39 | **0.28** |
| E8 seconds per answer ↓ | 34 | **13** |
| E8 input / output tokens ↓ | 54k / 4.8k | **33k / 1.6k** |

Reading it honestly:
- **Grounding is where ours wins most:** the baseline (same tools!) writes rounded / derived numbers ("about 10,400",
  "73%", "~36,000") and states causes as facts; ours copies values and labels hypotheses. Judge claim support 0.89 vs 0.59.
- **Cost:** ours is ~2.6× slower and uses ~1.6× input / ~3× output tokens (recipe + composer + one revision round).
- **E4 is mixed:** ours' evidence overlaps less across roles (0.02 vs 0.04), but its tool sets overlap more (0.39 vs
  0.28): the recipes make every role also fetch whole-corpus counts. Reported as is.
- **E1 golden misses shared by both systems** (D-E06, D-L02, D-M06, D-L05 KERNEL): golden facts were too narrow
  (exact template vs keyword search; a FATAL count the question does not ask for). Question-design issue, kept as is
  for comparability; fix in the next dev-set revision, not by tuning the agent.
- **Checker gap found:** 9 of ours' numbers are unverified by E2a (D-E03, D-L02, D-L06, D-M01) although the in-agent
  checker passed: they sit in `scope` / `hypotheses` / `unknowns`, which the checker does not cover, and some are the
  "12 of 15 shown" display notes the compose prompt sees. Next fix: checker covers every card section.
- Judge: Opus, structured, reasons stored as LangSmith feedback; 4 of 18 pairwise verdicts flipped with the order and
  are counted as inconsistent. **Human sanity check pending:** `eval/results/human_check.md` (6 blind answers) +
  `human_check_key.md` (judge scores) for Amirali / Konark.
- The private question set's runner was self-tested on the dev file: prints aggregates only; per-question output goes
  to its gitignored folder.
- Fixes during build: years / day-of-month in prose were counted as unverified numbers (checker, both systems);
  LangSmith feedback scores are capped at 1e5 (tokens logged in thousands); MCP server log level WARNING.
