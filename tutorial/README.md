# Logs, OpenTelemetry & SereneDB: hands-on tutorial (for someone who knows SQL)

Every command and output here was run against our local setup on 2026-10-09.
Time: ~30 minutes. You need: Docker, `psql`, and Python 3.

---

## 0. The 30-second mental model

```
your app ──(writes log lines)──► OpenTelemetry format ──(HTTP POST)──► SereneDB ──► a SQL table: otel_logs
                                                                                         │
                         you / our tool ◄──────── SQL + full-text search + Jev ◄─────────┘
```
A **log** is just a row that a program writes when something happens. **OpenTelemetry** is the standard
shape for those rows plus the standard way to ship them. **SereneDB** stores them in a normal SQL table and
adds search. Everything after ingest is SQL you already know.

---

## 1. Logs 101

A log line is a program's diary entry:

```
2026-10-09 14:05:31  ERROR  payment  Timeout after 30000ms calling stripe /v1/charges (attempt 3/3)
└─ when ──────────┘ └level┘ └ who ─┘ └─ what happened (free text, "the body") ──────────────────────┘
```

| Concept | Meaning | DB analogy |
|---|---|---|
| **timestamp** | when it happened | a `TIMESTAMP` column. Logs are a time series, so almost every query filters on time |
| **severity / level** | how bad: `TRACE < DEBUG < INFO < WARN < ERROR < FATAL` | an enum column you filter on |
| **service** | which program wrote it (`payment`, `checkout`) | a "source" column you GROUP BY |
| **body / message** | free text written by a developer | a `TEXT` column, so you need **search**, not `=` |
| **attributes** | extra structured key/values (`order_id=A-2918`, `http.status_code=502`) | a JSON column |
| **trace_id** | an ID shared by every log line that belongs to **one user request**, across all services | a foreign key that joins the story of one request together |

Three ideas that matter for our project:

1. **Logs are mostly repetitive.** The same `print` statement runs thousands of times with different numbers:
   `payment failed for order A-6072` and `payment failed for order A-8301` share one **template**,
   `payment failed for order <ORDER>`. Grouping lines into templates turns millions of rows into tens of patterns.
   It's the most important trick in log analysis, and it's what we feed to Jev.
2. **Errors cascade.** One root failure (a payment timeout) makes other services log errors too (checkout fails,
   the frontend returns 502). The **earliest** error in the chain is usually closest to the root cause, while the loudest
   one is usually just a symptom.
3. **Structured vs unstructured.** Old-school logs are one text line. Modern logs are structured, meaning the fields above
   are separate columns. OpenTelemetry is the standard for the structured form.

---

## 2. OpenTelemetry (OTel) 101

**OpenTelemetry** is a vendor-neutral standard (CNCF, same family as Kubernetes) for telemetry. "Telemetry" covers three signals:

| Signal | What it is | Example | SereneDB table |
|---|---|---|---|
| **Logs** | events, as text plus fields | "Timeout calling stripe" | `otel_logs` |
| **Traces** | the timing of one request through services, made of **spans** (one per step) | frontend 30 s → checkout 30 s → payment 30 s | `otel_traces` |
| **Metrics** | numbers over time | CPU 93%, requests/sec | `otel_metrics_*` (5 tables) |

We focus on **logs**.

**Other terms you'll see:**
- **OTLP** (OpenTelemetry Protocol) is the wire format. For us that means **HTTP POST JSON to `/v1/logs`**.
- **Resource** is *who* sent the data: `service.name`, environment, host. It's set once per batch, not per line.
- **Scope** is which library or module inside the app emitted it (rarely important).
- **LogRecord** is one log line: timestamp, severity, body, attributes, trace_id, span_id.
- **Collector** is an optional middleman process that receives, filters and forwards OTLP. SereneDB accepts OTLP
  **directly**, so we don't need one.

**What an OTLP log payload looks like** (simplified from `tutorial/send_logs.py`):
```json
{"resourceLogs": [{
   "resource": {"attributes": [{"key": "service.name", "value": {"stringValue": "payment"}}]},
   "scopeLogs": [{"scope": {"name": "tutorial"}, "logRecords": [{
       "timeUnixNano": "1791554731000000000",
       "severityText": "ERROR", "severityNumber": 17,
       "body": {"stringValue": "Timeout after 30000ms calling stripe /v1/charges (attempt 3/3)"},
       "traceId": "5b8aa5a2d2c872e8321cf37308d69df2",
       "attributes": [{"key": "provider", "value": {"stringValue": "stripe"}}]
   }]}]
}]}
```
Severity numbers are standardised: `INFO=9, WARN=13, ERROR=17, FATAL=21`. That makes `severity_number >= 13` mean "warning or worse"
regardless of what the app called its levels.

**Why OTel matters for our product:** almost every modern stack can emit OTLP. If our tool reads `otel_logs`,
any company can point its apps at SereneDB and use it with **zero custom parsing**. That's how we generalise.

---

## 3. Our setup

```bash
docker compose up -d                 # start SereneDB (repo root)
./docker/secrets.sh          # let SQL call Jev (re-run after every restart; secrets aren't persisted)
psql -h localhost -p 7890 -U postgres -d postgres     # SQL shell, no password (local only)
```
First time only (or after `docker compose down -v`): `psql -h localhost -p 7890 -U postgres -d postgres -f docker/init.sql`
(creates the `otel` login used by OTLP ingest).

| Port | What |
|---|---|
| `7890` | Postgres protocol, so any Postgres client works (`psql`, Python `psycopg`, DBeaver…) |
| `4318` | OTLP/HTTP ingest: `POST http://127.0.0.1:4318/v1/logs` with Basic auth `otel:otel` |

On startup SereneDB **creates the OTel tables automatically** (`otel_logs`, `otel_traces`, `otel_metrics_*`).

---

## 4. The `otel_logs` table

```sql
\d otel_logs
```
| Column | Type | From OTLP | Notes |
|---|---|---|---|
| `timestamp` | `TIMESTAMP_NS` | `timeUnixNano` | nanosecond precision, **UTC** |
| `observed_timestamp` | `TIMESTAMP_NS` | when the pipeline saw it | |
| `trace_id`, `span_id` | `VARCHAR` | request correlation | `NULL` if absent |
| `severity_text` | `VARCHAR` | `"ERROR"` | as the app wrote it |
| `severity_number` | `SMALLINT` | `17` | standardised; filter on this |
| `service_name` | `VARCHAR` | `resource.service.name` | **promoted** to a column for fast filtering |
| `body` | `VARCHAR` | the message | **full-text indexed** |
| `resource_attributes` | `JSON` | who sent it | e.g. `{"deployment.environment":"prod","service.name":"frontend"}` |
| `log_attributes` | `JSON` | per-line extras | e.g. `{"http_status_code":"502"}`, read with `->>` |
| `scope_name`, `event_name`, … | | | rarely needed |

The table is created `WITH (storage = 'search')`. It's a normal SQL table plus an **inverted index** (like Elasticsearch)
over `timestamp, body, severity, service_name, trace_id`. So you get SQL **and** search on the same rows.

---

## 5. Hands-on: an incident from start to finish

### 5.1 Load the example
`tutorial/send_logs.py` simulates a small shop (`frontend → checkout → payment → Stripe`), 4 orders per minute from
14:00 to 14:15 UTC. Between **14:05 and 14:12 Stripe times out**. It sends everything over real OTLP.
```bash
python3 tutorial/send_logs.py          # → sent 311 log records -> HTTP 200
```
Rows become visible after ~1–3 s, once the search index refreshes. To reset: `DELETE FROM otel_logs;`.

### 5.2 Look at it: plain SQL
```sql
SELECT "timestamp", service_name, severity_text, body FROM otel_logs ORDER BY "timestamp" LIMIT 5;
```
```
 2026-10-09 14:00:00 | frontend | INFO | GET /healthcheck 200 OK
 2026-10-09 14:00:04 | frontend | INFO | POST /checkout 200 OK order=A-1950
 2026-10-09 14:00:04 | frontend | INFO | POST /checkout order=A-1950
 2026-10-09 14:00:04 | checkout | INFO | creating payment for order A-1950
 2026-10-09 14:00:04 | payment  | INFO | charge succeeded for order A-1950
```
(Quote `"timestamp"`, since it's a keyword.)

### 5.3 "Is something wrong?" Errors per minute
```sql
SELECT time_bucket(INTERVAL '1 minute', "timestamp") AS minute,
       count(*) FILTER (WHERE severity_text = 'ERROR') AS errors,
       count(*) AS total
FROM otel_logs GROUP BY 1 ORDER BY 1;
```
```
 14:04:00 |  0 | 17
 14:05:00 | 12 | 25   ← incident starts
 ...
 14:11:00 | 12 | 25
 14:12:00 |  0 | 17   ← recovered
```
That's an **incident window computed in SQL**, a reliable number rather than a guess.

### 5.4 "Where?" Errors by service
```sql
SELECT service_name, severity_text, count(*) FROM otel_logs GROUP BY 1, 2 ORDER BY 1, 2;
```
```
 checkout | ERROR | 28     frontend | ERROR | 28     payment | ERROR | 28   payment | WARN | 28
```
Every service shows 28 errors, so counts alone can't tell you **which one is the cause**. Keep that in mind.

### 5.5 Full-text search (the `body` column)
`@@` means "matches this search". `BM25(...)` is a relevance score: higher means a better match.
```sql
SELECT "timestamp", service_name, body, BM25(otel_logs.tableoid) AS score
FROM otel_logs
WHERE body @@ websearch_to_tsquery('timeout -healthcheck')      -- word "timeout", NOT "healthcheck"
ORDER BY score DESC LIMIT 3;
```
Search syntax via `websearch_to_tsquery` works like Google:

| Query | Matches | Rows here |
|---|---|---|
| `body @@ 'timeout'` | the word *timeout* | 56 |
| `websearch_to_tsquery('"bad gateway"')` | exact phrase | 28 |
| `websearch_to_tsquery('timeout OR gateway')` | either | 84 |
| `websearch_to_tsquery('timeout -stripe')` | *timeout* but not *stripe* | |

How the body is split into searchable words (lowercased, no stemming, so identifiers stay intact):
```sql
SELECT ts_lexize('otel_body_dict', 'ERROR Timeout after 30000ms calling stripe /v1/charges');
-- {error,timeout,after,30000ms,calling,stripe,v1,charges}
```

### 5.6 Facets: instant "count by value" from the index
```sql
SELECT unnest(ts_dict_agg(service_name)) AS service, unnest(ts_dict_count(service_name)) AS n
FROM otel_logs WHERE body @@ 'timeout';
```
```
 payment  | 28
 checkout | 28
```
It's like `GROUP BY`, but served from the search index's dictionary, so it's very fast on millions of rows.

### 5.7 "What actually happened?" Follow ONE request with `trace_id`
```sql
SELECT "timestamp", service_name, severity_text, body
FROM otel_logs
WHERE trace_id = (SELECT trace_id FROM otel_logs
                  WHERE severity_text = 'ERROR' AND service_name = 'frontend'
                  ORDER BY "timestamp" LIMIT 1)
ORDER BY "timestamp";
```
```
 14:05:01     | frontend | INFO  | POST /checkout order=A-2918
 14:05:01     | checkout | INFO  | creating payment for order A-2918
 14:05:16     | payment  | WARN  | stripe /v1/charges slow response, retrying (attempt 2/3)
 14:05:31     | payment  | ERROR | Timeout after 30000ms calling stripe /v1/charges (attempt 3/3)   ← root cause
 14:05:31.005 | checkout | ERROR | payment failed for order A-2918: upstream timeout                ← symptom
 14:05:31.01  | frontend | ERROR | POST /checkout 502 Bad Gateway order=A-2918                      ← what the user saw
```
This is the **cascade** from section 1. The user saw a 502 from the frontend, but the earliest error is in `payment`
calling Stripe. The same answer from SQL across all requests:
```sql
SELECT service_name, min("timestamp") AS first_error
FROM otel_logs WHERE severity_text = 'ERROR' GROUP BY 1 ORDER BY 2;
-- payment 14:05:31 → checkout 14:05:31.005 → frontend 14:05:31.01
```

### 5.8 Templates: collapse 112 warnings/errors into 4 patterns
Replace the variable parts (IDs, numbers) so identical "print statements" group together:
```sql
SELECT regexp_replace(regexp_replace(body, 'A-[0-9]+', '<ORDER>', 'g'), '[0-9]+', '<N>', 'g') AS template,
       count(*) AS n, min("timestamp") AS first_seen, max("timestamp") AS last_seen
FROM otel_logs WHERE severity_number >= 13            -- WARN or worse
GROUP BY 1 ORDER BY first_seen;
```
```
 stripe /v<N>/charges slow response, retrying (attempt <N>/<N>)     | 28
 Timeout after <N>ms calling stripe /v<N>/charges (attempt <N>/<N>) | 28
 payment failed for order <ORDER>: upstream timeout                 | 28
 POST /checkout <N> Bad Gateway order=<ORDER>                       | 28
```
A real system has millions of lines but only hundreds of templates. **Templates + counts + first/last seen**
make up the "evidence table" our product builds and hands to Jev.
(Real data needs a smarter template miner than two regexes, e.g. Drain. Same idea.)

### 5.9 Structured attributes (JSON)
```sql
SELECT log_attributes ->> 'http_status_code' AS status, count(*)
FROM otel_logs WHERE service_name = 'frontend' GROUP BY 1 ORDER BY 1;
-- 200 | 32     502 | 28     (null) | 75
```
`->>` pulls a key out of the JSON as text, exactly as in Postgres.

### 5.10 Ask Jev from SQL: typed judgments on the templates
`ai_system_one(text, question, ...)` sends the text to Jev and returns a **typed** answer:
a probability (yes/no), a choice from your list, or a score on your scale. Asking **once per template** rather than once per row is
the cost trick.
```sql
WITH templates AS (
  SELECT DISTINCT regexp_replace(regexp_replace(body, 'A-[0-9]+', '<ORDER>', 'g'), '[0-9]+', '<N>', 'g') AS template
  FROM otel_logs WHERE severity_number >= 13
)
SELECT template,
       round(ai_system_one(template,
             'Does this log line describe a failure that a customer would directly notice?'), 2) AS customer_impact,
       (ai_system_one(template, 'Which kind of problem does this log line describe?',
             choice := ['external dependency', 'our own code bug', 'infrastructure', 'not a problem'])).choice AS kind
FROM templates;
```
```
 stripe ... slow response, retrying         | 0.51 | external dependency
 POST /checkout <N> Bad Gateway             | 0.83 | infrastructure
 payment failed ...: upstream timeout       | 0.92 | external dependency
 Timeout after <N>ms calling stripe ...     | 0.63 | external dependency
```
`customer_impact` is a **calibrated probability** computed by Jev, not a number an LLM made up. Each line is judged
**alone**, though, so "Bad Gateway" gets labelled infrastructure. Connecting the chain (5.7) is SQL's job, which is
exactly why the product combines them. For choice answers, `(...).probabilities` and `(...).confidence` give you the full picture.

---

## 6. How this maps to our product (engineer role)

| Step in the brief | What we just did |
|---|---|
| **question** | "Why did checkout fail around 14:05?" |
| **evidence** (SereneDB) | 5.3 incident window · 5.4/5.6 which services · 5.7 trace + first error · 5.8 templates with counts |
| **reliable summaries** | every number above is a SQL result you can re-run |
| **judgment** (Jev) | 5.10 typed, calibrated labels on templates; next we'll put the **evidence inside the choices** ("which of these 4 templates is the root cause?") |
| **explain + recommend** (LLM) | turns the evidence table into an answer card that cites template IDs and numbers |

---

## 7. Gotchas
- **Index refresh:** new or deleted rows show up in queries after ~1–3 s. A query run right after an insert or delete can see a mix.
- **UTC:** OTLP timestamps are UTC nanoseconds. OpenRCA data is UTC+8, so convert before comparing.
- **Secrets aren't persisted:** re-run `./docker/secrets.sh` after every restart.
- **Cost:** each distinct text sent to `ai_system_one` costs a request. Ask about templates, not raw rows. Use
  `SET sdb_ai_max_api_calls_per_query = 100;` as a safety cap.
- **Apple Silicon:** the image is amd64-only and runs emulated. It works, just slower.

## 8. Cheat sheet
```sql
-- time filter (index-friendly)
WHERE "timestamp" BETWEEN TIMESTAMP '2026-10-09 14:00' AND TIMESTAMP '2026-10-09 14:15'
-- warnings and worse
WHERE severity_number >= 13
-- search
WHERE body @@ websearch_to_tsquery('"connection reset" -healthcheck')
ORDER BY BM25(otel_logs.tableoid) DESC
-- per-minute buckets
GROUP BY time_bucket(INTERVAL '1 minute', "timestamp")
-- JSON attribute
log_attributes ->> 'http_status_code'
-- facet
SELECT unnest(ts_dict_agg(service_name)), unnest(ts_dict_count(service_name)) FROM otel_logs WHERE ...
-- Jev
ai_system_one(text, 'yes/no question?')                                  -- DOUBLE probability
ai_system_one(text, 'question?', choice := ['a','b','c'])                -- STRUCT(choice, probabilities, confidence)
ai_system_one(text, 'question?', score := ['low','medium','high'])       -- STRUCT(score, probabilities, confidence)
```
Further reading: `docs/serenedb/NOTES.md`, `docs/serenedb/docs/data_import_and_export/opentelemetry.md`,
`docs/serenedb/docs/sql/functions/ai.md`, `docs/jev/NOTES.md`.
