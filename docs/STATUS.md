# Status (read first; keep short and current)

_Last updated: 2026-10-17, plan 009 done (eval: ours vs baseline), plans 053–055 done (OpenStack patterns, Jev judgments, `value_outliers`, `rate_vs_baseline`; 8 MCP tools)._

## Stage: S4 — eval done (dev set): ours beats the baseline on grounding and quality, at ~2.6× latency; next: checker covers all card sections, UI, worked investigation
- **Plan 055 done (Konark, B3 leftovers):** MCP tool **`rate_vs_baseline`** (rate now vs same-length windows of the
  previous days, clipped at the data start; 4–6 ms) = engineer recipe step 4. Engineer eval (8 q, +2 new): ours vs
  baseline golden 0.875 vs 0.542, claims 0.878 vs 0.469, pairwise **8-0**; cost 47 s / 98k tokens per answer. "Unusual"
  beats raw volume only for alert onsets (precision 0.17 vs 0.14) → not an anomaly detector. **Swap review:**
  `docs/REVIEW.md` (Konark → lead/manager, Amirali → engineer). Details `plans/055-…` §7.
- **Plan 054 done (Konark):** Jev judged the 106 OpenStack patterns (3.2 s) → `top_patterns(openstack)` 0 → 8 real
  faults (+ the 503). New MCP tool **`value_outliers`** (slow operations vs their own pattern's median/MAD, p95 99 ms): catches
  **4/4 labelled anomalous VMs** (top 4 by ratio; 2 extra mild flags); engineer agent uses it (checker 55/55).
  Amirali: `value_outliers` added to `ROLE_TOOLS["engineer"]` + one recipe line; composer now reads **full** tool
  results (`ledger_json` no longer cuts to 12 rows; 4 dev questions re-run, all pass); **H18 amended: HTTP ≥ 500 counts
  as a problem line** (2 lines, BGL unchanged; `top_patterns(openstack)` → 9). Details `plans/054-…` §7.
- **Plan 009 done:** `python -m eval.run_eval` (LangSmith experiments). Ours vs baseline: claim support 0.89 vs 0.59,
  numbers grounded 0.99 vs 0.85, golden facts 0.79 vs 0.59, rubric 4.53 vs 3.91, pairwise 10-4; 34 s vs 13 s per answer.
  Humans: rate `eval/results/human_check.md` (judge sanity); write the private question set, then run its runner.
- **Plan 053 done (Konark):** OpenStack `pattern_id` (106 patterns, ids 100001+, HTTP status kept) → `patterns`/`bursts`/
  `episodes` cover both datasets; 32/32 checks. ⚠️ Labelled OpenStack VMs show **no special template**: the anomaly is
  slow spawn/build (37–51 s vs ≤ 28 s) → needs a numeric-outlier signal. One traceback = 25 ERROR patterns (group by
  shared bursts in `top_patterns`). Details: `plans/053-openstack-patterns.md` §7.
- **Plan 008 done:** gatherer per role = prebuilt ReAct agent (`create_agent`) + CoverageMiddleware + tool limit;
  composer subgraph (compose ⇄ check); MCP server role-neutral; all dev questions pass again (stacked on 007).
- **Plan 007 done:** `python -m agent.run [--role …] [--baseline] "question"`; LangGraph route → gather ⇄ tools →
  coverage → compose → check; every number verified against cited SQL results (25/25, 86/86, 47/47; baseline 30/34);
  Jev routes the role; one LangSmith trace per question.
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
| Run | E1 | E2a / E2c | E4 evid. | E6 | E7 | rubric | pairwise | latency |
|---|---|---|---|---|---|---|---|---|
| dev 2026-10-17 ours (`151ec54`) | 0.79 | 0.99 / 0.89 | 0.02 | priority top-10 5/10 (plan 006) | 1.00 | 4.53 | 10 | 34 s |
| dev 2026-10-17 baseline | 0.59 | 0.85 / 0.59 | 0.04 | — | 0.83 | 3.91 | 4 | 13 s |
