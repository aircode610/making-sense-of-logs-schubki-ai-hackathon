# 003: Engineer tools `search_logs` + `get_context` on a FastMCP server

- **Status:** done, except the live Claude Code check (needs a restart; see §7)
- **Owner:** Amirali · **Branch:** `feat/003-engineer-tools` · **Date:** 2026-10-17
- **PLAN.md block / slice:** B1 · `search_logs` + `get_context` (+ the MCP server skeleton Konark adds `count_by`/`trend` to)

## 1. Goal
The engineer's two core tools as MCP tools Claude can call: full-text search with time/component/severity/node filters,
and the events around a line. Rubric: search + analytics (25%), engineer role (30%), Best MCP Server award; brief
"full-text search with time filters and nearby events" + "include the query and filters, indicate truncation".

## 2. Done when (decided before starting)
- `search_logs("parity")` reports `total_matches` **121,498**; `'"cache parity error"'` **106,220**; `parity corrected`
  (AND) **105,924** = Python token check on the raw file. A time/node-filtered search equals a hand-written SQL count.
- `get_context` on a chosen KERNEL FATAL line returns before/after events that equal a hand-written SQL query
  (same node, ± 5 min), with per-side totals and `truncated` flags.
- Every result carries the envelope: `tool, params, sql, filters, scope, rows, total_matches, truncated, elapsed_ms,
  evidence_id`. Rows ≤ 50, long bodies cut (flagged).
- Claude Code in this repo lists the server from `.mcp.json` and answers one E1-style question by calling the tools.
- Tool p50 latency measured (≥ 20 calls each) and recorded in `PERFORMANCE.md`; target < 200 ms.

## 3. Approach
- **Files** (split so Konark can work in parallel without conflicts): `mcp_server/core.py` (connection from `PG*` env,
  `run()` → envelope, `evidence_id` = short hash of SQL + params), `mcp_server/search.py` (my two tools),
  `mcp_server/server.py` (FastMCP from `mcp==1.30`, stdio, registers tools; Konark adds `aggregate.py`).
  `.mcp.json` gets a `logs` stdio entry (`.venv/bin/python mcp_server/server.py`) so judges get it by cloning.
- **`search_logs(query, dataset?, start?, end?, component?, severity?, node?, midplane?, rack?, order='time'|'relevance',
  limit=20 ≤ 50)`** → matching lines (`line_id, dataset, ts, component, severity, node, body`) + one summary query
  with the same filters: `total_matches, first_ts, last_ts, distinct_nodes` (so the agent never infers frequency from
  the sample). Query syntax = `websearch_to_tsquery` (verified): words = all must appear, `"phrase"`, `OR`, `-word`.
  Relevance = `ORDER BY BM25 DESC` (WAND top-k via `optimize_top_k`). Parameters always bound (psycopg; verified).
- **`get_context(dataset, line_id, before_s=300, after_s=300, scope='node'|'midplane'|'rack'|'all', limit=20 per side)`**
  → the anchor line, `before` (nearest first) and `after` lists, `before_total` / `after_total`, `truncated`. OpenStack
  scopes `request` / `instance` coded now, tested once Konark's data is in.
- Tool docstrings = what the agent reads: purpose, when to use it, inputs, outputs, limits ("counts come from
  `total_matches`, never from the sample").
- No evidence table yet (ledger = B4); `evidence_id` is reproducible from SQL + params.

## 4. How we check it
A scratch script calls the tool functions directly and compares with hand SQL / plan 002 reference counts; 20× timing
per tool. Then the live Claude Code check. Held-out untouched.

## 5. Out of scope / risks
- Out: fuzzy/prefix flags (work in SQL: `term~1`, `pari*`; add later if cheap), `count_by`/`trend` (Konark), baseline
  rate + spread tools (B3 engineer recipe), evidence ledger, agent.
- `@@` can't be used inside `FILTER (...)` (verified): counts are separate queries; fine at these latencies.
- Tokenizer drops digits/hex (`0x00544eb8` → not one token): searching ids inside text won't work; node/instance ids
  are filter columns. Documented in the tool description.
- Claude Code needs a restart/approval to see a new `.mcp.json` server: you approve it once.

## 6. Steps
- [x] Branch; `core.py` + `search.py` + `server.py`
- [x] Scripted checks vs reference counts + hand SQL; timing
- [x] `.mcp.json` entry · [ ] you restart/approve; live E1-style question
- [x] README Tools section (both tools: purpose, inputs, outputs); PERFORMANCE, §7, STATUS, plans index

## 7. Results (filled after)
Done 2026-10-17 (all checks scripted; the tool functions and the stdio MCP protocol both tested).

| Check | Reference | Tool |
|---|---|---|
| `parity` | 121,498 (plan 002) | 121,498 |
| `"cache parity error"` | 106,220 | 106,220 |
| `parity corrected` (AND) | 105,924 (Python token count on raw file) | 105,924 |
| `parity` + July 2005 + INFO: total / distinct nodes / truncated (limit 5) | 1,553 / 10 / yes (hand SQL) | same |
| `get_context` line 500, node ±300 s: before / after totals, first 20 ids each side | 499 / 1,610 (hand SQL) | same, ids identical |
| MCP stdio client | — | 2 tools, readOnlyHint; call ok; unknown line_id → actionable error; limit > 50 → validation error |

- Latency (20 runs, p50/p95): `search_logs` 11/14 ms, relevance 16/19 ms, `get_context` node ±300 s 34/41 ms,
  midplane ±60 s 22/28 ms (`PERFORMANCE.md`). Target < 200 ms met.
- **Addition (approved after the fact by Amirali):** optional `severity` filter on `get_context`: busy nodes log
  thousands of INFO lines per window (1,610 in 5 min on line 500's node), which bury the FATAL neighbours.
- Learned: plain `body @@ 'a b'` = OR; `websearch_to_tsquery` gives AND + phrase/OR/-word. `@@` not allowed inside
  `FILTER (…)`. psycopg bound params work with `@@`. `line_id` point lookups ~20 ms without an index (rows ~ file order).
- **Pending:** live check in Claude Code (restart → approve `logs` server → one E1 question).
- Next: Konark adds `count_by` / `trend` in `mcp_server/aggregate.py` (register in `server.py`); OpenStack scopes
  `request` / `instance` get tested once OpenStack is loaded.
