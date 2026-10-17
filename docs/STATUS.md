# Status (read first; keep short and current)

_Last updated: 2026-10-17, S0 setup._

## Stage: S0 — setup done, nothing built yet
- Repo set up: docs, skills, MCPs (serenedb-docs, typesafe-docs, langchain-docs), docker, data scripts, ownership table.
- Data downloaded locally: BGL 4,747,963 lines · OpenStack 207,820 lines (`data/README.md`).
- Side-quest results and code archived in `archive/side-quest/` (read `docs/LESSONS.md` instead of the archive).

## First things in a fresh session (setup gaps, not yet done)
- [ ] Approve the 3 docs MCP servers on first `claude` start in this repo (`.mcp.json`).
- [ ] Old repo's SereneDB container is also named `serenedb` on port 7890: run `docker compose down` in
      `../jev-serenedb-side-quest` before `docker compose up -d` here (new, empty volume → data must be loaded).
- [ ] Plan 000: port the held-out guard (`.claude/hooks/` + `.claude/settings.json`) **before** anyone creates `eval/heldout/`.
- [ ] `uv venv` + install, then pin `requirements.txt`; add `ANTHROPIC_API_KEY`, `LANGSMITH_API_KEY` to `.env`.
- [ ] Konark: clone, own `.env` (keys shared privately, never in git), run the README setup (first clean-checkout test).
- [ ] Ask organisers: submission deadline + format (repo link, video?, slides upload).
- [ ] Later plans still missing: dev question set for eval, demo script + slides (5 min), MCP connection steps for judges.

## Next (in order; each item starts with an approved plan in `plans/`)
1. Hours 0–6: start SereneDB, load both datasets **with SereneDB in docker** (`load/*.sql`), plus `ownership` and `labels`;
   first full-text search + count by team. Record load time (`docs/PERFORMANCE.md`). Check SQL against `wc -l`/`awk` counts (E1 seeds).
2. Patterns (Drain3) + episodes; `describe_corpus`, `search_logs`, `get_context`, `count_by`, `trend` as MCP tools.
3. Baseline ReAct agent on those tools (LangGraph + LangSmith) → first three role answers.
4. Our layer: Jev pattern judgments, priority table, evidence ledger, answer card, claim checker.
5. Eval (`EVAL.md`), README, worked investigation, slides, rehearsal.

## Who is on what right now
Plan: `docs/PLAN.md` (vertical slices, mixed). B1: Amirali = BGL load + search/context tools; Konark = OpenStack load +
count/trend tools. **Jury Q&A today 18:50–19:00 CEST** (`docs/QA_JURY.md`).

## Open decisions
- Exact strong agent model (default Claude Opus 5.5; compare others on E2/E4 if time).
- Episode gap (30 min draft) and "problem pattern" thresholds: freeze after the first data look (`docs/ROLES.md`).
- Worked investigation topic: pick in B1.
- UI: Streamlit (default) vs something nicer if time allows.

## Results table (fill after each eval run)
| Run | E1 | E2 | E4 | E6 | E7 | latency | $ |
|---|---|---|---|---|---|---|---|
