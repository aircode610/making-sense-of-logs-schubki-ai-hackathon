# Part 2: full capabilities of SereneDB + Jev, for fast evidence and trustworthy confidence

Prerequisite: Part 1 (`tutorial/README.md`) with the tutorial incident loaded, plus `./docker/secrets.sh`.
Everything marked ✅ was run on our setup (2026-10-09) and the numbers shown are real. ⚠️ = documented but not yet tested by us.
Timings are from a laptop running SereneDB **emulated** (amd64 on Apple Silicon) and Jev over the internet.

---

## The principle: an evidence funnel

```
millions of log rows ──SereneDB index──► thousands (time + service + severity filter, index-only)
                     ──templates────────► tens (one row per "print statement" + counts + first/last seen)
                     ──search ranking───► top candidates (BM25 / vector / hybrid / significant terms)
                     ──Jev──────────────► typed judgments with calibrated probabilities (ONE request, many questions)
                     ──code─────────────► thresholds, weights, routing (deterministic)
                     ──LLM──────────────► explanation that cites evidence IDs
```
**Performance rule:** every step shrinks the data before the next, more expensive step sees it. SereneDB does the
heavy lifting inside its index. Jev only sees *templates or candidates*, never raw rows. The LLM sees only the final
evidence table. **Confidence rule:** every number comes from SQL, and every judgment carries a probability we can threshold on.

---

# Part A: SereneDB

## A1. Make sure the index does the work ✅
`otel_logs` is a search table, so predicates on its indexed columns (`timestamp`, `body`, `severity_text`, `severity_number`,
`service_name`, `event_name`, `trace_id`) run **inside the index**. Check with `EXPLAIN`:
```sql
EXPLAIN SELECT count(*) FROM otel_logs WHERE body @@ 'timeout' AND service_name @@ 'payment';
--  IRESEARCH_SCAN · Index Filter: And(Terms body='timeout', Terms service_name='payment') · Output: row-count only
```
`IRESEARCH_SCAN` with an `Index Filter` means fast. A `Column Filter` means the predicate is checked row by row afterwards (slower).
- **Index-friendly time range:** `"timestamp" @@ ts_between(TIMESTAMP_NS '...', TIMESTAMP_NS '...', true, false)` ✅ (75 errors in 14:05–14:12)
- **Index-friendly exact match:** `service_name @@ 'payment'`, `severity_text @@ 'ERROR'` ✅
- `JSON ->>` filters are column scans. If an attribute is hot, add an **expression index** (see `docs/serenedb/docs/data_import_and_export/opentelemetry.md`) ⚠️

## A2. Every way to match text ✅
| Need | Syntax | Our data |
|---|---|---|
| word | `body @@ 'timeout'` | 56 |
| exact phrase | `body @@ ts_phrase('bad gateway')` or `websearch_to_tsquery('"bad gateway"')` | 28 |
| words near each other | `body @@ ('payment' ## [0,7] ## 'timeout')` (0–7 words apart, in order) | finds `payment failed for order …: upstream timeout` |
| prefix | `body @@ ts_starts_with('gatew')` | 28 |
| regex on tokens | `body @@ ts_regexp('5[0-9][0-9]')` (HTTP 5xx) | 28 |
| **typo-tolerant** | `body @@ ts_levenshtein('timout', 1)` | 56 (finds *timeout*) |
| boolean | `('a' && 'b')`, `('a' \|\| 'b')`, `!!'a'`, `ts_any([...], min_match)`, `ts_all([...])` | |
| Lucene syntax | `to_tsquery('stripe AND (timeout OR slow) -succeeded')` | 56 |
| Google syntax | `websearch_to_tsquery('timeout -healthcheck')` | |
| Elastic bool query | `ts_compound(must, must_not, should)` ⚠️ | |

Matching is on **tokens**. `ts_lexize('otel_body_dict', '...')` shows how a line is tokenised: lowercased, no stemming,
and `io.grpc.Client` / `10.0.0.7` stay whole. That's good for logs.

## A3. Ranking ✅
```sql
SELECT body, BM25(otel_logs.tableoid) AS score FROM otel_logs WHERE body @@ 'timeout' ORDER BY score DESC LIMIT 10;
```
- **Scorers:** `BM25(k1,b)` (default), `TFIDF`, `lm_jm`, `lm_dirichlet`, `dfi`, …
- **Boost** a clause: `body @@ ('timeout'::tsquery ^ 5.0) OR body @@ 'slow'` (from the docs)
- **Recency:** multiply the score by a decay, e.g. `BM25(...) * (1.0 / (1 + minutes_ago))`. The pattern comes from `cookbook/search/recency-and-decay`.
- **Top-K speed (WAND):** `otel_logs` is already built with `optimize_top_k = 'bm25(1.2, 0.75)'`, so `ORDER BY BM25(...) DESC LIMIT k`
  with a single term or an OR of terms skips documents that can't make the top k. `EXPLAIN` shows `Top: k, optimized`.

## A4. Facets: counts straight from the index dictionary ✅
```sql
SELECT unnest(ts_dict_agg(service_name)) AS service, unnest(ts_dict_count(service_name)) AS n
FROM otel_logs WHERE body @@ 'timeout';          -- payment 28 · checkout 28
```
These are the fastest group-bys you can run over millions of rows, but they only work on indexed columns.

## A5. Significant terms: "what is unusual in this window?" ✅ ⭐
This is the most useful zero-knowledge evidence generator for incidents. It compares word frequency inside the incident window
(foreground) against the whole dataset (background). You don't have to know what to search for.
```sql
WITH bg AS (SELECT unnest(ts_dict_agg(body)) AS term, unnest(ts_dict_count(body)) AS bg_docs FROM otel_logs),
fg AS (SELECT unnest(ts_dict_agg(body)) AS term, unnest(ts_dict_count(body)) AS fg_docs FROM otel_logs
       WHERE "timestamp" @@ ts_between(TIMESTAMP_NS '2026-10-09 14:05:00', TIMESTAMP_NS '2026-10-09 14:13:00', true, false)),
t AS (SELECT (SELECT count(*) FROM otel_logs WHERE "timestamp" @@ ts_between(TIMESTAMP_NS '2026-10-09 14:05:00',
                    TIMESTAMP_NS '2026-10-09 14:13:00', true, false)) AS fg_total,
             (SELECT count(*) FROM otel_logs) AS bg_total)
SELECT term, fg_docs, bg_docs, round(fg_docs - bg_docs * t.fg_total::DOUBLE / t.bg_total, 1) AS lift
FROM fg JOIN bg USING (term) CROSS JOIN t WHERE fg_docs >= 5 ORDER BY lift DESC LIMIT 8;
```
Result: `timeout, charges, stripe, attempt, v1` (lift 21.4), then `response, retrying`. That points straight at Stripe.
Use a "before the incident" baseline window instead of "everything" for sharper results. `fg_docs >= N` removes one-off noise.

## A6. Templates table + embeddings ✅
Turn rows into templates once, store counts, time span and services, and attach an embedding:
```sql
CREATE TABLE log_templates (id INTEGER PRIMARY KEY, template VARCHAR, n INTEGER,
  first_seen TIMESTAMP_NS, last_seen TIMESTAMP_NS, services VARCHAR[], emb FLOAT[768]);
INSERT INTO log_templates
SELECT row_number() OVER (ORDER BY min("timestamp"), template)::INTEGER, template, count(*),
       min("timestamp"), max("timestamp"), list(DISTINCT service_name),
       ai_embed(template, 'gemini-embedding-001', 'gemini', 768)::FLOAT[768]      -- one embedding per TEMPLATE
FROM (SELECT *, regexp_replace(regexp_replace(body, 'A-[0-9]+', '<ORDER>', 'g'), '[0-9]+', '<N>', 'g') AS template
      FROM otel_logs) t
GROUP BY template;
CREATE TEXT SEARCH DICTIONARY tmpl_dict AS split_text(case := 'lower', break := 'alpha') WITH (frequency, position, norm);
CREATE INDEX log_templates_idx ON log_templates USING inverted (id, template tmpl_dict, emb ivf (metric = 'cosine'));
VACUUM (REFRESH_TABLE) log_templates;      -- make it searchable now instead of waiting for the background refresh
```
311 rows become 9 templates. Embedding cost scales with the number of templates, not rows.
(Our `OPENAI_API_KEY` returned 401, so we use Gemini via `GOOGLE_API_KEY`. `./docker/secrets.sh` registers it.)

## A7. Vector (semantic) search ✅
Query by meaning. The words don't need to match:
```sql
SELECT id, template FROM log_templates_idx           -- query the INDEX by name to use ANN
ORDER BY emb <=> ai_embed('the payment provider is down', 'gemini-embedding-001', 'gemini', 768)::FLOAT[768] LIMIT 4;
```
| Rank | Distance | Template |
|---|---|---|
| 1 | 0.252 | payment failed for order <ORDER>: upstream timeout |
| 2 | 0.334 | creating payment for order <ORDER> |
| 3 | 0.349 | POST /checkout <N> Bad Gateway |
| 4 | 0.397 | Timeout after <N>ms calling stripe … |

The same question via keyword search (`websearch_to_tsquery('payment provider down')`, which ANDs the terms) returns **0 rows**.
- **Operators:** `<=>` cosine, `<->` L2, `<#>` inner product, `<+>` L1. Use the one that matches the index metric.
- **Index types:** `ivf(...)` (clusters) or `hnsw(...)` (graph). Quantization (`sq8` by default, `sq4`, `pq`, `rabitq`, `tq`) trades size for recall.
- **Knobs:** `SET sdb_ivf_search_nprobe = 16` (more recall), `sdb_rerank_factor`, `sdb_hnsw_ef_search`.
- **Radius search:** `WHERE emb <=> $q < 0.3` returns everything within a similarity threshold, e.g. "all templates like this one".
- **Filtered ANN:** `WHERE template @@ 'payment' ORDER BY emb <=> $q LIMIT k`, which ranks by meaning among keyword matches.

## A8. Hybrid search (BM25 + vector, fused with RRF) ✅ ⭐
Each method misses things the other finds. RRF fuses **ranks** (scores aren't comparable): `score = Σ 1/(60 + rank)`.
```sql
WITH q AS MATERIALIZED (SELECT ai_embed('the payment provider is down','gemini-embedding-001','gemini',768)::FLOAT[768] AS v),
fused AS (
  SELECT id, ROW_NUMBER() OVER (ORDER BY s DESC) AS rank FROM (
    SELECT id, BM25(log_templates_idx.tableoid) AS s FROM log_templates_idx
    WHERE template @@ websearch_to_tsquery('payment OR provider OR down OR timeout') ORDER BY s DESC LIMIT 20) lex
  UNION ALL
  SELECT id, ROW_NUMBER() OVER (ORDER BY dist) AS rank FROM (
    SELECT id, emb <=> (SELECT v FROM q) AS dist FROM log_templates_idx ORDER BY dist LIMIT 20) vec)
SELECT id, SUM(1.0 / (60 + rank)) AS rrf FROM fused GROUP BY id ORDER BY rrf DESC LIMIT 5;
```
Result: `payment failed…` (bm25#1 + vector#1), `creating payment…`, `Timeout … stripe` (bm25#3 + vector#4), `502`, …
Note that `creating payment for order` (an INFO line) ranks #2. **Search finds what's related, not what's the cause.**
That's why the next step is Jev.

## A9. More tools in the box
| Tool | Use for logs | Status |
|---|---|---|
| `ts_highlight(body)` | show *why* a line matched: `upstream <b>timeout</b>` | ✅ |
| `ROW_NUMBER() OVER (PARTITION BY service_name ORDER BY BM25(...) DESC)` | best evidence line **per service** | ✅ pattern (cookbook `grouping-results`) |
| `trace_id` join | one request's story across services (Part 1, 5.7) | ✅ |
| `time_bucket` + window functions | error rate per minute, spike detection (z-score vs baseline) | ✅ |
| `minhash(tokens, 64)` + `ts_any(..., min_match)` | near-duplicate lines → smarter templates without embeddings | ⚠️ |
| `ai_agg(text, instr)` / `ai_summarize_agg(text)` | LLM summary per group in SQL (map-reduce) | ⚠️ (Gemini secret ready) |
| partial index (`CREATE INDEX ... WHERE severity_number >= 13`) | index only warnings and errors | ⚠️ |
| views / Parquet over S3 indexed | search archives without loading them | ⚠️ |

## A10. Performance knobs
| Knob | Effect |
|---|---|
| query the **index by name** (`FROM log_templates_idx`) | needed for ANN; base-table queries do a full scan |
| `VACUUM (REFRESH_TABLE) t` | make new rows searchable now (otherwise ~1–3 s) |
| `optimize_top_k` + `ORDER BY scorer DESC LIMIT k` | WAND pruning for top-k |
| `WITH x AS MATERIALIZED (...)` | compute an embedding or AI call once and reuse it |
| `SET sdb_ai_max_api_calls_per_query = N` | cost guard for any `ai_*` call |
| `WHERE` before AI calls; `ORDER BY ... LIMIT` in a subquery | AI only runs on surviving rows |

---

# Part B: Jev

Run all of these at once: `python3 tutorial/jev_capabilities.py` (needs `TYPESAFE_API_KEY` exported).

## B1. Evidence inside the choices ✅ ⭐
Put the **candidates themselves** (with their SQL-computed evidence) as the Choice options. Add a `none` option so Jev can abstain.
```python
criteria = {
  "T6": {"log_template": "stripe /v<N>/charges slow response, retrying (attempt <N>/<N>)", "service": "payment",
         "occurrences_in_incident": 28, "first_appearance": "first anomaly in the incident"},
  "T7": {..., "first_appearance": "15000 ms after the first anomaly"},
  "T8": {...}, "T9": {...},
  "none": "None of these templates is the root cause; the cause is not visible in these logs."}
question = {"type": "choice", "criteria": criteria,
  "instructions": "Which log template in the criteria is closest to the root cause of the failure in `question`? "
                  "A root cause is the earliest failure that the other failures follow from, not a downstream symptom."}
```
Result: **T6** (Stripe slow → retrying, the first sign) with confidence **0.92**; `T7 0.04, none 0.02, T8 0.00, T9 0.00`. **457 ms.**
Note that `first_appearance` was computed **in SQL and phrased in words**, because Jev is weak at comparing timestamps.

## B2. Robustness: option order and repeatability ✅
Jev can lean toward the first option (a known weakness), so we shuffle and re-ask:
| Run | Option order | Answer | Confidence |
|---|---|---|---|
| shuffle 1 | T9, none, T6, T7, T8 | T6 | 0.85 |
| shuffle 2 | T7, T6, none, T9, T8 | T6 | 0.94 |
| shuffle 3 | T6, none, T9, T7, T8 | T6 | 0.96 |
| repeat ×3 | same | T6 | p = 0.96 / 0.95 / 0.93 |

**Reliability trick:** ask 2–3 shuffled orders **inside one request** (they run in parallel and cost almost nothing extra), then
treat agreement as part of the confidence. If they disagree, say "not sure".

## B3. Many questions in one request (fan-out) ✅ ⭐
| Request | Latency | Input tokens | Cost |
|---|---|---|---|
| 1 question | 284 ms | 686 | $0.00003 |
| **11 questions** (root cause + symptom? + customer-visible? per template + severity + category) | **313 ms** | 1,367 | **$0.000057** |

Ten extra questions add about 30 ms. So **always ask everything you might need, all at once** (speculative fan-out), and let the code
use what's relevant. The 11-question answers:
```
T6 retrying  symptom=0.33   T7 timeout  symptom=0.53   T8 payment failed  symptom=0.95   T9 502  symptom=0.96
severity = 2.8 / 3     category = external_dependency (confidence 1.0)
```
The symptom probabilities rise along the causal chain, which is exactly right.

## B4. Structured criteria make probabilities sharper ✅ ⭐
Jev reads questions **literally**. Defining *yes* and *no* with examples (JSON criteria) pushes probabilities away from 0.5:
```json
"criteria": {
  "true":  {"definition": "The line reports an error response returned to the customer's request, or a customer action (checkout, payment, login) that failed.",
            "examples": ["POST /cart 500 Internal Server Error", "login failed for user", "order could not be placed"]},
  "false": {"definition": "The line is internal: retries, slow dependencies, background jobs or infrastructure messages, with no error returned to the customer yet.",
            "examples": ["retrying connection to db (attempt 2/5)", "cache miss for key", "GC pause 120ms"]}}
```
| Template | Vague question | Structured criteria |
|---|---|---|
| retrying (internal) | 0.26 | **0.07** |
| payment failed | 0.69 | **0.91** |
| 502 Bad Gateway | 0.75 | **0.91** |
The gap between yes and no grows from about 0.5 to **0.84**. This matters most for confidence: sharper probabilities mean more cases
clear the auto-act threshold, with fewer wrong ones.

## B5. Using confidence ✅
- **Choice/Score** return `confidence` (0 = flat, 1 = certain), computed from the probabilities, never self-reported.
  Example: the category for `502 Bad Gateway` came back `infrastructure` at **confidence 0.53**, against ≥ 0.9 for the clear lines.
  Jev is telling us it isn't sure, and our UI should show "needs review" there.
- **Noul** has no confidence field. Use `|2p − 1|`, and remember 0.5 means "unsure", not "medium".
- **Alternatives to test in benchmarks:** top probability, top/second ratio, agreement across shuffles (B2).
- **Policy:** high → state it; medium → state it with a "needs review" flag; low or `none` wins → "the logs don't show the cause".
  Thresholds are tuned on labelled data (Hadoop / GAIA / BGL), never guessed.

## B6. Jev inside SQL (stored judgments) ✅
One request per template answering four questions. **9 templates took 313 ms in total** (parallel), and reading them back takes **6 ms**:
```sql
CREATE TABLE template_triage AS
SELECT id, template, ai_system_one(template, questions := {
  is_error: {type: 'noul',   instructions: 'Does this log line report that something failed or went wrong?'},
  customer: {type: 'noul',   instructions: 'Does this log line show that a customer''s own request failed or returned an error?'},
  kind:     {type: 'choice', instructions: 'What kind of problem does this log line describe?',
             criteria: ['external dependency', 'our own code', 'infrastructure', 'not a problem']},
  severity: {type: 'score',  instructions: 'How severe is the situation in this log line for the business?',
             criteria: ['harmless', 'degraded', 'some customers blocked', 'outage']}
}) AS j FROM log_templates;
SELECT id, j.is_error, j.kind.choice, j.kind.confidence, j.severity.score FROM template_triage;
```
- **On ingest:** a `GENERATED ALWAYS AS (ai_system_one(...)) STORED` column judges new rows once (demo7). It works on our own
  tables, but don't add columns to `otel_logs` itself, since its schema is checked at startup.
- `questions :=` can also take the **raw API JSON** (structured criteria from B4).
- Single-question calls pack up to 32 rows per request (`batch_size`). That's cheaper, but answers can drift; use `batch_size := 1` for strict isolation.
- Identical texts in a batch share one request, so templates plus dedupe keep cost close to zero.

## B7. Other Jev patterns worth using
| Pattern | For us | Status |
|---|---|---|
| **Composite scoring**: separate Scores (severity, blast radius, recurrence, customer impact), weights in code | manager priority, with different weights per role | ⚠️ next |
| **Rerank**: one Noul per (question, candidate) after the BM25/hybrid shortlist | cleans A8's "creating payment" false positive | ⚠️ next |
| **Hierarchical choice**: component → failure class → cause, one Choice per level | big taxonomies (>255 options, or deep trees) | ⚠️ |
| **Two-stage**: Choice ranks many → re-ask top 3 with richer evidence (full lines, trace) | better root cause on big incidents | ⚠️ |
| **Citation check**: "does this evidence support this claim?" on each sentence the LLM writes | groundedness metric + guardrail | ⚠️ |
| **Jev probabilities as features** for a small classifier | hybrid vs pure-classifier baseline | ⚠️ |

## B8. What Jev must NOT do (keep in SQL or code)
Counting, arithmetic, comparing timestamps, generating text, and judging huge noisy states. Our split: **SQL computes
`occurrences`, `ms after first anomaly`, `services`, rates. Jev judges meaning. The LLM writes prose.**

---

# Part C: Putting it together, the efficient engineer pipeline
| Step | Tool | Cost/latency (tutorial scale) |
|---|---|---|
| 1. incident window | `time_bucket` error rate + z-score | ms |
| 2. what's unusual | significant terms (A5) | ms |
| 3. candidates | templates in window (A6) + hybrid search on the question (A8) | ms + 1 embedding |
| 4. per-candidate facts | SQL: counts, first seen, services, trace chain (Part 1 5.7) | ms |
| 5. judgments | **one** Jev request: root cause (evidence-in-choices, 2–3 shuffles) + symptom/customer Nouls + severity + category | ~300–450 ms, < $0.0001 |
| 6. decide | code: confidence gates, agreement across shuffles, `none` → "don't know" | µs |
| 7. explain | LLM gets only the evidence table, must cite `T6` etc.; Jev citation-check on its sentences | 1 LLM call |

---

# Part D: Metrics and traces (my take)

**Verdict: logs stay the core. Add traces as the first add-on, and metrics as a light "corroboration" add-on.**

- **Traces are nearly free for us and directly useful.** They arrive on the same OTLP endpoint, in the same database
  (`otel_traces`), joined by `trace_id`. They give the **call graph** (parent → child spans) and **where the time went** (`duration_ns`),
  which solves the cascade problem from Part 1 automatically: the deepest failing span is usually the root cause. One SQL query,
  no new AI.
- **Metrics answer the "why" that logs often can't** (CPU, memory, disk). OpenRCA showed most of its faults show up mainly in metrics.
  Keep it narrow: only for the top 1–3 candidate services from Jev, run one SQL query that computes a z-score against a baseline and
  turns it into **words** (`"memory: far above normal (4σ)"`), since Jev reads words better than numbers. That sentence goes into Jev's
  evidence for the confirm step.
- **Evidence it pays off:** an AI-SRE vendor benchmark on RCAEval reported root-cause top-1 accuracy of 29% with metrics only,
  77% with logs added, and 87% with traces too (vendor-reported, not independently verified, but the direction matches the RCA literature).
- **Why it's a differentiator:** most teams will build "chat with your logs". **"Logs say *what*, traces say *where*, metrics
  say *why*"**, all through one OTLP endpoint and one SQL engine, is a strong SereneDB story. The OTel schema is already there.
- **Scope guard:** build it only after the logs-only engineer pipeline works and is benchmarked. It should be one extra SQL evidence
  step and zero extra LLM calls. If time runs out, it's the first thing to drop.
