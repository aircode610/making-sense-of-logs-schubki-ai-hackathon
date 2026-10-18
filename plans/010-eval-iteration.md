# 010: Eval fit for iteration (version vs version, noise known, judge fixed)

- **Status:** done (2026-10-18)
- **Owner:** Amirali · **Branch:** `feat/010-eval-iteration` · **Date:** 2026-10-18
- **PLAN.md block / slice:** B4 · trust + perf (eval)

## 1. Goal
Make `eval.run_eval` the loop Amirali iterates against (new tools, prompts, faster DB backends): a change is kept only
if the eval says it helps beyond noise, with no regression on any question. Today the eval only answers "ours vs
baseline, once"; it can't tell "prompt v2 vs v1" apart from run-to-run noise.

## 2. Done when (decided before starting)
- **Judge sees what the composer saw:** `judge.claim_support` gets the full ledger (no `max_rows=8`). Re-judging the
  stored 20261017-174933 runs: E2c for ours goes up, and the "only N of M shown" class of unsupported claims is gone.
- **Failures count:** a run that errors or returns no card scores 0 (not dropped); `error_rate` per system in the table.
- **Version vs version:** `--compare <results.json>` prints per-metric delta and a per-question list of regressions
  (E1, E2a, E2c or rubric down), and the pairwise judge runs new-ours vs old-ours (both orders) instead of only vs baseline.
- **Baseline reused:** `--systems ours --reuse-baseline <results.json>` skips re-running the baseline (it doesn't change
  when we change our pipeline). A cheap tier `--no-judge` stays under ~5 min for the dev set.
- **Noise measured:** `--repeat 3` runs each question k times; table shows mean ± spread; recorded once in
  `docs/EVAL.md` as "a change smaller than X on metric Y is noise".
- **Stronger golden facts:** every manager question checks the **ranking** (top 3 = `priority_table` order, E6), not just
  one count; D-M05 gets a deterministic check; each question has ≥ 2 golden facts (now 7 of 20 have ≤ 1, 5 of them manager questions).
- **Tool-level bench for DB alternatives:** `bench/replay_tools.py` replays every tool call recorded in a results file
  against the running backend and reports identical-result rate + per-tool p50/p95. A new backend must score 100 %
  identical before an end-to-end run is worth paying for.
- **Per-stage latency:** E8 split into tool time vs LLM time (from the graph's tool messages), so "faster DB" and
  "fewer LLM turns" show up separately.

## 3. Approach
- `eval/judge.py`: full ledger to the claim judge. `eval/run_eval.py`: error rows scored 0, `--compare`, `--reuse-baseline`,
  `--repeat`, tool vs LLM seconds. `eval/judge.py` pairwise reused for version vs version (labels A/B, never names).
- `eval/dev_questions.yaml`: add golden facts (manager top-3 order from `priority_table` SQL; D-M05 must_mention already
  covers unknowns → add `must_not` + a check that no number appears outside the ledger). `build_golden.py` refills.
- `bench/replay_tools.py`: read `per_run[*].ledger` (query + params + result) → call the same MCP tool → diff.
- No change to the agent, the tools or the data.

## 4. How we check it
Re-judge stored runs (step 1) and compare numbers before/after; one `--repeat 3` dev run of ours (the noise figure);
`--compare` against 20261017-174933 on an unchanged agent → no "regressions" beyond the noise figure (sanity);
`replay_tools.py` on the current backend → 100 % identical. Held-out untouched; `run_heldout.py` keeps working
(aggregates only) since it calls `run_suite`.

## 5. Out of scope / risks
- Out: writing the private question set (humans), changing the agent or prompts (that is what this enables), UI.
- Risk: overfitting the 20 dev questions while tuning → the private set is the real test; humans should write it
  **before** heavy tuning. Dev set is ours (written after seeing data), so treat dev wins as hints.
- Risk: `--repeat 3` with judge ≈ 3× cost (Opus judge); run it once for the noise figure, then use 1× + `--compare`.
- Risk: replay is exact-match; a backend with different tie order needs a tie-insensitive diff (sort rows) for counts/tops.

## 6. Steps
- [ ] Judge full ledger + re-judge stored runs (before/after numbers)
- [ ] Errors scored 0 + error_rate
- [ ] `--reuse-baseline`, `--compare`, version-vs-version pairwise
- [ ] `--repeat` + noise figure in `EVAL.md`
- [ ] Golden facts: manager ranking (E6), ≥ 2 facts per question; `build_golden.py`
- [ ] Tool vs LLM seconds; `bench/replay_tools.py`
- [ ] §7, STATUS, EVAL.md "how to iterate" (3 commands)

## 7. Results (filled after)
- **Judge fix** (full ledger, `--rejudge` of the plan-009 answers → `20261018-023346`): claims supported ours
  0.89 → **0.92**, baseline 0.59 → **0.71**: the "only N rows shown" false negatives are gone and the gap is smaller
  than we quoted (+0.21, not +0.30). Baseline causes stated as fact: 0.39 per answer (ours 0). Pairwise unchanged 10-4.
- **Failures** score 0 (`failed_run`), `runs failed` row; offline test with an injected failure lowers the means.
- **`--reuse-baseline`, `--compare`, `--rejudge`, `--repeat`** work; `--compare` re-scores the old answers with the
  current golden facts. Every run writes `<stamp>.runs.json`; older results are fetched from LangSmith.
- **Noise** (`--repeat 3`, `20261018-025819`): E1 0.05, E2c 0.01, rubric 0.06, role fit 0.2, seconds ±5, input
  tokens ±8k (table in `docs/EVAL.md`). Same run vs the re-judged reference (older agent, stale DB): pairwise new vs old
  **12-4** (2 inconsistent), one per-question regression (D-M03 E1 1.0 → 0.56, a 3-rep mean).
- **Golden facts:** 4 manager questions check the computed `priority_table` order (E6; `build_golden.py` re-runs the
  tool and stops if the ranking changed), 19/20 questions have ≥ 2 facts (D-M05 has must_mention + must_not), D-L06's
  fact replaced (machine check did not get worse: 38 → 34; the top grower is `Kill job … timed out` 29 → 44).
  `must_not` was never checked before; it is now an E5 row.
- **Tool time split:** tools take **0.3 s of ~34 s** per answer (≈ 1 %); the rest is LLM turns.
- **Replay bench** (`bench/replay_tools.py`): caught a stale local DB (OpenStack `pattern_id` NULL, 76 % match);
  after `reload.sh` 75/75 calls match (one tie-order difference in `value_outliers.baselines`, sorted rows equal).
- Follow-ups: per-question noise is larger than the mean noise (thresholds in `REGRESSION` are a first guess);
  `value_outliers` could add a tie-breaker to its baseline order.
