# Making Sense of Logs — the right insights for the right people

SchubKI National AI Hackathon 2026 · SereneDB challenge · Team: Amirali, Konark.

> **SereneDB counts, Jev judges, the LLM explains — and every sentence is checked against the query that produced it.**

🚧 Work in progress (hackathon running 17–18 Oct 2026). Seven log datasets, 40 MCP tools over SereneDB, one agent for three roles.

## Workflow
Question → evidence (SereneDB full-text search + aggregations, via MCP tools) → recommendation (agent), for three roles:
**engineer** (what failed, where, what happened around it), **team lead** (what recurs, how often, which teams),
**manager** (what to prioritise and why, from measured frequency and spread only).

## Setup (clean checkout)
Requirements: Docker, Python 3.12, [`uv`](https://docs.astral.sh/uv/), `psql`.
```bash
cp .env.example .env                     # fill in keys (TypeSafe for Jev, Anthropic for the agent, Google for embeddings)
./scripts/download_data.sh               # BGL + OpenStack (~770 MB) into data/raw/
./scripts/download_data.sh --all         # optional: Zookeeper, Apache, OpenSSH (small Loghub sets, generality test)
./scripts/download_data.sh hdfs          # optional: HDFS_v1, 11M lines / 1.5 GB (the scale test)
docker compose up -d                     # SereneDB on localhost:7890 (+ OTLP/HTTP on :4318)
psql -h localhost -p 7890 -U postgres -d postgres -f docker/init.sql   # first start only
./docker/secrets.sh                      # after every start: registers AI keys in SereneDB
uv venv --python 3.12 && uv pip install -r requirements.txt
```
Load the data (SereneDB reads and parses the raw files itself; schema and loaders in [`load/`](load/)):
```bash
./load/reload.sh              # every dataset whose raw files exist; ~45 s for the five small ones, ~1 min 45 s with HDFS
LOAD_OTEL=1 ./load/reload.sh  # also pull a slice of the remote 1-billion-record OpenTelemetry Parquet over HTTPS (+2 min)
```
`reload.sh`: `00_cleanup.py` (drops workspaces / team views) → `00_schema.sql` (tables, dictionaries, generic mask +
entity macros, dataset registry) → one loader per dataset (`10_bgl`, `20_openstack`, `30_zookeeper`, `31_apache`,
`32_ssh`, `33_hdfs`, `40_otel_demo`; the new ones are one parse query + `\ir lib/stage_to_logs.sql`) → `90_publish`
(`VACUUM` refresh + compact) → `94_ownership` (ownership with `*` defaults, watchlist, remote sources) →
`95_patterns_episodes` (patterns, bursts, episodes) → `96_pattern_judgments` (stored Jev judgments + traits) →
`97_pattern_vectors` (template embeddings + IVF index, burst summaries) → `98_macros` (SQL API) → `99_roles.py`
(database roles) → `bench/check_counts.py`, `bench/check_patterns.py`, `bench/check_tools.py` (every tool vs
independent SQL on every loaded dataset). Everything AI-generated is committed (`data/pattern_judgments_*.csv`,
`data/pattern_traits_*.csv`, `data/pattern_vectors.parquet`, `data/burst_summaries.csv`), so a clean checkout needs no
key to load; regenerate with `scripts/judge_patterns.sh <ds>`, `scripts/judge_traits.py`, `scripts/embed_patterns.py`,
`scripts/summarize_bursts.py` (all run their AI calls inside SereneDB).

**A new log source** = `load/3x_<name>.sql` (parse the raw lines into `stage`: ts, component, severity, node,
location path, body, optional request id) + `\ir lib/stage_to_logs.sql` + rows in `data/ownership.csv` (`<ds>,*,team`
covers every component) + `scripts/judge_patterns.sh <ds>` / `judge_traits.py <ds>` / `embed_patterns.py`. No tool,
agent or eval code changes (CLAUDE.md rule 11). Or replay any dataset as OpenTelemetry into SereneDB's built-in OTLP
receiver: `.venv/bin/python scripts/otlp_replay.py <dataset> 2000`.

Connect Claude Code to the tools: the `logs` MCP server is registered in [`.mcp.json`](.mcp.json), so running
`claude` in this folder offers it (approve it once). Any other MCP client: stdio command `.venv/bin/python mcp_server/server.py`
(DB via `PGHOST`/`PGPORT`/`PGUSER`/`PGDATABASE`, default `localhost:7890`; `LOGS_DB_ROLE=logs_manager` or
`team_<team>` runs it with database-enforced access, see Roles).

Ask the agent (needs `ANTHROPIC_API_KEY` in `.env`; LangSmith tracing if `LANGSMITH_*` are set):
```bash
.venv/bin/python -m agent.run --role engineer "What failed on the R43-M0 midplane around 2005-08-19 13:56, and what happened just before and after?"
.venv/bin/python -m agent.run --role lead "Which problems recurred most in November 2005 (2005-11-01 to 2005-11-29), and which teams own them?"
.venv/bin/python -m agent.run --role manager "Based on November 2005, which problems deserve attention first and what should happen next?"
.venv/bin/python -m agent.run --role engineer "Which IP addresses drove the failed root logins on the SSH server in the first week of January 2018?"
.venv/bin/python -m agent.run "Is the rts panic problem getting worse in November 2005?"   # no --role: Jev routes the question
.venv/bin/python -m agent.run --baseline --role manager "…"                                # the reference ReAct agent
```
Each run prints the answer card + evidence (SQL) + the LangSmith trace URL, and saves `runs/agent/<time>-<kind>-<role>.json`.

The same questions as SQL (table macros, `load/98_macros.sql`): `logs_count`, `logs_search`, `problem_patterns`,
`team_problem_bursts`, `pattern_weeks`, `top_values`, `nearest_before`, e.g.
`SELECT * FROM problem_patterns('bgl', TIMESTAMP '2005-11-01', TIMESTAMP '2005-11-29');`

## Data
| Dataset | Lines | Span | What it is | Location / ids |
|---|---|---|---|---|
| `bgl` | 4,747,963 | 214 days | Blue Gene/L supercomputer RAS events | rack / midplane / node |
| `openstack` | 207,820 | 3 days | nova API / compute / scheduler | request, VM instance, tenant, HTTP status, latency |
| `zookeeper` | 74,380 | 27 days | ZooKeeper ensemble member (Java) | class / thread |
| `apache` | 56,482 | 264 days | Apache httpd error log | client IPs as entities |
| `ssh` | 655,147 | 28 days | OpenSSH auth log of an internet-facing host | host, session (`sshd-<pid>`), attacker IPs |
| `hdfs` (opt.) | 11,175,629 | 39 hours | Hadoop HDFS NameNode / DataNodes | block id (`blk_…`), datanode IPs |
| `otel` (opt.) | 1,702,944 | 30 min (sampled) | OpenTelemetry demo webshop (slice of 1 B remote records) | k8s namespace / node / pod, TraceId |

All from Loghub (BGL, OpenStack, Zookeeper, Apache, OpenSSH, HDFS) and the public OpenTelemetry `text_bench` Parquet.
See [`data/README.md`](data/README.md). Ownership (fictional, documented per row): [`data/ownership.csv`](data/ownership.csv).

## Tools (40, one MCP server)
MCP server [`mcp_server/`](mcp_server/) (FastMCP). Every tool is a fixed, parameterized SereneDB query: the LLM only
fills typed fields (dataset names are an enum of the loaded datasets). Every result is an **envelope**: `tool`,
`params`, `sql` (the exact queries that ran, values inlined), `filters`, `scope`, `total_matches`, `truncated`,
`elapsed_ms`, `evidence_id`, plus rows (≤ 50, messages cut at 300 chars). Totals are computed over all matches, never
from a sample. `explain_tool` shows any tool's query plan.

| Group | Tools (what they answer) | SereneDB features |
|---|---|---|
| Discover | `describe_corpus` (what is loaded), `list_values` (valid filter values), `suggest_terms` (spelling), `explain_search` (why a search matches) | term dictionary (`ts_dict_*`), `ts_lexize`, `EXPLAIN` |
| Search | `search_logs` (match = web / all / any / phrase / near / fuzzy / prefix / at_least / synonyms, `exclude_text`, `highlight`, `order` incl. BM25 × recency decay, `location` at any level, `entity`), `get_context` (before / after on node / location / request / VM) | inverted index, `ts_phrase(slop)`, `ts_levenshtein`, `ts_any(min_match)`, synonyms dictionary, `ts_highlight`, BM25, `expand_path` |
| Breakdowns | `facet` (one-pass breakdown of a search), `distinctive_terms` (significant terms: what is different in a window), `top_entities` (top IPs / paths / ids), `check_watchlist` (saved searches that fired) | `GROUPING SETS`, term dictionary, extracted entities |
| Counts | `count_by`, `trend`, `rate_vs_baseline`, `value_outliers` | aggregates, zero-filled `generate_series`, median / MAD |
| Patterns | `top_patterns`, `priority_table`, `pattern_history` (new or recurring), `whats_new` | patterns / bursts tables, `cume_dist`, stored Jev judgments |
| Timeline | `burst_timeline` (which error came first), `spread` (one node or fleet-wide), `precursors` (what comes before, with a control), `co_occurrence` (together, with a control), `periodicity` (on a schedule?), `request_timeline` (one request / session / block end to end) | window functions, **ASOF join**, `approx_top_k`, `entropy` |
| Analytics | `rollup` (subtotals), `heatmap` (team × week matrix), `reliability_trend` (slope + rule), `latency_profile`, `team_risk` | `ROLLUP`, `PIVOT`, `regr_slope`, `quantile_cont` |
| Semantic | `similar_patterns`, `find_patterns` (lexical / semantic / hybrid RRF), `summarize_burst` (model text, labelled) | `ai_embed` (Gemini), IVF vector index, RRF, `ai_summarize_agg` |
| Workspace | `create_focus_index` / `drop_focus_index` (index an investigation window, measured break-even), `index_stats`, `explain_tool` | search tables, inverted index, `sdb_metrics`, `EXPLAIN` |
| Remote | `remote_describe`, `remote_count_by`, `remote_search`, `remote_index` (the 1 B-record OTel Parquet on S3, in place) | `read_parquet` over HTTPS, row-group pruning, index on a view over remote files |

Numbers and dotted ids are whole search tokens (`503`, `172.16.96.116`); typed values are also extracted into
`entities` (`ip:…`, `path:…`, `uuid:…`, `url:…`). Latency per tool: [`docs/PERFORMANCE.md`](docs/PERFORMANCE.md).

## Roles (database-enforced access)
`load/99_roles.py` creates `logs_engineer`, `logs_lead` (may create focus indexes), `logs_manager` (read-only, no
workspace) and one `team_<team>` role per team in the ownership table. SereneDB has PostgreSQL roles and grants but no
row-level-security policies, so a team role reads views named `logs`, `patterns`, `bursts`, … in its own schema that
contain only its components; with `LOGS_DB_ROLE=team_web_platform` the unchanged tools see only that team's rows and
are refused (not leaked) everything else.

## Agent (`agent/`, LangGraph)
```
            ┌─► gather_engineer ─┐
  route ────┼─► gather_lead ─────┼─► handover ─► composer ─► END
            └─► gather_manager ──┘               (compose ─► check ─► revise ≤ 1 ─► Jev support)
```
Each `gather_<role>` is a prebuilt ReAct agent (LangChain `create_agent`) with the role's tool subset (engineer 14,
lead 13, manager 10 of the 40 tools), its evidence recipe and two middlewares: **CoverageMiddleware** (role checklist,
sends the model back while required evidence is missing) and **ToolCallLimitMiddleware**. The corpus description in
the prompts is built from the dataset registry. The **composer** subgraph only sees the evidence ledger.
- **route:** role given, or picked by **Jev** (calibrated choice, run inside SereneDB); LLM fallback.
- **composer → check:** deterministic **claim checker** (every number must be in a result the item cites, no invented
  money / downtime / impact, role checklist; one revision round). **Confidence = computed**, never self-reported.
- **Jev support:** for every fact of the final card, a calibrated probability that its cited evidence supports it
  (one `ai_system_one` query inside SereneDB), shown next to the fact.
- **Baseline:** the brief's reference design: `create_agent` with every read-only tool and a plain role prompt.
- **Tracing:** one LangSmith trace per question, with route, evidence ids, numbers verified, confidence, revisions.

## Evaluation (ours vs the reference ReAct agent with the same tools)
`.venv/bin/python -m eval.run_eval` runs both systems on 25 dev questions (10 engineer, 8 lead, 7 manager; 5 of them
on Zookeeper, Apache, OpenSSH, HDFS and the OTel slice) as LangSmith experiments, with deterministic metrics (golden
facts from hand-checked SQL incl. the manager's computed ranking order, numbers found in the evidence, tool use,
forbidden claims, cost), a Jev support probability per fact, and an Opus judge (claim support against the full
evidence, role rubric, pairwise in both orders). A failed run scores 0. Details and the noise floor: `docs/EVAL.md`;
latest reports: `eval/results/20261018-043511.md` (25 questions, ours vs the previous version and the baseline),
`eval/results/20261018-044019.md` (the 5 new-dataset questions, both systems fresh).

| Metric (25 dev questions; baseline = the 20 BGL / OpenStack ones) | ours | baseline |
|---|---|---|
| E1 golden facts in the answer (± 0.05 run-to-run) | **0.87** | 0.69 |
| E2a numbers found in the run's own tool results | **1.00** | 0.85 |
| E2b numbers found in the result the fact cites (ours) | **1.00** | — |
| E2c claims supported by the evidence (judge) | **0.95** | 0.71 |
| E2d Jev: fact supported by its cited evidence (mean p, ours) | 0.68 | — |
| E3 causes stated as fact, per answer (judge) ↓ | **0.24** | 0.39 |
| E3 states what the logs cannot establish | **1.00** | 0.11 |
| E5 invented money / downtime / impact (regex + judge + must_not) | 0 | 0 |
| E7 required tools called · valid first tool | **1.00 · 1.00** | 0.83 · 0.83 |
| Q rubric mean 1-5 (judge) | **4.57** | 3.96 |
| Q role fit 1-5 (judge) | **4.88** | 4.11 |
| Q next-step specificity 1-5 (judge) | **4.44** | 2.61 |
| Q pairwise vs baseline, both orders, consistent wins | **16** | 1 (1 inconsistent) |
| Q pairwise vs our previous version (8 tools) | **14** | 4 (2 inconsistent) |
| E4 tool overlap between roles on the same topic ↓ | **0.02** | 0.28 |
| E4 evidence overlap between roles on the same topic ↓ | **0.015** | 0.04 |
| E8 seconds per answer (of which inside tools) ↓ | 36 (0.3) | **13** (0.2) |
| E8 input / output tokens ↓ | 94k / 4.8k | **33k / 1.6k** |

New datasets only (5 questions, both systems fresh): pairwise **4-0** (1 inconsistent), claims supported 0.98 vs 0.73,
numbers grounded 1.00 vs 0.77, next-step specificity 4.4 vs 2.8.

Dev questions were written by us after seeing the data; a separate human-written private question set exists (its
runner prints aggregates only).

## Worked investigation
_Coming soon._

## Known limitations
- **Problem detection is pattern-level.** A pattern counts as a problem when it has problem-level lines (error-or-worse,
  WARN, HTTP 5xx, or no level) and the stored Jev judgment says fault or security event. Anomalies that are *sequences*
  (a missing step, as in HDFS blocks) are not errors: on HDFS the filter finds anomalous blocks at 5.5 % precision vs a
  2.9 % base rate (3 of its 4 problem patterns are 96–100 % precise; one frequent WARN pattern is not).
- **Template mining is regex + a Drain-lite pass**, not Drain: good on the 7 datasets here (BGL 1,126, OTel 1,426
  patterns), but a new format with many free-text fields may need one more mask in `lib/stage_to_logs.sql`.
- **Spread needs a node field.** Zookeeper and Apache log no host: `nodes = 0` means unknown (tools say so).
- **SereneDB behaviours we work around** (all documented in `docs/PERFORMANCE.md`): facet counts from the term
  dictionary were off by one when a segment was split across threads (we set `sdb_scan_split = 'never'`); bound text
  arguments to `ts_*` constructors failed next to timestamp parameters (we inline quoted literals); an index on a view
  over a search table is not supported (focus indexes copy the window into their own search table); BM25 does not work
  through a view (team-scoped search orders by time); no row-level-security policies (roles + views instead).
- **Remote sampling** (`USING SAMPLE`) disabled the time-filter pushdown on remote Parquet (392 s vs 32 s exact), so
  remote tools count exactly over pruned row groups and refuse windows over 10 minutes unless indexed.
- **Model text** (burst summaries) is context, never evidence: the checker ignores it and the tools label it.

## Citation
Zhu et al., *Loghub: A Large Collection of System Log Datasets for AI-driven Log Analytics*, ISSRE 2023.
Oliner & Stearley, *What Supercomputers Say: A Study of Five System Logs*, DSN 2007.
