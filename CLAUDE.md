# Making Sense of Logs — SchubKI National AI Hackathon 2026 (SereneDB challenge)

Team: **Amirali** (aircode610) + **Konark**. Public repo. Hackathon work days: Sat 17 + Sun 18 Oct 2026.

## 👉 START HERE: `docs/STATUS.md` (where we are, who does what, next steps)
Then, as needed: `docs/ROLES.md` (**what each role asks, evidence, answer**) · `docs/CHALLENGE.md` (brief + rubric +
checklist; verbatim original `docs/BRIEF.md`) · `docs/PERFORMANCE.md` (DB internals) · `docs/EVAL.md` (how we prove it) ·
`docs/INVESTIGATION.md` (worked investigation) · `docs/HELDOUT.md` (private eval plan) · `docs/DECISIONS.md`.

## Layout: code in `src/` (mcp_server, loader, agent, evals, bench, scripts, sql, formats); `data/config` + `data/jev` committed, `data/raw` never; eval data in `eval/`.

## Mode: HACKATHON (not production)
- **Minimal code that gets results.** Scripts over frameworks, one file over five, no abstractions "for later",
  no tests beyond the eval harness. Iterate on code until the result is there; delete what doesn't earn its place.
- **⚠️ Plan before every task (mandatory).** No code/data work without an approved plan: `plans/NNN-name.md` (copy
  `plans/TEMPLATE.md`, one screen), drafted by Claude, approved by Amirali or Konark. Deviation → stop, update the plan,
  re-approve. See `plans/README.md`. Plans stay short so the loop stays fast.
- **Results beat effort.** Every hour ask: does this move a rubric line (`docs/CHALLENGE.md` §Rubric)?
- **Novelty is the point.** The brief's reference design (ReAct agent + MCP SQL tools) is what every
  team builds; it is our **baseline**, not our product. We must show, with numbers, that ours is better.

## Non-negotiables (from the brief + our side-quest experience)
1. **Numbers come from SQL, never from a model.** Every number in an answer traces to an executed query (kept with its result).
2. **Every tool result states its query, filters, scope and whether it was truncated.**
3. **Facts / hypotheses / next steps are separated and labelled.** "The logs don't establish X" beats a guess.
4. **Lines ≠ incidents.** Count matching entries accurately; never present a line count as a number of incidents.
5. **Manager answers never invent money, downtime or customer impact.**
6. **Same agent + same corpus for all three roles**; roles differ in questions, evidence and actions, not length.
7. Confidences shown to users are computed (Jev probabilities / rules), never LLM self-reported.
8. **Performance is a feature.** Load and query optimally using database internals (sort order + zonemaps, inverted and
   ART indexes, rollups, streaming). Measure every change (`EXPLAIN ANALYZE`, `src/bench/`), record it in `docs/PERFORMANCE.md`.
9. **Polished final answers:** the agent uses a strong model (not Haiku/Flash). Jev stays for fast typed judgments.
10. **Public repo: never commit keys.** Keys live in `.env` (gitignored); `.env.example` lists names only.
11. **Generalize everything (plan 011).** Tune on BGL / OpenStack, but no dataset names, components, severities or
   other dataset-specific values in tool, agent, eval-harness or loader-library code paths. Dataset knowledge lives in
   data: the dataset's own loader file (`src/sql/3x_<name>.sql` = one parse query + `\ir lib/stage_to_logs.sql`), the
   `datasets` registry row it writes, and config rows (`data/config/ownership.csv` incl. `*` defaults, `data/config/watchlist.csv`,
   `data/config/remote_sources.csv`). A new dataset must need no code change; every new tool or rule is tested on at least one
   extra Loghub dataset (`src/bench/check_tools.py` runs every tool on every loaded dataset; `src/bench/lint_generic.py` fails
   on dataset values in code and on incomplete tool descriptions).

## Workflow
- **Held-out (`eval/heldout/**`) is never read, searched or written by Claude** (`docs/HELDOUT.md`); only
  `python3 eval/run_heldout.py <args>` touches it and prints aggregates only.
- Commit/push only when the user asks. Branches: short-lived `feat/NNN-name` (one per plan) → PR/merge to `main`; ask before pushing `main`.
- Teammate works in parallel: pull before editing shared docs; keep `docs/STATUS.md` short and current.
- **After each milestone:** update `docs/STATUS.md`, add a decision to `docs/DECISIONS.md` if one changed.
- Keep README.md (public, judged) accurate: setup from a clean checkout must work at all times on `main`.

## Stack (agreed)
SereneDB (docker, local) · Python 3.12 + `uv` · **LangGraph** (agent) · **LangSmith** (tracing/eval) ·
**MCP** (our tools; FastMCP) · `langchain-mcp-adapters` (agent uses the same MCP tools Claude uses) ·
**Jev / TypeSafe** (typed judgments, in SQL via `ai_system_one` or SDK) · agent + prose LLM = a **strong** model via
`init_chat_model(AGENT_MODEL)` (default `anthropic:claude-opus-5-5`) · **data loaded by SereneDB itself in docker**
(`read_csv`/`COPY` from `/data`, SQL in `src/sql/`) · UI: Streamlit unless we decide otherwise.

## Docs & tools for the coding agent (use them, don't guess)
| Need | Use |
|---|---|
| SereneDB | MCP `serenedb-docs` (search_docs, read_section) · in-server `sdb_docs.search` from SQL |
| Jev / TypeSafe | skill **`typesafe-ai`** (`.claude/skills/typesafe-ai/SKILL.md`) · MCP `typesafe-docs` |
| LangGraph / LangChain / LangSmith | MCP `langchain-docs` (docs.langchain.com) · Context7 |
| Other libraries | Context7 MCP |
| Web search | Tavily MCP |
| Building our MCP server | skill `mcp-builder` |

## Environment
- Copy `.env.example` → `.env`, fill keys. Python: `uv venv --python 3.12 && uv pip install -r requirements.txt`.
- SereneDB: `docker compose up -d` (first time only: `psql -h localhost -p 7890 -U postgres -d postgres -f docker/init.sql`),
  then `./docker/secrets.sh` after **every** (re)start (AI secrets are not persisted).
  SQL: `psql -h localhost -p 7890 -U postgres -d postgres` (trust auth). OTLP/HTTP `:4318` (`otel:otel`).
  Image is amd64-only (emulated on Apple Silicon: slower; keep loads lean). `./data` is mounted read-only at `/data`.
- Data: `./src/scripts/download_data.sh` → `data/raw/BGL.log`, `data/raw/openstack/*.log` (gitignored).
  Ownership table: `data/config/ownership.csv` (committed, fictional, documented in README).
- Claude's Bash on Amirali's Mac does not load `~/.zshrc`; read keys from `.env` (never print them).
