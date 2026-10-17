# Walkthrough: one question end to end (experiment 001, dev)

**Example:** `application_1445062781478_0015#w0`. Jev was right, both LLM baselines were wrong.
**Dashboard:** `.venv/bin/streamlit run apps/trace_viewer.py` → Session = latest `001-dev-…`, Jev variant
`A2_full_evidence_structured`, filter Ground truth = machine down, Show = right only → pick this example.

- **Question:** *"Why did Hadoop job application_1445062781478_0015 fail?"* (wording 0)
- **Ground truth:** `machine down`. During this cluster run a worker machine was switched off (Loghub fault injection).
- **Job:** PageRank, cluster run `1445062781478`, 15 containers, 2,735 log lines, 7 minutes.

---

## Step 0: ingest (once, before any question). `pipeline/hadoop.py`, `patterns.py`, `ingest.py`
1. **Parse** each container file (`container_…_000001.log` …). A line like
   `2015-10-17 15:45:59,146 ERROR [RMCommunicator Allocator] org.apache…RMContainerAllocator: Container complete event for unknown container id container_1445062781478_0015_01_000012`
   becomes `{ts, level=ERROR, severity=17, thread, logger, message}`. Lines that don't start with a timestamp are
   stack-trace continuations and are glued to the previous record's body.
2. **Drain3** mines a template from the first line of the message after **generic masks** (UUID, `word_123_456` ids,
   IPs, host:port, paths, hex, numbers):
   `Container complete event for unknown container id container_1445062781478_0015_01_000012`
   → `Container complete event for unknown container id <ID>` → cluster 162 → **`pattern_id = P162`**.
   Lines with the same template share an id across all jobs. 115,455 dev lines became **245 patterns**.
3. **OTLP → SereneDB.** Each record is sent as an OpenTelemetry LogRecord and lands as one row in `otel_logs`:

| column | value for this line |
|---|---|
| `timestamp` | `2015-10-17 15:45:59.146` |
| `service_name` | `hadoop-mapreduce` (promoted from `resource.service.name`) |
| `severity_text` / `severity_number` | `ERROR` / `17` (OTel scale: INFO 9, WARN 13, ERROR 17, FATAL 21) |
| `body` | the full message (+ stack trace if any), full-text indexed |
| `resource_attributes` (JSON) | `{"application.id":"application_1445062781478_0015","container.id":"container_…_000001","service.name":"hadoop-mapreduce"}` |
| `log_attributes` (JSON) | `{"logger":"…RMContainerAllocator","pattern_id":"P162","thread":"RMCommunicator Allocator"}` |

Nothing in the row reveals the label. The job id only lives in `resource_attributes.application.id`.

---

## Step 1: Pattern brick (15 ms). `bricks.pattern_brick`, SQL in `pipeline/queries.py`
The question's job id is extracted by code (the question *wording* is never used to search). Then three queries run.

### 1a. Corpus statistics (`PATTERN_STATS`, once per run, not per question)
```sql
SELECT log_attributes ->> 'pattern_id'                          AS pattern_id,
       count(*)                                                 AS n_lines,
       count(DISTINCT resource_attributes ->> 'application.id') AS n_jobs,       -- in how many jobs it appears
       max(severity_number)                                     AS max_severity
FROM public.otel_logs
WHERE service_name = 'hadoop-mapreduce'
GROUP BY 1;
```
Line by line:
- `log_attributes ->> 'pattern_id'`: `->>` pulls a key out of the JSON column as text. That's the Drain3 id we stored at ingest.
- `count(DISTINCT … 'application.id')`: the number of **different jobs** containing the pattern. That's the **rarity** baseline.
- `WHERE service_name = …`: only Hadoop rows (the tutorial rows in the same table are ignored).

For our two patterns:

| pattern | lines (all jobs) | jobs with it (of 35) | max severity |
|---|---|---|---|
| P162 `Container complete event for unknown container id <ID>` | 11 | **7** | 17 (ERROR) |
| P89 `Could not delete hdfs://<HOSTPORT><PATH><ID>` | 148 | **30** | 13 (WARN) |

(`TOTAL_JOBS` = `count(DISTINCT application.id)` = 35.)

### 1b. Job facts (`JOB_FACTS`)
```sql
SELECT min("timestamp") AS t0, max("timestamp") AS t1,                              -- job start / end
       count(DISTINCT resource_attributes ->> 'container.id')             AS n_containers,
       count(*)                                                           AS n_lines,
       count(*) FILTER (WHERE severity_number >= 21)                      AS n_fatal,
       count(*) FILTER (WHERE severity_number >= 17 AND severity_number < 21) AS n_error,
       count(*) FILTER (WHERE severity_number >= 13 AND severity_number < 17) AS n_warn
FROM public.otel_logs
WHERE service_name = 'hadoop-mapreduce'
  AND resource_attributes ->> 'application.id' = 'application_1445062781478_0015';
```
- `FILTER (WHERE …)` = count only the rows matching that condition (several counts in one pass over the job's rows).
- Result: t0 15:43:47.586, t1 15:51:00.077 (7 min), 15 containers, 2,735 lines: **0 FATAL, 1 ERROR, 3 WARN**
  (the other 2,731 are INFO).

### 1c. The job's WARN-or-worse patterns (`JOB_PATTERNS`)
```sql
SELECT log_attributes ->> 'pattern_id'                         AS pattern_id,
       max(severity_number)                                    AS max_severity,
       any_value(severity_text ORDER BY severity_number DESC)  AS severity_text,   -- the worst level seen
       count(*)                                                AS n,              -- lines in THIS job
       count(DISTINCT resource_attributes ->> 'container.id')  AS n_containers,   -- how spread out
       min("timestamp")                                        AS first_seen,
       left(any_value(body ORDER BY "timestamp"), 300)         AS example_line    -- first real line, cut to 300 chars
FROM public.otel_logs
WHERE service_name = 'hadoop-mapreduce'
  AND resource_attributes ->> 'application.id' = 'application_1445062781478_0015'
  AND severity_number >= 13                                    -- [KNOB] EVIDENCE_MIN_SEVERITY: WARN and worse
GROUP BY 1;
```
- `GROUP BY 1` = one row per pattern in this job.
- `any_value(x ORDER BY y DESC)` = take `x` from the row with the highest `y`.
- **`severity_number >= 13` is the key filter.** It drops all 2,731 INFO lines. That's what makes the evidence thin (see "What this shows").

Result, after Python adds the template text and `n_jobs_with_pattern` from 1a:

| pattern | severity | n (this job) | containers | first_seen | jobs with it |
|---|---|---|---|---|---|
| P162 | ERROR | 1 | 1 of 15 | 15:45:59 | 7 |
| P89 | WARN | 3 | 1 of 15 | ~15:50 | 30 |

**Dashboard:** expander "Pattern" shows this table, the job facts and the exact SQL.

---

## Step 2: Evidence brick (0 ms, pure Python). `bricks.evidence_brick`
Turns rows into a small, ranked, **worded** evidence list, because Jev is weak at numbers and dates (docs/jev/NOTES.md).

1. **Rank** patterns by `(severity desc, n_jobs_with_pattern asc = rarer first, n desc)`. P162 (ERROR, 7 jobs) comes
   before P89 (WARN, 30 jobs). Keep the top `TOP_K_EVIDENCE = 12` [KNOB].
2. **Number → words**, all computed from the SQL values:
   - `occurrences`: `"1 lines in 1 of 15 containers"`
   - `first_appearance`: (first_seen − t0) / (t1 − t0) = (15:45:59 − 15:43:47) / 7m12s ≈ 0.30
     → `< 0.33` → **"early in the job"** (buckets: <5% very start, <33% early, <66% midway, else late)
   - `rarity`: 7 / 35 = 0.20 → `≤ 0.25` → **"rare: seen in 7 of 35 jobs"** (buckets: 1 job = only this job,
     ≤25% rare, ≤60% occasional, else common); P89: 30/35 = 0.86 → **"common"**
   - `example_line`: the raw first occurrence (shows real values the template masked)
3. Job summary: `duration "about 7 minutes"`, `containers 15`, `lines "2735 lines: 0 FATAL, 1 ERROR, 3 WARN"`.

Output (exactly what Jev and the B1 LLM receive, minus the internal `_pattern_id`):
```json
{"question": "Why did Hadoop job application_1445062781478_0015 fail?",
 "job": {"duration": "about 7 minutes", "containers": 15, "lines": "2735 lines: 0 FATAL, 1 ERROR, 3 WARN"},
 "evidence": {
  "E1": {"log_pattern": "Container complete event for unknown container id <ID>", "severity": "ERROR",
         "occurrences": "1 lines in 1 of 15 containers", "first_appearance": "early in the job",
         "rarity": "rare: seen in 7 of 35 jobs",
         "example_line": "Container complete event for unknown container id container_1445062781478_0015_01_000012"},
  "E2": {"log_pattern": "Could not delete hdfs://<HOSTPORT><PATH><ID>", "severity": "WARN",
         "occurrences": "3 lines in 1 of 15 containers", "first_appearance": "late in the job",
         "rarity": "common: seen in 30 of 35 jobs",
         "example_line": "Could not delete hdfs://msra-sa-41:9000/pageout/out5/_temporary/1/_temporary/attempt_1445062781478_0015_m_000002_1"}}}
```
**Is E1 actually informative?** Of the 7 dev jobs containing P162, **6 are machine down** (1 disk full). When a
machine dies, YARN reports completion events for containers it can no longer match, so this rare ERROR is a real signal.

---

## Step 3: Verdict brick (236 ms). `bricks.verdict_brick`, questions in `pipeline/prompts.py`
**One** Jev request (`jev-1.13.0`) = the state above + two questions evaluated in parallel:
- `root_cause`: Choice over the 4 classes. Each option carries the **structured definition**, e.g. machine down:
  `{"definition": "A worker machine stopped or crashed while the job was running.", "covers": "A host abruptly
  disappearing: its tasks/containers are lost, it stops answering, work is rescheduled elsewhere, connections to that
  host are refused.", "does_not_cover": "A host that is still running but unreachable over the network."}`
- `key_evidence`: Choice over `E1`, `E2`, `none` ("which single item most directly shows the cause?"). That's the
  **evidence-in-choices** pattern, used for the citation.

| result | value |
|---|---|
| root_cause probabilities | normal 0.13 · **machine down 0.83** · network 0.02 · disk 0.02 |
| confidence | **0.77** = (0.83 − 1/4) / (1 − 1/4), computed from the distribution, not self-reported |
| key_evidence | **E1** (confidence 0.85) |
| cost | 1,094 input tokens → $0.000046 · 235 ms |

**Dashboard:** "Verdict" shows the bar chart and *Exact Jev request* (state + both questions, verbatim).

## Step 4: Finding brick (0 ms). `bricks.finding_brick`
`{"answer": "machine down", "confidence": 0.77, "badge": "auto", "cited_evidence": "E1",
"cited_pattern": "Container complete event for unknown container id <ID>"}`
Badge = `auto` because 0.77 ≥ `AUTO_THRESHOLD` 0.6 (placeholder until tuned on dev).

---

## Step 5: what the LLM baselines receive and answer (`pipeline/baselines.py`, `prompts.py`)
Every baseline trace now stores its **exact input** (`request.system` + `request.prompt`), shown in the dashboard
under each baseline as *Exact LLM input*. You can check whether the LLM is dumb or we made its job harder.

### Fairness fix found while writing this
In the first dev run the LLM only got the one-line `definition` of each class, while Jev got
`definition + covers + does_not_cover`. **We were making it harder for the LLM.** Fixed: both now receive the identical
structured definitions. Old results kept in `runs/001/dev_results_v1_unfair_llm_definitions.md`.

### B1: LLM on the same evidence (`gemini-3.8-flash`, thinking off, temperature 0)
**System message**
```
You are an SRE assistant. You diagnose why a Hadoop MapReduce job behaved as it did, using only the log information given. Answer with JSON only.
```
**Prompt** (= the question + the **identical** evidence state Jev gets + the **identical** class definitions)
```
Question: Why did Hadoop job application_1445062781478_0015 fail?

Log evidence for this job (computed by the database; E-ids are evidence items):
{ ...the exact JSON from Step 2: question, job, E1, E2... }

Choose exactly one class from: ['normal', 'machine down', 'network disconnection', 'disk full'].
Class definitions: { ...normal / machine down / network disconnection / disk full,
                     each with definition + covers + does_not_cover, identical to Jev's criteria... }

Return JSON: {"class": <one of the classes>, "confidence": <number 0-1, how sure you are>, "key_evidence": <E-id or "none">}
```
(825 input tokens. The full verbatim prompt is in the dashboard.)

**Reply:** `{"class": "normal", "confidence": 0.95, "key_evidence": "none"}`. 4,297 ms, $0.0012.
Same answer as with the old, unfair prompt (normal, 0.95), and the same in both repeat runs (0.85, 0.85).
**So on this example it's the LLM, not us:** it got the same facts, including the rarity of E1 and a definition saying
"tasks/containers are lost", and still dismissed the single rare ERROR as noise, with high self-reported confidence.

**What still differs between Jev and B1 (by design, not unfairness):** Jev answers each question as a separate typed
judgment (`root_cause`, `key_evidence`) and returns a full probability distribution. The LLM writes one JSON with a
self-reported number. Same information in, different kind of output.

### B2: LLM on raw logs
Same system message; prompt = question + **raw lines** of the job (all WARN/ERROR/FATAL lines + first and last 50
lines, timestamp + level + body, capped at 120k chars) + the same class definitions. No patterns, no rarity, no
timing words: this measures "just throw the logs at an LLM".
**Reply for this example:** `network disconnection`, self-reported 0.85. 7,430 input tokens, 2,158 ms, $0.0038. Wrong:
with ~9× more text than B1 it latched onto the wrong signal.

### B4: rules
No keyword from `RULES` matches, the job has 1 ERROR → fallback "machine down". Right, but **by luck**: the fallback
fires for any job with an error.

---

## Summary for this example (fair re-run, session `001-dev-20261009-164907`)
| system | answer | confidence | latency | input tokens | cost |
|---|---|---|---|---|---|
| **Jev (A2)** | **machine down ✅** | 0.77 *computed* from probabilities | 236 ms | 1,094 | $0.000046 |
| B1 LLM same evidence | normal ❌ | 0.95 *self-reported* (×3 repeats: 0.95, 0.95, 0.95) | 4,297 ms | 825 | $0.0012 (27×) |
| B2 LLM raw logs | network disconnection ❌ | 0.85 *self-reported* | 2,158 ms | 7,430 | $0.0038 (82×) |
| B4 rules | machine down ✅ (by luck) | n/a | 0 | n/a | 0 |

## Whole dev set after the fairness fix (105 questions)
| system | accuracy | macro-F1 | Brier ↓ | ECE ↓ | p50 latency | $/1k |
|---|---|---|---|---|---|---|
| **Jev A2** | **0.40** | **0.48** | **1.01** | **0.43** | **255 ms** | **$0.06** |
| B1 LLM same evidence (fair prompt) | 0.29 | 0.35 | 1.29 | 0.64 | 2,541 ms | $1.14 |
| B1 LLM same evidence (old, one-line definitions) | 0.32 | 0.38 | 1.20 | 0.59 | 2,234 ms | $0.88 |
| B2 LLM raw logs (fair prompt) | 0.33 | 0.38 | 1.20 | 0.59 | 1,927 ms | $5.51 |
Giving the LLM the full definitions did **not** help it (B1 macro-F1 0.38 → 0.35). The gap to Jev is not caused by our prompt.
Note: Jev's repeat runs were served from the cache in this re-run, so its consistency figure here (1.0) is not a fresh
measurement; the live measurement from the first run is **0.97** (B1: 0.80).

## What this shows
1. **Traceable end to end:** every number comes from the SQL in Step 1, every word from Step 2's bucket rules, Jev's
   full input/output and the LLM's full input/output are stored per example.
2. **Jev wins where the evidence holds a subtle signal** (one rare ERROR) that the LLM dismisses as noise. And the LLM
   is **confidently wrong** (0.95), which is the reliability problem in one row.
3. **But the evidence is thin:** 4 of 2,735 lines survive the `severity_number >= 13` filter. Most machine-down jobs
   don't even have P162. The failure signal lives in INFO lines (killed/retried tasks) and in duration. That's the A4
   amendment proposed for plan 001: rarity-ranked patterns at any severity + duration vs typical jobs.

---

## Addendum: the same example under A4 (amendment 1, frozen variant)
A4 selects rare patterns at **any** severity. For this job it adds INFO lines like `Cannot assign container … NodeId …`
(rare, 6/35 jobs) **and** `Going to preempt <NUM> due to lack of space for maps` (rare, 3/35). Duration becomes
"about 7 minutes, shorter than a typical job (20 min)". Jev now answers **disk full** (0.52) vs machine down (0.43): ❌.
It read "lack of space" literally (that line is about scheduler slots, not disk). A known Jev weakness ("literal reading",
docs/jev/NOTES.md). Over all 105 questions A4 is still clearly better (macro-F1 0.48 → 0.52, Brier 1.01 → 0.83), but this
example shows the cost of letting rare INFO lines in: more signal, and some misleading noise.

---

## Addendum 2: fair mirrored run (amendment 2, D11)
Every variant now runs on both models with identical evidence and class options (verified 525/525).
For this question:

| Variant | Jev | LLM (same evidence + options) |
|---|---|---|
| A2 | machine down ✅ (0.77 computed) | normal ❌ (0.95 stated) |
| A4 (frozen) | disk full ❌ (0.36 computed, "needs review") | normal ❌ (0.90 stated) |

Under A4 both models get this one wrong. The difference is in how they're wrong: Jev's low confidence (0.36) flags its
answer for review, while the LLM states 0.90 on a wrong answer. Over all 105 questions accuracy is a tie (macro-F1 0.51
vs 0.49); see `docs/PIPELINE.md` §11.
