# Making Sense of Logs — the right insights for the right people

SchubKI National AI Hackathon 2026 · SereneDB challenge · Team: Amirali, Konark.

> **SereneDB counts, Jev judges, the LLM explains — and every sentence is checked against the query that produced it.**

🚧 Work in progress (hackathon running 17–18 Oct 2026). This README is filled in as the prototype comes together.

## Workflow
Question → evidence (SereneDB full-text search + aggregations, via MCP tools) → recommendation (agent), for three roles:
**engineer** (what failed, where, what happened around it), **team lead** (what recurs, how often, which teams),
**manager** (what to prioritise and why, from measured frequency and spread only).

## Setup (clean checkout)
Requirements: Docker, Python 3.12, [`uv`](https://docs.astral.sh/uv/), `psql`.
```bash
cp .env.example .env                     # fill in keys
./scripts/download_data.sh               # BGL + OpenStack (~770 MB) into data/raw/
docker compose up -d                     # SereneDB on localhost:7890
psql -h localhost -p 7890 -U postgres -d postgres -f docker/init.sql   # first start only
./docker/secrets.sh                      # after every start: registers AI keys in SereneDB
uv venv --python 3.12 && uv pip install -r requirements.txt
```
Load the data (SereneDB reads and parses the raw files itself; schema and loaders in [`load/`](load/)):
```bash
./load/reload.sh   # drops + recreates tables, loads BGL (4,747,963 rows) + OpenStack (207,820) + ownership, publishes the index, builds patterns/bursts/episodes, then checks counts (~30 s)
```
`reload.sh` runs `load/00_schema.sql` → `10_bgl.sql` → `20_openstack.sql` → `90_publish.sql` (`VACUUM` refresh + compact:
the inverted index is eventually consistent, so counts are only exact once it is published) → `95_patterns_episodes.sql`
(log templates → `patterns`, `bursts`, `episodes`; built from published rows) → `96_pattern_judgments.sql` (Jev
judgments per pattern from the committed `data/pattern_judgments_bgl.csv`; no TypeSafe key needed) → `bench/check_counts.py`,
`bench/check_patterns.py`. Regenerating the judgments needs a key: `scripts/judge_patterns.sh bgl` (~20 s, ≈ $0.02).

Connect Claude Code to the tools: the `logs` MCP server is registered in [`.mcp.json`](.mcp.json), so running
`claude` in this folder offers it (approve it once). Any other MCP client: stdio command `.venv/bin/python mcp_server/server.py`
(DB via `PGHOST`/`PGPORT`/`PGUSER`/`PGDATABASE`, default `localhost:7890`). Agent and UI: _coming soon_.

## Data
Loghub **BGL** (4,747,963 lines, 214.7 days) and **OpenStack** (207,820 lines). See [`data/README.md`](data/README.md).
Ownership table (fictional): [`data/ownership.csv`](data/ownership.csv).

## Tools
MCP server [`mcp_server/`](mcp_server/) (FastMCP, read-only). Every result is an **envelope**: `tool`, `params`, `sql`
(the exact queries that ran, values inlined), `filters`, `scope`, `total_matches`, `truncated`, `elapsed_ms`,
`evidence_id`, plus the tool's rows. Returned lines are capped (≤ 50, messages cut at 300 chars and flagged); totals are
computed over all matches, so frequency never comes from a sample.

| Tool | Purpose | Inputs | Returns |
|---|---|---|---|
| `search_logs` | Find log lines by message text and/or filters (engineer: locate an error, when it started, how widespread) | `query_text` (web-search syntax: words = AND, `"phrase"`, `OR`, `-word`; optional), `dataset`, `start`/`end`, `component`, `severity`, `node`, `midplane`, `rack`, `request_id`, `instance_id`, `pattern_id`, `order` (`time` / `recent` / `relevance` = BM25), `limit` ≤ 50 | matching lines (`line_id, ts, component, severity, node, body`, …) + over all matches: `total_matches`, `first_ts`, `last_ts`, `distinct_nodes` |
| `get_context` | What happened just before and after one line, on the same node / midplane / rack (BGL) or request / VM (OpenStack) | `dataset`, `line_id`, `before_s`/`after_s` (default 300), `scope`, optional `severity`, `limit` per side ≤ 50 | `anchor`, `before` / `after` (nearest first), `before_total` / `after_total`, per-side `truncated` |
| `top_patterns` | Team lead: which problems recur in a period, how often, where, whose, growing? | `dataset`, `start`/`end` (default: last 28 days of the dataset), `team`, `component`, `problem_only`, `problem_filter` (`jev` / `severity`), `rank_by` (`bursts` / `nodes` / `lines` / `growth`), `limit` ≤ 50 | per log pattern: template, component, team, lines, **bursts** (recurrences, 30-min gap), nodes, weeks_active, bursts in the previous period + change, `new`, `top_node_share`; both periods as absolute dates |
| `priority_table` | Manager: computed priority of problem patterns + team roll-up | `dataset`, `start`/`end`, `limit`, `problem_filter` | ranked items with `score` = 100 × Σ weight × percentile of 5 inputs (bursts, change, nodes, persistence, Jev `p_problem`), the inputs, per-input contributions, the weights; per-team bursts now vs previous period; `unknown` (no cost/downtime/impact in logs) |

Full-text tokens are letters only (lowercased): numbers and hex ids inside messages are not searchable; use the
`node` / `request_id` / `instance_id` filters for ids. Latency: p95 < 45 ms per call on the full corpus
([`docs/PERFORMANCE.md`](docs/PERFORMANCE.md)).

## Worked investigation
_Coming soon._

## Known limitations
_Coming soon._

## Citation
Zhu et al., *Loghub: A Large Collection of System Log Datasets for AI-driven Log Analytics*, ISSRE 2023.
Oliner & Stearley, *What Supercomputers Say: A Study of Five System Logs*, DSN 2007.
