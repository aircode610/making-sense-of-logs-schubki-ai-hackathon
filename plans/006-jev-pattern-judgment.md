# 006: Jev judges each pattern "real fault or routine output?" (inside SereneDB)

- **Status:** done (2026-10-17)
- **Owner:** Amirali · **Branch:** `feat/006-jev-pattern-judgment` · **Date:** 2026-10-17
- **PLAN.md block / slice:** B3 · Jev pattern judgments in SQL (the novelty step; `NOVELTY.md`, `ROLES.md` "problem pattern")

## 1. Goal
Replace "problem = FATAL/ERROR severity" with a calibrated Jev probability per **pattern** (1,126 BGL templates, judged
once, ~cents), so `top_patterns` / `priority_table` stop ranking routine register dumps first. Measured against the
plan 005 baseline on the same table. Role insight (30%), recommendation quality (25%), novelty (20%).

## 2. Done when (decided before starting)
- Every BGL pattern has `p_fault` (+ `p_dump`, `p_corrected`, `kind`) from `ai_system_one`, stored in
  `pattern_judgments`; run time, requests and cost recorded (`PERFORMANCE.md`).
- **Re-measured, tune period 2005-11-01 → 11-29, labels as a check only:** alert-carrying patterns in the top 10 of
  `priority_table` (baseline 1/10), `top_patterns` by bursts (0/10) and by lines (6/10); plus pattern-level
  precision / recall of `p_fault ≥ 0.5` vs severity-only against "pattern carries alerts" (tune part). Reported as
  measured, also if it does not beat the baseline.
- Tools: `problem_filter = 'jev' | 'severity'` on both (default `jev`, `severity` kept as the visible baseline);
  `p_fault` returned per row; priority `severity` input = `p_fault`. `bench/check_patterns.py` still reproduces every
  score independently.
- **Clean checkout needs no TypeSafe key:** judgments are committed as `data/pattern_judgments_bgl.csv` and loaded by
  `reload.sh`; `scripts/judge_patterns.sh` regenerates them (needs the key).

## 3. Approach
- **One request per pattern, 4 questions fanned out** (`docs/jev/NOTES.md`: snap judgments, minimal state, literal
  criteria, semantic text). State = component, severity, template, one real example line. Questions:
  `fault` (Noul: does it report that hardware or software failed / lost function / an operation was aborted, vs routine
  status, counters, configuration, informational notes), `dump` (Noul: one line of a multi-line register/status dump),
  `corrected` (Noul: says the error was corrected / recovered automatically), `kind` (Choice: hardware, kernel/software,
  network/IO, job/application, not a problem). Criteria written as JSON with covers / does-not-cover examples taken
  from generic log semantics, not from label categories.
- **Run in SereneDB:** `SELECT ai_system_one(state, questions := {...}, batch_size := 1)` over `patterns`, exported with
  `\copy` to the CSV (keyed by dataset + component + template, so it survives pattern-id renumbering).
  `load/96_pattern_judgments.sql` loads it; `95` stays as is.
- **Rule in code (not fitted):** problem = `p_fault ≥ 0.5`. The other answers are shown for explanation; combining
  them (e.g. `p_fault × (1 − p_dump)`) is tried once on the tune part and kept only if it wins there; frozen in DECISIONS.
- Wording iterations: at most 2, judged on the tune part only; held-out slice never inspected.

## 4. How we check it
Label-share table + precision/recall on the tune part (script in `bench/`), `check_patterns.py` re-run, one MCP call.
Held-out: `run_heldout.py` later scores E6 on the slice; nothing here looks at it.

## 5. Out of scope / risks
- Out: OpenStack judgments (after Konark's masks; same script), LLM comparison (E6 eval plan), agent.
- Risk (LESSONS.md): Jev reads errors literally → may call corrected/routine "errors" faults. Mitigation: explicit
  criteria for corrected/routine + the separate `corrected` / `dump` questions.
- Risk: API limits / `sdb_ai_max_api_calls_per_query` → raise for this one query; 1,126 requests.
- Risk: if Jev does not beat severity, we say so and keep `severity` as default (honest reporting, EVAL.md).

## 6. Steps
- [x] Branch; question set; dry run on 20 patterns (eyeball)
- [x] Full run → CSV; `96_pattern_judgments.sql`; reload wiring; `judge_patterns.sh`
- [x] Tools: `problem_filter`, `p_fault`; check script
- [x] Measurement table (tune part); freeze rule (DECISIONS); PERFORMANCE, README, §7, STATUS, QA_JURY; push branch

## 7. Results (filled after)
Done 2026-10-17.

**Headline (tune period 2005-11-01 → 11-29, labels as a check only, `bench/eval_top10.py`):**

| Top 10 | severity filter (plan 005) | Jev filter (H18) |
|---|---|---|
| `priority_table` score | 1/10 | **5/10** |
| `top_patterns` by bursts | 0/10 | **5/10** |
| by nodes | 4/10 | 4/10 |
| by lines | 6/10 | 6/10 |

Pattern level, tune part (`bench/eval_problem_filter.py`; 1,058 patterns, 76 carry alerts):

| Rule | flagged | precision | recall | F1 | alert share of flagged bursts |
|---|---|---|---|---|---|
| severity | 701 | 0.11 | 1.00 | 0.20 | 0.08 |
| Jev p_fault ≥ 0.5 | 726 | 0.10 | 0.97 | 0.18 | 0.11 |
| Jev p_fault × (1 − p_dump) ≥ 0.5 | 621 | 0.12 | 0.95 | 0.21 | 0.32 |
| **severity AND p_fault × (1 − p_dump) ≥ 0.5** (chosen) | 506 | 0.14 | 0.95 | 0.25 | **0.39** |

- Jev on `fault` alone ≈ severity (reads "error" literally, as LESSONS.md predicted); the `dump` question is what
  helps. Pattern precision stays low because BGL labels mark 41 admin-chosen categories: many unlabelled patterns do
  describe real faults ("uncorrectable error detected in EDRAM bank", "NodeCard is not fully functional").
- **Integrity:** first draft criteria contained BGL text (picked after seeing plan 005 output) → replaced with generic
  examples before the full run. **1 of 2 wording iterations used:** `dump` criteria describe the `name.....value`
  field format generically (alert share of flagged bursts 0.28 → 0.39 for the chosen rule). Held-out slice not looked at.
- Cost/time: 1,126 patterns in 20 s, ≈ $0.02; stored in `data/pattern_judgments_bgl.csv` (committed), loaded by
  `load/96_pattern_judgments.sql`; `reload.sh` needs no key.
- `bench/check_patterns.py` reproduces all Jev-mode scores independently (judgments read from the stored table, rule
  applied in Python; SQL-style rounding for ties). 9/9 ok, p95 47 ms.
- Remaining noise: `…exception…<N>` flag fields (ranks 7–10 in Nov). Next lever: collapse patterns that always
  co-occur (one dump = one item), or one more `dump` wording iteration.
- **Seen during the final reload (Konark's plan 052 area):** one run of `check_counts.py` got FATAL since 2005-12-05 =
  38,421 (want 38,420) right after the reload; repeated queries 5× = 38,420 and the next full reload passed. Transient
  index state after publish/compaction → suggest `90_publish.sql` / `reload.sh` wait until two consecutive counts agree.
