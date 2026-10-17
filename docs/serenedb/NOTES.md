# SereneDB — distilled notes

Source: github.com/serenedb/serenedb (docs/, examples/, tests/.../site_docs) snapshot 2026-10-09. Live docs MCP: `serenedb-docs`.

## What it is
- "Real-time search analytics DB": Postgres wire protocol + DuckDB-style columnar/vectorized SQL engine
  + IResearch inverted index (full-text, vector, hybrid) + RocksDB durable storage. Apache-2.0.
- Pitched use cases include **logging**, RAG, agents' DB, OLAP, zero-ETL federated search (remote Postgres/ClickHouse/Parquet/S3).

## Run
```bash
docker run -d --name serenedb -p 7890:7890 -v serenedb-data:/var/lib/serenedb serenedb/serenedb
psql -h localhost -p 7890 -U postgres -d postgres
```
OTLP log ingest (no collector needed): `serened ./data --listen 'postgres://0.0.0.0:7890,http://0.0.0.0:4318?api=otel'`
→ `POST /v1/logs` writes `otel_logs` (body full-text searchable/BM25). Schema: `otel/otel_schema.sql`.

## Doc map (docs/serenedb/docs/)
- `sql/indexes/inverted/*` — full-text, vector, hybrid, ranking (BM25 etc.), text analysis, json, modeling, views
- `cookbook/search/*` — **significant-terms** (what's distinctive in a subset → "what changed in this incident window"),
  faceted-search, grouping-results, highlighting, fuzzy, phrase/proximity, recency-and-decay, similar-documents, RRF
- `sql/functions/ai.md` — AI functions (below); `sql/query_syntax`, window functions, GROUPING SETS, PIVOT
- `data_import_and_export/*` — CSV/JSON/Parquet, OpenTelemetry
- Runnable SQL for each doc `<SqlLogicTest id="X"/>` → `doc-examples/X.test` (`# DOCS_TEST_RAW` blocks show query+output)

## AI functions in SQL (sql/functions/ai.md)
- Chat-model (secret `TYPE openai`, any OpenAI-compatible incl. Ollama/OpenRouter): `ai_generate`, `ai_classify`,
  `ai_classify_labels`, `ai_extract`, `ai_filter`, `ai_score`, `ai_rerank`, `ai_translate`, `ai_redact`,
  aggregates **`ai_agg(text, instruction)`**, **`ai_summarize_agg(text)`** (map-reduce over big groups).
- Embeddings: `ai_embed`, `ai_similarity` (+ IVF vector index, `<=>` cosine).
- **Jev**: `ai_system_one(input, instructions [, noul|choice|score] [, batch_size])` or
  `ai_system_one(input, questions := {id: {type, instructions, criteria}, ...})` → STRUCT per question.
  Secret `TYPE typesafe` (`api_key`, `base_url`, `model`, `path`). Works with TypeSafe API, OpenRouter, local Kev.
  - Single-question calls pack up to `batch_size` rows (default 32) per request → answers can drift; `batch_size := 1` for isolation.
  - `questions` JSON can be the raw API format (structured instructions/criteria with examples).
  - **Generated stored column** = classify on INSERT, re-run only when input column changes; reads free. (examples/demo7)
  - NULL input → NULL, no request. Identical texts in a chunk share one request (dedupe = cheap for repetitive logs).
  - Controls: `sdb_ai_max_api_calls_per_query`, `sdb_ai_throw_on_error`, `sdb_ai_max_concurrent_requests`, etc.
  - Cost trick: WHERE filters run before AI calls; `ORDER BY ... LIMIT` → put in subquery first.

## Mental model for logs
Ingest (COPY / OTLP) → inverted index on message → SQL: counts, rates, time buckets, windows, significant terms, top-N
→ `ai_system_one` columns for per-log/per-template judgments → aggregate the stored judgments per role.
