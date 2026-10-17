# 005: Team-lead + manager tools `top_patterns` + `priority_table`

- **Status:** done (2026-10-17); approved with "scores must come from real data, nothing LLM"
- **Owner:** Amirali · **Branch:** `feat/005-lead-manager-tools` · **Date:** 2026-10-17
- **PLAN.md block / slice:** B3 · team lead + manager tools (recipes/answer cards = agent plan, later)

## 1. Goal
Two MCP tools over `patterns` / `bursts` (plan 004): the lead's "what recurs, how often, whose is it, getting worse?"
and the manager's computed, auditable priority ranking. Role insight (30%), recommendation quality (25%); ROLES.md
L1/L4/L5/L6 and M1/M2/M4. The tool ranks; the LLM only explains (CLAUDE.md non-negotiables 1, 5, 7).

## 2. Done when (decided before starting)
- `top_patterns` values equal hand SQL for 2 patterns (lines, bursts, nodes in a period, previous-period bursts),
  and its burst totals equal a direct count on `bursts`; `problem_only` and `team` filters checked.
- **No model anywhere in these tools:** every input is a SQL aggregate over `logs` / `bursts` / `patterns`, the weights
  are constants in code, the score is arithmetic in the tool, and the result carries the SQL that produced the inputs.
- `priority_table`: for the top items, **each input is recomputed from the raw tables by independent hand SQL** in the
  check script (not copied from the tool), then inputs × weights reproduce every score;
  no ranking uses raw line counts; team roll-up sums equal the per-pattern rows.
- Measured sanity (labels as a check only, tune part `< 2005-12-05`): share of alert-carrying patterns in the top 10
  by priority vs top 10 by lines vs top 10 by problem severity alone. Reported, not tuned to.
- Both tools in the MCP server (6 tools listed); p95 < 200 ms; README Tools rows; `bench/check_counts.py` extended.

## 3. Approach
- **File:** `mcp_server/patterns.py`, results via `core.envelope` (same shape as the other tools). Registered in `server.py`.
- **Period:** `start`/`end` optional; default = last 28 days of the dataset ("corpus now" = its last ts, ROLES.md).
  Always echoed as absolute dates, plus the **previous period** of equal length used for comparisons.
- **`top_patterns(dataset, start?, end?, team?, component?, problem_only=True, rank_by='bursts'|'nodes'|'lines'|'growth',
  limit=20 ≤ 50)`** → per pattern in the period: `pattern_id, template, component, team, severity, lines, bursts,
  nodes, weeks_active, bursts_prev, change` (now − prev), `first_seen` (corpus) + `new` (first seen in period),
  `top_node_share` (largest node's share of lines: one bad node vs fleet, L4). Problem = pattern has lines with
  severity FATAL/FAILURE/SEVERE/ERROR (BGL) or ERROR/CRITICAL (OpenStack); deterministic for now (Jev refines in B3).
  Bursts counted by start time; lines/nodes from `logs` (index group-by).
- **`priority_table(dataset, start?, end?, limit=10)`** → problem patterns ranked by
  `score = Σ wᵢ · pctrank(inputᵢ)` over the candidates, inputs: frequency = bursts, trend = bursts − bursts_prev,
  spread = nodes, persistence = weeks_active / weeks in period, severity = problem share of lines. Weights in code,
  returned with the result (start: 0.30 / 0.20 / 0.25 / 0.15 / 0.10), plus each item's per-input contribution and
  owner team, and a **team roll-up** (problem bursts now vs prev, top item per team). Percentile ranks keep it
  scale-free and robust to storms; raw lines are shown but never used for ranking.
- Tool descriptions say what the numbers are (bursts, not incidents; counts are lines) and that the ranking is computed.

## 4. How we check it
Check script vs hand SQL + score recomputation; label-share comparison on the tune part only; MCP stdio listing.
Held-out untouched (the weights are fixed up front, not fitted).

## 5. Out of scope / risks
- Out: Jev pattern judgments (next plan; then `severity` input uses the Jev probability), agent recipes / answer cards,
  OpenStack patterns (Konark's masks: the tools already work per dataset once `pattern_id` is set).
- Risk: deterministic "problem" = 727 BGL patterns, only 76 carry alerts (plan 004) → the priority list may show routine
  FATAL register dumps. Shown honestly in the label-share check; the fix is the Jev judgment, not weight tuning.
- Risk: percentile ranks over few candidates are coarse; fine for top-10 explanations.

## 6. Steps
- [x] Branch; `patterns.py` (`top_patterns`, `priority_table`); register
- [x] Check script (hand SQL, score recompute, roll-up sums, label-share sanity); timings
- [x] README Tools, PERFORMANCE, §7, STATUS, plans index; push branch

## 7. Results (filled after)
Done 2026-10-17. `mcp_server/patterns.py`; check `bench/check_patterns.py` (in `load/reload.sh`); 6 MCP tools.

- **No model anywhere:** every input is a SQL aggregate; percentiles (`cume_dist`) and the weighted score are computed
  in the same SQL (weights inlined), which is returned in `sql`. Independent check on 2005-11-01 → 11-29 (tune part):
  all 281 candidates' inputs recomputed with separate plain queries, percentiles + scores in plain Python → **all 50
  returned items match exactly** (inputs, scores, order); contributions sum to scores; team roll-up = sum over candidates;
  `top_patterns` rows = hand SQL; team filter ok. Latency median 34 / p95 44 ms.
- Fixed during build: persistence > 1 (28 days touch 5 calendar weeks → weeks in period = calendar weeks touched);
  `percent_rank` gave tied top values the lowest rank (e.g. problem_share = 1.0 for almost all) → `cume_dist`.
- **Measured weakness (labels as check only, tune period):** top 10 by priority 1/10 carry alerts; by lines 6/10; by
  bursts 0/10. Cause: machine-check **register dumps** (`debug wait enable……0`, `data address space……0`, ~30 FATAL
  lines per event, each its own pattern, 30+ nodes every week) are not alerts but win on recurrence + spread. The
  deterministic "problem = severity" filter can't see that. Not fixed by weight tuning (would fit labels). Fix =
  next plan: **Jev judgment per pattern** ("real fault or routine output?") as the candidate filter / severity input,
  and re-measure the same table. Possible extra: collapse patterns that always co-occur (one dump = one item).
- Default period (last 28 days) is inside the held-out slice: fine for the agent, but development checks use
  November 2005 only.
