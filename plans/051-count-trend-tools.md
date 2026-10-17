# 051: `count_by` + `trend` MCP tools

- **Status:** draft
- **Owner:** Konark · **Branch:** `feat/051-count-trend-tools` (from `main` after 050 is merged) · **Date:** 2026-10-17
- **PLAN.md block / slice:** B1 · `count_by` + `trend` (Amirali: `search_logs` + `get_context`, plan 003)

## 1. Goal
Two FastMCP tools giving exact full-corpus counts and time series over both datasets, with the query, filters, scope and
truncation stated in every result. Moves "search + analytics" (25%) and non-negotiables 1, 2, 4; the lead/manager
answers (counts by team/component, week-over-week trend) are built on them (`docs/ROLES.md`).

## 2. Done when
- `count_by(dataset?, group_by, filters, period)` where `group_by` ∈ dataset | team | component | severity | node
  (`pattern` later, after B2). Filters: dataset, component, severity, team, node, status, text (`body @@`), `ts` period.
- `trend(bucket, group_by?, filters, period)` where `bucket` ∈ hour | day | week; empty buckets are returned as 0.
- Every result is JSON: `{query_sql, params, filters, period (absolute), scope, rows, total_lines, truncated, row_limit}`;
  period defaults to the whole dataset and is always echoed in absolute timestamps ("now" = last ts of the dataset).
- Counts equal the awk/grep references from plans 002 + 050 (BGL by severity/component/team, OpenStack by component/
  severity/team, one text filter). `trend` buckets sum to the `count_by` total for the same filters.
- Counts are **lines**, labelled as such (no "incidents"). Only identifiers from a whitelist reach SQL; values are bound params.
- p95 per call < 200 ms on the full corpus (measured in `docs/PERFORMANCE.md`).

## 3. Approach
- **Files:** `mcp_server/counts.py` (the two tools + one `run(sql, params)` helper using `psycopg`, DSN from `.env`
  defaults to `localhost:7890`) and, if Amirali's `mcp_server/server.py` is not on `main` yet, a minimal
  `mcp_server/server.py` that only registers tools via `mcp.tool()` so plan 003 can add to it. Pull first; no refactor.
- **SQL:** group-by on `logs` (search table + inverted index: counts come from the index term dictionary, see
  `PERFORMANCE.md`); team via `LEFT JOIN ownership` (unmapped → `unowned`); week/day/hour via `date_trunc`, gaps filled
  with `generate_series` joined to the counts. Check with `EXPLAIN ANALYZE` that the join does not lose the fast path;
  fallback: map component→team in a CASE built from `ownership` at call time.
- No LLM, no Jev in these tools. Trend direction (rising/flat/falling) is **not** here (rule lives in the agent layer, B3).
- Config via `.env` names already in `.env.example` (no keys needed for the DB).

## 4. How we check it
Script `bench/check_counts.py` (one file): calls both tools directly and asserts the reference counts from 002 §7 and
050 §7, bucket sums = totals, plus timings. Needs BGL loaded locally (`psql -f load/00_schema.sql load/10_bgl.sql
load/20_openstack.sql`). Also one call through an MCP client to prove the tool schema/response over stdio. Held-out untouched.

## 5. Out of scope / risks
- Out: `top_patterns`, `priority_table`, pattern/episode grouping, trend direction rules, agent wiring.
- Risk: tool-name/response-shape clash with Amirali's tools → fix the shared envelope above now and tell Amirali.
- Risk: team join slows group-by → fallback in §3. Risk: BGL timestamps span 7 months, OpenStack 3 days → weekly
  buckets on OpenStack are 1–2 buckets; default bucket chosen by span and stated in the result.
- Risk: BGL needs loading locally (18 s) to test; fine.

## 6. Steps
- [ ] Pull; merge 050 into the branch base; check whether `mcp_server/` exists on `main`
- [ ] `counts.py`: `run` helper, `count_by`, `trend`, envelope
- [ ] `bench/check_counts.py` against reference counts + timings; MCP stdio smoke test
- [ ] PERFORMANCE.md, §7 here, STATUS, plans index; tell Amirali the envelope; commit only when asked

## 7. Results (filled after)
