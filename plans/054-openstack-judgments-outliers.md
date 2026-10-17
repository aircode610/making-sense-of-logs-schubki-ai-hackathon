# 054: OpenStack Jev judgments + slow-operation outliers (MCP tool)

- **Status:** done (2026-10-17)
- **Owner:** Konark · **Branch:** `feat/054-openstack-judgments-outliers` · **Date:** 2026-10-17
- **PLAN.md block / slice:** B3 · engineer slice (baseline step: "is this value normal for this pattern?")

## 1. Goal
Make OpenStack problems visible to the agent: (a) Jev judgments for the 106 OpenStack patterns, so `top_patterns` /
`priority_table(dataset='openstack')` stop returning 0 rows; (b) a `value_outliers` MCP tool that flags operations
far slower than their own pattern's normal (plan 053: the labelled VMs differ only by spawn/build time). Moves search +
analytics (25 %) and role insight (30 %), engineer + lead roles, and is a novelty point (value anomalies inside normal templates).

## 2. Done when (decided before starting)
- `data/pattern_judgments_openstack.csv` committed, 106 rows; `top_patterns(dataset='openstack')` (default Jev filter)
  returns the image-cache traceback / `InvalidDiskInfo`, token-validation CRITICAL and 503 patterns, and no routine
  lifecycle patterns (list reported; cost + time reported).
- `value_outliers(dataset, pattern_id?, start?, end?)` returns, per pattern with a duration (`Took <N> seconds`) or
  `latency_ms`, the baseline (n, median, p95, MAD), threshold and the flagged lines (with instance/request ids), plus
  the usual envelope (sql, scope, total_matches, truncated). Rule fixed **before** looking at labels:
  flag `value > median + 6 × MAD` (robust, per pattern), at least 2 s / 2× median.
- Check vs labels (check only): of the 4 labelled VMs, how many are flagged on spawn/build; how many other instances
  are flagged (report precision / recall at instance level, no tuning on it).
- Numbers in the result match an independent SQL query (added to `bench/check_patterns.py` or `check_counts.py`);
  p95 < 200 ms; `./load/reload.sh` passes.
- One agent run (`python -m agent.run --role engineer "…slow VM spawns in OpenStack?"`) uses the tool and cites it.

## 3. Approach
- (a) `scripts/judge_patterns.sh openstack` (exists; same questions as BGL, generic criteria). `96_…sql` already loads
  `pattern_judgments_*.csv`. No change to the questions unless a routine pattern lands as a problem (then stop + re-plan).
- (b) `mcp_server/outliers.py`, registered in `server.py`, reusing `core.envelope`. Value = `regexp_extract(body,
  'Took ([\d.]+) seconds')` or `latency_ms`, one CTE per pattern: `median`, `quantile_cont(.95)`, MAD; flagged lines
  sorted by value / median. Computed at query time (≤ 70k lines per pattern, no new table unless p95 says so).
- Agent: one line in the engineer recipe (`agent/prompts.py`) naming `value_outliers` for "slow / took long / latency"
  questions. Tell Amirali (his file).

## 4. How we check it
Independent SQL for baseline + flagged counts; label check on the full OpenStack corpus (no OpenStack held-out split,
DECISIONS H13 is BGL only); timings in `PERFORMANCE.md`; one LangSmith trace.

## 5. Out of scope / risks
- Out: grouping traceback lines into one fault (lead tools, Amirali), per-instance episodes, BGL value outliers.
- Risk: Jev marks routine OpenStack WARNINGs (`Unknown base file`) as faults → report, no prompt tuning in this plan.
- Risk: MAD ≈ 0 on very regular patterns → floor (2 s / 2× median) prevents flagging noise.

## 6. Steps
- [x] Branch; judge OpenStack patterns; reload; `top_patterns` / `priority_table` openstack check
- [x] `outliers.py` + register + independent check; label check; timings
- [x] Engineer recipe line; one agent run
- [x] §7, PERFORMANCE, STATUS, QA_JURY, plans index; tell Amirali

## 7. Results (filled after)
Done 2026-10-17.

| Check | Result |
|---|---|
| Jev judgments OpenStack | 106 / 106 in **3.2 s** (`data/pattern_judgments_openstack.csv`); every routine lifecycle pattern `p_problem` < 0.1 |
| `top_patterns(dataset='openstack')` (default Jev filter) | 0 → **8** patterns: `InvalidDiskInfo` image-cache fault (6 of its traceback lines), token validation ERROR + CRITICAL; no routine patterns |
| `value_outliers(openstack)` | 16 flagged lines, **6 VMs**; 12 lines = spawn + build of those VMs, 4 = HTTP calls > 2 s on 2017-05-17 06:25 |
| Label check (instance level, rule fixed before) | **recall 4/4**, precision 4/6; the 4 labelled VMs are the 4 highest ratios (2.57, 2.12, 1.58, 1.49); unlabelled ones at 1.35 and 1.14 |
| Independent check (Python regex + `statistics`, `check_counts.py`) | flagged lines, VM count and VM set equal |
| Latency | median 91 ms, p95 99 ms (20 calls); BGL returns 0 (no durations) |
| `./load/reload.sh` | 43/43 checks (34 counts + 9 patterns), also after the 5xx amendment |
| Agent (`--role engineer`, "Were any OpenStack VMs abnormally slow to start?") | used `value_outliers` → `search_logs` → `get_context`; names all 6 VMs with ratios, timeline of the slowest, checker 55/55 ([trace](https://eu.smith.langchain.com/o/4f105c8d-96ef-4fa2-84a1-2cb5426fa80c/projects/p/4c514ef8-76e3-4720-bf07-3ca5723c9170/trace/4a37e556-5fad-4e3c-aec5-6246f5400386/run/4a37e556-5fad-4e3c-aec5-6246f5400386)) |

- **Threshold wording:** "at least 2 s / 2× median" (§2) was ambiguous; implemented as max(median + 6·MAD,
  median + 2 s), parameters `k` / `min_excess_s`. For transparency: a "≥ 2× median" floor would catch only 2/4
  labelled VMs (0 false). Not tuned further on labels.
- **Amendment (approved by Konark):** the severity gate (H18) dropped the HTTP 503 (Jev 0.57), because nova logs
  failed requests at INFO. A **problem line is now problem severity OR HTTP status ≥ 500** (`PROBLEM_LINE` in
  `mcp_server/patterns.py`, `problem_lines` in `95_patterns_episodes.sql`). Exactly 2 lines in the corpus match (both
  503s); BGL has no status, so all BGL numbers are unchanged (`check_patterns.py` passes). `top_patterns(openstack)`
  8 → 9. The vCPU-count WARNING (Jev 0.73) stays out: changing the gate for warnings would need re-measuring BGL.
- **Deviation (same step, noted):** the agent gives each role a tool whitelist (`ROLE_TOOLS` in `agent/graph.py`), so
  `value_outliers` was added there as well as to the engineer recipe in `agent/prompts.py`.
- **Fix found by the agent run:** the composer shows only 12 rows per result (`ledger_json`), and the 4 HTTP rows came
  first, so the first run reported "only 4 of 6 VMs visible". Added an `instances` field (one row per flagged VM); the
  re-run names all 6. **Then (asked by Konark):** `ledger_json` (`agent/checker.py`) by default passes every tool result in
  full (tools already cap rows at 50; the eval judge keeps its `max_rows=8`). Re-run on 4 questions, all checker-passed: slow VMs 57/57 (says "not truncated"),
  R43-M0 kernel panics 27/27 (43 s), lead Nov 2005 92/92 (28 s), manager Nov 2005 37/37 (36 s).
- **Experiment, reverted (asked by Konark): drop the severity gate, Jev only** (`_problem_where` in
  `mcp_server/patterns.py`: `jev` → only `p_fault × (1 − p_dump) ≥ 0.5`). Measured with Amirali's scripts (BGL tune
  period, labels as a check only):

  | | with severity gate (kept) | Jev only (reverted) |
  |---|---|---|
  | `top_patterns(openstack)` | 9 | 10 (+ vCPU-count WARNING, Jev 0.73) |
  | BGL top 10 by bursts with alerts (`eval_top10.py`) | **5/10** | 3/10 |
  | BGL priority / by nodes / by lines top 10 | 5 / 4 / 6 | 5 / 4 / 6 |
  | BGL tune patterns flagged · precision · burst-precision (`eval_problem_filter.py`) | 506 · 0.14 · **0.39** | 621 · 0.12 · 0.32 |
  | Nov 2005 candidates / `check_patterns.py` | 125 / passes | 178 / fails (reference = H18) |

  Why: BGL severities are honest, so the gate removes harmless patterns Jev over-scores; OpenStack logs failed
  requests at INFO. To revisit: drop the gate **for OpenStack only** (BGL untouched) to also get the vCPU warning;
  re-run `bench/eval_top10.py`, `bench/eval_problem_filter.py`, `bench/check_patterns.py`.
- Follow-ups: traceback grouping in `top_patterns` (25 → 1 fault), per-instance episodes, severity gate for
  INFO-level HTTP 5xx.
