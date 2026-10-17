# 48 h plan: parallel, mixed tracks

Principle: **both of us touch every layer** (DB, tools, agent, UI, eval). We split by **vertical slice** (one dataset or
one role end to end), not by layer, and swap halfway so each reviews the other's work. Shared contracts first so we never
block each other.

## 0. Contracts (together, 30 min, before splitting)
- `logs` schema + `ownership` + `labels` (kept apart from agent tools).
- **Tool result envelope:** `{tool, params, sql, scope, filters, rows, total_matches, truncated, elapsed_ms, evidence_id}`.
- **Answer card JSON** (`ROLES.md`): answer, facts[evidence_id], hypotheses, unknown, next_step, scope, confidence.
- File layout: `load/*.sql`, `mcp_server/server.py`, `agent/graph.py`, `app/app.py`, `eval/`, `bench/`.

## Blocks (A = Amirali, K = Konark; swap freely)
| Block | A | K | Together at the end of the block |
|---|---|---|---|
| **B1 data** (Sat, until ~18:30) | BGL load in SQL (parse, sort, typed columns), inverted index, `search_logs` + `get_context` | OpenStack load in SQL (request/instance/latency/status parsed), ownership, `count_by` + `trend` | cross-check: each verifies the other's counts against `wc`/`awk` (E1 seeds); first numbers for the jury |
| **Jury Q&A 18:50–19:00** | pitch | notes | update `QA_JURY.md` log + act on advice |
| **B2 patterns + MCP** (Sat evening) | patterns + episodes for BGL; MCP server skeleton with A's tools | patterns for OpenStack; rollup tables; add K's tools to the MCP server; Claude connects via README steps | baseline ReAct agent (LangGraph) answers one question per role |
| **B3 roles** (Sun morning) | **team lead + manager** slices end to end: `top_patterns`, `priority_table`, recipes, cards | **engineer** slice end to end: recipe (anchor → context → spread → baseline), card | swap and review; Jev pattern judgments in SQL (whoever is free) |
| **B4 trust + perf** (Sun midday) | evidence ledger + claim checker | bench + optimisations (`PERFORMANCE.md`) | eval run ours vs baseline (`EVAL.md`), dev only |
| **B5 ship** (Sun afternoon) | UI answer card + evidence drawer; held-out script run | README, worked investigation, tool docs; clean-checkout test on K's machine | slides + 5-min demo rehearsal ×2 |

Rules: every cell above starts as an approved plan in `plans/` (`plans/README.md`); merge to `main` small and often; whoever finishes early picks the next row of the other column; `STATUS.md` says
who is on what right now.
