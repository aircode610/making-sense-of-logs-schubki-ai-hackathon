# 016: Ship as one MCP server: two-step setup, load the base corpus (with Jev) or your own logs from Claude

- **Status:** done (approved Amirali 2026-10-18)
- **Owner:** Amirali · **Branch:** `feat/016-ship-mcp` (from `feat/015-session-report` + merge of `origin/main` = plan 057) · **Date:** 2026-10-18
- **PLAN.md block / slice:** Execution (20 %: clean checkout, clear setup) + Best MCP Server award ("Claude can connect and
  answer questions using your setup instructions"); builds on 012 / 014 / 015 (Amirali) + 057 (Konark)

## 1. Goal
A judge (or any user) clones the repo, starts SereneDB, adds our MCP to Claude, and from inside Claude loads the base
corpus (BGL + OpenStack, from the brief's own Zenodo links, with our loader + Jev judgments) or their own log file, then
asks the three roles' questions. No host psql, no key needed for the base corpus, no reload script, no server restart.

**From the brief / organisers (constraints):** SereneDB image **`serenedb/serenedb:26.10.1`** pinned (Pavel: "we use the
latest version"; amd64-only, Docker emulates it on Apple Silicon: say so in the README); datasets downloaded exactly as the
brief says (`curl -L … ?download=1`, Zenodo record 8196385, file names from its table); our schema + loader + ownership
table in the repo, README says how to start SereneDB, load BGL + OpenStack, start the agent workflow (clarification
2026-10-17); "using an existing agent to call your tools is sufficient" → Claude via MCP is the main path, our LangGraph
agent stays as the second path.

## 2. Done when (decided before starting)
- **Setup = 2 commands + 1 sentence** (README, tested from a fresh clone in an empty folder with a fresh SereneDB volume):
  `docker compose up -d` → `claude` in the repo folder (project `.mcp.json`, `uv run` installs deps on first start) or
  `claude mcp add -s user logs -- uv run --directory "$PWD" mcp_server/server.py` for any folder → *"Load the base corpus"*.
  `.env` optional (keys only for live Jev on new data, embeddings of the query text, and our own agent).
- **Load from Claude:** `load_logs(source)`: `source` = a Loghub name from the brief's table (`bgl`, `openstack`, …:
  download per the brief, our hand-written loader if we have one, else lnav auto-detection) or a file path anywhere on
  disk (streamed with `COPY … FROM STDIN`, Konark's lnav detection, refused < 95 % with the candidates listed). Runs as a
  background job (no MCP timeout); `setup_status` shows DB / version / datasets / keys / job progress. Only the new
  dataset is built: patterns, bursts, episodes, examples, ownership (057 chain), pattern index, role grants; other datasets
  untouched (diff test = 0 vs a full reload). Same name again = replace; `remove_dataset(name)`.
- **Jev included in the load:** known datasets get the committed judgments / traits / areas / vectors (no key); a new
  dataset is judged inside SereneDB when a TypeSafe key works (stored in the DB, CSV export optional), otherwise
  `datasets.judged = false` and every problem tool / macro falls back to the level rule and says so in its result.
- **Active dataset, no restart:** registry refreshes after every load / remove; first load (or `LOGS_DATASET`) sets the
  active dataset; `use_dataset(name | 'all')` switches ('all' = whole loaded corpus, for the brief's "counts by dataset /
  team over the whole base corpus"; tools that need one dataset then say so). Tools keep no `dataset` parameter.
- The server registers AI secrets from `.env` itself (no `./docker/secrets.sh` after every restart); `docker/init.sql`
  folded into the schema step (idempotent); no host `psql` anywhere in the setup path (Python runner for `load/*.sql`).
- Checks: `check_tools` (all tools × all datasets, pinned + 'all'), `check_counts`, `check_patterns`, `lint_generic`
  (token budget kept: descriptions trimmed if the 4 new tools push it over); one dataset added without a key → fallback
  path checked; **clean-checkout test** (fresh clone in /tmp, second SereneDB on port 7891, headless `claude -p`: load
  base corpus, then the engineer / lead / manager questions, session-report links); load times measured on the emulated
  image and stated in the README.

## 3. Approach
- **Merge** origin/main (057): conflicts in agent/graph.py, agent/prompts.py, DECISIONS.md; Konark's `owner_of`,
  `ownership_gaps`, `ingest_report` work pinned.
- **Setup:** `docker-compose.yml` → `serenedb/serenedb:26.10.1`, port from `SERENEDB_PORT` (default 7890); `pyproject.toml`
  (server + loader deps; agent extras optional) so `uv run` needs no venv step; `.mcp.json` `logs` → `uv run`.
- **Loader without psql (`loader/`, Python):** runs the existing `load/*.sql` files over psycopg, supporting exactly what
  they use (`\set`, `:'v'` / `:v`, `\if :{?v}` / `\else` / `\endif`, `\ir`, `\timing`); `reload.sh` = thin wrapper (CLI
  `uv run python -m loader all|<names>`). SQL files stay the readable "supplied loader".
- **Per-dataset steps:** 93 / 94 / 95 / 96 / 96b / 97 + roles written as one-dataset versions (`:ds`; DELETE + INSERT),
  the full reload loops over them (one code path).
- **Catalog (`data/catalog.csv`):** the brief's Loghub table (name, Zenodo file, lines, size) + our loader file if any;
  big ones (HDFS_v2, Thunderbird, Windows, Spark…) need `confirm_large=true`. Download = the brief's curl semantics in
  Python into `data/raw/` (mounted at `/data`).
- **Own files:** Konark's `scripts/ingest.py` split into a library (detect + generated SELECT); the generated loader reads
  a streamed staging table instead of `read_csv('/data/…')` for paths outside `data/`.
- **Server:** `core.registry()` refreshable, `active()` instead of `pinned()`; new tools `load_logs`, `setup_status`,
  `use_dataset`, `remove_dataset` (writes: `destructiveHint` on remove); background jobs in a thread.
- README: Setup rewritten to the 2-step path (+ Apple Silicon / emulation note, Linux VM alternative, Pavel's
  troubleshooting); worked investigation unchanged; STATUS, DECISIONS, plans index.

## 4. How we check it
Diff test (per-dataset build vs full reload on zookeeper + bgl: patterns, bursts, episodes, ownership, examples equal);
problem counts identical for judged datasets; fallback counts = independent level-rule SQL; check_* + lint; clean-checkout
run end to end with timings; session report on the clean run. Held-out untouched; current DB volume untouched (test DB on 7891).

## 5. Out of scope / risks
Out: formats not in lnav (refused), LLM-written parsers, remote SereneDB without our `/data` mount for the BASE corpus
(own files stream, so they work anywhere; base corpus via mount, stated), URLs as `source` other than the catalog.
Risks: emulated amd64 on Macs is slow (BGL load + Jev CSV join measured and stated; background job keeps Claude
responsive); MCP tool-count / token budget (4 new tools: trim descriptions); `uv run` first start may exceed the client's
MCP start timeout (README: `uv sync` once if so; measure); big downloads (709 MB BGL zip) from Zenodo can be slow.

## 6. Steps
- [x] Merge origin/main, resolve conflicts, 057 tools pinned; checks pass
- [x] Setup: compose 26.10.1 + port, pyproject + `uv run`, `.mcp.json`, secrets + init from the server/loader
- [x] Python SQL runner; reload via it = same tables as psql (diff)
- [x] Per-dataset build steps + diff test vs full reload
- [x] Catalog + brief-style download; own files: detection library + streaming; replace / remove
- [x] Jev at load (committed for known, live with key, `judged` flag + level fallback in every problem tool / macro)
- [x] Server: refreshable registry, active dataset + 'all', `load_logs` / `setup_status` / `use_dataset` / `remove_dataset`, jobs
- [x] check_tools / counts / patterns / lint; clean-checkout test with headless Claude, 3 roles; timings
- [x] README setup rewrite, STATUS, DECISIONS, §7

## 7. Results (filled after)
- **Merge** of main (plan 057) clean: 3 conflicts resolved (lead subset = plan-014 changes + 057 ownership tools; both
  composer rules; DECISIONS renumbered H30/H31). Konark's tools work in single-dataset mode.
- **Per-dataset build = old global build:** after a full reload through the new loader, patterns, bursts, episodes,
  ownership, judgments, traits, datasets, templates, labels, pattern index: identical (EXCEPT ALL both ways = 0);
  2 example-value ties and the order inside `entities` differed between ANY two runs (also psql vs psql) →
  `extract_entities` now sorted. Full reload 216 s → 122 s (no psql, no compaction per step).
- **Add one dataset:** the forced `COMPACT_TABLE` rewrote all 17M rows (41 s) for a 21k-line file → incremental loads
  only refresh (background compaction merges): **1.6 s** end to end; with live Jev + traits + areas + embeddings 15 s.
  Android (1,555,005 lines) from the catalog: 19 s, 19,242 patterns (= plan 057).
- **Live Jev = committed:** Proxifier judged at load vs Konark's committed CSV: corr(p_fault) 0.996, same problem decision
  287 / 287; ownership inferred for 20 components; embeddings 287 / 287.
- **No key:** problem rule = explicit error-or-worse / WARN / 5xx lines (`patterns.error_lines`); "no level" lines need
  Jev (else every syslog pattern would count). Fallback counts = independent SQL (zookeeper without judgments: 21 = 21);
  judged results unchanged; every problem tool + macro says so in `hints`.
- **Clean checkout** (fresh clone, empty SereneDB volume on port 7891, repo's `.mcp.json`, headless Claude Sonnet):
  "Load the base corpus" → 72 s (download 770 MB per the brief + load + committed Jev); engineer / lead / whole-corpus
  manager questions answered with report links; final run = load + lead answer in one prompt, 106 s.
- **Checks:** check_counts 42 ok, check_patterns ok, check_tools 39 tools x 10 datasets pass (incl. a file loaded from
  /tmp without Jev), lint passes; tool definitions 32,203 tokens in the shipped mode (budget 36,000).
- **Verify:** each recorded call stores its dataset; Verify re-runs on it (switches in between) and skips write steps.
- Deviations: `use_dataset(name | 'all')` → no 'all' (whole-corpus = one call per dataset, the brief allows it;
  Claude did this unprompted); the derived step files 93-97 / 96b and `scripts/ingest.py` were replaced (one code path);
  `requirements.txt` kept for the agent, the server installs from `pyproject.toml`.
- Not done: our agent's model call could not be run (the `.env` Anthropic key returns 401; MCP side checked).
