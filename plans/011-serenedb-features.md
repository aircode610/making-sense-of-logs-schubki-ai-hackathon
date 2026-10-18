# 011: SereneDB full-capability tools (all non-wild ideas of docs/SERENEDB_IDEAS.md), generalized to new datasets

- **Status:** done, in review (2026-10-18; approved by Amirali, 2026-10-18: "implement all the ideas fully … as one pr … just don't implement the wild cards")
- **Owner:** Amirali · **Branch:** `feat/011-serenedb-features` (on top of plan 010) · **Date:** 2026-10-18
- **PLAN.md block / slice:** B3–B5 · tools, huge data, bonuses

## 1. Goal
Expose (nearly) every SereneDB capability that helps the three roles as **atomic MCP tools** (fixed SQL, typed
fields), use SereneDB's AI functions internally, cover the brief's optional extensions (agent-managed index workspace,
remote/huge Parquet, role-based access, logs↔traces), and make the whole pipeline **dataset-agnostic**: a new Loghub
dataset = one loader file + ownership rows, everything else unchanged. Moves every rubric line + MCP + Huge awards.

## 2. Done when (decided before starting)
- Every non-wild idea of `docs/SERENEDB_IDEAS.md` (§A–N) is implemented, or listed in §7 with the measured reason it
  was dropped (feature missing in this SereneDB build, cost, no data).
- Each new tool: numbers equal an independent SQL query (`bench/check_tools.py`), p95 recorded, description written
  for selection; all tools pass on **bgl, openstack and ≥ 2 new Loghub datasets** (generality test).
- `./load/reload.sh` from scratch passes all checks (old + new); `bench/replay_tools.py` on the reference eval = 100 %
  (old tools unchanged) or every difference explained.
- Agent: role tool subsets + recipes extended; dev eval (`--compare` vs the plan-010 reference): no regression beyond
  noise, E7 tool selection stays ≥ 0.9; one agent run per role on a new dataset passes the checker.
- Workspace index and remote-Parquet index: build time vs saved query time measured (break-even) in `PERFORMANCE.md`.
- `CLAUDE.md` rule: everything generalized (no dataset names in tool/agent code paths).
- An artifact explains everything end to end with examples for someone who doesn't know SereneDB.

## 3. Approach (details per area in docs/SERENEDB_IDEAS.md)
- **Generalization first:** dataset registry (`datasets` table: name, description, location levels, entity fields)
  filled by each loader; tools validate `dataset` against it instead of a hard-coded `Literal`; generic `location`
  path column; shared mask macro for new loaders (old loaders keep their masks so pattern ids and stored Jev
  judgments stay valid).
- **Schema:** `offset` flag (highlighting), extracted entities (IPs, hex codes, ids) via `split_by_pattern`, location
  path via `expand_path`, synonyms dictionary for log jargon — each verified with `ts_lexize` and replay.
- **Tools:** new modules in `mcp_server/` (discover, search modes, facets/terms, bursts/timeline, correlation,
  analytics, semantic, workspace, remote, otel); SQL as table macros where SereneDB supports them.
- **AI in SQL:** multi-question Jev per pattern (cause family, actionable, symptom/cause, owner hint), Gemini
  embeddings of pattern templates + vector index, stored burst summaries (`ai_summarize_agg`), labelled as model text.
- **Agent:** `ROLE_TOOLS` + recipes; composer unchanged except new evidence kinds.
- **Data:** new Loghub sets from the brief (small ones) for generality; OTel Parquet over HTTPS for the huge-data path.

## 4. How we check it
Per feature: run the query by hand, then the tool, then the independent check; `reload.sh` checks; replay bench;
dev eval with `--compare`; agent runs per role on bgl, openstack and a new dataset. Held-out untouched.

## 5. Out of scope / risks
- Out: the wild ideas (§O and items tagged "wild"), UI, slides.
- Risk: feature missing or broken in this SereneDB build → record and skip. Risk: emulated amd64 image is slow for
  index builds over remote data → keep remote slices small, record times. Risk: tool count confuses selection →
  per-role subsets, E7 measured.

## 6. Steps
- [ ] Probe every feature on our instance (SQL by hand), record what works
- [ ] Generalization: registry, dynamic dataset validation, location path, shared masks; CLAUDE.md rule
- [ ] Schema/dictionary upgrades; reload + replay unchanged
- [ ] New tools (one module at a time, each with checks)
- [ ] AI in SQL (Jev multi-question, embeddings, burst summaries)
- [ ] Workspace + remote Parquet + OTel/request timeline + roles/grants
- [ ] New datasets (loaders, ownership, Jev), tools + agent on them
- [ ] Agent subsets/recipes, dev eval compare, per-role runs
- [ ] Docs (README tools, PERFORMANCE, DECISIONS, STATUS), artifact, PR

## 7. Results (filled after)
**Implemented** (idea ids from `docs/SERENEDB_IDEAS.md`):
- Generalization: dataset registry, `load/lib/stage_to_logs.sql` (generic masks, Drain-lite, entities, location path,
  continuation lines), ownership `*` defaults, watchlist + remote-source config, CLAUDE.md rule 11. Datasets: BGL,
  OpenStack, Zookeeper, Apache, OpenSSH, HDFS_v1 (11,175,629 lines in 47 s; 575,061 blocks / 16,838 anomalous = Loghub),
  OTel slice (1.7M records pulled over HTTPS with row-group pruning in 83 s). New tools work unchanged on all 7.
- A1-A6 (match modes, exclusion, explain_search, fuzzy recovery via suggest_terms / synonyms), B1 (relevance × recency),
  C1 (highlight; `offset` flag), D1-D7 (distinctive_terms, facet, list_values, suggest_terms, watchlist, data range in
  describe_corpus), E1 (expand_path location), E2 (entities), E3 (query-time synonyms), F1-F3 (similar / find patterns,
  hybrid RRF), G1 (Jev traits incl. threat), G2 (Jev support per fact, E2d), G4 (burst summaries), G11 (AI call caps),
  H1-H3 (focus index, index_stats, explain_tool), I1-I3 (remote describe / count / search / index, row-group stats),
  I4/I5 (OTel slice and HDFS through the same pipeline), J1 (OTLP replay), J4 (request_timeline with sessions),
  K1-K9, K11-K13 (co-occurrence, precursors via ASOF, reliability_trend, rollup, heatmap, periodicity, spread, latency,
  describe_corpus, table macros, QUALIFY-style top-n), L1/L2 (persona + team roles), M6 (index health in index_stats).
**Measured:** see `docs/PERFORMANCE.md` 2026-10-18 rows: remote index 2.8M rows in 1.1 s, search 281 ms → 0.94 ms
(break-even 4 searches); focus index break-even ~31 query pairs (corpus index already fast); full reload 44 s (5 small
datasets) / 1 min 45 s with HDFS; 32 new tools median 3-80 ms.
**Eval** (`eval/results/20261018-043511.md`, 25 q): pairwise vs baseline 16-1, vs previous version 14-4, new datasets
4-0 (`…044019.md`); E1 0.87 (+0.01, within noise), claims supported 0.95, tool overlap between roles 0.31 → 0.02,
next-step specificity 4.44. Worse: causes stated as fact (lead 0.11 → 0.5 per answer, judge; new correlation tools
tempt causal wording; follow-up: composer rule for precursors / co_occurrence), +29k input tokens. E7 first tool now
accepts several valid first tools (the new atomic tools are legitimate first calls).
**Generalization findings fixed on the way:** SSH had 0 problem patterns (attacks are not faults) → Jev threat;
Zookeeper / BGL faults at WARN → WARN is problem-level (BGL priority top-10 alerts 5/10 unchanged, top-by-bursts
5 → 4/10); signed / alphanumeric ids (OTel 47,635 → 1,426 patterns); node-less datasets say spread is unknown.
**HDFS check of the problem filter** (block labels): 5.5 % precision vs 2.9 % base, 44 % recall; 3 of 4 problem
patterns 96-100 % precise; HDFS anomalies are sequence anomalies (limitation in README).
**SereneDB issues found** (worked around, PERFORMANCE / DECISIONS H24): TsDict facet counts off by one with split
segments; bound text args to ts_* constructors next to timestamp params; a list of bound ::tsquery crashed the server;
bound ints inside window queries; vector column alone in a projection returned no rows; PIVOT needs explicit IN with
params; no index on a view over a search table; no partial index on search tables; BM25 not through views.
**Dropped, with reason:** I6 sampling (pushdown lost: 392 s vs 32 s exact, 5.7 % off); J2/J3 traces / metrics (no trace
or metric data loaded; tools would be untestable); E4 sparse n-grams for ids (entities + keyword filters cover it);
E5 MinHash (embeddings available; no use case left); E6 template keyword field (pattern_id filters cover it);
F6/F7 (embeddings present; IVF clusters not exposed); G5/G6/G7 (traits cover cause / tags; rerank not needed with BM25
+ RRF); H4-H8 (not needed: tools already 3-80 ms; recorded); M2 (`check_sql` lives on SereneDB's own docs MCP endpoint,
not exposed through ours); M4/M5 (UI / exports out of scope). Wild ideas (§O and "wild" items): not built, as agreed.
