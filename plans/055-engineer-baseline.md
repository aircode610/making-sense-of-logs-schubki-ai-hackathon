# 055: B3 leftovers: engineer rate baseline, dev questions, swap review

- **Status:** done (2026-10-17)
- **Owner:** Konark · **Branch:** `feat/055-engineer-baseline` · **Date:** 2026-10-17
- **PLAN.md block / slice:** B3 · engineer slice (recipe step 5 "baseline") + "swap and review"

## 1. Goal
Finish the engineer slice: the agent says whether an error's **rate is unusual** for that node / component ("14 lines
in the last hour vs about 2/h over the previous 7 days", `ROLES.md` engineer recipe step 5), the dev eval covers the
engineer tools added since plan 009, and each of us reviews the other's role answers. Moves role insight (30 %) and
search + analytics (25 %).

## 2. Done when (decided before starting)
- MCP tool `rate_vs_baseline` (in `mcp_server/counts.py`): same filters as `count_by` (text, pattern_id, node,
  component, severity, status…) for a window [start, end) vs the previous `days` (default 7) → lines + rate/h in the
  window, lines + rate/h in the baseline, ratio (or "0 in baseline → new"), baseline hours with ≥ the window's rate
  (share), max hourly baseline rate; usual envelope. Numbers equal independent SQL (`check_counts.py`); p95 < 200 ms.
- Engineer recipe step "Baseline" + `ROLE_TOOLS["engineer"]` include it; one agent run on a BGL incident cites it.
- `eval/dev_questions.yaml` +2 engineer questions with golden SQL: slow VM spawns (`value_outliers`) and "is this rate
  unusual?" (`rate_vs_baseline`); `eval/build_golden.py` fills values; engineer subset of `eval.run_eval`
  (ours + baseline) run and reported next to plan 009's numbers.
- `docs/REVIEW.md`: one checklist per reviewer (Konark → lead/manager answers, Amirali → engineer answers) built from
  `ROLES.md` "Answer content / Must not", plus the run files to read. The review itself is done by humans.

## 3. Approach
- `rate_vs_baseline`: two counts over `logs` with the shared `_where` (index-friendly: same filters, two time ranges)
  + hourly buckets of the baseline for the "share of hours ≥ now" and max. Rates are lines per hour (lines ≠
  incidents, stated in scope). No new table.
- Agent: one recipe line + tool name in `ROLE_TOOLS` (Amirali's files, small additions, tell him).
- Dev questions: BGL question from the tune part (< 2005-12-05) only; written after looking at the data, so dev only.

## 4. How we check it
Independent SQL for every tool number; `./load/reload.sh` checks; eval on the engineer subset; held-out untouched.

## 5. Out of scope / risks
- Out: significant terms (recipe step 6), UI, clean-checkout test (plan 056), checker changes.
- Risk: very bursty logs make "rate/h" misleading → also return the share of baseline hours ≥ now (robust to bursts).

## 6. Steps
- [x] Branch; `rate_vs_baseline` + register + independent checks + timing
- [x] Recipe + ROLE_TOOLS; one agent run
- [x] +2 dev questions, build golden, engineer eval subset (ours vs baseline)
- [x] `docs/REVIEW.md`; §7, STATUS, PERFORMANCE, QA_JURY, README tool table, plans index

## 7. Results (filled after)
Done 2026-10-17.

**`rate_vs_baseline`** (`mcp_server/counts.py`): window vs earlier windows **of the same length** (1 h → hourly,
1 day → daily), baseline **clipped to the dataset's first line** (`baseline_clipped`, `no_baseline_data`). Both were
fixed after a first version (divided by 7 × 24 h even before the data started: 4,300× one day after BGL starts, now
204.8× over the 8 h that exist; compared a 1-day window with single hours: "20 of 168 hours as busy", now "all 7
previous days had ≥ 1 line"). 6 independent Python recomputations in `check_counts.py` (1 h / 1 day / 5 min windows,
OpenStack clip, no data, new). Latency median 4–6 ms, p95 8–9 ms (> 17k calls).

| Live agent run (engineer) | Answer | checker |
|---|---|---|
| R43-M0 kernel panic | new: nothing in the previous 30 days | 26/26 |
| OpenStack 503 2017-05-16 06:00 | new "by the little data available", baseline only 34 h | 30/30 |
| BGL machine check, whole day 2005-10-10 | **No**: 1 line vs 21 in the 7 days before, every day had some | 35/35 |
| BGL FATAL 2005-06-04 00:00 | 204.8×, baseline only 8 h (data starts 2005-06-03) | 53/53 |

**Does "unusual" point at real trouble?** (`bench/eval_rate_baseline.py`, BGL tune part 2005-06-10 → 12-05, 4,272
hours, labels as a check only; rule fixed before: new, or ratio ≥ 3 and ≤ 5 % of baseline windows as busy; compared
with flagging the same number of busiest hours)

| Truth | base rate | "unusual" precision / recall | busiest hours precision / recall |
|---|---|---|---|
| any alert in the hour, all lines | 0.19 | **0.31** / 0.11 | 0.26 / 0.09 |
| any alert in the hour, FATAL lines | 0.66 | 0.65 / 0.23 | **0.73** / 0.25 |
| alert onset (category quiet ≥ 7 days), all lines | 0.04 | **0.06** / 0.13 | 0.05 / 0.10 |
| alert onset, FATAL lines | 0.12 | **0.17 / 0.34** | 0.14 / 0.27 |

→ Better than raw volume for **onsets**, no help for **chronic** alerts (BGL's biggest categories recur all the time).
It answers "unusual vs recent history?", not "is it broken?": we do **not** pitch it as an anomaly detector. OpenStack
(no hourly labels): flags the first image-cache ERROR hour (new) + 2 jumps (42×, 22×), both 503 hours, and the
05-16 traffic jump (~1k → 8k lines/h, workload, not a fault); the 4 slow VMs are not rate anomalies (`value_outliers`
catches them). Idea, not done: "unusual AND Jev p_problem ≥ 0.5".

**Engineer eval** (`eval/results/20261017-184655.md`, 8 questions incl. new D-E07 slow VMs + D-E08 rate, ours vs
baseline, Opus judge): golden facts 0.875 vs 0.542 · numbers grounded 0.995 vs 0.811 · claims supported 0.878 vs
0.469 · unknowns stated 1.0 vs 0.125 · required tools 1.0 vs 0.75 · rubric 4.75 vs 3.88 · next-step specificity
4.75 vs 2.25 · **pairwise 8-0**. D-E07: ours 1.0 golden (names a445709b, 50.72 vs 19.74 s), baseline 0.0. vs plan 009
engineer (same 6 old questions: golden 0.833 both runs): claims 0.842 → 0.878, rubric 4.6 → 4.75; **cost: 41 → 47 s
and 67k → 98k input tokens per answer** (full tool results to the composer + one more tool call). D-E06 still misses
its golden fact (both systems).

- Agent: `rate_vs_baseline` in `ROLE_TOOLS["engineer"]`, recipe step 4 "Baseline", engineer card mentions "rate vs
  the usual rate" (Amirali's files, additions only).
- `docs/REVIEW.md`: swap-review checklists (Konark → lead / manager, Amirali → engineer) + findings table. Review
  itself: humans.
