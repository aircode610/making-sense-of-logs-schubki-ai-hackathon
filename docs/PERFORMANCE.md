# Performance is a feature

Every tool answers in milliseconds over the whole base corpus, and we can prove it with numbers. We work at the level of
database internals: storage order, index structures, pre-aggregation, streaming. Every choice is measured
(`EXPLAIN ANALYZE` + the bench script) and kept only if it wins. Verify SereneDB behaviour in the docs before relying on
it (MCP `serenedb-docs`, `docs/serenedb/docs/cookbook/performance/*`, `sql/indexes/*`).

## What SereneDB gives us (from its docs)
- Columnar, vectorized (DuckDB-style) execution; durable storage on RocksDB (LSM tree).
- **Zonemaps** (min-max per row group) on every column, automatically. They pay off only if data is **ordered**
  (time-sorted data → time filters skip row groups; docs show 2.5× smaller, 1.5× faster when ordered).
- **ART index** (Adaptive Radix Tree, SereneDB's B-tree counterpart): `CREATE INDEX`; for highly selective point lookups.
  It slows inserts.
- **Inverted index** (`USING inverted`): full-text (BM25, phrase, fuzzy), vector, hybrid. Configurable analyzers and
  features (frequency / position / norm), which trade index size against capabilities.
- Remote Parquet / HTTP / S3 reads with predicate and projection pushdown (huge-dataset award).
- OTLP/HTTP streaming ingest into `otel_logs`.

## Techniques we plan to use (measure each; keep the winners)
| Layer | Technique | Expected win |
|---|---|---|
| Load | **SQL-native load inside the docker SereneDB** (`read_csv` / `COPY` from `/data`), parse once into typed columns (TIMESTAMP, small ints, low-cardinality strings) | no Python round trips; no regex at query time |
| Storage order | insert **sorted by (dataset, ts)** | zonemap pruning for every time-filtered tool |
| Full-text | inverted index on `body` with the minimal features: position only if phrase search needs it, norm for BM25; filter columns (ts, component, severity, node) indexed in the same index if supported | search + filter in one index pass |
| Point lookups | ART on `request_id`, `instance_id`, `node` (if `EXPLAIN` shows a scan) | context retrieval in ms |
| Patterns | `pattern_id` integer computed once at load (masking in SQL, or Drain3 offline) | group-bys on an int, not text |
| Pre-aggregation | **rollup tables** at load: (hour × pattern × node × severity) counts and episode table | lead/manager tools read thousands of rows, not millions; exact counts preserved |
| Algorithms | episodes via window functions (`LAG` gap split) once at load; top-k; exact counts always (brief), approximate (HLL distinct, quantile sketches) only when labelled | linear-time passes |
| Streaming | rollups maintainable incrementally from the OTLP stream (new rows → update hour buckets) | live data story |
| Query layer | prepared, parameterized statements; `LIMIT` for rows + separate fast `count(*)`; result cache keyed by SQL hash (evidence ledger) | repeated questions near-free |
| Agent | role recipe fires its first tool calls **in parallel**; Jev judges ~patterns, not lines; fewer LLM turns | lower end-to-end latency |
| Optional | agent-managed index workspace: create an index for a time range, measure build time vs time saved over repeated queries | brief's optional extension |
| Optional | remote OTel Parquet (`part_000`… on S3): rows scanned, bytes read, latency, cost | huge-dataset award |

## Bench (`bench/`, to build)
For every tool: p50/p95 over ≥ 20 runs on the base corpus, plus load time, table and index sizes, rows scanned
(`EXPLAIN ANALYZE`). The same bench with and without each optimisation. Results table here and in the README.

Targets (aspirational, revise after first measurements): tool p95 < 200 ms on the base corpus; full load < 10 min under
emulation; end-to-end role answer dominated by the LLM, not the database.

## Results
| Date | Change | Tool / query | Before | After | Notes |
|---|---|---|---|---|---|
| 2026-10-17 | BGL load, SQL-native (`load/10_bgl.sql`), search table + one inverted index, insert sorted by ts | full load 4,747,963 lines | — | **18.0 s** | parse (read_csv + regex + strptime) 16.2 s · sorted insert 1.6 s · labels 0.1 s; amd64 emulated on Apple Silicon. Raw 709 MB → 224 MB on disk (data + index, whole volume) |
| 2026-10-17 | (baseline) | `count(*) GROUP BY severity`, `ts >= 2005-12-05` | — | 16 ms | `EXPLAIN ANALYZE`: no row scan — dataset/ts become index Terms + Range, counts come from the index term dictionary (`TsDict: severity`) |
| 2026-10-17 | (baseline) | whole-corpus `GROUP BY component` / `severity` | — | 3–39 ms | no plain-table A/B needed (plan 002 threshold was 1 s) |
| 2026-10-17 | (baseline) | full-text `body @@ 'parity'` count / `ts_phrase('cache parity error')` | — | 7 ms / 32 ms | 121,498 / 106,220 lines, equal to the Python token count |
| 2026-10-17 | (baseline) | count by team (join `read_csv('/data/ownership.csv')`) | — | 51 ms | |
| 2026-10-17 | OpenStack load, SQL-native (`load/20_openstack.sql`), same `logs` table, insert sorted by ts | full load 207,820 lines (3 files) | — | **~1.2 s** | parse 0.9 s · sorted insert 0.4 s; typed request_id/instance_id/tenant_id/status/latency_ms via regex. Plan 050 |
| 2026-10-17 | MCP tool (plan 003) | `search_logs("parity")`, whole corpus, 2 queries (rows + summary) | — | p50 11 / p95 14 ms | 20 runs, Python call incl. psycopg round trips |
| 2026-10-17 | MCP tool | `search_logs` relevance (BM25), July filter | — | p50 16 / p95 19 ms | WAND top-k via `optimize_top_k` |
| 2026-10-17 | MCP tool | `get_context` node ±300 s (busy node: 499 before / 1,610 after) | — | p50 34 / p95 41 ms | 4 queries (2 lists + 2 counts) |
| 2026-10-17 | MCP tool | `get_context` midplane ±60 s | — | p50 22 / p95 28 ms | |
| 2026-10-17 | MCP `count_by` / `trend` (plan 051), team join + zero-filled buckets | 16 calls over both datasets (`bench/check_counts.py`) | — | median 7 ms, p95 45 ms, max 76 ms | count_by team ≈ 110 ms cold; trend by team (96 weekly rows) ≈ 150 ms. index is eventually consistent: query only after `VACUUM (REFRESH_TABLE)` (plan 052) |
| 2026-10-17 | Full reload `load/reload.sh` (plan 052): DROP + BGL + OpenStack + `VACUUM` refresh/compact + checks | end to end | — | **~21 s** | BGL parse 10.5 s + insert 1.8 s · OpenStack 1.4 s · `COMPACT_TABLE` 6.1 s · checks 1 s; 2 runs, 29/29 checks |
| 2026-10-17 | Template masking in the BGL loader (7 regexes, plan 004) | BGL parse step | 16.2 s | 23.2 s | +7 s for 1,126 templates over 4.7M lines; pattern id assignment 75 ms; full reload (schema + BGL + OpenStack) 27 s |
| 2026-10-17 | Episodes / bursts / patterns at load (`load/95_patterns_episodes.sql`, window `LAG` gap split) | build 3 tables | — | 1.2 s / 0.9 s / 0.15 s | 2,417,597 node-episodes · 36,714 bursts · 1,126 patterns; whole pipeline ≈ 31 s |
| 2026-10-17 | Template masking in the OpenStack loader (9 regexes, plan 053) | OpenStack loader | ≈ 1.2 s (plan 050, whole loader) | stage 1.3 s + insert 0.3 s | 106 templates over 207,820 lines; full `./load/reload.sh` (both datasets, publish, patterns, 32 checks) 27.7 s |
