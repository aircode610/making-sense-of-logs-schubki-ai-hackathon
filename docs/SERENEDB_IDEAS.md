# SereneDB feature catalog → tool ideas (unfiltered)

_2026-10-18. Source: a full pass over the SereneDB docs (`docs/serenedb/rendered/**`, 341 pages; MCP `serenedb-docs`),
the brief (`docs/BRIEF.md`) and our role spec (`docs/ROLES.md`). Purpose: list **everything** SereneDB can do that is
relevant to the challenge, as ideas for new atomic MCP tools and internal pipeline steps. Nothing here is filtered or
approved yet; each idea that survives gets its own plan and is measured (`eval/run_eval --compare`, `bench/replay_tools.py`)._

Legend: **Role** E = engineer, L = team lead, M = manager, A = all · **Brief** = which brief line it moves
(R = role insight 30 %, S = search + analytics 25 %, Rec = recommendation 25 %, X = execution/novelty 20 %,
MCP = Best MCP award, Huge = Huge Datasets award, Bonus = traces/metrics/row-level security) · **Effort** S/M/L ·
⚠ = needs verification (not tested on our instance).

---

## 0. Design principles for the new tools

1. **Atomic tools, query already written.** Each tool answers one question shape with a fixed, reviewed SQL query; the
   LLM only fills typed fields (dataset, time range, node, pattern id, enum options). Open-ended SQL is not needed
   (brief: "a small set of parameterized queries is sufficient").
2. **The queries live in SereneDB as table macros** (`CREATE MACRO name(args) AS TABLE …`, `sql/statements/create_macro`).
   The MCP tool becomes a thin wrapper: `SELECT * FROM burst_timeline($dataset, $burst_id, $limit)`. Wins:
   - one source of truth: judges can run the exact same macro from `psql`;
   - the tool's SQL in the envelope is one short line instead of a 40-line CTE;
   - per-role `GRANT EXECUTE`-style access via roles + views (see §L);
   - tests in `bench/` call the macro directly.
3. **Every tool keeps the envelope** (`query, filters, scope, total_matches, truncated, evidence_id, elapsed_ms`) and
   caps rows (≤ 50). Add `next_tools` hints ("to see what happened around a row, call get_context(line_id)").
4. **Atomic vs generic — the trade-off.** Atomic tools give exact descriptions, typed inputs, predictable result shapes,
   and tool selection we can measure (E7). The cost is selection confusion when there are too many. The plan: atomic
   tools, but each role's gatherer sees ≤ 12 of them (per-role subsets, already in place), with `verb_object` names
   grouped by prefix (`find_*`, `count_*`, `compare_*`, `explain_*`). Optional escape hatch: `check_sql` (§M) to plan a
   query without running it. A generic `run_sql` stays **out** by default.
5. **Measure every new tool**: does E7 tool selection stay at 1.0? Does E1/E2c go up on the questions it targets? Does
   `replay_tools.py` stay at 100 %? (plan 010 loop).

---

## 1. Gap analysis: brief + role question bank vs today's 8 tools

Today: `search_logs`, `get_context`, `count_by`, `trend`, `rate_vs_baseline`, `top_patterns`, `priority_table`,
`value_outliers`.

| Requirement / question | Covered today? | Gap → idea (section) |
|---|---|---|
| Full-text search + time filters (brief, engineer) | ✅ `search_logs` | No fuzzy/typo tolerance, no proximity, no highlighted snippet (§A, §C) |
| Nearby events (brief, engineer) | ✅ `get_context` | No "which pattern preceded this on the same node" (§K ASOF) |
| Counts by component/team + trend (brief, lead/manager) | ✅ `count_by`, `trend` | Trends count lines; no burst-per-week trend, no slope (§K) |
| Phrase / fuzzy / detailed comparisons (brief, optional) | ⚠ phrase only | `ts_levenshtein`, `ts_ngram`, proximity `##`, `min_match` (§A) |
| Agent manages its own index workspace (brief, optional) | ❌ | `create_focus_index` / `drop_focus_index` + measured break-even (§H) |
| Larger datasets, remote Parquet (brief, optional; Huge award) | ❌ | Index views over the 50B-row OTel Parquet, Thunderbird (§I) |
| Logs ↔ traces/metrics (bonus) | ❌ | OTLP listener, `otel_traces`, ASOF joins (§J) |
| Row-level security per role (bonus) | ❌ | Roles + grants on views/macros; no native RLS (§L) |
| E6 "Has this error happened before? Is it new?" | ⚠ partly (`first_ts` inside top_patterns) | `pattern_history` (§N) |
| E7 "Which error came first in this burst?" | ❌ | `burst_timeline`, `first_in_burst` (§N) |
| E5 "Local to one node or system-wide right now?" | ⚠ via count_by | `spread_now` (nodes, racks, top-node share) (§N) |
| L3 latency p50/p95 per service per hour | ⚠ value_outliers | `latency_profile` with `quantile_cont`/`histogram` (§K) |
| L5 "What's new this period?" | ⚠ `rank_by=growth` / `new` flag | `whats_new` + significant terms (§D) |
| L7 "Do these two patterns occur together?" | ❌ | `co_occurrence` (§K) |
| M3 "Is reliability improving?" (problem episodes per week) | ⚠ lines only | `reliability_trend` on bursts with slope (§K) |
| "What does pattern X mean / similar problems?" | ❌ | `similar_patterns` via embeddings or MinHash (§F) |
| Discoverability: which values exist (nodes, components, teams) | ❌ | `list_values`, `describe_corpus`, `suggest_terms` (§D) |

---

## A. Full-text search operators (`sql/indexes/inverted/full-text-search.md`, `sql/functions/search/full-text.md`)

What SereneDB has that we don't use yet: `ts_phrase(..., slop := N)` and the `##` proximity chain with gaps
(`'link' ## [0,3] ## 'severed'`), `ts_levenshtein(text, distance)` (typos), `ts_ngram` (n-gram similarity),
`ts_starts_with`, `ts_like`, `ts_regexp` (RE2 on tokens), `ts_any(list, min_match)` / `::min_match(K)` ("at least 2
of these 4 words"), `ts_all`, `ts_compound(must, must_not, should)` (ES bool query), `^` boosting, `to_tsquery` with
Lucene syntax (`+required -excluded "phrase" term~ prefix*`), `ts_between`/`ts_ge` ranges on indexed columns,
`ts_lexize` (show how a string is tokenized), convenience predicates `has_any_tokens`, `levenshtein_matches`.

Ideas:
- **A1 `search_logs` modes** (E, S, Effort S): add `match = all | any | phrase | near | fuzzy | prefix | at_least_k`
  enum + `slop`/`distance`/`k` fields; the LLM picks a mode, the query stays fixed. Covers the brief's optional "phrase
  matching, fuzzy matching".
- **A2 `search_logs` exclusions** (E, S): `exclude_text` field → `!!` / `must_not` so "kernel panic -heartbeat" works.
- **A3 `explain_search(text)`** (E, MCP): returns `ts_lexize('log_body_dict', text)` and the `EXPLAIN` filter tree,
  so the agent (and a judge) can see why a search matched 0 rows ("your term `ciod:` tokenizes to `ciod`").
- **A4 typo recovery** (E, S): when a search returns 0, retry automatically with `ts_levenshtein(term, 1)` and say so
  in the scope ("0 exact matches; 412 with one-edit fuzzy matching on `severd`→`severed`").
- **A5 boosted multi-field search** (E): `body @@ (q ^ 3) OR template @@ q` — rank lines whose *pattern template*
  matches above incidental mentions.
- **A6 range predicates through the index** (perf): rewrite our `ts >= / ts <` filters as `ts @@ ts_between(...)` and
  numeric `latency_ms @@ ts_ge(...)`, check `EXPLAIN` shows them in the `IRESEARCH_SCAN` filter, record in
  `PERFORMANCE.md`.

## B. Ranking (`sql/indexes/inverted/ranking.md`, `cookbook/search/{ranking,recency-and-decay,boosting,reciprocal-rank-fusion}.md`)

Scorers: `BM25(k1,b)`, `TFIDF`, `lm_jm`, `lm_dirichlet`, `indri_dirichlet`, `dfi`, `raw_tf`, `raw_boost`, `raw_dl`;
arithmetic on scores; WAND top-k (`optimize_top_k`, we already enable it); RRF for fusing ranked lists.

Ideas:
- **B1 `rank = relevance | recent | severe | rare`** in `search_logs` (E, S): `BM25 × exp(-age/τ)` (recency decay),
  `BM25 × severity_weight`, `BM25 × idf(pattern)` (rare messages first). The LLM picks the intent; formula is fixed.
- **B2 "most informative lines" for evidence** (E, Rec): rank lines inside a burst by `dfi('chi_squared')` or
  `lm_dirichlet` so the sample shown is the most distinctive, not the first 10.
- **B3 RRF of text + pattern rank** (E): fuse BM25 rank with "pattern is a Jev problem" rank, so evidence lines lean to
  real faults.
- **B4 show WAND** (perf, X): `EXPLAIN` shows `Top: k, optimized` for top-k searches; screenshot for slides.

## C. Highlighting (`sql/functions/search/highlighting.md`, `cookbook/search/highlighting.md`)

`ts_highlight(body, ts_offsets(body), 'StartSel=«, StopSel=», MaxWords=20, MaxFragments=2')` on the indexed column;
needs the `offset` feature flag in the dictionary to be fast (otherwise recomputed per row).

Ideas:
- **C1 snippets in every search result** (E, MCP, S Effort S): return `snippet` with the matched words marked, so the
  answer card quotes *why* a line matched. Add `offset` to `log_body_dict` (`WITH (frequency, position, norm, offset)`),
  measure index size and load time.
- **C2 evidence appendix with highlights** (Rec): the card's evidence section shows highlighted lines → easier human
  check ("shows its work").

## D. Term dictionary: facets, significant terms, suggestions (`sql/functions/search/term-dictionary.md`, cookbook `significant-terms`, `tag-cloud`, `faceted-search`, `autocomplete`, `spell-correction`, `saved-searches`, `result-cardinality`)

`ts_dict_agg / ts_dict_count / ts_dict_freq / ts_dict_score / ts_dict_min / ts_dict_max` read the index's term
dictionary directly (no document scan); plain `GROUP BY` / `count(DISTINCT)` / `GROUPING SETS` on keyword columns are
rewritten onto it (`EXPLAIN` shows `TsDict:`); `approx_count_distinct` for cardinality.

Ideas:
- **D1 `distinctive_terms(window, baseline)`** — significant terms (E, L, S, Effort M, ★ novelty): foreground =
  lines in the incident window (or one burst / one node), background = the previous N days; rank tokens by lift
  `fg − bg × fg_total/bg_total` with a floor. Answers "what is different about this incident?" without an LLM.
  Same tool for L5 "what's new this period" (terms that appear now but not before).
- **D2 `facet(filter, dimensions[])`** (A, S, Effort S): one query, `GROUPING SETS ((component),(severity),(rack),
  (team))` over the matches of a search → "of 49,651 matching lines: 98 % KERNEL, FATAL; 1,024 nodes in 16 racks".
  Served from the dictionary; whole-corpus aggregation the brief asks for, cheap.
- **D3 `list_values(dataset, field, prefix?)`** (A, MCP, Effort S): distinct components / racks / nodes / teams /
  services with counts, from the dictionary. Lets the agent discover valid filter values instead of guessing.
- **D4 `suggest_terms(text)`** (E, MCP, Effort S): autocomplete + spell correction from the dictionary
  (`ts_levenshtein` over terms ranked by `ts_dict_count`). Fixes agent typos before searching.
- **D5 `vocabulary(window)`** — tag cloud by `ts_dict_freq` (L): loudest words in a period; contrast count vs freq to
  separate "many lines" from "many nodes".
- **D6 watchlist / saved searches** (L, M, Effort M): a `watchlist` table of known-bad terms or pattern ids (from Jev
  problem patterns); `which_watches_fired(window)` = which saved searches have hits in the window, with counts.
  "Percolator" pattern from the cookbook. Could also be written by the agent itself after an investigation.
- **D7 `data_range(dataset)`** (A): `ts_dict_min/max` and counts → the agent states the exact corpus span in every
  scope line.

## E. Text analysis / custom dictionaries (`sql/indexes/inverted/text-analysis.md`, `sql/statements/create_text_search_dictionary/*`, `sql/functions/search/tokenizers/*`)

Templates: `split_text`, `split_by_pattern` (RE2 extract or split), `split_by_delimiters`, `split_text_csv`,
`split_by_non_alpha`, `split_text_icu`, `generate_ngrams`, `generate_sparse_ngrams` (substring search), 
`generate_wildcard_ngrams`, `generate_shingles` (word n-grams), `expand_path` (path → all ancestors), `stem_words`,
`remove_stopwords`, `filter_tokens` (lambda filter), `normalize_tokens`, `expand_solr_synonyms`,
`expand_wordnet_synonyms`, `minhash`, `classify_text` / `find_nearest_words` (fastText models), the `sql` template
(any SQL expression as a tokenizer), `pipeline` (`|`), `keyword`.

Ideas:
- **E1 hierarchical location field with `expand_path`** (E, L, ★, Effort S): index BGL `node` as
  `R02 / R02-M1 / R02-M1-N0 / …` tokens in one field, so `location @@ 'R02-M1'` matches every node under that
  midplane without separate `rack`/`midplane` columns, and `get_context(scope=…)` becomes one predicate. Also lets
  `count_by(location_level)` roll up at any level.
- **E2 entity extraction at index time with `split_by_pattern`** (E, S): extra indexed expressions that pull IPs
  (`\d+\.\d+\.\d+\.\d+`), hex codes, job ids, error numbers, file paths out of `body` as their own terms →
  `search_logs(ip='172.16.96.116')`, `count_by(ip)`. "Every error points at 172.16.96.116" becomes a count, not a
  guess from samples.
- **E3 log-jargon synonyms** (E, S): `expand_solr_synonyms('error, err, fail, failed, failure\nkill => terminate\n
  ciod, io daemon\n…')` dictionary so the agent's plain-English search finds the log's spelling.
- **E4 substring search on ids** (E): `generate_sparse_ngrams` dictionary on `instance_id` / `request_id` so a prefix
  or fragment (`9fafc51c`) finds the full UUID.
- **E5 `minhash` near-duplicate messages** (L, Effort M): signature index over masked bodies → group messages that are
  almost the same but differ in more than our masks catch; a check on our 1,126 patterns ("these 14 patterns are
  near-duplicates, merge them?").
- **E6 template field with `keyword` dictionary + facets** (L): store `template` on each row (or `pattern_id` →
  dictionary facets) so "top patterns in this search" is a `TsDict` facet.
- **E7 `classify_text` with a fastText model** ⚠ (wild, Effort L): train a tiny fastText classifier on BGL alert labels
  (labels table, *tune split only*) → index-time category tokens. Probably not worth it vs Jev, but it is "AI inside
  the tokenizer".
- **E8 `sql` template**: any normalization we do in `10_bgl.sql` (masks) could become an index-time dictionary
  instead of a column — the masked template becomes searchable without storing it.

## F. Vector and hybrid search (`sql/indexes/inverted/{vector-search,hybrid-search}.md`, `sql/functions/vector.md`, cookbook `hybrid-search`, `similar-documents`, `reciprocal-rank-fusion`)

`FLOAT[N]` columns with `ivf (metric, nlist, quant)` or `hnsw (m, ef_construction)` in the same inverted index as text;
kNN `ORDER BY emb <=> q LIMIT k`; range search; filtered ANN (`WHERE body @@ … ORDER BY emb <-> q`); RRF fusion;
quantization (`sq8`, `pq`, `rabitq`, `tq`); `sdb_ivf_search_nprobe`, `sdb_hnsw_ef_search`.

Embeddings come from `ai_embed` (needs an OpenAI-compatible embeddings endpoint: OpenAI key, or a local Ollama
`all-minilm` container ⚠). Key cost insight: **embed the ~1,232 pattern templates, not the 5M lines** (seconds,
cents).

Ideas:
- **F1 `similar_patterns(pattern_id | text, k)`** (E, L, ★, Effort M): "what else looks like this error?" — kNN over
  template embeddings, with each neighbour's bursts/nodes/team. Groups related faults (all "Link has been severed"
  variants, all ciod socket errors) that differ in wording.
- **F2 `find_patterns(meaning)`** — semantic search over templates (E, L): "network problems", "memory errors",
  "job launch failures" → pattern ids, then counts via `top_patterns(pattern_ids=…)`. Bridges the agent's vocabulary
  and the log's.
- **F3 hybrid search over lines via their pattern** (E): lexical `@@` on body + vector rank on the line's pattern
  embedding, fused with RRF.
- **F4 cross-dataset analogies** (L, wild): nearest OpenStack patterns to a BGL pattern ("is there a cloud-side
  equivalent of this storage error?").
- **F5 incident similarity** (L, M, wild): embed each burst as the sequence of templates around it (or mean of
  template vectors) → "the Nov 17 ciod storm looks like the Sep 3 storm" (recurrence across time, not just same
  pattern).
- **F6 embedding-free fallback** (S): MinHash signatures (§E5) for "similar" when no embedding provider is available.
- **F7 problem-type clusters** (M): k-means is built into IVF (`nlist` clusters); expose the IVF cluster of each
  pattern as a "problem family" for a manager-level roll-up ⚠ (cluster ids are not exposed directly; would need
  our own clustering via SQL over vectors).

## G. AI functions in SQL — internal use (`sql/functions/ai.md`)

Available: `ai_system_one` (Jev: `noul` probability, `choice` with probabilities, `score` on an ordered scale,
multi-question `questions := {...}` struct, `batch_size`), chat functions over an OpenAI-compatible secret
(`ai_generate`, `ai_classify`, `ai_classify_labels`, `ai_extract`, `ai_filter`, `ai_score`, `ai_rerank`,
`ai_translate`, `ai_redact`), aggregates `ai_agg(text, instruction)` and `ai_summarize_agg(text)` (map-reduce over
big groups), embeddings `ai_embed`, `ai_similarity`; stored generated columns (classify on insert); quotas
`sdb_ai_max_api_calls_per_query`, `sdb_ai_max_output_tokens_per_query`; `sdb_ai_throw_on_error=false`; dedupe of
identical texts per chunk (cheap for repetitive logs).

Ideas (Jev keeps confidences computed, per non-negotiable 7):
- **G1 more Jev questions per pattern, one call** (A, R, ★, Effort S): extend `judge_patterns.sql` to a
  `questions := {...}` struct: `fault` (noul, have), `dump` (noul, have), `cause_family` (choice: hardware / network /
  storage-io / software / job-config / environment), `actionable` (score: none/low/high: is there something to fix?),
  `symptom_or_cause` (choice), `owner_hint` (choice over our teams, to **cross-check the ownership table**). Stored in
  `pattern_judgments`; tools return them with probabilities. Manager gets "cause family" roll-ups with computed
  confidence.
- **G2 Jev claim support score** (Rec, trust, Effort M): for each card fact, ask Jev `noul` "does this evidence row
  support this sentence?" → a calibrated per-fact support probability shown next to the fact; an extra computed
  signal on top of the deterministic number check.
- **G3 stored generated Jev column for live ingest** (X, wild): `pattern_kind GENERATED ALWAYS AS (ai_system_one(...))
  STORED` on a `pattern_templates` table, so a new pattern from new logs is judged on insert (demo7 shows the
  mechanism). Story: "new log source → patterns → judged automatically".
- **G4 `summarize_burst(burst_id)`** (E, L, Effort M): `ai_summarize_agg(body ORDER BY ts)` over a burst's distinct
  lines, **precomputed and stored** for the top bursts, labelled "model summary, not evidence". Agent cites counts from
  SQL and the summary as context.
- **G5 `ai_extract` structured fields from templates** (S): `{"resource": …, "operation": …, "error_code": …}` per
  template (1,232 calls) → new facet columns ("operation=mount fails on 3 patterns").
- **G6 `ai_classify_labels` subsystem tags** (L, M): multi-label tags per template (memory, network, filesystem,
  scheduler, hardware, job) → team-independent roll-ups.
- **G7 `ai_rerank` search results** (E): rerank the top 50 BM25 hits against the engineer's question (`ORDER BY
  ai_rerank(q, body)` in a subquery with `LIMIT`, per the docs' cost rule).
- **G8 `ai_agg` per team** (M, wild): "what do these 40 problem patterns have in common?" as a one-line manager
  context, clearly labelled as model text.
- **G9 `ai_translate` for German stakeholders** (M, X, wild): SchubKI jury is German; `answer_in = de` option that
  translates the final card in SQL. Low effort demo moment.
- **G10 `ai_redact` for the manager view** (Bonus, wild): strip IPs / tenant ids / user paths from lines a manager
  role sees.
- **G11 cost guards** (X): set `sdb_ai_max_api_calls_per_query` in every tool that calls AI, report `ai_calls` in the
  envelope (cost is a judged property for the Huge award).
- ⚠ Chat functions need an OpenAI-compatible endpoint. Options: OpenAI key, OpenRouter (Claude models via
  `anthropic/...` ids), local Ollama. Anthropic's own OpenAI-compatible endpoint is untested here.

## H. Indexes, workspace and performance (`sql/indexes/*`, `sql/statements/create_index/inverted.md`, `sql/indexes/inverted/maintenance.md`, `cookbook/performance/*`)

Partial inverted indexes (`CREATE INDEX … WHERE predicate`, kept current by DML), `INCLUDE` columns, indexed
expressions, generated columns, `row_group_size`, `optimize_top_k`, `refresh_interval`/`compaction_interval`,
`VACUUM (REFRESH|COMPACT|RECOMPUTE_STATS)`, `sdb_indexes()`, `sdb_metrics` per-index stats (`num_docs`,
`index_size`, `avg_commit_time_ms`…), ART indexes, zonemaps and sort order, `EXPLAIN` / `EXPLAIN ANALYZE`,
`TEMP` tables, prepared statements.

Ideas:
- **H1 `create_focus_index(dataset, start, end, filter?)` / `drop_focus_index(name)`** (E, X, brief optional
  extension, ★, Effort M): partial inverted index over one investigation window (`WHERE ts BETWEEN … AND dataset=…`)
  with extra features (offsets for highlighting, extra extracted fields). Tools that get `index=` use it.
  **Measure what the brief asks**: build time vs time saved over N repeated questions → break-even N, in
  `PERFORMANCE.md` and on a slide.
- **H2 `index_stats()`** (MCP, X): `sdb_indexes()` + `sdb_metrics` (docs, size, segments, commit time) so the agent
  and judges see the workspace state; also proves the focus index exists/was dropped.
- **H3 `explain_tool(tool, args)`** (MCP, X): returns `EXPLAIN` of a tool's query (shows `IRESEARCH_SCAN`, `TsDict:`,
  `Top: k, optimized`), so "does the index serve this?" is visible. Plus `elapsed_ms` already in envelopes.
- **H4 indexed time buckets** (perf): indexed expressions `(date_trunc('hour', ts))` / generated `hour` column → trend
  and baseline queries become dictionary facets.
- **H5 `INCLUDE` the columns tools return** (perf): `INCLUDE (component, severity, node, pattern_id)` for faster
  materialization; measure with the replay bench.
- **H6 ART index on `bursts(dataset, pattern_id, start_ts)`** (perf): point lookups for burst drill-down.
- **H7 prepared statements** (perf): prepare each tool query once per connection.
- **H8 sort order + zonemaps** on `bursts` / `episodes` by `start_ts` (perf): range pruning, measured.

## I. Views, external data, remote data, huge datasets (`sql/indexes/inverted/{views,external-data}.md`, cookbook `indexing-external-data`, `iceberg-insert-to-searchable`, `network_cloud_storage/*`, `data_import_and_export/{parquet,multiple_files,partitioning}`)

An inverted index on a **view over `read_parquet('https://…/*.parquet')`** = zero-ETL full-text + BM25 + facets over
files that stay in S3; only postings are built; counts/scores answered from the index; other columns materialized
live; `REINDEX` incremental for globs; `reindex_interval`; Iceberg via `CREATE SERVER … iceberg_fdw`; attached
PostgreSQL/ClickHouse (`postgres_fdw`, `clickhouse_fdw`) can be indexed too; `parquet_metadata`, `parquet_bloom_probe`,
hive partitioning, globs + `filename` column, `USING SAMPLE`.

Ideas (Huge Datasets award; "remote data source indexing" is what the judges suggested):
- **I1 remote OTel Parquet, queried in place** (Huge, ★, Effort M): `CREATE VIEW otel_remote AS SELECT * FROM
  read_parquet('https://public-pme.s3.eu-west-3.amazonaws.com/text_bench/part_000.parquet')` (1B rows, first
  30 min). Tools: `remote_count_by(service, severity, window)`, `remote_search(text, window, limit)` with the same
  envelope + `rows_scanned`, `bytes_read` (from `EXPLAIN ANALYZE`) and wall time. Show how widening to
  `part_00[0-9]` (5 h) costs "a line of config".
- **I2 index the remote view** (Huge, brief optional indexing, ★, Effort L): `CREATE INDEX otel_remote_idx ON
  otel_remote USING inverted (Timestamp, ServiceName, SeverityText, Body otel_body_dict)` over one part or a time
  slice (the files are sorted by timestamp; a `WHERE` on the view body keeps it a slice). Measure: build time, index
  size, query time before/after, break-even. This is the "remote data source indexing" story end to end.
- **I3 pruning evidence** (Huge): `parquet_metadata()` shows row-group min/max on `Timestamp` → explain why a 5-minute
  window reads only a few row groups; `parquet_bloom_probe` for `TraceId` lookups.
- **I4 role answers on OTel data** (Huge, R): same three roles over the OTel demo app (services = owners): engineer
  investigates one trace's errors, lead sees error rate per service per 5 min, manager ranks services. Needs an
  ownership mapping for OTel services (fictional, like ours).
- **I5 a bigger Loghub set** (Huge, Effort M–L): Thunderbird (211M lines, 29.6 GB) or Windows (114M): load to local
  Parquet once (`COPY … TO … (FORMAT parquet)` partitioned by day), index the view over the glob, run the same
  pattern pipeline. Report rows, size, load time, query p95.
- **I6 `USING SAMPLE` estimates** (Huge, S): on very large remote data, an explicit `sample_estimate(…)` tool that
  says "estimated from a 1 % bernoulli sample", never presented as an exact count.
- **I7 Iceberg pipeline** (wild): write our `logs` to an Iceberg table and index it via `iceberg_fdw`, `REINDEX` as a
  freshness barrier — "any engine writes, SereneDB searches".
- **I8 attach an external Postgres** (wild): e.g. a CMDB/ownership table living in Postgres, joined live
  (`postgres_fdw`) — ownership stays in the system of record.

## J. OpenTelemetry, traces and metrics (`data_import_and_export/opentelemetry.md`, `docs/serenedb/otel/otel_schema.sql`)

Built-in OTLP/HTTP receiver (`--listen 'http://0.0.0.0:4318?api=otel'`, already in our compose) writes `otel_logs`,
`otel_traces`, five `otel_metrics_*` search tables with an inverted index each; trace↔log join on `trace_id`;
`quantile_cont(duration_ns, …)`; facets via `ts_dict_*`; expression indexes on hot attribute paths.

Ideas:
- **J1 replay our logs as OTLP** (X, ★, Effort M): a small exporter that posts BGL/OpenStack lines to `/v1/logs`
  (service.name = component, resource attrs = node/rack) → our tools run on `otel_logs` too. Story: "plug any OTel
  pipeline into this agent".
- **J2 traces bonus** (Bonus, Effort L): HDFS_v3 TraceBench, RCAEval or Nezha (trace ids in logs) → `otel_traces` +
  `otel_logs`; tools `trace_timeline(trace_id)`, `slow_spans(service, window)`, `logs_for_trace(trace_id)`,
  `error_rate(service, bucket)`.
- **J3 metrics bonus** (Bonus): RCAEval metrics → `otel_metrics_gauge`; `metric_around(event_ts, metric, window)` via
  **ASOF join** (value of CPU/memory as of each error).
- **J4 OpenStack request = pseudo-trace** (E, Effort S): treat `request_id` as a trace id; `request_timeline` across
  nova-api → scheduler → compute with per-hop latency (we have `latency_ms` inline).

## K. SQL analytics features (`sql/functions/aggregates`, `window_functions`, `query_syntax/*`, `statements/pivot`, `create_macro`, cookbook `sql_features/asof_join`)

Statistical aggregates (`regr_slope`, `regr_intercept`, `corr`, `covar`, `entropy`, `mad`, `median`, `mode`,
`quantile_cont/disc`, `skewness`, `kurtosis`, `stddev`), approximate (`approx_count_distinct`, `approx_quantile`,
`approx_top_k`, `reservoir_quantile`), `histogram`, `equi_width_bins`, window functions (`lag`, `lead`, `ntile`,
`cume_dist`, `fill`…) + `QUALIFY`, `GROUPING SETS / ROLLUP / CUBE`, `PIVOT`/`UNPIVOT`, ASOF joins, recursive CTEs
(`USING KEY`), `time_bucket`, `generate_series` (zero-filled buckets), lambdas and list functions, `SUMMARIZE`,
`DESCRIBE`, table macros, `query_table`.

Ideas:
- **K1 `co_occurrence(pattern_a, pattern_b | top, window_s, scope=node|midplane)`** (L7, ★, Effort M): how often B
  follows A on the same node within N seconds, vs chance (lift); `corr` of hourly counts as a second signal. Labelled
  as association, never causation.
- **K2 `precursors(pattern_id, window_s)`** (E, Rec, ★): ASOF join each occurrence to the *previous* event of any
  other pattern on the same node → "in 87 % of `rts panic` bursts, `ddr uncorrectable` appeared on the same node
  within 2 min before". Strong engineer hypothesis material, computed.
- **K3 `failure_chain(burst_id)`** (E, L, wild): recursive CTE walking "next burst on the same midplane within 10 min"
  → cascade chains across racks; return as an ordered list (and a Mermaid graph in the card).
- **K4 `reliability_trend(dataset, period, bucket=week)`** (M3, Effort S): problem *bursts* per week (Jev filter),
  zero-filled with `generate_series`, plus `regr_slope` per week and a plain verdict rule ("slope < 0 and last 2
  weeks below median → improving"). Computed, not adjectives.
- **K5 `rollup(dataset, period, by=[team, component, severity])`** (L, M, S, Effort S): one query with
  `GROUPING SETS`/`ROLLUP` → totals, subtotals per team and per component, whole-corpus row. Exactly the brief's
  "aggregation over the whole base corpus".
- **K6 `heatmap(dataset, period, rows=team|component|rack, cols=week|day|hour)`** (L, M): `PIVOT` matrix of bursts,
  ready to render as a small table/chart in the card or UI.
- **K7 `periodicity(pattern_id)`** (L, Effort M): inter-arrival times with `lag()`, `histogram`/`mode` of gaps →
  "recurs every ~6 h" or "every job launch" (cron-like faults).
- **K8 `concentration(pattern_id, period)`** (L4): top-node share, `entropy` over nodes, `approx_top_k(node, 5)` →
  "one bad node" vs "fleet-wide" with numbers.
- **K9 `latency_profile(service, period, bucket)`** (L3): `quantile_cont(latency_ms, [0.5,0.95,0.99])`,
  `histogram(equi_width_bins…)` per nova service per hour, plus error rate (`status >= 500`).
- **K10 `change_points(series)`** (L, M, wild): simple SQL change detection (rolling mean ± k·MAD with window
  functions) on daily bursts → dates where a pattern's level shifted.
- **K11 `describe_corpus()`** (A, MCP, Effort S): `SUMMARIZE`-style stats per dataset (rows, span, components,
  severities, patterns, bursts) as the agent's first orientation call.
- **K12 table macros as the tool layer** (MCP, X, Effort M): see §0.2 — every tool above is a macro.
- **K13 `QUALIFY` top-n per group** (L): "top 3 patterns per team" in one query.

## L. Security and roles (`security/*`, `sql/statements/{grant,create_role,set_role}`)

PostgreSQL-style roles, `GRANT/REVOKE`, column privileges, role membership + `SET ROLE`, HBA auth. **No native
row-level security policies** found in the docs.

Ideas (bonus "row-level security to control which records each role can access"):
- **L1 one DB role per persona** (Bonus, ★, Effort M): `engineer` can read `logs` raw lines; `lead` and `manager`
  get only views/macros of aggregates (bursts, patterns, priority), `manager` has no `SELECT` on `logs.body` (column
  privilege). The MCP server opens its connection with `SET ROLE <persona>` per call, so **the database enforces**
  what each role may see. Honest note in README: emulated with views + grants, not RLS policies.
- **L2 per-team row scoping** (Bonus): views `logs_team_<team>` filtered by ownership, granted to team roles → a
  team lead only sees their components.
- **L3 audit**: every tool call already carries its SQL; add `current_role` to the envelope.

## M. Meta, ops and integrations (`sql/functions/{metadata,docs}.md`, `clients/{elasticsearch-api,grafana}.md`, `configuration/*`)

`sdb_logs()` (SereneDB's own log), `sdb_metrics`, `sdb_settings`, `sdb_tables`, `sdb_functions`; the server-side
docs MCP endpoint (`?api=mcp`: `search_docs`, `read_doc`, `describe_object`, **`check_sql`** = plan a statement
without running it); Elasticsearch-compatible REST API (`?api=es`, `_bulk`, `_search`); Grafana via the Postgres
data source; `COPY … TO` Parquet/JSON/CSV.

Ideas:
- **M1 dogfooding: SereneDB's own logs as a third dataset** (X, wild, ★ demo): `sdb_logs()` → the same agent
  investigates the database it runs on ("why did that commit fail?"). One-line loader, live data.
- **M2 `check_sql` escape hatch** (MCP): if a question needs a query no tool has, the agent drafts SQL and validates it
  with `check_sql` (plan only, never runs) → we show it to the user as a *suggested query*, not as evidence. Keeps
  "numbers from executed queries" intact.
- **M3 ES API ingest** (X, wild): Filebeat/Logstash/ES clients `_bulk` straight into SereneDB → our tables; "drop-in
  for an ELK stack". Also lets Kibana-style tools read our data ⚠.
- **M4 Grafana dashboard for the manager** (X, Effort M): the priority table and reliability trend as Grafana panels
  on the same SQL/macros; the agent answer links to the panel.
- **M5 evidence bundle export** (Rec): `COPY (SELECT …) TO 'runs/<id>/evidence.parquet'` per answer, so evidence is
  re-checkable offline.
- **M6 index health in answers** (trust): `sdb_metrics.num_buffered_docs > 0` → the tool warns "index not fully
  refreshed, counts may lag" (we hit this eventual-consistency issue in plan 052).

## N. New atomic tools for the role question bank (drawn from the sections above)

| Tool (fields the LLM fills) | Backing SereneDB feature | Role · question |
|---|---|---|
| `describe_corpus()` | SUMMARIZE, `ts_dict_min/max`, counts | A · orientation, scope lines |
| `list_values(dataset, field, prefix?, limit)` | term dictionary facets | A · valid filter values |
| `suggest_terms(text)` | dictionary + `ts_levenshtein` | E · typo fix before search |
| `explain_search(text)` | `ts_lexize`, `EXPLAIN` | E · why 0 hits |
| `search_logs(…, mode, exclude_text, rank, highlight)` (extended) | `##`, slop, fuzzy, `min_match`, scorers, `ts_highlight` | E2 |
| `facet(dataset, text, start, end, dims[])` | `GROUPING SETS` on dictionary | A · E5, L1 |
| `burst_timeline(burst_id | pattern_id+time)` / `first_in_burst` | bursts + window functions | E7 |
| `pattern_history(pattern_id)` | patterns, bursts, `generate_series` | E6 "new or recurring?" |
| `spread_now(pattern_id, window)` | `count(DISTINCT)`, `approx_top_k`, entropy | E5 |
| `precursors(pattern_id, window_s, scope)` | ASOF join | E · hypothesis material |
| `distinctive_terms(window, baseline)` | significant terms (`ts_dict_*`) | E, L5 |
| `similar_patterns(pattern_id | text, k)` / `find_patterns(meaning)` | `ai_embed` + IVF/HNSW, or MinHash | E, L |
| `request_timeline(request_id)` | OpenStack request as trace | E3/E4 |
| `latency_profile(service, start, end, bucket)` | `quantile_cont`, `histogram` | L3 |
| `co_occurrence(a, b|top, window_s, scope)` | self-join / ASOF, `corr` | L7 |
| `concentration(pattern_id, period)` | top-node share, entropy, `approx_top_k` | L4 |
| `whats_new(dataset, period)` | `first_ts` + significant terms | L5 |
| `periodicity(pattern_id)` | `lag`, `histogram` | L |
| `rollup(dataset, period, by[])` | `GROUPING SETS`/`ROLLUP` | L, M · whole-corpus |
| `heatmap(dataset, period, rows, cols)` | `PIVOT` | L, M |
| `reliability_trend(dataset, period, bucket)` | bursts, `generate_series`, `regr_slope` | M3 |
| `team_risk(team, period)` | priority inputs per team + trend | M2 |
| `what_if_priority(weights)` | same SQL, different weights | M · "what if spread mattered more?" (still computed) |
| `which_watches_fired(window)` | saved searches over the dictionary | L, M |
| `create_focus_index` / `drop_focus_index` / `index_stats` | partial inverted index, `sdb_metrics` | E · brief optional |
| `remote_count_by` / `remote_search` / `remote_index` | `read_parquet` over HTTPS, index on view | Huge award |
| `trace_timeline` / `logs_for_trace` / `metric_around` | `otel_*` tables, ASOF join | Bonus |
| `explain_tool(tool, args)` | `EXPLAIN` | MCP award, X |

---

## O. Wild ideas (deliberately unfiltered)

- **Agent writes its own watchlist**: after an investigation the agent saves the pattern ids/terms as a saved search;
  the next run of `which_watches_fired` tells the lead whether it came back.
- **Live demo stream**: replay BGL at 1000× speed through the OTLP endpoint while the agent answers "what's happening
  right now?"; index visibility (`refresh_interval`) shown live.
- **Jev on ingest**: new pattern → generated Jev column judges it the moment it is written (G3); the manager table
  updates itself.
- **German answers** via `ai_translate` for the SchubKI jury (G9).
- **Failure-chain graph** (K3) rendered as Mermaid in the answer card.
- **"Show me the index working"** slide: one query, three `EXPLAIN`s: `IRESEARCH_SCAN` filter, `TsDict:` facet,
  `Top: k, optimized`.
- **Cross-dataset "same problem, different system"** via embeddings (F4).
- **Manager what-if** (`what_if_priority`): weights as inputs, ranking recomputed in SQL, so a manager can ask
  "what if spread mattered twice as much?" and still get computed numbers.
- **SereneDB inspects itself** with `sdb_logs()` (M1).
- **Kibana/ES compatibility** shown with a single `curl _search` against our logs (M3).
- **Per-role DB users** so the manager literally cannot read raw lines (L1).
- **Evidence bundles as Parquet** that a judge can open in any tool (M5).
- **Iceberg + REINDEX freshness barrier**: "anyone writes logs to the lake, the agent sees them after one REINDEX" (I7).

---

## P. How we iterate from here

1. Pick a batch (suggestion: the small, high-signal ones first: A1, C1, D2, D3, K4, K5, N `burst_timeline` /
   `pattern_history`, then the ★ ones: D1, K2, F1, H1, I1–I2, L1).
2. One plan per batch (`plans/NNN-*.md`), tools as table macros + MCP wrappers, descriptions written for selection.
3. Add 1–2 dev questions per new tool (with golden SQL), run `eval.run_eval --systems ours --reuse-baseline <ref>
   --compare <ref>`, keep only tools that move the targeted question without regressions or a drop in E7.
4. Performance and cost numbers go to `docs/PERFORMANCE.md` (index build vs saved time, remote bytes read).
