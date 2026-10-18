# Making Sense of Logs: the right insights for the right people

SchubKI National AI Hackathon 2026 · SereneDB challenge · Amirali, Konark

> SereneDB searches and counts, Jev judges which messages are real faults, Claude explains, and every number in an
> answer traces back to the query that produced it.

**For judges:** [try it step by step](docs/TRY_IT.md) · [demo script](docs/DEMO.md) · [worked investigation](docs/INVESTIGATION.md) · [eval dashboard](docs/dashboard.html) (download and
open) · [all tools](docs/TOOLS.md) · [slides](docs/slides/making-sense-of-logs.pptx)

## Workflow
**Question → evidence → recommendation.** You ask Claude a question about the logs. Claude calls our MCP tools, and
each tool is a fixed, parameterised SereneDB query (full-text search, nearby events, counts, trends, rankings). Each
result carries its SQL, filters, scope, exact total and a truncation flag. Claude then answers for the role, with
facts, a labelled hypothesis, the unknowns and a next step:

| Role | Asks | Gets |
|---|---|---|
| Engineer | What failed, where, what happened before and after? | the matching lines, the events around them, how far it spread, a next check |
| Team lead | What recurs, how often, and whose is it? | recurring problems over a stated period, counts and trends by team (ownership table) |
| Manager | What deserves attention first? | a computed priority ranking with owners and actions; never cost, downtime or impact |

## Setup (clean checkout)
Needs [Docker](https://docs.docker.com/get-docker/), [uv](https://docs.astral.sh/uv/) and
[Claude Code](https://claude.com/claude-code). No API keys are needed for the base corpus.
```bash
git clone https://github.com/aircode610/making-sense-of-logs-schubki-ai-hackathon
cd making-sense-of-logs-schubki-ai-hackathon
docker compose up -d     # SereneDB 26.10.1 on localhost:7890
uv sync                  # Python 3.12 + the server's dependencies (optional: `uv run` also does it on first start)
claude                   # approve the MCP server "logs" when asked
```
Then tell Claude: **"Load the base corpus"**. BGL and OpenStack are downloaded from the brief's Zenodo links and
loaded by our loader (`src/sql/`) in 72 s, with the committed Jev outputs. To run the whole pipeline live, Jev
included: `uv run python -m loader load base --fresh` (about 2 min; needs a key, see [Keys](#keys-env)).

| Also | Command |
|---|---|
| Our own agent, the eval | `uv sync --extra agent` (keys: see below) |
| Use the server from any folder | `claude mcp add -s user logs -- uv run --directory "$PWD" python src/mcp_server/server.py` (run in the repo) |
| Any other MCP client | stdio command `uv run --directory <repo> python src/mcp_server/server.py` |
| Load without Claude | `uv run python -m loader load base` |

Apple Silicon runs the amd64 image under emulation: it works, slower.

## Keys (`.env`)
**None are needed to try it:** the base corpus loads with its committed Jev outputs, and every tool works.
Keys only matter when you load data **live** (`--fresh`, your own log files, other Loghub sets) or run our agent / the eval.
`cp .env.example .env`, fill what you need. The server registers the AI keys in SereneDB itself on start.

| Key | Used for | Without it |
|---|---|---|
| `TYPESAFE_API_KEY` | **Jev** at load time: real fault or routine, kind, security threat, cause, owner and area per kind of message | Loading still works. Problems are judged by **log level only** (stated in every result), which is less accurate: real alerts in the top 10 drop from 5 to 1 on BGL. Logs without levels (e.g. SSH) then have no problem patterns: rankings come back empty, search and counts still work. |
| `GOOGLE_API_KEY` | Gemini **embeddings** of message templates at load time (semantic / hybrid pattern search) | `find_patterns` falls back to word (lexical) search; `similar_patterns` says it has no vectors. Everything else is unaffected. |
| `ANTHROPIC_API_KEY` | **our own LangGraph agent** and the **evaluation** (agents + Opus judge) | Not needed for the MCP server with Claude Code (Claude Code uses your own Claude login). |
| `LANGSMITH_*` | optional tracing of our agent | no traces |
| `PG*` | the SereneDB connection (default `localhost:7890`) | defaults are used |

| You want to | Keys |
|---|---|
| Try it with Claude Code on the base corpus | none |
| Run the full pipeline live: `uv run python -m loader load base --fresh` | `TYPESAFE_API_KEY` (+ `GOOGLE_API_KEY` for semantic search) |
| Load your own log file (*"Load ~/logs/app.log"*) | `TYPESAFE_API_KEY` recommended (+ `GOOGLE_API_KEY`) |
| Run our agent or the evaluation | `ANTHROPIC_API_KEY` (+ `uv sync --extra agent`) |

## Run it
Ask in plain words:
- *"What failed on the R43-M0 midplane around 2005-08-19 13:56, and what happened just before and after?"*
- *"Which problems recurred most in November 2005, and which teams own them?"*
- *"Based on November 2005, what deserves attention first?"*

Or use a prompt: `/mcp__logs__worked_investigation` (one topic, all three roles). At the end Claude gives a link to the
**session report**: a local page where every number is linked to the query behind it, with a **Verify** button that
re-runs the query. To load your own logs, tell Claude *"Load ~/logs/app.log"* (the format is detected automatically).

## Tools
One MCP server ([`src/mcp_server/`](src/mcp_server/)) with **44 tools, 5 prompts, 6 resources** and argument completions.
The full list with inputs and outputs is in [`docs/TOOLS.md`](docs/TOOLS.md), generated from the server itself.

| Need | Main tools |
|---|---|
| Search (full text, time filters, phrase / fuzzy) | `search_logs`, `find_patterns`, `suggest_terms` |
| Nearby events | `get_context`, `burst_timeline`, `request_timeline`, `precursors` |
| Counts and trends | `count_by` (component / team / severity …), `trend`, `rollup`, `heatmap`, `rate_vs_baseline` |
| Recurring problems | `top_patterns`, `pattern_history`, `spread`, `whats_new` |
| Priorities | `priority_table`, `reliability_trend`, `team_risk`, `owner_of` |
| Setup | `load_logs`, `setup_status`, `use_dataset`, `session_report` |

- **Prompts:** `investigate_failure`, `review_recurring_problems`, `set_priorities`, `worked_investigation`,
  `whole_corpus_counts`.
- **Resources:** `logs://datasets`, `logs://glossary`, `logs://ownership/bgl`, `logs://field-guide/openstack`, … (templates per dataset),
  `logs://session/latest`.
- **Limits:** results return at most 50 rows, and the totals are always exact over all matches.

## Worked investigation
[`docs/INVESTIGATION.md`](docs/INVESTIGATION.md) · evidence page [`docs/investigation/report.html`](docs/investigation/report.html) (opens offline)

**Topic:** the rank-1 problem in BGL, November 2005: a new fault, *"ciod: … Link has been severed"*.

| Role | Evidence (tools) | Answer | Next step |
|---|---|---|---|
| Engineer | full-text search, burst timeline, top IPs | 12,996 lines on 1,024 nodes, all to one host; 64 job launches failed 21 min before | check host 172.16.96.116 at 05:30–05:40 |
| Team lead | top patterns, rollup by team, trend, owner | 451 problem bursts (node-platform 283); this fault: 31 bursts, owner disputed | both teams triage it together |
| Manager | priority ranking, reliability trend | rank 1 of 133 (score 97.8); problem bursts per week 69.6 → 119.3 | name one owner now |
| Whole corpus | count by team, per dataset | BGL 4,747,963 lines · OpenStack 207,820 lines | |

- **Checked:** 20 tool calls, 1.8 s in SereneDB, 62 / 62 numbers traced to a query, 17 / 17 steps re-run identically.
- **Not established:** the cause (the host's own logs are not in the corpus), and any cost or downtime.

## Evaluation
50 questions with frozen answer keys, 9 datasets, 3 roles, a blind Opus judge in both answer orders.
Every answer and verdict: [dashboard](docs/dashboard.html).

| | Claude Code + our MCP vs plain Claude Code | Our agent vs the brief's reference agent |
|---|---|---|
| Wins (all 50) | **30 – 15** | **16 – 12** |
| Wins on BGL + OpenStack | **18 – 4** | **13 – 2** |
| Wrong claims | **116 vs 186** | **53 vs 69** |
| Seconds per answer | **14 vs 86** | 44 vs 22 |
| Where it loses | engineer questions on small logs (8 – 9) | manager questions on small datasets (2 – 6) |
| Re-run | `uv run python -m evals.cc_ab` | `uv run python -m evals.ab --arms product,baseline` |

## Known limitations
- The logs hold no cost, downtime or customer impact, so answers say so instead of estimating them.
- Claude Code + our server answers in ~14 s (vs 86 s on raw files); our LangGraph agent takes ~44 s. Almost all of it
  is LLM time; the database takes < 1 s.
- Plain Claude Code still wins some engineer questions on small logs (9 to 8), where grep can read every line.
- New log files without a `TYPESAFE_API_KEY` judge problems by log level only, which is less accurate.
- Line counts are not incident counts: tools count recurrences ("bursts") separately.
- The tools show what happened, not why: causes are labelled as hypotheses.

## Repository layout
| Path | What |
|---|---|
| `src/mcp_server/` | the MCP server: 44 tools, prompts, resources, session report |
| `src/loader/` · `src/sql/` | loading: download, format detection, SQL parsers, per-dataset build, live Jev |
| `src/formats/` | 76 lnav log format definitions (format detection) |
| `src/agent/` · `src/evals/` · `src/bench/` | our LangGraph agent, the evaluation harness, checks and benchmarks |
| `src/scripts/` | Jev / embedding generators, dashboard and report builders, data download |
| `data/config/` · `data/jev/` | inputs (ownership, catalog, severity map …) · committed Jev outputs (`--fresh` ignores them) |
| `data/raw/` | downloaded logs (never committed) |
| `eval/` | questions, answer keys, results |
| `docs/` · `plans/` | documentation, dashboard, slides · one plan per piece of work |

More detail (data, schema, agent, roles, performance, huge datasets): [`docs/TECHNICAL.md`](docs/TECHNICAL.md).

## Citation
Zhu et al., *Loghub: A Large Collection of System Log Datasets for AI-driven Log Analytics*, ISSRE 2023.
Oliner & Stearley, *What Supercomputers Say: A Study of Five System Logs*, DSN 2007.
