# 011: SereneDB full-capability tools (all non-wild ideas of docs/SERENEDB_IDEAS.md), generalized to new datasets

- **Status:** approved (Amirali, 2026-10-18: "implement all the ideas fully … as one pr … just don't implement the wild cards")
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
