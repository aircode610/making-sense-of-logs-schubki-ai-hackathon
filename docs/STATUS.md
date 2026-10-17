# Status (read first; keep short and current)

_Last updated: 2026-10-17, plan 006 done (Jev pattern judgment: priority top 10 alerts 1/10 → 5/10)._patterns + priority_table; 6 MCP tools)._

## Stage: B3 — 6 MCP tools + Jev pattern judgments; next: agent (baseline ReAct + our recipes)
- **Plan 006 done:** Jev judges each pattern once (20 s, ≈ $0.02, stored CSV). Problem filter H18 → priority top-10 alert
  patterns 1/10 → 5/10, top by bursts 0/10 → 5/10 (tune period). Konark: flaky count right after reload seen once (plan 006 §7).
- **Plan 005 done:** `top_patterns` + `priority_table` (score computed in SQL, reproduced independently). Measured: with
  severity as the problem filter, priority top 10 holds 1/10 alert patterns (register dumps win) → next plan = Jev
  "real fault or routine?" per pattern, re-measure.
- **Plan 004 done:** `pattern_id` on every BGL row (1,126 templates, SQL masks), tables `patterns`, `bursts`,
  `episodes` (`load/95_patterns_episodes.sql`, runs after `90_publish`). Gap frozen 30 min; bursts = headline unit (H16).
  **Reload: `./load/reload.sh`** (00 → 10 → 20 → 90 → 95 + checks). Konark: OpenStack masks → `pattern_id` in `20_openstack.sql`.
- **Plan 003 done:** MCP server `mcp_server/` (`search_logs`, `get_context`; registered in `.mcp.json`), counts equal
  reference, p95 < 45 ms. Konark: add `count_by`/`trend` in `mcp_server/counts.py` (plan 051), register in `server.py`; reuse `core.envelope`.
  Live Claude Code check passed (kernel-panic investigation, plan 003 §7).
- **Plan 002 done:** `load/00_schema.sql` (shared `logs` + `labels`, one inverted index) + `load/10_bgl.sql`: 4,747,963
  rows in 18 s, every count equals awk (table in `plans/002-bgl-load.md` §7). Konark: insert OpenStack into the same
  `logs` table (`dataset='openstack'`; columns `request_id, instance_id, tenant_id, status, latency_ms` ready).
- Repo set up: docs, skills, MCPs (serenedb-docs, typesafe-docs, langchain-docs), docker, data scripts, ownership table.
- Data downloaded locally: BGL 4,747,963 lines · OpenStack 207,820 lines (`data/README.md`).
- Side-quest results and code archived in `archive/side-quest/` (read `docs/LESSONS.md` instead of the archive).

- **Plan 050 done (Konark):** `load/20_openstack.sql`: 207,820 OpenStack rows + `ownership` table in ~1.2 s, all counts equal awk/grep
  (`plans/050-openstack-load.md` §7). Next: plan 051 `count_by` + `trend` tools.

- **Plan 051 done (Konark):** MCP tools `count_by` + `trend` (`mcp_server/counts.py`), 29 checks vs awk/grep pass
  (`bench/check_counts.py`), median 7 ms / p95 45 ms. ⚠️ **Reload = `./load/reload.sh`** (DROP + load +
  `VACUUM` refresh/compact + count check, ~21 s): the index is eventually consistent, counts right after a bulk insert can be off (plan 052).

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
