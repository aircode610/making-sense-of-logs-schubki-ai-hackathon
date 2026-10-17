# Decisions (append-only, newest at the bottom)

Side-quest decisions D1–D14 are in `archive/side-quest/docs/DECISIONS.md`. Hackathon decisions are H1…

| # | Date | Decision | Why |
|---|---|---|---|
| H1 | 2026-10-17 | **Hackathon mode:** minimal code, iterate to results. **Every task still needs an approved plan** (`plans/NNN-name.md`, one screen, Claude drafts, Amirali/Konark approve). | Planning keeps two people in parallel and on target; short plans keep it fast. |
| H2 | 2026-10-17 | **Stack:** SereneDB (local docker) + MCP server (FastMCP) + LangGraph agent via `langchain-mcp-adapters` + LangSmith + Jev + a strong LLM (H8); Streamlit UI. | One toolset for Claude, our agent and the UI; tracing for free. |
| H3 | 2026-10-17 | **The brief's ReAct + SQL-tools design is our baseline**, measured on the same questions; our product must beat it on `EVAL.md` metrics. | Everyone builds it; novelty must be shown with numbers. |
| H4 | 2026-10-17 | **Eval replaced:** rubric-driven (query correctness, groundedness, role distinctness, forbidden claims, label agreement, tool selection, cost) instead of side-quest macro-F1. Held-out kept (H10). | Judges score grounded, role-specific answers, not classification F1. |
| H5 | 2026-10-17 | **D10 lifted:** Anthropic models allowed. | Judges connect Claude to our MCP server. |
| H6 | 2026-10-17 | Ownership table invented in `data/ownership.csv` (BGL components → node-platform / cluster-control / hpc-workloads; nova services → cloud-api / cloud-compute). | Brief requires it for team-level counts. |
| H7 | 2026-10-17 | Jev raw doc dumps are not committed (public repo); use the `typesafe-docs` MCP or `scripts/refresh_docs.sh`. SereneDB docs (Apache-2.0) and the TypeSafe skill (MIT) are committed. | Licensing of third-party docs. |
| H8 | 2026-10-17 | **Agent/explanation LLM = strong model** (default Claude Opus 5.5, configurable); Gemini Flash dropped from the answer path. Jev stays for typed judgments. | Polished final answers matter more than LLM speed. |
| H9 | 2026-10-17 | **Data loaded by SereneDB itself in docker** (`read_csv`/`COPY` from `/data`, parsing in SQL, `load/*.sql`), as the organisers suggest. | Brief's recommended path; less code. |
| H10 | 2026-10-17 | **Held-out eval kept** (`docs/HELDOUT.md`): held-out questions + a BGL time slice; only `eval/run_heldout.py` (written together) touches it; guard hook ported. | Show generalization, not demo-tuning. |
| H11 | 2026-10-17 | **Performance is a first-class goal** (`docs/PERFORMANCE.md`): sort order/zonemaps, inverted + ART indexes, rollups, streaming; every change benchmarked. | Huge-datasets award, execution score. |
| H12 | 2026-10-17 | **Work split = vertical slices, mixed** (`docs/PLAN.md`): both touch every layer, swap halfway. | Parallelism without silos. |
| H13 | 2026-10-17 | **BGL held-out slice = `ts >= 2005-12-05 00:00`** (last 30 days; 129,874 lines, 13,597 alert lines). Tuning uses only earlier data; `eval/heldout/` gitignored. | Fixed before any data load or tuning, so E6 on the slice is unbiased. |
| H14 | 2026-10-17 | **Default agent model = Claude Sonnet 5.5** (`.env.example`), refines H8; still a strong model. | Amirali's choice; Opus remains an option to compare on E2/E4. |
| H15 | 2026-10-17 | **Own schema, loader (`load/*.sql`) and ownership table (`data/ownership.csv`), SereneDB in our docker**, confirmed by organisers (`BRIEF.md` § clarifications). README documents start → load BGL + OpenStack → start agent. | Brief's "supplied loader/schema/instance" wording was ambiguous; organisers said to ship our own. Confirms H6 and plan 002. |
| H16 | 2026-10-17 | **Patterns = SQL masking at load (1,126 BGL templates); episode gap frozen at 30 min; the headline "how often" unit for lead/manager = bursts** (same pattern anywhere, gap > 30 min; 36,714 in BGL) with nodes as spread; per-node episodes (2.4M) kept for detail (plan 004). | Gap sweep 5–240 min has no elbow, so the ROLES draft stays; node-episodes ≈ lines/2 for fleet-wide patterns (no correction for "lines ≠ incidents"), bursts are 65× fewer and only 1 lasts > 1 day. Masks: 100% of tune-part alert lines sit in single-category patterns. |
