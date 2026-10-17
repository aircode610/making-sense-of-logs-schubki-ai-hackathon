# The pipeline, explained: what it does, how, why, and where each idea comes from

This is the reference for experiment 001 (Loghub Hadoop) and the pipeline code in `pipeline/`. It explains every step,
every technique, every label we use (A0–A4, B1–B4, metrics) and the literature behind them.
Companion docs: `runs/001/walkthrough.md` (one example traced end to end), `pipeline/README.md` (file map + knobs),
`plans/001-hadoop-minimal.md` (the approved plan + amendment), `docs/PRODUCT.md` (principles).

---

## 1. The problem in one paragraph
An engineer asks *"Why did Hadoop job X fail?"*. The answer must be one of four classes: `normal`, `machine down`,
`network disconnection`, `disk full`. Ground truth comes from Loghub's Hadoop dataset, where those faults were injected
on purpose (§9). We want a system that answers **correctly**, says **how sure it is in a way we can trust**, is **fast
and cheap**, and is **traceable**: every claim can be followed back to the SQL and the log lines behind it.

## 2. The big picture
```
raw log files ─► parse ─► Drain3 patterns ─► OTLP ─► SereneDB otel_logs           (once, at ingest)

question ─► [1 Pattern] ─► [2 Evidence] ─► [3 Verdict] ─► [4 Finding]               (per question)
              SQL            Python          1 Jev call     Python
              counts,        rank +          typed answer   answer card:
              rarity,        numbers→words   + probabilities class, confidence,
              job facts                                     badge, citation
```
These are the four "Lego bricks" of `docs/PRODUCT.md`. Each brick only adds its own piece and every step is recorded in
the `traces` table, which the dashboard (`apps/trace_viewer.py`) displays.

**Division of labour (the core design rule):**
- **SereneDB computes every number** (counts, rarity, durations). Numbers are never produced by a model.
- **Python turns numbers into words** (e.g. "rare: seen in 7 of 35 jobs") because Jev is weak at numbers and dates.
- **Jev makes the judgment** (which class? which evidence item?) and returns calibrated probabilities.
- **No LLM is in the main pipeline yet.** LLMs appear only as baselines (B1, B2) to compare against.

---

## 3. Ingest (once): from raw files to rows
Code: `pipeline/hadoop.py`, `pipeline/patterns.py`, `pipeline/ingest.py`, `experiments/001_hadoop/run_dev.py ingest`.

### 3.1 Parsing
Each Hadoop container log line looks like
`2015-10-17 15:45:59,146 ERROR [RMCommunicator Allocator] org.apache…RMContainerAllocator: Container complete event …`.
A regex splits it into timestamp, level, thread, logger and message. Lines that don't start with a timestamp are
**continuations** (Java stack traces) and are appended to the previous record's body, so a stack trace stays attached to
the error that produced it. Timestamps are treated as UTC.

### 3.2 Templates / patterns (Drain3)
**Idea.** Almost every log line is produced by a `print`/`log` statement with variable parts, so thousands of lines share
one **template**: `payment failed for order A-6072` and `… A-8301` → `payment failed for order <*>`. Grouping lines by
template is called **log parsing**. It gives compression (115k lines → 245 patterns), identity (count a pattern, see where
it appears), and cost control (judge a pattern once, not every line).

**Drain** (He et al., 2017) is the standard online log parser. It routes each line through a **fixed-depth parse tree**
(first by number of tokens, then by the first few tokens) to a small set of candidate clusters, then joins the most
similar cluster if token similarity ≥ `sim_th`, otherwise opens a new cluster. Online (one pass, incremental), fast, and
the best-performing heuristic parser in the Loghub benchmarks. **Drain3** is the maintained open-source implementation
(IBM / logpai) with persistence and masking.

**Our settings** (`config.py`): `sim_th = 0.4`, `depth = 4`. **Generic masks** (`patterns.py`) replace variable tokens
*before* mining, e.g. UUIDs → `<UUID>`, `container_1445_0011_01_000002`-style ids → `<ID>`, IPs → `<IP>`,
`host:port` → `<HOSTPORT>`, paths → `<PATH>`, hex → `<HEX>`, numbers → `<NUM>`. They are deliberately **not
Hadoop-specific** (the generalization rule in `docs/PRODUCT.md`). The template is mined from the **first line** of the
message only (stack traces vary too much). The result is a `pattern_id` like `P162` on every record.

### 3.3 OpenTelemetry + OTLP into SereneDB
**OpenTelemetry (OTel)** is the vendor-neutral standard for telemetry (logs, traces, metrics). **OTLP** is its wire
protocol. SereneDB accepts OTLP/HTTP directly (`POST :4318/v1/logs`) and stores each LogRecord as a row of `otel_logs`.
Using OTel as the input contract is what makes the product general: any OTel-instrumented system can plug in.

What lands in the row: `timestamp`, `severity_text`/`severity_number` (OTel scale: INFO 9, WARN 13, ERROR 17, FATAL 21),
`body` (message + stack trace, full-text indexed), `service_name = hadoop-mapreduce`, `resource_attributes`
(`application.id` = the job, `container.id`), `log_attributes` (`logger`, `thread`, **`pattern_id`**). The label is never
stored. 35 dev jobs → 115,455 rows. `otel_logs` keeps SereneDB's built-in inverted index unchanged (lean rule).

---

## 4. Brick 1: Pattern (SQL)
Code: `bricks.pattern_brick`, queries in `pipeline/queries.py`. The job id is taken from the question by code. The
**question's words are never used to search** ("the question never gates evidence", `docs/PRODUCT.md`).

| Query | What it computes | Why |
|---|---|---|
| `PATTERN_STATS` (once per run) | for every pattern: lines, **number of jobs it appears in**, max severity | rarity baseline |
| `TOTAL_JOBS` (once) | number of jobs in the corpus (35 in dev) | denominator for rarity |
| `TYPICAL_DURATION` (once, A4) | median job duration across the corpus | baseline for "longer than usual" |
| `JOB_FACTS` | job start/end, #containers, #lines, #FATAL/#ERROR/#WARN | job-level summary |
| `JOB_PATTERNS` | per pattern **in this job**: max severity, count, #containers, first time seen, one example line | the candidate evidence |

`JOB_PATTERNS` takes a severity cutoff: **WARN and worse** for variants A0–A3, **all severities** for A4 (the Evidence brick
then selects; see §5). Rarity = "in how many jobs does this pattern appear" is the same intuition as **inverse document
frequency** (Spärck Jones, 1972): a pattern seen in almost every job carries little information, a pattern seen in few
jobs is informative.

## 5. Brick 2: Evidence (Python)
Code: `bricks.evidence_brick`. Two jobs: **select + rank** candidate patterns, and **turn numbers into words**.

**Selection and ranking per variant:**
- A0–A3 (`evidence = basic/full`): all WARN+ patterns of the job, ranked severity ↓, rarity ↑, count ↓.
- A4 (`evidence = rarity`): patterns that are **rare** (in ≤ 25% of jobs, any severity) **plus** all WARN+ patterns,
  ranked rarity ↑, severity ↓, count ↓.
- Keep the top `TOP_K_EVIDENCE = 12` as items `E1…E12`.

**Numbers → words** (all computed from SQL values):
| Field | Rule |
|---|---|
| `occurrences` | `"{n} lines in {containers} of {total containers} containers"` |
| `first_appearance` | position of first occurrence in the job's time span: <5% "at the very start", <33% "early", <66% "midway", else "late" |
| `rarity` | jobs with pattern / total jobs: 1 job "seen only in this job", ≤25% "rare", ≤60% "occasional", else "common" |
| `example_line` | the first real line (first 300 chars): shows values the template masked |
| `duration` (A4) | job duration vs corpus median: ≥1.5× "about N× longer than a typical job", ≤0.67× "shorter than a typical job", else "typical" |

The resulting **state** (question + job summary + E-items) is the exact input to Jev and to the LLM baseline B1.

## 6. Brick 3: Verdict (one Jev request)
Code: `bricks.verdict_brick`, questions in `pipeline/prompts.py`. Model pinned to `jev-1.13.0`.

**Jev** (TypeSafe AI) is a "System One" model: no text generation. Input = a **state** + typed **questions**; output =
a typed answer with a probability distribution and a confidence, in ~250 ms. Three question types: **Choice** (one of N
options), **Score** (position on ordered levels), **Noul** (probability a yes/no statement is true). All questions in one
request are evaluated **in parallel and independently** (one question can't see another's answer).

We ask two Choice questions in **one** request:
1. `root_cause`: Choice over the 4 classes. In "structured" mode each option carries a **definition**, what it
   **covers** and what it **does not cover** (`CLASS_DEFINITIONS_STRUCTURED`). These definitions are generic SRE
   knowledge, never Hadoop log strings.
2. `key_evidence`: Choice over the evidence ids `E1…Ek` plus `none`. This is the **evidence-in-choices** technique from
   TypeSafe's docs (the "line-by-line search" cookbook): the candidates themselves are the options, so the model *selects*
   evidence instead of generating text. It gives the Finding its citation and lets the model say "none".

**Confidence** is computed from the probabilities, not self-reported. For a Choice with n options and top probability
p_max: `confidence = (p_max − 1/n) / (1 − 1/n)` (0 = uniform, 1 = certain). Example: 0.83 among 4 → (0.83 − 0.25)/0.75 = 0.77.

**Shuffles (A3 only):** the same root_cause question repeated with the options in random orders inside the same
request. Agreement across orders = robustness to **option-order bias** (a known weakness of both LLMs and Jev).

## 7. Brick 4: Finding (Python)
Code: `bricks.finding_brick`. The answer card: `answer`, `confidence` (× shuffle agreement if shuffles were used),
`badge` = **auto** if confidence ≥ `AUTO_THRESHOLD`, else **needs review**, `cited_evidence` (E-id + pattern text).
The threshold is tuned on dev (§10.4) and frozen before held-out. "Needs review" is how the system says "I'm not sure"
instead of guessing (**selective prediction**, §10.3).

## 8. Orchestration and tracing
- **LangChain** wires the bricks (`pipeline/chain.py`): each brick is a `RunnableLambda`, and
  `RunnablePassthrough.assign` adds its output to the example dict, so each step's input and output are cleanly separable.
- **Tracing** (`pipeline/trace.py`): a LangChain callback writes one row per step to `traces` (run id, question id, step,
  timestamp, latency, full input JSON, full output JSON, error). LLM baseline traces include the **exact system message
  and prompt** (`request`), and Jev traces include the exact Jev request (state + questions).
- **Cache** (`pipeline/cache.py`): every model call is stored by a hash of its full request, so reruns are free and
  reproducible. Failures are never cached. Shuffle seeds use a stable hash (crc32) so reruns are identical.
- **Dashboard** (`apps/trace_viewer.py`): pick a session → variant → filters → example; see all bricks + baselines.

---

## 9. Data and evaluation protocol
**Dataset: Loghub Hadoop** (Zhu et al., 2023; collected by Lin et al., 2016). Logs of 55 MapReduce jobs (WordCount,
PageRank) on a 5-machine cluster. Faults were **injected**: *machine down* (a server turned off), *network disconnection*
(a server unplugged from the network), *disk full* (a disk filled up), plus normal runs. Labels are per job.

**Split** (`scripts/make_split.py`, `docs/DECISIONS.md` D4/D5): groups = (cluster run, application type), and whole
groups go to one side so nothing leaks. **Dev = 35 jobs** (105 questions = 35 × 3 wordings), **held-out = 20 jobs**
(80 questions, incl. one wording never seen in dev). Held-out contains situations absent from dev (PageRank +
network disconnection, PageRank + disk full) and 11 new templates. **Claude never sees held-out data**: enforced by a
hook (`.claude/hooks/guard_eval_data.sh`); it is evaluated once, at the end, by `scripts/eval_heldout.py`.

**Questions:** generated from ground truth with fixed wordings (*"Why did Hadoop job X fail?"*, *"What went wrong with
job X?"*, *"Did job X complete normally? If not, what was the cause?"*; held-out only: *"Job X looks unhealthy — what's
the root cause?"*). Several wordings per job test **paraphrase robustness**.

**Dev vs held-out discipline:** we may tune anything on dev (prompts, thresholds, variants). Held-out is touched **once**,
with a frozen configuration. Otherwise the reported numbers would be optimistic (overfitting to the test set).

---

## 10. Glossary: every label and metric we use

### 10.1 Variants (ablations) A0–A4
An **ablation study** changes one component at a time and measures the effect, so each component has to earn its place
(our "lean rule"). All variants use the same Jev model and the same 105 dev questions.

| Label | Evidence | Class options | Shuffles | Tests |
|---|---|---|---|---|
| **A0** basic evidence, plain labels | WARN+ patterns: template, severity, occurrences | names only (`"disk full"`) | 0 | minimal baseline |
| **A1** full evidence, plain labels | A0 + first appearance, rarity, example line | names only | 0 | does richer evidence help? |
| **A2** full evidence, structured | as A1 | definition + covers + does_not_cover | 0 | do class definitions help? |
| **A3** + 3 shuffles | as A2 | as A2 | 3 extra orders | does order-robustness add value? |
| **A4** rarity evidence, structured | rare patterns at any severity + WARN+, rarity-ranked; duration vs typical job | as A2 | 0 | does fixing the evidence bottleneck help? (amendment 1) |

### 10.2 Baselines B1–B4
| Label | What it is | Why it's there |
|---|---|---|
| **B1** LLM, same evidence | `gemini-3.8-flash` (thinking off, temperature 0) gets the **identical** state and class definitions as Jev; returns JSON with a class and a **self-reported** confidence | isolates the model: same input, Jev vs LLM |
| **B2** LLM, raw logs | same model; gets the job's raw WARN/ERROR/FATAL lines + first/last 50 lines (≤120k chars) | "just throw the logs at an LLM", no SereneDB evidence |
| **B3** classifier | **TF-IDF** over the job's pattern ids (bag of patterns weighted by count) + **logistic regression** (class-balanced) | classic supervised ML; needs labelled training data |
| **B4** rules | hand-written keyword rules ("no space" → disk full, "timed out" → network, …), else "error → machine down" | the non-general, hand-crafted approach |

**B3 has two evaluations:**
- **LORO-CV** (leave-one-run-out cross-validation) trains on all cluster runs but one and tests on the held-out run.
  Harsh: in dev, disk full and network disconnection each occur in only one run, so the model never sees them in
  training. It measures generalization to unseen situations.
- **Stratified 5-fold CV** splits **jobs** into 5 folds that keep the class proportions, so every class is in every
  training fold. This is the fair "accuracy if trained on similar data" estimate.

**LLM confidence:** the LLM writes a number ("confidence": 0.95). We turn it into a distribution (that number on its
class, the remainder spread over the others). That's how an LLM product would expose confidence, and the literature
shows such verbalized confidence tends to be **overconfident** (Xiong et al., 2024; Tian et al., 2023).

### 10.3 Metrics
| Metric | Meaning | Good |
|---|---|---|
| **Accuracy** | share of questions answered correctly | high |
| **Macro-F1** | F1 = harmonic mean of precision and recall, computed **per class** then averaged equally. Our main accuracy metric because classes are imbalanced (machine down = 57% of dev): a system that always says "machine down" gets 57% accuracy but low macro-F1 | high |
| **95% bootstrap CI** | resample the examples 1,000× with replacement, recompute the metric, take the 2.5th–97.5th percentiles (Efron, 1979). Shows how uncertain a number is with small n | narrow |
| **Brier score** | mean squared error between the predicted probability vector and the one-hot truth, summed over classes (Brier, 1950). Range 0 (perfect) to 2 (confident and wrong). Rewards being right **and** honest about uncertainty | low |
| **ECE** (expected calibration error) | bucket answers by confidence (5 bins), compare average confidence with actual accuracy in each bin, take the weighted average gap (Naeini et al., 2015; Guo et al., 2017). "When it says 80%, is it right 80% of the time?" | low |
| **Selective accuracy / coverage** | answer only when confidence ≥ threshold: accuracy on the answered ones / share answered. Plotting both = risk-coverage curve (El-Yaniv & Wiener, 2010; Geifman & El-Yaniv, 2017) | high both |
| **Self-consistency (repeatability)** | same input asked 3 times → same answer? | high |
| **Paraphrase consistency** | same job, different wordings → same answer? | high |
| **Option-order agreement** | same question, shuffled options → same answer? (Zheng et al., 2024; Pezeshkpour & Hruschka, 2024 on LLM order bias) | high |
| **Latency p50 / p95** | median / 95th-percentile time per question | low |
| **Cost per 1k questions** | input tokens × list price (Jev $0.042/M input tokens; Gemini price in `config.py` is an assumption) | low |

### 10.4 Threshold tuning ("auto" vs "needs review")
On dev, find the **smallest confidence threshold** at which selective accuracy reaches 90% (`run_dev.tune_threshold`).
Answers above it get the "auto" badge. If no threshold reaches 90%, the result is `None`: the system is not yet reliable
enough to act automatically on any slice. That's what happened for A2 (H4 failed).

### 10.5 Success criteria (fixed in the plan before running)
- **H1** Jev macro-F1 ≥ LLM-same-evidence − 0.05. **H2** Jev Brier ≤ LLM Brier. **H3** Jev ≥ 5× faster and cheaper.
- **H4** at the dev-tuned threshold, held-out selective accuracy ≥ 0.9 with coverage ≥ 0.6.

---

## 11. Results (dev, 105 questions)
Latest: `runs/001/dev_results.md` (session `001-dev-20261011-…`, amendment 2 = **fair, mirrored**). History:
`dev_results_v1_unfair_llm_definitions.md` (LLM got shorter definitions), `dev_results_v2_fair_llm.md` (LLM only on frozen variant).

**Fairness check:** in every one of the 525 Jev/LLM pairs (5 variants × 105 questions) the LLM prompt contained the
identical evidence state and identical class options as Jev's request (verified automatically over all traces).

### 11.1 Every variant on both models
| Variant | Jev macro-F1 | LLM macro-F1 | Jev Brier | LLM Brier | Jev ECE | LLM ECE |
|---|---|---|---|---|---|---|
| A0 basic evidence, plain labels | 0.41 | **0.44** | **0.95** | 1.14 | **0.36** | 0.55 |
| A1 + timing, rarity, example line | **0.43** | 0.31 | **1.02** | 1.28 | **0.45** | 0.64 |
| A2 + structured definitions | **0.48** | 0.34 | **1.01** | 1.29 | **0.43** | 0.64 |
| A3 + 3 shuffled orders | **0.48** | 0.37 | **1.01** | 1.27 | **0.43** | 0.63 |
| **A4 rarity evidence (FROZEN)** | **0.51** [0.39, 0.59] | 0.49 [0.39, 0.59] | **0.84** | 0.92 | **0.32** | 0.43 |

Frozen by the **average** of both models' macro-F1 (A4: 0.50; next best A0: 0.43).

### 11.2 Frozen config (A4) vs everything
| System | Accuracy | Macro-F1 | Brier ↓ | ECE ↓ | p50 | p95 | $ / 1k q |
|---|---|---|---|---|---|---|---|
| **Jev A4** | 0.48 | 0.51 | **0.84** | 0.32 | **233 ms** | **311 ms** | **$0.08** |
| LLM A4 (same evidence + options) | 0.48 | 0.49 | 0.92 | 0.43 | 1,863 ms | 6,967 ms | $1.33 |
| LLM on raw logs (B2) | 0.33 | 0.38 | 1.20 | 0.59 | 1,927 ms | 6,615 ms | $5.51 |
| Classifier, stratified 5-fold (B3) | 0.57 | 0.48 | 0.65 | 0.22 | ~0 | ~0 | needs labels |
| Classifier, leave-one-run-out (B3) | 0.43 | 0.23 | 0.84 | 0.12 | ~0 | ~0 | needs labels |
| Keyword rules (B4) | 0.57 | 0.36 | 0.86 | 0.43 | 0 | 0 | 0 |

| Consistency | Jev | LLM |
|---|---|---|
| Same answer across 3 repeated runs | 0.91 | 0.89 |
| Same answer across question wordings | **0.91** | 0.71 |
| Same answer across shuffled option orders (A3) | **0.96** | 0.88 |

### 11.3 What it means (fair reading)
- **Accuracy is a tie** under the best shared configuration: Jev 0.51 vs LLM 0.49 macro-F1, same accuracy (0.48),
  overlapping confidence intervals. We should not claim Jev is more accurate.
- **With the least evidence (A0) the LLM is slightly better** (0.44 vs 0.41).
- **Jev's real advantages are calibration, consistency, speed and cost:** lower Brier and ECE in every variant,
  same answer across wordings 91% vs 71%, 8× faster at p50 (22× at p95), 17× cheaper.
- **Techniques help the two models differently:**
  - richer evidence fields (A1) helped Jev slightly (+0.02) and **hurt the LLM a lot** (0.44 → 0.31);
  - structured class definitions (A2) helped Jev (+0.05) and the LLM a little (+0.03);
  - shuffles (A3) did nothing for Jev and cost the LLM 4× the calls (p50 11 s);
  - **rarity-first evidence (A4) helped both, the LLM most** (A2 → A4: Jev 0.48 → 0.51, LLM 0.34 → 0.49). The evidence step (SereneDB + selection)
    is the biggest lever for everyone.
- **H4 fails for both models:** no confidence threshold reaches 90% selective accuracy on dev.
- Success criteria (dev, directional): H1 ✅ (0.51 vs 0.49), H2 ✅ (0.84 vs 0.92), H3 ✅ (8× faster, 17× cheaper), H4 ❌.

### 11.4 H4 analysis: can any confidence signal make "auto" answers ≥ 90% accurate? (amendment 3)
Offline re-scoring of the mirrored dev traces, both models alike (`experiments/001_hadoop/h4_confidence.py`,
`runs/001/h4_results.md`). Signals tried: computed confidence, top probability, top-two margin, key-evidence confidence,
answer/citation consistency, shuffle agreement, agreement across 3 wordings (Jev); self-reported confidence, shuffle
agreement, wording agreement (LLM).
- **No signal reaches 90% selective accuracy at any coverage, for either model.** Best at ≥80%: 10% coverage (Jev), 5% (LLM).
- **Jev ranks its answers better** (AURC 0.42–0.45 vs 0.51–0.53; its most confident third is 54% right vs 37%).
- **Why:** 5 dev jobs (15 questions) are labelled machine down / disk full but their logs show no trace of the fault
  (e.g. one common WARN, no ERROR, shorter than a typical job). **Both models answer "normal" on all 15**, Jev at
  0.69–1.00, the LLM at 0.95–0.99. Given that evidence, "normal" is the honest reading; the label likely reflects a
  fault on a machine this job didn't depend on (cf. Loghub's label-quality issue #56). Excluding those jobs (diagnostic
  only), the most confident third is 67% right (Jev) vs 60% (LLM): still far from 90%.
- **Decision:** keep the current confidence formula (no alternative gave a meaningful gain, lean rule). H4 is limited by
  evidence and label quality on Hadoop; re-test on GAIA.

### 11.5 Held-out result (run once, 2026-10-11): the dev conclusions did NOT generalize
80 questions (20 jobs, incl. situations absent from dev and one unseen wording). Frozen A4; corpus = dev + held-out jobs;
fairness verified (identical evidence 80/80). Script `scripts/eval_heldout.py` (aggregates only).

| System | Accuracy | Macro-F1 [95% CI] | Brier ↓ | ECE ↓ | p50 | $ / 1k |
|---|---|---|---|---|---|---|
| Jev A4 (frozen) | 0.33 | 0.32 [0.22, 0.41] | 1.03 | 0.50 | 242 ms | $0.08 |
| LLM A4, identical input | 0.41 | 0.42 [0.31, 0.52] | 1.06 | 0.52 | 1,809 ms | $1.37 |
| LLM on raw logs (B2) | 0.53 | 0.54 [0.42, 0.66] | 0.86 | 0.42 | 1,462 ms | $6.01 |
| **Classifier trained on all dev (B3)** | **0.65** | **0.66** [0.53, 0.75] | **0.64** | **0.33** | ~0 | needs labels |
| Keyword rules (B4) | 0.40 | 0.27 [0.20, 0.33] | 1.20 | 0.60 | 0 | 0 |

Same answer across wordings: Jev 0.85, LLM 0.80, raw-logs LLM 0.85. Accuracy on the held-out-only wording: Jev 0.35,
LLM 0.40, raw-logs LLM 0.50, classifier 0.65.

**Criteria on held-out:** H1 ❌ (Jev 0.32 vs LLM 0.42), H2 ≈ (Brier 1.03 vs 1.06, essentially even), H3 ✅ (7.5× faster,
18× cheaper), H4 ❌.

**Reading (hypotheses only: held-out data is never inspected):**
1. The evidence step (A4: rarity framing, duration vs typical, top-12) was chosen on dev and appears to overfit it.
2. Held-out deliberately contains situations dev never had (PageRank + network disconnection / disk full).
3. The raw-logs LLM doing best of the LLM setups suggests our evidence selection discards useful information on new data.
4. The classifier may profit from templates shared between related cluster runs (a run is split by application type).
5. n = 20 jobs: intervals overlap; the ranking itself is uncertain.
6. **Domain shift from the split** (found after the run, from split metadata): held-out was 100% PageRank while dev was
   71% WordCount, and A4's duration baseline ignored job type (normal PageRank jobs run ~4.9 min vs ~13.1 for WordCount).
Full hypothesis table and test plan: `plans/002-ideas.md` Part A.
**Lesson for experiment 002:** freeze evidence choices with grouped cross-validation on dev (not a single dev score),
test evidence selection against the raw-logs baseline early, and keep the classifier as a strong, honest reference.

### 11.6 Experiment 002 (GAIA, three roles): dev results (2026-10-11)
Plan + full tables: `plans/002-gaia-question-design.md` §11; raw: `runs/002/dev_results.md`. Grouped 5-fold CV by day,
657 engineer questions (219 windows: 35 fault, 69 memory "no-trace", 115 normal). Identical input for Jev and the LLM
in 100% of pairs. GAIA code: `pipeline/gaia*.py`, `experiments/002_gaia/`; viewer `apps/trace_viewer_002.py`.

| Role · system | Jev | LLM | Other |
|---|---|---|---|
| Engineer, E0 (001-style evidence) macro-F1 | 0.34 | 0.99 | |
| Engineer, **E1 per-service 24 h baseline (frozen)** | 0.80 | 0.97 | raw-logs LLM 0.46 · classifier 0.92 · rules 1.00 (keywords chosen after the data look) |
| Engineer, frozen E1/Q7: root-cause service top-1 | 1.00 | 1.00 | rules 1.00 |
| Engineer, Q1 "can't tell" option | 0.87 | 0.98 | not kept (gain < 1 fold-SD) |
| Engineer, "auto" selective accuracy (CV threshold) | 0.91 @ 100% | 0.99 @ 100% | |
| Lead, same-problem F1 · repeat accuracy | 1.00 · 0.93 | 1.00 · 1.00 | cosine 1.00 · rule 0.94 |
| Manager, agrees with impact rule · order-robust | 0.94 · 1.00 | 0.83 · 0.89 | |
| Latency p50 · $ / 1k (engineer) | 228 ms · $0.06 | 1,606 ms · $0.99 | raw logs $57 |

**Reading:** per-service baselines (H-2/H-5) fixed the evidence: Jev 0.34 → 0.80. With identical evidence the LLM is
better at telling a routine error at ~2× its usual rate from a fault (Jev reads shown errors literally); both localize
perfectly; Jev is fully consistent and more order-robust on the manager judgment, 7× faster, 17× cheaper.

### 11.7 Experiment 002: held-out result (run once, 2026-10-12): the dev conclusions held
932 questions (Aug 25–31 + July with webservice1 logs only), frozen E1/Q7, identical input 100%. Full table: plan §11.2.

| System | Macro-F1 [95% CI] | Root service | Brier | p50 | $ / 1k |
|---|---|---|---|---|---|
| **Jev E1/Q7** | **0.85** [0.74, 0.93] (dev 0.80) | 0.64 | 0.13 | 237 ms | $0.05 |
| **LLM E1/Q7**, identical input | **0.90** [0.81, 0.96] (dev 0.97) | 0.64 | 0.09 | 1,792 ms | $0.90 |
| LLM on raw logs | 0.38 | 0.60 | 1.05 | 2,485 ms | $23.55 |
| Classifier (all dev) | 0.67 | — | 0.36 | ~0 | needs labels |
| Keyword rules (dataset-informed) | 0.76 | 0.64 | 0.15 | 0 | 0 |

Lead: same-problem F1 0.85 / 0.87, repeat 0.84 / 0.81. Manager: 100% / 100% agreement and order robustness (12 pairs).
**Reading:** unlike 001, the CV-frozen evidence generalized: Jev improved on new data and the gap to the LLM shrank from
0.17 to 0.05 (C1 missed by 0.002). Root service drops to 0.64 for both because July has only webservice1's logs: a db
fault is invisible there. Raw-logs LLM and classifier collapse on July; SereneDB's per-service evidence is what both
judgment models stand on. Experiment 002 closed (D14).

**Post-hoc dev check (amendment 4, 2026-10-12):** removing raw counts from the evidence (words only) left every Jev answer
unchanged (macro-F1 0.804 both; Brier 0.134 → 0.147); the LLM moved by ±1 question. Counts are not the cause of Jev's false
alarms. 73% of dev questions have no unusual pattern and are trivially "no fault"; on the rest, Jev says "fault" for almost
any item (15/78 quiet windows right) while the LLM rejects most routine noise. Next design: decide "no items → no fault" and
the citation in code, and give Jev one narrow per-item question (plan §11.3).

## 12. References
- **Drain**: P. He, J. Zhu, Z. Zheng, M. R. Lyu. *Drain: An Online Log Parsing Approach with Fixed Depth Tree.* IEEE ICWS 2017. Implementation: Drain3, github.com/logpai/Drain3.
- **Loghub**: J. Zhu, S. He, P. He, J. Liu, M. R. Lyu. *Loghub: A Large Collection of System Log Datasets for AI-driven Log Analytics.* IEEE ISSRE 2023 (arXiv:2008.06448).
- **Hadoop dataset origin**: Q. Lin, H. Zhang, J.-G. Lou, Y. Zhang, X. Chen. *Log Clustering Based Problem Identification for Online Service Systems.* ICSE 2016.
- **IDF / rarity**: K. Spärck Jones. *A statistical interpretation of term specificity and its application in retrieval.* Journal of Documentation, 1972.
- **Brier score**: G. W. Brier. *Verification of forecasts expressed in terms of probability.* Monthly Weather Review, 1950.
- **ECE**: M. P. Naeini, G. F. Cooper, M. Hauskrecht. *Obtaining Well Calibrated Probabilities Using Bayesian Binning.* AAAI 2015. Popularized by C. Guo, G. Pleiss, Y. Sun, K. Q. Weinberger. *On Calibration of Modern Neural Networks.* ICML 2017.
- **Selective prediction**: R. El-Yaniv, Y. Wiener. *On the Foundations of Noise-free Selective Classification.* JMLR 2010. Y. Geifman, R. El-Yaniv. *Selective Classification for Deep Neural Networks.* NeurIPS 2017.
- **Bootstrap**: B. Efron. *Bootstrap Methods: Another Look at the Jackknife.* Annals of Statistics, 1979.
- **LLM verbalized confidence**: M. Xiong et al. *Can LLMs Express Their Uncertainty? An Empirical Evaluation of Confidence Elicitation in LLMs.* ICLR 2024. K. Tian et al. *Just Ask for Calibration.* EMNLP 2023.
- **Option-order bias**: C. Zheng et al. *Large Language Models Are Not Robust Multiple Choice Selectors.* ICLR 2024. P. Pezeshkpour, E. Hruschka. *Large Language Models Sensitivity to The Order of Options in Multiple-Choice Questions.* Findings of NAACL 2024.
- **Jev / System One models, evidence-in-choices, confidence formula**: TypeSafe AI documentation, docs.typesafe.ai (local copy `docs/jev/`).
- **OpenTelemetry**: opentelemetry.io (logs data model, OTLP). **SereneDB**: serenedb.com docs (local copy `docs/serenedb/`).
