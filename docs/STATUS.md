# Status (read first; keep short and current)

_Last updated: 2026-10-17, plans 002 + 050 done (BGL + OpenStack loaded)._

## Stage: B1 — BGL loaded and verified; OpenStack load + tools next
- **Plan 002 done:** `load/00_schema.sql` (shared `logs` + `labels`, one inverted index) + `load/10_bgl.sql`: 4,747,963
  rows in 18 s, every count equals awk (table in `plans/002-bgl-load.md` §7). Konark: insert OpenStack into the same
  `logs` table (`dataset='openstack'`; columns `request_id, instance_id, tenant_id, status, latency_ms` ready).
- Repo set up: docs, skills, MCPs (serenedb-docs, typesafe-docs, langchain-docs), docker, data scripts, ownership table.
- Data downloaded locally: BGL 4,747,963 lines · OpenStack 207,820 lines (`data/README.md`).
- Side-quest results and code archived in `archive/side-quest/` (read `docs/LESSONS.md` instead of the archive).

- **Plan 050 done (Konark):** `load/20_openstack.sql`: 207,820 OpenStack rows + `ownership` table in ~1.2 s, all counts equal awk/grep
  (`plans/050-openstack-load.md` §7). Next: plan 051 `count_by` + `trend` tools.

## First things in a fresh session (setup gaps, not yet done)
- [x] Approve the 3 docs MCP servers on first `claude` start in this repo (`.mcp.json`).
- [x] Old repo's SereneDB container is also named `serenedb` on port 7890: run `docker compose down` in
      `../jev-serenedb-side-quest` before `docker compose up -d` here (new, empty volume → data must be loaded).
- [x] Plan 001: held-out guard live (hook + deny rules, `eval/heldout/` gitignored); BGL slice fixed at `>= 2005-12-05` (H13).
- [ ] Amirali + Konark: write `eval/heldout/questions.yaml` (~10 per role, **without Claude**; follow `docs/HELDOUT_BRIEF.md`); golden SQL after B1.
- [x] `uv venv` + install, then pin `requirements.txt` (plan 000). SereneDB up, `init.sql` + secrets done, Jev from SQL works.
- [x] Keys filled; Anthropic + LangSmith verified (LangSmith account is **EU**: `LANGSMITH_ENDPOINT` required).
- [ ] Konark: clone, own `.env` (keys shared privately, never in git), run the README setup (first clean-checkout test).
- [x] Submission deadline: **Sun 18 Oct 2026, 23:59 CET**. [ ] Still ask organisers: format (repo link, video?, slides upload).
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
- Exact strong agent model: Sonnet 5.5 in `.env.example` (2026-10-17); CLAUDE.md still says Opus 5.5 (compare on E2/E4).
- Episode gap (30 min draft) and "problem pattern" thresholds: freeze after the first data look (`docs/ROLES.md`).
- Worked investigation topic: pick in B1.
- UI: Streamlit (default) vs something nicer if time allows.

## Results table (fill after each eval run)
| Run | E1 | E2 | E4 | E6 | E7 | latency | $ |
|---|---|---|---|---|---|---|---|
