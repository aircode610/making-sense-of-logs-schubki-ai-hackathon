# Architecture (target; draft 2026-10-17 — change freely, keep it short)

```
data/raw (BGL, OpenStack) ──load/*.sql run by SereneDB in docker (read_csv/COPY from /data, parse in SQL)──►  SereneDB
                                                                   ├─ logs         one row per line (both datasets)
                                                                   ├─ patterns     template, counts, first/last, + Jev columns
                                                                   ├─ episodes     bursts of a pattern per node/component
                                                                   ├─ ownership    data/ownership.csv
                                                                   ├─ rollups      hour × pattern × node × severity counts
                                                                   ├─ labels       eval only; no agent tool reads it
                                                                   └─ evidence     ledger: every tool call + SQL + result
                    ▲
mcp_server/  FastMCP: parameterized SQL tools (search, context, counts, trend, patterns, priority, scope)
                    ▲  (same tools, three clients)
    ┌───────────────┼──────────────────────┐
 Claude (judges)  agent/ LangGraph          eval/ (golden SQL, groundedness, role checks, baseline vs ours)
                  role recipe → tool calls → answer card → claim checker   (traced in LangSmith)
                    ▲
                 app/  Streamlit: role picker, question, answer card, evidence drawer (SQL + rows)
```

## Schema (first cut; decide in hours 0–6 after DESCRIBE)
- `logs(dataset, line_id, ts, component, severity, severity_number, node, location, request_id, object_id, status, duration_ms, entities, body, pattern_id)` (generic since plan 012; per-dataset meanings in `datasets`; `severity_number` = OTel SeverityNumber 1–24 from
  `severity_map`, plan 057)
  — BGL: node = location field, label = alert category (`-` → NULL); OpenStack: component = nova service,
  request/instance/latency parsed from body. Full-text index on `body` (+ filters on ts/dataset/component/severity).
  Loaded by SereneDB in docker: `read_csv` each raw line as one column, parse with SQL string/regex functions, insert
  sorted by ts. Labels go to a separate `labels` table. Python only where SQL can't do a step (e.g. Drain3).
- `ingest_runs(dataset, file, format, format_title, sample_lines, sample_matched, ts_format, year_assumed, field_map,
  candidates, regexes_skipped)` + `ingest_unparsed(dataset, line_id)` (plan 057 part 3): written by auto-detected loaders
  (`load/gen/*.sql` from `scripts/ingest.py`), read by `ingest_report`; empty for hand-written loaders.
- `patterns(pattern_id, dataset, component, template, lines, nodes, first_ts, last_ts, example)` + Jev judgment columns.
- `ownership(dataset, component, team, description, area, area_source, area_confidence, source, confidence, disputed_by,
  dispute_confidence)` (plan 057: curated rows + inference chain, built by `load/96b_ownership_inferred.sql`; tools join
  on (dataset, component) and read `team`; `top_patterns` / `priority_table` / `owner_of` also read source /
  confidence / disputed_by); `evidence(id, ts, tool, params, sql, rows, truncated, result_json)`.

## Tools (first cut; every result returns `sql`, `filters`, `scope`, `rows_returned`, `total_matches`, `truncated`)
| Tool | For | Inputs | Returns |
|---|---|---|---|
| `describe_corpus` | all | — | datasets, time spans, line counts, components, teams |
| `search_logs` | engineer | text (full-text; phrase/fuzzy opt.), dataset, time range, component/severity/node filters, limit ≤ 50 | matching lines + total count |
| `get_context` | engineer | dataset, timestamp or line id, ± seconds, same node/request/instance?, limit | events before/after |
| `count_by` | lead/manager | group_by (dataset/team/component/severity/pattern/node), filters, period | full-corpus counts |
| `trend` | lead/manager | bucket (hour/day/week), group_by?, filters, period | time series |
| `top_patterns` | lead | period, rank_by (lines/episodes/nodes/growth), problem_only | patterns with counts, episodes, teams |
| `priority_table` | manager | period | ranked problems with score inputs (frequency, trend, spread, severity) |
| optional `create_index`/`drop_index`, `query_remote_parquet` | extensions | | |

## Agent (LangGraph)
`route` (role given or inferred) → `gather` (role recipe: fixed first tool calls + ReAct for follow-ups) →
`compose` (LLM writes the answer card from evidence ids only) → `check` (numbers ⊂ cited results; Jev claim check;
fail → revise once or mark unverified). Strong LLM via `init_chat_model(AGENT_MODEL)` (default Claude Opus 5.5); MCP tools via `langchain-mcp-adapters`.
Baseline agent = `create_react_agent` with the same tools and a role prompt (for `EVAL.md`).

## Repo layout (planned)
`load/` · `mcp_server/` · `agent/` · `app/` · `eval/` (+ `eval/heldout/`, never read by Claude) · `bench/` · `docs/` · `data/` · `docker/` · `scripts/` · `archive/side-quest/`
