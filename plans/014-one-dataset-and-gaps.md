# 014: One dataset per session + fix the 8 gaps from the plan-013 A/B

- **Status:** done (Amirali, 2026-10-18: "address each of the 8 problems … change the structure")
- **Owner:** Amirali · **Branch:** `feat/014-one-dataset` (on top of `feat/013-blind-ab`) · **Date:** 2026-10-18
- **PLAN.md block / slice:** MCP + agent + eval

## 1. Goal
Match real use: a user adds our MCP to Claude Code over **their own logs = one dataset** (stored in our schema, maybe a
dataset we never saw). The LLM gets a database + a question; it never has to guess the dataset. Then close the gaps the
A/B traces showed and measure it.

## 2. Done when
- `LOGS_DATASET=<name>` pins the MCP server: no `dataset` parameter in any tool schema, instructions / field guide /
  describe_corpus describe only that dataset, every query filtered to it; unset = today's multi-dataset server.
- Agent + eval run one MCP server per question's dataset; `bench/check_tools.py` + `bench/lint_generic.py` pass.
- Each of the 8 gaps has a change and a check (below); A/B re-run on 50 questions: pinned new vs pinned old, and pinned
  new vs plan-013 new (stored answers), with the time split.

## 3. Approach (gap → change)
1. **Dataset scoping (16 q mixed datasets):** pinning above (server-side, generic; `core.registry()` filtered, tool
   wrapper injects the dataset and drops the parameter from the schema). Remote tools only when unpinned.
2. **No latency tool for engineers (D-X23):** `latency_profile` → engineer subset; add an endpoint grouping if the
   pattern grouping masks paths (check first).
3. **No "who drove it" for leads (D-X10):** `top_entities` → lead subset.
4. **Narrow context window (D-E01):** `get_context` returns the nearest line before / after outside the window
   (same scope) with its gap in seconds, so "nothing nearby" is never silently wrong.
5. **HDFS has no node (D-X15-17):** `load/33_hdfs.sql` fills node from the datanode named in the line (`<ip>:50010:`,
   `dest: /<ip>:50010`); loader-only.
6. **Apache continuation lines inherit a component (D-X14):** `load/31_apache.sql` derives the component of a
   continuation line from its own text (default httpd); generic library unchanged.
7. **Misreadable outputs:** `pattern_history` buckets = real lines per bucket (not lines of bursts starting there);
   `reliability_trend` says "improving / worsening" only beyond a noise rule; `top_patterns` / `priority_table` list
   the top recurring patterns the problem filter excluded (so a judged-benign but frequent pattern is visible).
8. **Truncation:** truncated results say how many rows are missing and the limit to pass (envelope hint).
- Subsets: drop `similar_patterns` (lead), `precursors`, `distinctive_terms` (engineer): never used in 50 q, cost tokens
  every turn; they stay on the server for other clients.
- Data fixes change a few golden values (apache, hdfs): re-run `build_golden.py`; update the affected answer-key
  numbers (truth changed with the data, documented), nothing else in the keys.

## 4. How we check it
check_tools on every dataset (pinned + unpinned); targeted re-checks of D-E01, D-X10, D-X14, D-X17, D-X23, D-M03;
full A/B. Held-out untouched.

## 5. Out of scope / risks
MCP transport overhead (~0.5 s/call) noted, not fixed. Reload of HDFS (11M) is slow on the emulated image.

## 6. Steps
- [x] Loaders (5, 6) + reload; golden values unchanged; 6 keys get a `data_update` note
- [x] Pinned server (1), tool changes (4, 7, 8), subsets (2, 3); check_tools 36×9 unpinned + pinned (zookeeper, hdfs) pass, 0 leaks
- [x] Agent + eval per-dataset servers (`mcp_config(ds)`, `--arms`, `--reuse`); smoke on D-X23 / D-X10 / D-M03 / D-E01: all reach the key's answer (D-E01 needed a composer rule: report nearest outside-window lines)
- [x] A/B run (new vs old, pinned); results, STATUS, DECISIONS. Run B (vs plan-013 answers) postponed

## 7. Results (filled after)
Run `eval/results/ab-20261018-155748.md` (git e4a61a9; every question on an MCP server pinned to its dataset; new =
plan-014 subsets + fixes, old = plan-010 subsets, both on today's tool code; shared tool-neutral prompt; 0 failed, 0 leaks).

| | plan 013 (unpinned) | plan 014 (pinned + gap fixes) |
|---|---|---|
| wins new / old / tie / inconsistent | 19 / 11 / 13 / 7 | **17 / 6 / 18 / 9** |
| engineer · lead · manager (new-old) | 11-4 · 4-4 · 4-3 | **10-2 · 6-2 · 1-2** |
| claim accuracy new / old | 0.944 / 0.930 | **0.966** / 0.937 |
| wrong claims new / old | 53 / 64 | **34** / 60 |
| found the real problem (of 2) | 1.58 / 1.40 | 1.57 / 1.38 |
| rubric (1-5) | 3.83 / 3.69 | **4.00** / 3.79 |
| golden facts E1 | 0.823 / 0.806 | **0.901** / 0.850 |
| wall s (llm + tool + other) | 44.4 / 41.0 | 44.4 (40.1 + 3.8 + 0.5) / 43.6 (39.8 + 3.4 + 0.5) |
| SereneDB s per run (ms per call) | 0.38 (59) / 0.26 (45) | 0.53 (80) / 0.40 (68) |
| input tokens | 131k / 98k | 119k / 102k |

- New loses only 6 of 50; wrong claims down 36 % vs plan 013's new arm (53 → 34); golden facts 0.82 → 0.90. Pinning helps
  both arms (old E1 0.81 → 0.85) and removed the mixed-dataset failures (D-M01/M03/M05 now ties).
- Gap cases: D-E01 (context window) and D-L04 old → new win; D-M03 lost → tie; D-X23 (latency) reaches the key.
- Managers are mostly ties (8): both arms read the same priority_table; the extra tools do not change the answer.
- Speed: same as before (LLM 90 %); the new arm's 13 % fewer input tokens than plan 013 (trimmed subsets).
- Not run: plan-014 new vs plan-013 new (stored answers), postponed (Amirali). Caveats: one run; 9 inconsistent.
