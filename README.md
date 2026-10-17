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
judgments per pattern from the committed `data/pattern_judgments_{bgl,openstack}.csv`; no TypeSafe key needed) → `bench/check_counts.py`,
`bench/check_patterns.py`. Regenerating the judgments needs a key: `scripts/judge_patterns.sh bgl` (~20 s, ≈ $0.02), `… openstack` (~3 s).

Connect Claude Code to the tools: the `logs` MCP server is registered in [`.mcp.json`](.mcp.json), so running
`claude` in this folder offers it (approve it once). Any other MCP client: stdio command `.venv/bin/python mcp_server/server.py`
(DB via `PGHOST`/`PGPORT`/`PGUSER`/`PGDATABASE`, default `localhost:7890`). UI: _coming soon_.

Ask the agent (needs `ANTHROPIC_API_KEY` in `.env`; LangSmith tracing if `LANGSMITH_*` are set):
```bash
.venv/bin/python -m agent.run --role engineer "What failed on the R43-M0 midplane around 2005-08-19 13:56, and what happened just before and after?"
.venv/bin/python -m agent.run --role lead "Which problems recurred most in November 2005 (2005-11-01 to 2005-11-29), and which teams own them?"
.venv/bin/python -m agent.run --role manager "Based on November 2005, which problems deserve attention first and what should happen next?"
.venv/bin/python -m agent.run "Is the rts panic problem getting worse in November 2005?"   # no --role: Jev routes the question
.venv/bin/python -m agent.run --baseline --role manager "…"                                # the reference ReAct agent
```
Each run prints the answer card + evidence (SQL) + the LangSmith trace URL, and saves `runs/agent/<time>-<kind>-<role>.json`.

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
| `search_logs` | Find log lines by message text and/or filters (locate an error, when it started, how widespread) | `query_text` (web-search syntax: words = AND, `"phrase"`, `OR`, `-word`; optional), `dataset`, `start`/`end`, `component`, `severity`, `node`, `midplane`, `rack`, `request_id`, `instance_id`, `pattern_id`, `order` (`time` / `recent` / `relevance` = BM25), `limit` ≤ 50 | matching lines (`line_id, ts, component, severity, node, body`, …) + over all matches: `total_matches`, `first_ts`, `last_ts`, `distinct_nodes` |
| `get_context` | What happened just before and after one line, on the same node / midplane / rack (BGL) or request / VM (OpenStack) | `dataset`, `line_id`, `before_s`/`after_s` (default 300), `scope`, optional `severity`, `limit` per side ≤ 50 | `anchor`, `before` / `after` (nearest first), `before_total` / `after_total`, per-side `truncated` |
| `top_patterns` | Which problems recur in a period, how often, where, whose, and are they growing? | `dataset`, `start`/`end` (default: last 28 days of the dataset), `team`, `component`, `problem_only`, `problem_filter` (`jev` / `severity`), `rank_by` (`bursts` / `nodes` / `lines` / `growth`), `limit` ≤ 50 | per log pattern: template, component, team, lines, **bursts** (recurrences, 30-min gap), nodes, weeks_active, bursts in the previous period + change, `new`, `top_node_share`; both periods as absolute dates |
| `priority_table` | Computed priority ranking of problem patterns + per-team roll-up | `dataset`, `start`/`end`, `limit`, `problem_filter` | ranked items with `score` = 100 × Σ weight × percentile of 5 inputs (bursts, change, nodes, persistence, Jev `p_problem`), the inputs, per-input contributions, the weights; per-team bursts now vs previous period; `unknown` (no cost/downtime/impact in logs) |
| `value_outliers` | Operations far slower than normal **for their own pattern** (problems that log no error, only an unusual number: slow VM spawns, slow API calls) | `dataset`, `pattern_id`, `instance_id`, `start`/`end` (lines to flag; baseline = whole dataset), `k` (default 6), `min_excess_s` (default 2), `limit` ≤ 50 | `baselines` per pattern (n, median, p95, MAD, threshold = max(median + k×MAD, median + min_excess_s), flagged); `instances` (every flagged VM, max ratio); flagged lines with `value_s`, `ratio` to the median, ids |

Full-text tokens are letters only (lowercased): numbers and hex ids inside messages are not searchable; use the
`node` / `request_id` / `instance_id` filters for ids. Latency: p95 < 45 ms per call on the full corpus
([`docs/PERFORMANCE.md`](docs/PERFORMANCE.md)).

## Agent (`agent/`, LangGraph)
```
            ┌─► gather_engineer ─┐
  route ────┼─► gather_lead ─────┼─► handover ─► composer ─► END
            └─► gather_manager ──┘               (compose ─► check ─► revise ≤ 1)
```
Each `gather_<role>` is a prebuilt ReAct agent (LangChain `create_agent`, the successor of LangGraph's
`create_react_agent`) with the role's tool subset, its evidence recipe and two middlewares: **CoverageMiddleware**
(the role checklist, sends the model back while required evidence is missing) and the built-in
**ToolCallLimitMiddleware**. The **composer** is a separate subgraph that only sees the evidence ledger.
- **route:** role given, or picked by **Jev** (calibrated choice, run inside SereneDB); LLM fallback.
- **gather_\<role\>:** the LLM follows the role's **evidence recipe** with the role's tool subset (engineer: search →
  context → spread; lead: top_patterns → trend → counts by team; manager: priority_table → team roll-up); tool calls run
  concurrently; every result envelope enters an **evidence ledger** keyed by `evidence_id`.
- **coverage (middleware):** deterministic role checklist (which tools must have run); missing → nudge, ≤ 2.
- **handover:** the gatherer's tool results → **evidence ledger** keyed by `evidence_id`.
- **composer → compose:** the LLM writes a structured **answer card** (answer, scope, facts with evidence ids, ranked problems,
  labelled hypotheses, unknowns, next steps) from the ledger only.
- **composer → check:** deterministic **claim checker**: every number must be found in a result the item cites, no invented money /
  downtime / customer impact, role checklist; one revision round, then unverified items are marked.
  **Confidence = computed** (verified-number rate, halved if the checklist is incomplete), never self-reported.
- **Baseline:** the brief's reference design: `create_agent` with all tools and a plain role prompt (no recipe, no
  coverage, no composer), free text. Same core as our gatherers, so the eval isolates our layer.
- **MCP server:** one server (`logs`) with all 6 tools and role-neutral descriptions; per-role subsets exist only
  inside our agent.
- **Tracing:** one LangSmith trace per question (`ours:<role>` / `baseline:<role>`), tags (kind, role, model), metadata
  (question, git sha, route + Jev probabilities, evidence ids, numbers verified, confidence, revisions, latency).

## Evaluation (ours vs the reference ReAct agent with the same tools)
`.venv/bin/python -m eval.run_eval` runs both systems on 18 dev questions (6 per role) as LangSmith experiments, with
deterministic metrics (golden facts from hand-checked SQL, numbers found in the evidence, tool use, forbidden claims,
cost) and an Opus judge (claim support against the evidence, role rubric, pairwise in both orders). Details: `docs/EVAL.md`;
latest report: `eval/results/20261017-174933.md`.

| Metric (18 dev questions, 6 per role) | ours | baseline |
|---|---|---|
| E1 golden facts in the answer | **0.79** | 0.59 |
| E2a numbers found in the run's own tool results | **0.99** | 0.85 |
| E2b numbers found in the result the fact cites (ours) | **1.00** | — |
| E2c claims supported by the evidence (judge) | **0.89** | 0.59 |
| E3 causes stated as fact, per answer (judge) ↓ | **0.11** | 0.39 |
| E3 states what the logs cannot establish | **1.00** | 0.11 |
| E5 invented money / downtime / impact (regex + judge) | 0 | 0 |
| E7 required tools called | **1.00** | 0.83 |
| Q rubric mean 1-5 (judge) | **4.53** | 3.91 |
| Q role fit 1-5 (judge) | **4.83** | 4.17 |
| Q next-step specificity 1-5 (judge) | **4.28** | 2.56 |
| Q pairwise, both orders, consistent wins | **10** | 4 (4 inconsistent) |
| E4 evidence overlap between roles on the same topic ↓ | **0.02** | 0.04 |
| E4 tool overlap between roles on the same topic ↓ | 0.39 | **0.28** |
| E8 seconds per answer ↓ | 34 | **13** |
| E8 input / output tokens ↓ | 54k / 4.8k | **33k / 1.6k** |

Dev questions were written by us after seeing the data; a separate human-written private question set exists (its
runner prints aggregates only).

## Worked investigation
_Coming soon._

## Known limitations
_Coming soon._

## Citation
Zhu et al., *Loghub: A Large Collection of System Log Datasets for AI-driven Log Analytics*, ISSRE 2023.
Oliner & Stearley, *What Supercomputers Say: A Study of Five System Logs*, DSN 2007.
