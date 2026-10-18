# Technical reference (the full former README)

SchubKI National AI Hackathon 2026 · SereneDB challenge · Team: Amirali, Konark.

> **SereneDB counts, Jev judges, the LLM explains — and every sentence is checked against the query that produced it.**

One MCP server that sets itself up: load the base corpus or your own logs from Claude, then 40 analysis tools over
SereneDB for three roles (44 tools in all, with setup and the session report), 5 prompts, 6 resources.

**For judges, three links:**
- **[Worked investigation](INVESTIGATION.md)**: one real problem seen by the three roles, with tool calls, SQL and
  results. Its evidence page [`docs/investigation/report.html`](investigation/report.html) works offline: every
  number is linked to its step, and every step shows its re-run result.
- **[Eval dashboard](dashboard.html)** (download and open; GitHub shows the source): 50 golden questions, our
  agent vs the brief's reference design, a blind Opus judge, every answer and verdict, and how to re-run it.
- **[Tools, prompts, resources](TOOLS.md)**: generated from the server's own MCP listing.

## Workflow
Question → evidence (SereneDB full-text search + aggregations, via MCP tools) → recommendation (agent), for three roles:
**engineer** (what failed, where, what happened around it), **team lead** (what recurs, how often, which teams),
**manager** (what to prioritise and why, from measured frequency and spread only).

## Setup (clean checkout): 2 commands, then ask Claude
Requirements: [Docker](https://docs.docker.com/get-docker/), [`uv`](https://docs.astral.sh/uv/) (it installs Python
3.12 and the server's two dependencies on first start), [Claude Code](https://claude.com/claude-code). No `psql`, no
keys needed for the base corpus.
```bash
git clone https://github.com/aircode610/making-sense-of-logs-schubki-ai-hackathon && cd making-sense-of-logs-schubki-ai-hackathon
docker compose up -d          # SereneDB 26.10.1 on localhost:7890 (the organisers' version)
claude                        # in this folder: approve the project MCP server `logs` (.mcp.json) when asked
```
Then, in Claude: **"Load the base corpus"**. Claude calls `load_logs(source='base')`: BGL and OpenStack are downloaded
exactly as the brief says (`curl -L "https://zenodo.org/records/8196385/files/<file>?download=1"`, into `data/raw/`),
parsed by SereneDB with our loaders ([`load/`](../load/)), and get their stored Jev judgments (committed CSVs, so no key).
Measured on a clean clone (MacBook, Apple Silicon, emulated amd64 image): **72 s** from the request to both datasets
loaded (BGL 4,747,963 lines, OpenStack 207,820 lines), 34 s when the raw files are already downloaded. Then ask the
three roles' questions (examples below). `setup_status` shows the database, the loaded datasets and a running load.

**Your own logs:** "Load ~/logs/app.log" → `load_logs(source='~/logs/app.log')`: the file is streamed into SereneDB
from wherever it is (`COPY … FROM STDIN`), its format detected from the 76 vendored
[lnav format definitions](../formats/lnav/) (≥ 95 % of a 2,000-line sample, else nothing is loaded and the closest formats
are listed: no guessed timestamps), only that dataset is built (other datasets untouched), and it becomes the active
dataset. With `TYPESAFE_API_KEY` in `.env` its patterns are judged by Jev inside SereneDB during the load (Proxifier,
21,329 lines: 1.6 s without Jev, 15 s with Jev + embeddings; live judgments vs the committed ones: correlation 0.996,
same problem decision on 287 / 287 patterns); without a key, problem tools fall back to log levels and say so in every
result. Other Loghub sets: `load_logs(source='zookeeper')` etc. (the brief's table, `data/catalog.csv`).

**One dataset at a time:** tools take no `dataset` argument; they work on the active dataset (the last loaded, or
`use_dataset(name)`). Whole-corpus questions: Claude switches and reports per dataset (the brief allows that).

**Session report:** at the end Claude gives a link (or ask *"show me the session report"*): a local page with the
answer, every tool call (what it found, time inside SereneDB, the SQL, the dataset it ran on) and **Verify** buttons
that re-run each read step on a read-only connection and compare with what Claude saw. `http://127.0.0.1:8765/latest`
shows the session live. Session files: `runs/sessions/` (local). Port: `LOGS_REPORT_PORT`.

Options (`.env`, all optional; copy `.env.example`): `TYPESAFE_API_KEY` (Jev on new data), `GOOGLE_API_KEY`
(embeddings for semantic pattern search on new data), `ANTHROPIC_API_KEY` (our own agent). The server registers the
keys in SereneDB itself on start (no `docker/secrets.sh` step). Another port: `SERENEDB_PORT=7891 docker compose up -d`
and `PGPORT=7891`. From any folder (user scope):
`claude mcp add -s user logs -- uv run --quiet --directory "$PWD" python mcp_server/server.py` (run in the repo).
Any other MCP client: stdio command `uv run --directory <repo> python mcp_server/server.py` (DB via `PGHOST` /
`PGPORT` / `PGUSER` / `PGDATABASE`, default `localhost:7890`; `LOGS_DATASET=<name>` = the dataset active at start;
`LOGS_DATASET='*'` = the multi-dataset server where every tool takes `dataset`, used by our eval harness;
`LOGS_DB_ROLE=logs_manager` or `team_<team>` = database-enforced access, see Roles).

Apple Silicon: SereneDB 26.10.1 is published for linux/amd64 only; `docker compose` runs it under emulation (works,
slower; a plain `docker pull` without `--platform linux/amd64` fails). Any Linux x86-64 machine runs it natively.

### Without Claude: the same loader as a CLI
```bash
uv run python -m loader load base                       # = load_logs(source='base'); also: bgl, openstack, zookeeper, …
uv run python -m loader load ~/logs/app.log --name app  # any file
uv run python -m loader status | remove <name> | reload # reload = drop + rebuild every dataset whose raw file exists
./load/reload.sh                                        # reload + checks (every tool vs independent SQL)
```
How a dataset is built (one code path for the MCP tool, the CLI and the full reload): `load/00_schema.sql` +
`load/01_derived.sql` once (tables, dictionaries, generic mask + entity macros) → the dataset's loader (`load/10_bgl`,
`20_openstack`, `30_zookeeper`, …, or a generated one from format detection; each hand-written one is one parse query
+ `\ir lib/stage_to_logs.sql`) → `VACUUM` refresh → [`load/lib/build_dataset.sql`](../load/lib/build_dataset.sql) for that
dataset only (example values, episodes / bursts / patterns, stored Jev judgments + traits + areas, pattern index,
then [`lib/ownership_dataset.sql`](../load/lib/ownership_dataset.sql): curated owners + Konark's inference chain, plan
057) → macros, roles. The SQL files are run by [`loader/sqlrun.py`](../loader/sqlrun.py) (the psql features they use:
`\set`, `\ir`, `\if`); `psql -f` runs them too. A per-dataset build equals the old whole-corpus build (all derived
tables identical on 8 datasets, plan 016). Everything AI-generated for our datasets is committed
(`data/pattern_judgments_*.csv`, `pattern_traits_*.csv`, `component_areas_*.csv`, `pattern_vectors*.parquet`,
`burst_summaries.csv`); regenerate with `scripts/judge_patterns.sh <ds>`, `judge_traits.py`, `judge_areas.py`,
`embed_patterns.py`, `summarize_bursts.py` (all run their AI calls inside SereneDB). A new format that lnav does not
know = a hand-written `load/3x_<name>.sql` (parse query into `stage` + `\ir lib/stage_to_logs.sql`, one sentence per
filled field, e.g. `\set request_meaning 'trace id …'`) + a row in `data/catalog.csv`; no tool, agent or eval code
changes (CLAUDE.md rule 11; `bench/lint_generic.py` enforces it). Or replay any dataset as OpenTelemetry into
SereneDB's built-in OTLP receiver: `uv run python scripts/otlp_replay.py <dataset> 2000`.

### Our own agent (second path; the brief accepts an existing agent such as Claude)
`uv sync --extra agent` once; needs `ANTHROPIC_API_KEY` in `.env` (LangSmith tracing if `LANGSMITH_*` are set):
```bash
uv run python -m agent.run --role engineer "What failed on the R43-M0 midplane around 2005-08-19 13:56, and what happened just before and after?"
uv run python -m agent.run --role lead "Which problems recurred most in November 2005 (2005-11-01 to 2005-11-29), and which teams own them?"
uv run python -m agent.run --role manager "Based on November 2005, which problems deserve attention first and what should happen next?"
uv run python -m agent.run --role engineer "Which IP addresses drove the failed root logins on the SSH server in the first week of January 2018?"
uv run python -m agent.run "Is the rts panic problem getting worse in November 2005?"   # no --role: Jev routes the question
uv run python -m agent.run --baseline --role manager "…"                                # the reference ReAct agent
```
Each run prints the answer card + evidence (SQL) + the LangSmith trace URL, and saves `runs/agent/<time>-<kind>-<role>.json`.

The same questions as SQL (table macros, `load/98_macros.sql`): `logs_count`, `logs_search`, `problem_patterns`,
`team_problem_bursts`, `pattern_weeks`, `top_values`, `nearest_before`, e.g.
`SELECT * FROM problem_patterns('bgl', TIMESTAMP '2005-11-01', TIMESTAMP '2005-11-29');`

## Data
| Dataset | Lines | Span | What it is | Location / ids |
|---|---|---|---|---|
| `bgl` | 4,747,963 | 214 days | Blue Gene/L supercomputer RAS events | rack / midplane / node |
| `openstack` | 207,820 | 3 days | nova API / compute / scheduler | request id, VM (`object_id`), tenant entity, HTTP status, durations |
| `zookeeper` | 74,380 | 27 days | ZooKeeper ensemble member (Java) | class / thread |
| `apache` | 56,482 | 264 days | Apache httpd error log | client IPs as entities |
| `ssh` | 655,147 | 28 days | OpenSSH auth log of an internet-facing host | host, session (`sshd-<pid>`), attacker IPs |
| `hdfs` (opt.) | 11,175,629 | 39 hours | Hadoop HDFS NameNode / DataNodes | block id (`blk_…`), datanode IPs |
| `otel` (opt.) | 1,702,944 | 30 min (sampled) | OpenTelemetry demo webshop (slice of 1 B remote records) | k8s namespace / node / pod, TraceId |
| `linux` (opt.) | 25,567 | 264 days | syslog of one Linux server (unseen-dataset test) | host, `<program>-<pid>`, attacker IPs |
| `healthapp` (opt.) | 253,395 | 11 days | Android health app (unseen-dataset test) | app module, process id |
| `android` (opt., auto-detected) | 1,555,005 | — | Android framework logcat (format detected from lnav, plan 057) | tag → component, pid |
| `proxifier` (opt., auto-detected) | 21,329 | — | Proxifier proxy client log (format detected from lnav, plan 057) | app → component, app pid |

All from Loghub (BGL, OpenStack, Zookeeper, Apache, OpenSSH, HDFS, Linux, HealthApp) and the public OpenTelemetry
`text_bench` Parquet. One generic schema: `node`, `location` (path, any level), `request_id`, `object_id`, `status`,
`duration_ms`, `entities`; what each means per dataset is a row of the `datasets` table. **`severity_number`** (plan 057):
one level scale for every format, the OpenTelemetry SeverityNumber (TRACE 1, DEBUG 5, INFO 9, WARN 13, ERROR 17,
FATAL 21–24) mapped from the raw `severity` word by `data/severity_map.csv` (OTel data model, RFC 5424, Java logging,
lnav words; e.g. BGL SEVERE → 18, FAILURE → 21, Apache NOTICE → 10, OpenStack CRITICAL → 22); NULL when the format
has no level (SSH, Linux, HealthApp). Informational: the problem rule still uses the raw level (DECISIONS H22).
See [`data/README.md`](../data/README.md). Ownership (fictional, documented per row): [`data/ownership.csv`](../data/ownership.csv).
**Ownership table (plan 057):** `ownership(dataset, component, team, description, area, area_source, area_confidence,
source, confidence, disputed_by, dispute_confidence)`, one row per component that has an owner. `source` = `curated`
(1.0) / `curated default` (`*` row, 0.95) / `jev owner_hint` (Jev picks among the dataset's curated teams) / `rule: …`
(public name list → area → team in `data/area_teams.csv`, 0.9) / `jev area` (Jev picks the area, p ≥ 0.6). Curated
rows always win; `disputed_by` flags a curated owner contradicted by confident Jev hints (p ≥ 0.8) for most of the
component's lines; inferred owners below 0.6 are not stored (the component stays `unowned`).

## Tools (44 in one MCP server, plus prompts and resources)
MCP server [`mcp_server/`](../mcp_server/) (FastMCP), written to be handed to ANY agent (Claude Code, our agent, another
LLM) with a free-form question (plan 012): no roles in the server, nothing dataset-specific in its code.
- **Descriptions follow one template**: the question the tool answers, *Use when*, *Not for* (names the better
  sibling tool), *Returns*, *Caveats*, *Example*, *Next* (which ids to pass on). Shared parameters (node, location,
  request_id, object_id, …) are described once in `core.py`.
- **Server instructions** (shown by MCP clients) = the investigation loop (orient → anchor → widen → check), the ids
  that flow between tools, the glossary (line, pattern, burst, episode, problem pattern), and a **field guide**
  generated from the data: per dataset its span, levels, components, teams, and what node / location / request_id /
  object_id / status / duration / entities mean there with a real example value.
- **Results suggest the next step** (`hints`): 0 matches → fuzzy / synonyms / suggest_terms; an unknown component or
  level → the closest real values; a sample → the counting tools; found patterns → their history / spread / precursors.
- **Prompts** (slash commands in Claude Code: `/mcp__logs__<name>`): `investigate_failure`, `review_recurring_problems`,
  `set_priorities` (one per role), `worked_investigation` (one topic, three roles, step-cited facts) and
  `whole_corpus_counts` (one `count_by` per loaded dataset, reported together). Arguments complete from the data
  (dataset, component, team, severity).
- **Resources** (`@logs:<uri>` in Claude Code): `logs://datasets`, `logs://glossary`, `logs://field-guide/{dataset}`,
  `logs://ownership/{dataset}`, `logs://session/latest` (every call so far with its SQL, totals, truncation) and
  `logs://session/{sid}/step/{n}` (one step in full). Tools return ≤ 50 rows; the full evidence trail is a resource.
- Full reference (purpose, inputs, outputs of every tool): [`docs/TOOLS.md`](TOOLS.md), generated by
  `scripts/tools_doc.py` from the live server.
- Checked: `bench/check_tools.py` runs every tool on every loaded dataset against independent SQL (tool × dataset
  matrix); `bench/lint_generic.py` (no dataset values in code, template complete, definitions ≤ 36k tokens);
  `bench/tool_use.py` (role-free benchmark: a plain agent with only this server, Opus and Sonnet) and
  `bench/claude_code_run.py` (Claude Code itself, headless, with only this server).

Every tool is a fixed, parameterized SereneDB query: the LLM only fills typed fields (dataset names are an enum of the
loaded datasets). Every result is an **envelope**: `tool`,
`params`, `sql` (the exact queries that ran, values inlined), `filters`, `scope`, `total_matches`, `truncated`,
`elapsed_ms`, `evidence_id`, plus rows (≤ 50, messages cut at 300 chars). Totals are computed over all matches, never
from a sample. `explain_tool` shows any tool's query plan.

| Group | Tools (what they answer) | SereneDB features |
|---|---|---|
| Discover | `ingest_report` (how an auto-detected dataset's format was found and how much matched), `describe_corpus` (what is loaded), `list_values` (valid filter values), `suggest_terms` (spelling), `explain_search` (why a search matches) | term dictionary (`ts_dict_*`), `ts_lexize`, `EXPLAIN` |
| Search | `search_logs` (match = web / all / any / phrase / near / fuzzy / prefix / at_least / synonyms, `exclude_text`, `highlight`, `order` incl. BM25 × recency decay, `location` at any level, `entity`), `get_context` (before / after on node / location at any level / component / request / object) | inverted index, `ts_phrase(slop)`, `ts_levenshtein`, `ts_any(min_match)`, synonyms dictionary, `ts_highlight`, BM25, `expand_path` |
| Breakdowns | `facet` (one-pass breakdown of a search), `distinctive_terms` (significant terms: what is different in a window), `top_entities` (top IPs / paths / ids), `check_watchlist` (saved searches that fired) | `GROUPING SETS`, term dictionary, extracted entities |
| Counts | `count_by`, `trend`, `rate_vs_baseline`, `value_outliers` | aggregates, zero-filled `generate_series`, median / MAD |
| Ownership | `owner_of` (who owns a component, source + confidence, dispute), `ownership_gaps` (unowned / inferred / disputed components with their lines) | curated table + rules + Jev area / owner hint (plan 057) |
| Patterns | `top_patterns`, `priority_table`, `pattern_history` (new or recurring), `whats_new` | patterns / bursts tables, `cume_dist`, stored Jev judgments |
| Timeline | `burst_timeline` (which error came first), `spread` (one node or fleet-wide), `precursors` (what comes before, with a control), `co_occurrence` (together, with a control), `periodicity` (on a schedule?), `request_timeline` (one request / session / block end to end) | window functions, **ASOF join**, `approx_top_k`, `entropy` |
| Analytics | `rollup` (subtotals), `heatmap` (team × week matrix), `reliability_trend` (slope + rule), `latency_profile`, `team_risk` | `ROLLUP`, `PIVOT`, `regr_slope`, `quantile_cont` |
| Semantic | `similar_patterns`, `find_patterns` (lexical / semantic / hybrid RRF), `summarize_burst` (model text, labelled) | `ai_embed` (Gemini), IVF vector index, RRF, `ai_summarize_agg` |
| Workspace | `create_focus_index` / `drop_focus_index` (index an investigation window, measured break-even), `index_stats`, `explain_tool` | search tables, inverted index, `sdb_metrics`, `EXPLAIN` |
| Remote | `remote_describe`, `remote_count_by`, `remote_search`, `remote_index` (the 1 B-record OTel Parquet on S3, in place) | `read_parquet` over HTTPS, row-group pruning, index on a view over remote files |

Numbers and dotted ids are whole search tokens (`503`, `172.16.96.116`); typed values are also extracted into
`entities` (`ip:…`, `path:…`, `uuid:…`, `url:…`). Latency per tool: [`docs/PERFORMANCE.md`](PERFORMANCE.md).

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

## Evaluation: 50 golden questions, blind judge
**Dashboard: [`docs/dashboard.html`](dashboard.html)** (every question, both answers, the judge's reasons, how
to re-run). The final run is `eval/results/ab-20261018-193248.md`.

**Setup.** 50 questions over 9 datasets for three roles (21 engineer, 15 lead, 14 manager; 6 have a false premise).
Each has a **frozen answer key** (`eval/answer_keys/*.yaml`): the true answer, the SQL that establishes it, its
result, and the traps. Agents without context built the keys from raw SQL and Loghub's labels. **Our agent** (the
LangGraph role recipes, coverage checks and claim checker) runs against **the brief's reference design** (a ReAct
agent with the same MCP tools and a plain role prompt). Both use Sonnet 5.5, on a server pinned to the question's
dataset. The **judge** is an Opus agent with read-only SQL. It grades both answers against the key, blind: tool names
and evidence ids are stripped, a leak scan runs, and the answer order is seeded-random. It judges every pair twice
with the order swapped, and only wins where both orders agree are counted.

| Result (`eval.ab --arms product,baseline`) | Our agent | Reference ReAct |
|---|---|---|
| Order-consistent wins, all 50 | **16** | 12 (9 tie, 13 inconsistent) |
| … on the base corpus (BGL + OpenStack, 23 q) | **13** | 2 (4 tie, 4 inconsistent) |
| … engineer questions (21 q) | **10** | 2 |
| … manager questions (14 q) | 2 | **6** |
| Wrong claims over all answers (judge vs key + SQL) ↓ | **53** | 69 |
| Claim accuracy | **94.5 %** | 92.7 % |
| Golden facts mentioned | **0.84** | 0.71 |
| Role rubric 1-5 (fit, next step, evidence, separation, clarity) | **3.79** | 3.52 |
| Found the key's answer 0-2 | 1.50 | 1.53 |
| Seconds per answer (inside SereneDB) ↓ | 44 (0.48) | **22** (0.30) |

**Reading.** We are clearly better on the base corpus and for the engineer. Overall we make fewer wrong claims at about
twice the latency, and the time goes to the LLM, not to SereneDB. The reference agent wins more manager questions on
the 7 extra datasets. Our manager recipe always starts from the computed priority ranking, but on a small log with one
problem, a free search goes deeper into that problem. That is the next thing to fix. The 3 OTel questions scored 0 for
both systems, because the optional OTel slice was not loaded for this run.

**How we got here** (each step is a committed run; see the dashboard):
| Step | Measured | Source |
|---|---|---|
| Severity alone as the problem signal → Jev judgment per pattern | real alerts in the priority top 10: 1/10 → **5/10** | `plans/006-…` |
| Our agent vs reference, 25 dev questions (earlier judge) | claims supported 0.95 vs 0.71, next-step 4.4 vs 2.6, pairwise 16-1 | `eval/results/20261018-043511.md` |
| 40 tools vs the first 8, same agent, 50 golden questions | 19-11, wrong claims 53 vs 64 | `eval/results/ab-20261018-144958.md` |
| Plan-014 fixes (one dataset per server + 8 gaps) | 17-6, wrong claims 34 vs 60 | `eval/results/ab-20261018-155748.md` |
| Final: our agent vs the reference design | 16-12; base corpus 13-2 | `eval/results/ab-20261018-193248.md` |

**Run it yourself** (needs `ANTHROPIC_API_KEY`; about 45 min for 50 questions):
```bash
uv sync --extra agent
uv run python -m loader load base     # + zookeeper apache ssh hdfs linux healthapp for the other questions
uv run python -m eval.ab --arms product,baseline --ids D-E01,D-L04   # smoke test, 2 questions
uv run python -m eval.ab --arms product,baseline                     # all 50
uv run python scripts/build_dashboard.py                             # rebuild docs/dashboard.html
```

### Earlier: 25 dev questions with deterministic metrics (`eval.run_eval`, LangSmith experiments)
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
**[`docs/INVESTIGATION.md`](INVESTIGATION.md)**: the rank-1 item of the manager's computed priority for November
2005 is a new ciod "Link has been severed" storm (12,996 lines on 1,024 BGL I/O nodes, all to one peer, 31 bursts).
The engineer gets its first burst and the 21 minutes before it, the lead gets recurrence by team and a disputed
owner, and the manager gets the computed top 3 with a decision. Plus whole-corpus counts by team for BGL and
OpenStack, and OpenStack's slow VMs. 20 tool calls; 62 / 62 numbers in the answer found in a result; 17 / 17 read
steps give the same result on re-run. Evidence: [`docs/investigation/report.html`](investigation/report.html)
(static export of the session report: `scripts/export_report.py <session> <out.html>`).

## Working with huge datasets (optional award)
| What | Data actually queried | Time | Notes |
|---|---|---|---|
| HDFS_v1 loaded by SereneDB | 11,175,629 lines, 1.58 GB | 47 s load | 575,061 blocks, 16,838 anomalous (= Loghub's labels) |
| 1 B-record OTel Parquet on S3, in place | `part_000` footer: 1,624 row groups | 0.6 s | no download: `read_parquet` over HTTPS |
| Remote count by service, 10 s window | 10 of 1,624 row groups (6.1 M rows) | 2.8 s | time-sorted file → row-group pruning |
| Remote inverted index over a 5 s slice | 2.8 M rows stay on S3 | build 1.1 s, search 0.94 ms (vs 281 ms scan) | **break-even after 4 searches** |
| Focus index, one BGL day | 5,692 rows copied | build 64 ms, 2.5 ms per search | break-even ~31 searches: the corpus index is already fast |

Remote tools refuse windows over 10 minutes unless indexed (sampling disabled the time pushdown: 392 s vs 32 s exact).
Details and every measurement: [`docs/PERFORMANCE.md`](PERFORMANCE.md).

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
- **Latency:** our agent takes ~44 s per answer vs ~22 s for the reference ReAct agent. About 90 % of that is LLM time,
  < 1 s is SereneDB. Claude + the MCP server answers in about the same time as the reference agent.
- **Manager answers on small single-problem logs:** the reference agent wins more of these (eval above). Our recipe
  starts from the computed ranking even when one problem dominates.
- **New data without a Jev key:** problem detection falls back to log levels (stated in every result), which is
  measurably worse (priority top 10: 1/10 real alerts vs 5/10 with Jev).
- **Apple Silicon:** SereneDB runs emulated (amd64 image), so loads are ~2× slower than on Linux x86-64.

## Citation
Zhu et al., *Loghub: A Large Collection of System Log Datasets for AI-driven Log Analytics*, ISSRE 2023.
Oliner & Stearley, *What Supercomputers Say: A Study of Five System Logs*, DSN 2007.
