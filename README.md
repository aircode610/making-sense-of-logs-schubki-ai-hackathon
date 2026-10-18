# Making Sense of Logs: the right insights for the right people

SchubKI National AI Hackathon 2026 · SereneDB challenge · Amirali, Konark

> SereneDB searches and counts, Jev judges which messages are real faults, Claude explains, and every number in an
> answer traces back to the query that produced it.

**For judges:** [worked investigation](docs/INVESTIGATION.md) · [eval dashboard](docs/dashboard.html) (download and
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
claude                   # approve the MCP server "logs" when asked
```
Then tell Claude: **"Load the base corpus"**. This downloads BGL and OpenStack from the brief's Zenodo links and loads
them with our loader (`load/`). It takes 72 s on a clean clone.

Other ways to connect:
- From any folder: run `claude mcp add -s user logs -- uv run --directory "$PWD" python mcp_server/server.py` in the repo.
- Any other MCP client: use the stdio command `uv run --directory <repo> python mcp_server/server.py`.
- The same loader without Claude: `uv run python -m loader load base`.

Apple Silicon runs the amd64 image under emulation. It works, but slower.

## Run it
Ask in plain words:
- *"What failed on the R43-M0 midplane around 2005-08-19 13:56, and what happened just before and after?"*
- *"Which problems recurred most in November 2005, and which teams own them?"*
- *"Based on November 2005, what deserves attention first?"*

Or use a prompt: `/mcp__logs__worked_investigation` (one topic, all three roles). At the end Claude gives a link to the
**session report**: a local page where every number is linked to the query behind it, with a **Verify** button that
re-runs the query. To load your own logs, tell Claude *"Load ~/logs/app.log"* (the format is detected automatically).

## Tools
One MCP server ([`mcp_server/`](mcp_server/)) with **44 tools, 5 prompts, 6 resources** and argument completions.
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
- **Resources:** `logs://datasets`, `logs://glossary`, `logs://field-guide/{dataset}`, `logs://ownership/{dataset}`,
  `logs://session/latest`.
- **Limits:** results return at most 50 rows, and the totals are always exact over all matches.

## Worked investigation
[`docs/INVESTIGATION.md`](docs/INVESTIGATION.md) covers a new fault in BGL in November 2005: "Link has been severed",
12,996 lines on 1,024 nodes, ranked 1st by the computed priority. It is seen by all three roles, with the tool calls,
the SQL and the results. It also has whole-corpus counts by team for BGL and OpenStack. 62 of 62 numbers trace to a
query. The evidence page ([`report.html`](docs/investigation/report.html)) opens offline.

## Evaluation
We tested on 50 questions with frozen answer keys, against the brief's reference design (a ReAct agent with the same
tools), with a blind Opus judge. On the base corpus we win **13 to 2**, on engineer questions **10 to 2**, and over
all 50 questions **16 to 12**. We make fewer wrong claims (53 vs 69). We lose on manager questions on small extra
datasets (2 to 6). Every answer is in the [dashboard](docs/dashboard.html); re-run with
`uv run python -m eval.ab --arms product,baseline`.

## Known limitations
- The logs hold no cost, downtime or customer impact, so answers say so instead of estimating them.
- An answer takes ~44 s (vs 22 s for the reference agent). Almost all of it is LLM time; the database takes < 1 s.
- New log files without a `TYPESAFE_API_KEY` judge problems by log level only, which is less accurate.
- Line counts are not incident counts: tools count recurrences ("bursts") separately.
- The tools show what happened, not why: causes are labelled as hypotheses.

More detail (data, schema, agent, roles, performance, huge datasets): [`docs/TECHNICAL.md`](docs/TECHNICAL.md).

## Citation
Zhu et al., *Loghub: A Large Collection of System Log Datasets for AI-driven Log Analytics*, ISSRE 2023.
Oliner & Stearley, *What Supercomputers Say: A Study of Five System Logs*, DSN 2007.
