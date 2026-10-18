# 014: One dataset per session + fix the 8 gaps from the plan-013 A/B

- **Status:** running (Amirali, 2026-10-18: "address each of the 8 problems … change the structure")
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
- [ ] A/B runs, results, STATUS / DECISIONS

## 7. Results (filled after)
