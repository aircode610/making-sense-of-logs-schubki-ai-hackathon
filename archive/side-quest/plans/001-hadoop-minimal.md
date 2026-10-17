# 001: Hadoop minimal pipeline (warm-up)

- **Status:** done (closed 2026-10-11 after one held-out run, D12). Originally approved (2026-10-09; user: "keep everything simple, minimal, debuggable; document calibration knobs: Jev prompts, SereneDB queries, ...")
- **Branch:** `exp/001-hadoop-minimal`
- **Dataset(s):** Loghub Hadoop (`dataset/hadoop/`, 55 MapReduce jobs, 394k lines incl. stack-trace continuation lines)
- **Date:** 2026-10-09

## 1. Question this experiment answers
On a small, log-only dataset with known answers, does a **minimal SereneDB + Jev pipeline** (patterns → SQL evidence →
one Jev request) answer the engineer question *"why did this job fail?"* as accurately as a fast LLM, a classifier and
rules, while being **better calibrated, faster and cheaper**? And is the end-to-end machinery (OTLP ingest, Drain3,
4 bricks, tracing, split/guard, metrics) sound before we scale to GAIA?

## 2. Hypothesis and success criteria (fixed before running)
- **H1 (accuracy):** Jev macro-F1 on held-out ≥ fast-LLM-same-evidence macro-F1 − 0.05.
- **H2 (calibration):** Jev Brier score ≤ LLM Brier score (LLM confidence = self-reported, as an LLM would give it).
- **H3 (efficiency):** Jev p50 latency ≤ 1/5 of LLM p50, cost per question ≤ 1/5 of LLM.
- **H4 (abstention works):** at the dev-tuned confidence threshold, held-out selective accuracy ≥ 0.9 with coverage ≥ 0.6.
- **Machinery:** 100% of examples have a complete 4-brick trace; held-out guard never triggered by pipeline dev work.
- ⚠️ Held-out n ≈ 20 → wide confidence intervals. Hadoop is a **warm-up**: we report 95% bootstrap CIs and treat
  results as directional; the real verdict comes from GAIA (002+) and BGL.

## 3. Data
**Preprocessing (dev and held-out identical code):**
- Parse each container log: line = `YYYY-MM-DD HH:MM:SS,mmm LEVEL [thread] logger: message`. Lines without that
  prefix are continuations (stack traces) → appended to the previous record's body.
- → OTel log records, sent over **OTLP** to SereneDB: `timestamp`, `severity_text/number`, `body`,
  resource `service.name=hadoop-mapreduce`, `application.id`, `container.id`; scope = Java logger; attribute `thread`.
- No labels, app names or file paths that leak the answer go into the logs.

**Split (D4), unit = job; groups = (cluster run, application type):**
| Group (run, app) | Jobs | Labels | Split |
|---|---|---|---|
| 1445062781478 PageRank | 10 | MD 7, N 3 | dev |
| 1445087491445 WordCount | 10 | MD 8, N 2 | dev |
| 1445094324383 WordCount | 5 | MD 5 | dev |
| 1445175094696 WordCount | 5 | Net 4, N 1 | dev |
| 1445182159119 WordCount | 5 | Disk 5 | dev |
| 1445076437777 PageRank | 5 | MD 3, N 2 | **held-out** |
| 1445144423722 PageRank | 5 | Net 3, N 2 | **held-out** |
| 1445182159119 PageRank | 10 | MD 5, Disk 4, N 1 | **held-out** |
- **Dev 35** (MD 20, Normal 6, Net 4, Disk 5) · **Held-out 20 = 36%** (MD 8, Normal 5, Net 3, Disk 4). All 4 classes in both.
- **Novelty per brick:**
  - *Pattern:* held-out comes from unseen cluster runs → `make_split.py` reports how many held-out templates are unseen by the dev-fitted Drain3 (count only).
  - *Evidence:* network disconnection and disk full **on PageRank** never occur in dev (new evidence situations).
  - *Verdict:* same (class × app) combos unseen in dev.
  - *Finding / question:* 1 of the 4 question wordings is used **only** in held-out (unseen phrasing).
- **Mechanics:** `scripts/make_split.py` moves held-out job dirs to `dataset/heldout/hadoop/`, writes dev
  questions/labels to `dataset/dev/hadoop/`, held-out ones to `dataset/heldout/hadoop/`, prints aggregates only.
- **Disclosure:** to design this split Claude has seen the label file (job id → class) and per-run label counts for all
  55 jobs, plus the 5 first lines of one dev job. No held-out log content has been read.

**Questions (D6), per job, ground truth = class:**
- dev wordings: "Why did Hadoop job {app} fail?" · "What went wrong with job {app}?" · "Did job {app} complete normally? If not, what was the cause?"
- held-out-only wording: "Job {app} looks unhealthy — what's the root cause?"
- Each job is asked with every wording assigned to its split (paraphrase robustness).
- Answer space: `normal`, `machine down`, `network disconnection`, `disk full` (closed set).
- Scope = the job id in the question (code extracts it) → **evidence is gathered from the job's logs, never by the
  question's words** (PRODUCT.md generalization principle).

## 4. Pipeline under test (bricks)
| Brick | What exactly is built | Tool |
|---|---|---|
| Pattern | Drain3 (generic masks: numbers, hex, IPs, host:port, paths, ids; depth/sim defaults) fitted online on dev, `pattern_id` written to `log_attributes`; `patterns` table: id, template, severity mix, count, #jobs, first/last seen | Drain3 + SereneDB |
| Evidence | Per job (SQL only): WARN+ patterns with count, #containers affected, first appearance (as words, e.g. "starts 40% into the job"), **rarity** = fraction of all jobs that contain the pattern (as words), job duration, #containers, max severity. Top-K=12 by severity then rarity. Each Evidence row stores its SQL. | SereneDB |
| Verdict | **One Jev request per job** (`jev-1.13.0`): `root_cause` Choice over the 4 classes with structured definitions; `key_evidence` Choice over evidence ids `E1..Ek` + `none` (for citation). | Jev SDK |
| Finding | `{class, confidence, badge (auto / review / don't know via dev-tuned thresholds), cited evidence ids}`. No LLM prose in 001 (classification is what we measure; explanation layer comes later). | code |

**SereneDB:** `otel_logs` built-in index unchanged (lean rule). New tables `patterns`, `evidence`, `verdicts`,
`findings`, `traces` (plain tables, no extra indexes until measured). Held-out lives in a **separate schema `heldout`**,
ingested through a **second OTLP listener** `http://0.0.0.0:4319?api=otel&schema=heldout` (config change to
`docker/serened.conf`). Dev code only ever touches `public`.

## 5. Baselines and ablations
**Baselines (D7)**, same split, same questions:
- **B1 LLM-same-evidence:** `gemini-3.8-flash`, minimal thinking, gets the identical evidence state, returns JSON
  `{class, confidence 0–1, key_evidence}`.
- **B2 LLM-raw-logs:** same model, gets the job's WARN/ERROR/FATAL lines + first/last 50 lines, capped at ~30k tokens.
- **B3 classifier:** TF-IDF (bag of pattern templates weighted by count) + logistic regression; dev estimate via
  leave-one-group-out CV; final fit on all dev → held-out. Probabilities used for calibration metrics.
- **B4 rules:** majority class + a hand-written keyword rule set (shows what a non-general approach gets).

**Ablations on dev (lean rule, one at a time, keep only what helps):**
- A0: root_cause with plain label names, evidence = WARN+ patterns only.
- A1: + rarity & timing evidence. A2: + structured class definitions. A3: + 3 shuffled-order copies of root_cause
  in the same request (agreement → confidence). The best dev config is frozen before held-out.

## 6. Metrics
Accuracy, **macro-F1** (imbalanced classes), per-class recall · **Brier, ECE (5 bins), reliability diagram** ·
selective accuracy vs coverage curve · self-consistency (3 repeats) · option-order robustness (3 shuffles) ·
paraphrase consistency (same job, different wording → same answer?) · latency p50/p95 · $ per 1k questions ·
95% bootstrap CIs on held-out.

## 7. Tracing (D8)
- Each brick step is a **LangChain Runnable** (`RunnableLambda` around SQL / Drain3 / TypeSafe SDK / Gemini); a custom
  callback handler writes one row per step to SereneDB `traces`: run_id, example_id, split, step, brick, input JSON,
  output JSON, SQL, latency_ms, tokens, $, model version, error.
- **Viewer:** `apps/trace_viewer.py` (Streamlit): pick run → example → see Pattern → Evidence (with SQL) → Verdict
  (probabilities) → Finding, plus baselines side by side and ground truth. Dev only; held-out traces live in schema
  `heldout` and the viewer shows them only behind a `--show-heldout` flag for the user.
- `langchain-typesafe` is alpha (0.0.1a3) → we wrap the stable `typesafe-sdk` 0.7.3 ourselves.
- All Jev/Gemini responses cached on disk (keyed by request hash) → reruns are free and reproducible.

## 8. Held-out protocol
- `make_split.py`: runs once at the start; output = split summary (sizes, class counts, novelty counts).
- `eval_heldout.py --pipeline <frozen-config> --baselines all`: ingests held-out via port 4319 into schema `heldout`,
  runs pipeline + baselines, writes traces into `heldout.traces`, **prints only the aggregate metrics table**.
- Run **once**, after dev config is frozen and the user says go. No iteration on held-out results.

## 9. Out of scope / risks
- Out: LLM explanation prose, metrics/traces signals, hybrid/vector search, lead/manager roles, GAIA/BGL.
- Risks: Drain3 on Python 3.14 (fallback: `uv` venv with Python 3.12) · tiny n · Hadoop labels are per job, not per
  node, so "which machine" can't be scored · Gemini thinking budget param name must be verified · OTLP second listener
  needs a SereneDB restart (data persists).

## 10. Steps (checklist)
- [ ] Python env (`.venv`, pinned `requirements.txt`): typesafe-sdk, drain3, langchain, langchain-google-genai, psycopg, scikit-learn, streamlit; verify Drain3 on 3.14.
- [ ] Add OTLP listener for `heldout` schema; restart SereneDB; `init.sql` grants for both schemas.
- [ ] `scripts/make_split.py` (user reviews) → run → split summary.
- [ ] Ingest dev jobs via OTLP (parser + continuation-line handling).
- [ ] Pattern brick: Drain3 + `pattern_id` + `patterns` table.
- [ ] Evidence brick: SQL per job, stored with its SQL.
- [ ] Verdict brick: Jev request; Finding brick: thresholds tuned on dev.
- [ ] Tracing (callback → `traces`) + Streamlit viewer.
- [ ] Baselines B1–B4 on dev.
- [ ] Ablations A0–A3 on dev → freeze config.
- [ ] `scripts/eval_heldout.py` (user reviews) → user approves → run once.
- [ ] Results section + commit on branch.

## 11. Results (filled after running)
**Dev (2026-10-11), fair mirrored run (amendment 2), frozen = A4** (by average macro-F1 of both models).
Fairness verified: identical evidence + class options in 525/525 Jev/LLM pairs. Full tables: `docs/PIPELINE.md` §11.
Jev A4 macro-F1 0.51 / Brier 0.84 / 233 ms / $0.08 per 1k vs LLM A4 0.49 / 0.92 / 1,863 ms / $1.33.
Accuracy is a tie; Jev wins calibration, consistency (wordings 0.91 vs 0.71), speed, cost. LLM slightly better on A0.
H1 ✅ H2 ✅ H3 ✅ H4 ❌ (no threshold reaches 90% for either model). Held-out: not run yet.
**Report:** https://claude.ai/artifact/8XPVMCUAX2aPirdtSeiUgE (source `reports/001-hadoop.html`).

---
## Amendment 1 (approved by user 2026-10-11)
**Why:** dev run showed the bottleneck is the Evidence brick: `severity_number >= 13` keeps ~4 of ~2,700 lines per job;
37/60 machine-down questions → "normal". Dev check (labels used for diagnosis only, never by the pipeline): rare INFO
patterns such as `TaskAttempt killed because it ran on unusable node` (88% machine down) appear in 12/20 machine-down
jobs; median duration normal 7.6 min vs machine down 27.5 min.
**Changes:**
- **A4 = rarity-first evidence + typical-duration comparison** (generic, label-free): candidate patterns = any severity
  with rarity ≤ 25% of jobs, plus all WARN+; ranked rarity → severity → count; top-K 12 unchanged; job duration phrased
  relative to the corpus median job duration. Jev questions/prompts unchanged.
- **B3 also evaluated with stratified 5-fold CV over jobs** (every class in every training fold), in addition to
  leave-one-run-out.
- **Fairness fix (already applied):** LLM baselines receive the identical structured class definitions as Jev; exact LLM
  input stored in traces. LLM calls have a 60 s timeout, failures recorded (not cached).
- Then: freeze best of A0–A4 on dev, tune the auto threshold, run held-out once.

## Amendment 2 (requested by user 2026-10-11): mirrored, fair ablations
**Principle:** the goal is a fair comparison, not a Jev win. Every variant change applies to BOTH models.
- Each variant A0–A4 runs on Jev **and** on the LLM (`LLM A0…A4`, gemini-3.8-flash, thinking off):
  - identical evidence state (same Evidence brick output, verified automatically per question),
  - identical class options: plain label names for A0/A1, structured definitions for A2–A4,
  - A3: the LLM is also asked with 3 shuffled class orders; its confidence is multiplied by order agreement, exactly as Jev's.
- Frozen variant chosen on Jev+LLM jointly is NOT allowed to favour one model: we report every variant for both, and pick
  the variant by the **average** macro-F1 of the two models (so evidence choices aren't tuned to one model).
- Dashboard shows, per question, Jev's exact request and the LLM's exact prompt side by side, with a check that the
  evidence state embedded in both is identical.
- B2 (raw logs), B3, B4 unchanged.

## Amendment 3 (approved by user 2026-10-11): H4 confidence signals (analysis only)
**Why:** H4 failed for both models: no threshold on the default confidence gives ≥90% selective accuracy on dev.
**What:** offline re-scoring of the existing dev traces of the mirrored run (no new model calls, no new data), for
**both models alike**. Candidate "should we answer automatically?" signals:
- Jev: computed confidence (current), top probability, top-two margin, key-evidence confidence, root-cause/key-evidence
  consistency (a non-normal answer must cite an item; "normal" must cite `none`), A3 shuffle agreement, agreement across
  the 3 question wordings.
- LLM: self-reported confidence (current), A3 shuffle agreement, agreement across the 3 wordings.
For each signal: risk-coverage curve, best coverage at ≥90% and ≥80% selective accuracy, and AURC (area under the
risk-coverage curve, lower is better). Script: `experiments/001_hadoop/h4_confidence.py`.
**Caveat:** thresholds picked on dev are optimistic; held-out validates the chosen signal once.

### Amendment 3 result (2026-10-11)
No confidence signal reaches 90% selective accuracy for either model (best at ≥80%: Jev 10% coverage, LLM 5%). Jev
ranks better (AURC 0.42–0.45 vs 0.51–0.53). Cause: 5 dev jobs labelled as failures show no fault in their logs; both
models say "normal" on all 15 of their questions. Decision: keep the current confidence; re-test H4 on GAIA.
Details: `docs/PIPELINE.md` §11.4, `runs/001/h4_results.md`.

### Held-out result (run once, 2026-10-11): status → done
Macro-F1: Jev 0.32 · LLM same input 0.42 · LLM raw logs 0.54 · classifier (all dev) 0.66 · rules 0.27. Brier Jev 1.03 vs
LLM 1.06. H1 ❌ H2 ≈ H3 ✅ H4 ❌. Dev conclusions did not generalize. Details + hypotheses: `docs/PIPELINE.md` §11.5.
The user asked Claude to do the held-out steps itself; Claude edited the two config files (guard exemption approved,
D5 note) and wrote/ran the evaluation script. Two attempts failed before reading any data (venv re-exec, schema grant).

### Held-out: user steps (before Claude writes the evaluation script)
1. In `docker/serened.conf`, replace the `--listen=` line with (adds a 2nd OTLP listener writing to its own schema):
   `--listen=postgres://0.0.0.0:7890,http://0.0.0.0:4318?api=otel,http://0.0.0.0:4319?api=otel&schema=<held-out schema name>`
   using the held-out schema name from section 4 of this plan.
2. In `docker-compose.yml`, add the port mapping `"127.0.0.1:4319:4319"` under `ports:`.
3. `docker compose up -d` (recreates the container; data persists), then `./docker/secrets.sh`.
4. Tell Claude "listener added". Claude then writes the evaluation script (you review it), you approve, it runs once.
