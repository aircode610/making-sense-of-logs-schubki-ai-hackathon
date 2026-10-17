# 002: GAIA, three roles, one pipeline: which judgment step makes the answers trustworthy?

- **Status:** done (closed 2026-10-12 after one held-out run, D14). Approved 2026-10-11 (July held-out, impact rule as written; amendments 1–2)
- **Branch:** `exp/002-gaia-question-design` (created from `main` 2026-10-11)
- **Dataset(s):** GAIA MicroSS business logs (Aug 2021, all 10 services; Jul 2021 webservice1 only) + `run/` injection records
- **Date:** 2026-10-11
- **Inputs:** the brief (`.claude/CLAUDE.md`), `docs/PRODUCT.md`, `plans/002-ideas.md` (H-1…H-10, Q0–Q10), `docs/PIPELINE.md` §11, D1–D12

## 1. Problem and question this experiment answers
**The problem (brief):** turn logs into answers people can act on, for three roles, via **question → evidence →
recommendation**. SereneDB finds the evidence and computes every number; a judgment step decides what it means; an LLM
explains and recommends. **Trust is the product:** numbers from SQL, computed confidence, cited evidence, "can't tell"
when the logs don't show it.

| Role | Their question | What they need to act |
|---|---|---|
| **Engineer** | "What went wrong between T1 and T2, where, and how sure are we?" | fault + root-cause service + key evidence + confidence; "not visible in logs" when true |
| **Team lead** | "What keeps coming back, and is today's incident one of them?" | incidents grouped into recurring problems + SQL counts / frequency / time pattern |
| **Manager** | "Which problem should we fix first?" | ranked problems with SQL impact numbers + an impact judgment + confidence |

**Question for 002:** on a noisy multi-service system and on windows it hasn't seen, can one pipeline answer all three
roles' questions reliably enough to act on (correct, calibrated, abstains honestly, holds up on held-out)? **Which
judgment component** (Jev, fast LLM, classifier, rules) and **which question design** per role gets there?
Jev vs LLM is measured fairly (D11) as part of this, not as the goal.

**Scope weight:** engineer = the main, fully measured part (most labels, all ablations). Lead and manager = smaller
measured slices built on the engineer's incidents, enough to know if the design works before the demo.

## 2. Success criteria (fixed before running)
Dev numbers = mean over grouped-CV folds (§5) ± fold SD; CIs = bootstrap clustered by day. "Model" = Jev and LLM alike.

**Can the user act on it? (primary, per role, held-out)**
| # | Role | Pass if |
|---|---|---|
| R1 | Engineer | best system: fault macro-F1 ≥ 0.80 and root-cause-service top-1 ≥ 0.70 on diagnosable windows |
| R2 | Engineer | abstains honestly: ≥ 80% "no fault visible" on no-trace (memory) windows, ≤ 10% on fault windows |
| R3 | Engineer | "auto" badge works: a dev-tuned threshold gives selective accuracy ≥ 0.90 at coverage ≥ 0.5 (001's H4) |
| R4 | Lead | same-problem judgment: pairwise F1 ≥ 0.85; new-vs-repeat accuracy ≥ 0.80 |
| R5 | Manager | priority judgment agrees with the pre-registered impact ranking (§3.3) on ≥ 0.80 of pairs, and is order-robust (≥ 0.90 same answer when options swap) |
| R6 | All | generalization: held-out ≥ dev-CV mean − 0.10 on each role's main metric (001 dropped 0.19) |

**Pipeline health (gates and comparisons)**
| # | Claim | Pass if |
|---|---|---|
| G1 | **Evidence doesn't lose information** (H-4) | best E-variant, LLM macro-F1 ≥ raw-logs LLM (B2) − 0.02 on dev CV. **Gate:** fail → redesign Evidence before any Q-ablation |
| C1 | Jev vs LLM accuracy (fair) | reported per role; parity = Jev ≥ LLM − 0.05 |
| C2 | Jev vs LLM calibration | Brier and ECE per role |
| C3 | efficiency | Jev ≥ 5× faster p50 and cheaper per question (per role) |
| C4 | question design | a Q-variant is kept only if it beats the role's base design by ≥ 1 fold-SD on the **average** of both models |

## 3. Data

### 3.1 What the quick look found (dev-side only, 2026-10-11)
Sources: `run/` injection records (all of Jul + Aug, aggregates) and streamed business logs **Aug 1–5 only**.
| Fault (run records) | Services | Count Jul / Aug | Duration | Visible in business logs? |
|---|---|---|---|---|
| file moving → "file not found" | webservice1/2 only | 43 / 36 | 10 min | **Yes, crisp**: `No such file or directory: …source_file.csv` ERROR, error rate ×20 (7/7 windows) |
| access permission denied | dbservice1/2 only | 15 / 20 | 1 h | **Yes**: `access redis service denied` + `service refuse` on db; **propagates** as `error in the downstream service` on webservice (×30) |
| memory anomaly (1 GB, 10 min) | all 10 | 652 / 715 | 10 min | **No** (122 windows: volume ratio p50 1.00, error ratio p50 1.04, no enriched template) |
| CPU anomaly | mostly db1, mob2 | 15 / 66 | ~3 s | no (too short); **excluded** |
| login failure (QR expired, mob delays 11 s) | mobservice1/2 | ~33k records | per request, all day (~27/h) | only as webservice `error in the downstream service` ~11 s after calling mob; **part of the normal background** |

- ~3.9M records/day across 10 services; one day streams in ~50 s (whole Aug ≈ 25 min). Multi-line CSV records.
- **Heavy normal ERROR noise:** ~4.5k ERROR/day per db/web instance, 66k WARNING/day per redis instance → per-service
  baselines are mandatory (H-2/H-5).
- **Fault type ↔ service is confounded** (file only on web, access only on db) → the engineer question is
  **system-wide** (no service named); localization is a separate answer.
- **Faults recur on a schedule** (e.g. file moving starts at hh:00, every few hours) → real material for the lead role.
- Faults overlap (a file-moving window inside an access-denied hour). July business logs exist only for webservice1.

**Honest consequence:** only **2 log-visible fault types** → the engineer "what" is easy once seen; the hard parts are
fault vs normal under noise, root vs symptom service, abstaining on memory windows, and generalization. For the lead,
GAIA has few distinct problems (truth = 4 (fault, service) problems + distractors); for the manager there is no
ground-truth priority (§3.3 uses a pre-registered proxy). BGL (003) adds class richness and calibration n.

### 3.2 Units and ground truth per role
**Engineer: 15-min system-wide windows** (~330 windows × 3 wordings ≈ 1,000 questions; exact counts from the split script)
- **fault**: contains a file-missing or permission-denied injection start; window start = injection start − U(0, 5) min
  (seeded jitter). Truth = (fault type, root-cause service).
- **no-trace**: contains a memory injection, no other injection ±30 min. Truth = "no fault visible in logs".
- **normal**: no injection (except per-request login background) ±30 min; sampled evenly by hour of day.
- Overlapping-fault windows: reported separately (multi-label, "any correct"), not in the primary metric.
- Label hygiene: drop injections followed by an `exception injection failed` record.

**Lead: incidents over a period** (built from engineer windows; truth from injection records)
- *Same problem?* pairs of windows (fault–fault same/different problem, fault–normal-noise, fault–memory). Problem =
  (fault type, service). Balanced sample, ~400 pairs dev-side. Truth = same (fault type, service).
- *New or repeat?* a fault window + the list of known problems from **earlier** days (from SQL, evidence-in-choices) →
  "repeat of problem k" or "new". Truth from injection records (first occurrence in the period = new).
- Numbers the lead sees (occurrences, mean gap, hour-of-day pattern, total affected minutes) are SQL only.

**Manager: problems over a week** (built from the lead's groups)
- Per problem, SQL computes: occurrences, total affected minutes, error lines, failed requests (distinct `trace_id`
  with an ERROR in the affected window), services touched. Tiny **service catalog** (§3.5) adds customer-facing / criticality.
- *Which first?* pairs of problems → Choice. **No ground-truth priority exists**, so truth = a **pre-registered impact
  rule** written before running: rank by failed requests × customer-facing weight (2 if customer-facing, else 1), ties by
  total affected minutes. We measure agreement with that transparent rule, order robustness and citation of numbers,
  not "correct priorities". Pairs sampled from weekly windows (multiple weeks, varied problem sets).

### 3.3 Questions (D6), per role
| Role | Dev wordings | Held-out-only wording |
|---|---|---|
| Engineer | "What went wrong in the system between {t1} and {t2}?" · "Was there an incident between {t1} and {t2}? If so, what caused it and where?" · "Users reported errors around {t}. What happened?" | "Something looked off between {t1} and {t2}: what's the root cause?" |
| Lead | "Is the incident at {t} the same problem as the one at {t'}?" · "Has the incident at {t} happened before this week?" · "What problems kept coming back in {period}?" | "Is {t} a repeat offender or something new?" |
| Manager | "Which of these problems should we fix first: {A} or {B}?" · "What should the team prioritise this week?" | "If we can fix only one thing this week, which one?" |

Code extracts time window / period / incident ids only; the question never gates evidence (PRODUCT.md).

### 3.4 Split (D4/D5), `scripts/make_split.py` (extended for GAIA)
- **Groups = whole days** (no window, pair or problem-week crosses sides). Lead pairs and manager weeks are built
  **within** a side. Seed 2026.
- **Amendment 1 (2026-10-11, before running):** held-out = **Aug 25–31 (the last week) + all of July** (webservice1 only);
  dev = Aug 1–24 (includes the forced Aug 1–10). Why: one chronological streaming pass can then fit Drain3 on dev days
  only and match held-out rows against it (no template leakage, honest novelty counts), and "train on past weeks, test on
  the next week" is how production sees data. Stratification becomes a check instead of an optimization: the script
  aborts if dev or the Aug held-out week lacks either fault type. Windows whose ±30 min context crosses a side or month
  boundary are dropped. Expected: ~43 dev fault windows vs ~45 held-out (≈13 Aug + ≈35 July).
- **Controlled novelty (counts reported):** time (unseen days, unseen month), telemetry (July = one service's logs),
  Pattern (templates unseen by dev Drain3), question (held-out-only wording per role). Fault types are not held out (only 2).
- **History never crosses into held-out:** in dev, "previous 24 h" = previous 24 dev hours.
- **Disclosure:** Claude has seen aggregate injection counts for both months, ~10 July injection rows (Jul 1–4, 13–14),
  no July business logs. Option: move July to dev, held-out becomes Aug-only.
- Prints aggregates only; held-out rows → `dataset/heldout/gaia/`, dev → `dataset/dev/gaia/`.

### 3.5 Ingest
- Stream once (`scripts/gaia_stream.sh`); masks + **Drain3 on unique masked strings**, fitted on dev only.
- Raw rows → OTLP → `otel_logs` for question windows: **all levels inside the 15-min window, WARN+ within ±30 min**
  (the pre-registered fallback, taken up front: windows ± 30 min at all levels would be ~65M rows). Fields:
  `service_name`, severity, `trace_id`, `log_attributes.pattern_id`.
- Whole month → minute rollup `(minute, service, severity, pattern_id, n)` + `(minute, service, n_error_traces)`
  (history for baselines, rarity, recurrence, impact numbers). Written per side by `make_split.py`; sum on load
  (a late row can repeat a key).
- Service catalog `service_catalog(service, tier, customer_facing, owner)`: 10 rows, written by hand from GAIA's
  architecture (web = customer-facing entry; mob/log/redis/db = internal), committed before running.

## 4. Pipeline under test (same bricks, role = scope + questions)
| Brick | Engineer | Lead | Manager | Tool |
|---|---|---|---|---|
| Pattern | templates in window | templates across period | — | Drain3 + SQL |
| Evidence | E-variants below (window vs own 24 h, cross-service) | incident fingerprints (top anomalous templates, service, ratios) + recurrence table | problem table: occurrences, minutes, failed requests, catalog flags | SQL |
| Verdict | engineer Qs | lead Qs | manager Qs | Jev `jev-1.13.0` / LLM form |
| Finding | answer card: fault + service + confidence + cited evidence | grouped problems + numbers | ranked list + numbers + confidence | Python |

**Evidence variants (engineer; lead/manager reuse the frozen one):**
| ID | Evidence | Tests |
|---|---|---|
| E0 | 001's A4 as is (corpus-relative rarity, global baseline) | reference |
| E1 | **per-service baseline + fixed history**: window rate vs same service's last 24 h (median/MAD → ratio, z); templates new in 24 h | H-2, H-5 |
| E2 | E1 + **cross-service view**: per-service error-ratio table + earliest service to depart from baseline | H-6, localization |
| E3 | E2 + raw WARN/ERROR sample (dedup by template, cap 60 lines) | H-4 recall |

**Evidence recall check (H-4):** per fault window, does the evidence contain the fault's signature template (the template
most enriched in fault windows of the **training folds**)? recall@K per E-variant, plus G1.

### 4.1 Jev question sets per role (each mirrored for the LLM as one JSON form, D11)
| Role | Base design | Variants (from 002-ideas) | What each Jev question is |
|---|---|---|---|
| **Engineer** | **Q0**: fault-type Choice (2 faults + "no fault visible") + key-evidence Choice E1…Ek/none | **Q1** add "can't tell from these logs"; **Q2** Noul "logs show a fault?" → type Choice; **Q7** root-cause service Choice over SQL candidates (+ "none"); **Q3** 8–12 symptom Nouls → class in code; **Q10** Q3 answers → per-fold LR; later Q4 per-evidence fan-out, Q8 ensembles, Q9 few-shot | atomic judgments on one window's evidence |
| **Lead** | **L0**: Noul "same underlying problem?" over two incident fingerprints | **L1** = Q6 broad taxonomy Choice per incident, group in code; **L2** new-vs-repeat Choice over known problems (evidence-in-choices) + "new"; Q8 ensembles if L0 is wording-sensitive | similarity / identity judgments; grouping and counting stay in SQL/code |
| **Manager** | **M0**: Choice "which to fix first?" over two problems with their SQL numbers | **M1** = Q5 Scores per problem (user impact, severity, urgency; ordered levels), rank in code; **M2** Noul "customer-facing impact?" + Score combined with SQL numbers by a fixed formula | judgment on top of SQL numbers; Jev never computes them |

Jev: structured criteria (definition / covers / does_not_cover); confidence computed from distributions (001 formula).
LLM: `gemini-3.8-flash`, thinking 0, temperature 0, same questions/options/evidence, self-reported confidence per question.
The explanation/recommendation LLM text stays out of scope (judgments are what we measure).

## 5. Baselines and ablations
**Baselines (D7), per role where meaningful:**
| | Engineer | Lead | Manager |
|---|---|---|---|
| B1 LLM, identical input | every variant | every variant | every variant |
| B2 LLM on raw logs (**wording 0 only**, amendment 2) | window WARN/ERROR + first/last 50 (≤120k chars) | both windows' raw WARN/ERROR | — (numbers must come from SQL) |
| B3 classifier | TF-IDF pattern counts per service + LR, per fold | cosine similarity of fingerprints, threshold per fold | — |
| B4 rules | keywords + "earliest new ERROR's service" | same top template + same service | the impact rule itself (it is the proxy truth; reported for reference) |

**Amendment 2 (2026-10-11, user, cost):** B2 runs on one wording per window/pair (wording 0) instead of all, ~⅔ cheaper
(B2 is ~half the LLM budget, est. total ≈ $55–65 LLM + ≈ $2 Jev before this cut). G1 compares on wording 0 for both sides.
Amendment 1 approved with it.

**Protocol:** dev = 5 grouped folds (whole days, stratified). Zero-shot variants scored per fold (mean ± SD); only B3,
Q9, Q10, thresholds and the recall signature train on other folds. **Freeze rule:** best average of both models; gain
< 1 fold-SD over the simpler variant → keep the simpler one. Knob sweeps (top-K 12/20, history 6/24 h, ratio cutoff)
reported as sensitivity.

**Run order (lean; each wave ends with docs + report update, rule 7):**
| Wave | Runs | Why this order |
|---|---|---|
| **1. Engineer evidence** | E0–E3 × Q0 × {Jev, LLM} + B2/B3/B4 | 001 failed on evidence; G1 gates everything; lead/manager reuse it |
| **2. Engineer questions** | Q1, Q2, Q7 on frozen E | each targets a measured GAIA problem: memory windows (R2/R3), fault vs normal under noise, root vs symptom (R1) |
| **3. Lead** | L0, L2 (+ L1) | needs frozen engineer incidents; cheap; tests the recurrence story |
| **4. Manager** | M0, M1 | needs lead groups; smallest truth signal, so last |
| 5. Only if room | Q3/Q10, Q4, Q8, Q9; L/M ensembles | transfer to BGL and calibration polish; higher cost or overfit risk |

## 6. Metrics
- **Engineer:** fault macro-F1 + accuracy, root-cause-service top-1, abstention on no-trace and false "no fault" on fault
  windows, evidence recall@K.
- **Lead:** pairwise precision/recall/F1 for same-problem, new-vs-repeat accuracy, grouping purity (problems found vs true).
- **Manager:** pairwise agreement with the impact rule, Kendall τ of the full ranking, order robustness, share of answers
  whose cited numbers match SQL.
- **All roles, both models:** Brier, ECE, reliability diagram, selective accuracy vs coverage (AURC), repeat / paraphrase /
  option-order consistency, latency p50/p95, $ / 1k questions, tokens. Results per fault type and per service (H-1).

## 7. Tracing
As 001: per question per brick, SQL + rows, evidence state, exact Jev request and exact LLM prompt, outputs, latency,
cost; role and variant tagged. Automatic fairness check (identical evidence + options per Jev/LLM pair). Trace viewer
extended with role + variant pickers. Runs in `runs/002/`.

## 8. Held-out protocol
- `make_split.py`: streams Jul/Aug, assigns days, writes per-side windows, lead pairs, manager weeks, questions and labels;
  prints aggregates (counts per role × fault × service × side, novelty counts). Reviewed by you before running.
- `eval_heldout.py`: ingests held-out into the `heldout` schema (port 4319), history = all preceding data, runs the frozen
  config per role on Jev **and** LLM + baselines (B3 trained on all dev), prints aggregates only. **Run once.**

## 9. Out of scope / risks
- Out: request-level questions (~17k login failures; later calibration set), metrics/traces, the LLM explanation text,
  `ai_system_one` parity, scheduled digests (the manager/lead questions are asked interactively here).
- Risk: few positives (~56 Aug + ~20 Jul) → wide CIs; read per slice. Risk: lead truth has only 4 problems; manager
  truth is a proxy rule (stated as such in every report). Risk: ingest speed on emulation (fallback §3.5). Risk: normal
  windows assume no unrecorded faults.
- Scope change: STATUS/CLAUDE.md say "engineer role only"; approving this plan adds lead/manager slices → logged as D13.

## 10. Steps (checklist)
- [x] Branch `exp/002-gaia-question-design` from `main`
- [x] Approve plan → log D13 (three-role scope) in `docs/DECISIONS.md`, update STATUS
- [ ] `make_split.py` GAIA mode (review with you) → run → aggregates in this plan
- [ ] Ingest dev: rollup + window rows + catalog; diagnosability table (confirms §3.1 on all dev days)
- [ ] Wave 1 (engineer evidence) → G1 gate → freeze E → docs + new report `reports/002-gaia.html`
- [ ] Wave 2 (engineer Qs) → freeze → docs/report
- [ ] Wave 3 (lead) → freeze → docs/report · Wave 4 (manager) → freeze → docs/report · (wave 5 only by plan amendment)
- [ ] Frozen configs per role + criteria check on dev → `eval_heldout.py` (review) → run once → docs/report

## 11. Results (filled after running)

### 11.0 Split (run 2026-10-11, `make_split.py --dataset gaia`, aggregates only)
| Side | Days | Windows (fault / no-trace / normal) | Engineer questions | Fault windows by (fault, service) | Lead pairs (pos) · repeat items (new) · manager weeks |
|---|---|---|---|---|---|
| dev | 23 (Aug 1–24) | 219 (35 / 69 / 115), 4 overlapping | 657 | file web1 10, web2 12 · permission db1 6, db2 7 | 220 (110) · 31 (6) · 4 |
| held-out | 37 (Jul 1–31 + Aug 25–31) | 233 (58 / 81 / 94), 13 overlapping | 932 | file web1 29, web2 7 · permission db1 10, db2 12 | 120 (60) · 45 (6) · 5 |

- Rows: dev 80.0M streamed, 8.86M kept (window rows + WARN+ ±30 min); held-out 31.3M streamed, 3.43M kept. 321 malformed.
- July file faults dropped (on webservice2, no logs): 21; windows dropped at a side boundary: 1.
- **Pattern novelty is low:** dev Drain3 has 59 templates; held-out adds 4, used by 2 of 1.13M held-out WARN+ rows. GAIA's
  log vocabulary is stable, so held-out novelty is mainly time, telemetry (July = webservice1 only) and wording.
- Held-out has more fault windows than dev (58 vs 35) because of July; dev CV folds hold ~7 fault windows each.

### 11.1 Dev results (2026-10-11, grouped 5-fold CV by day; `runs/002/dev_results.md`, `runs/002/wave*.json`)
Fairness: identical state + options for Jev and the LLM in 100% of pairs, every variant and role. Spend: Jev $0.32
(5,391 calls), LLM $18.32 (5,846 calls; ~$12 of it the raw-logs baseline).

**Wave 1, engineer evidence (Q0), macro-F1 (fold mean ± SD):**
| Evidence | Jev | LLM | Note |
|---|---|---|---|
| E0 001's A4 (corpus rarity, no baseline) | 0.34 ± 0.06 | 0.99 ± 0.02 | Jev reads routine ERROR lines as faults (no-fault on quiet windows 30%) |
| **E1 per-service 24 h baseline (frozen)** | 0.80 ± 0.05 | 0.96 ± 0.04 | Jev's remaining errors = false alarms on routine errors at ~2× usual |
| E2 + cross-service view | 0.81 ± 0.06 | 0.99 ± 0.02 | best mean, but within 1 fold-SD of E1 → lean rule keeps E1 |
| E3 + raw WARN/ERROR sample | 0.79 ± 0.06 | 0.98 ± 0.02 | |
| B2 LLM on raw logs (wording 0) | | 0.46 | flags routine errors; $57 / 1k questions |
| B3 classifier (5-fold by day) | 0.92 (fold 0.96 ± 0.09) | | |
| B4 keyword rules | 1.00 | | **not a fair generic baseline**: keywords chosen after the data look |
- G1 passes (LLM on E1 0.98 vs raw logs 0.46 on wording 0). Evidence recall@K = 1.00 for every variant (signature
  template always in the evidence).

**Wave 2, question designs on E1** (Jev / LLM macro-F1): Q0 0.80 / 0.97 · **Q1 abstain 0.87 / 0.98** · Q2 two-stage
0.79 / 0.95 · Q7 root service 0.80 / 0.99 with **root-service top-1 1.00 / 1.00**. Q1's gain (avg +0.037 F1, +0.03
Brier, +0.02 no-trace) is below the pre-registered keep rule (≥ 1 fold-SD ≈ 0.044, Brier ≥ 0.05, no-trace ≥ 0.10)
→ not kept. **Frozen engineer config: E1/Q7.**
- Frozen config consistency (Jev / LLM): repeat 1.00 / 0.99 · option order 1.00 / 1.00 · paraphrase 1.00 / 0.99.
- R3 "auto" threshold (tuned on 4 folds, applied to the 5th): selective accuracy 0.91 / 0.99 at coverage 1.00 / 1.00.
- Latency p50 228 ms vs 1,606 ms (7×); cost $0.06 vs $0.99 per 1k questions (17×).

**Wave 3, lead** (220 pairs, 110 same): L0 "same problem?" F1 1.00 / 1.00 (Brier 0.007 / 0.0002); L1 broad taxonomy
grouping 0.99 / 1.00; cosine baseline 1.00; same-top-pattern rule 0.94. L2 new-vs-repeat (30 items): 0.93 / 1.00.

**Wave 4, manager** (18 problem pairs, proxy truth = impact rule): M0 "fix first" agreement 0.94 / 0.83, order-robust
1.00 / 0.89; M1 impact Score ranking 0.83 / 0.72.

**Criteria on dev (directional; held-out decides):** R1 ✅ (LLM 0.99 + root 1.00; Jev 0.80 + root 1.00, at the edge)
· R2 ✅ both (no-fault on memory windows 0.87 / 0.99, false "no fault" on faults 0 / 0) · R3 ✅ both · R4 ✅ both ·
R5 Jev ✅, LLM ❌ (order robustness 0.89) · C1 engineer ❌ (Jev 0.80 vs LLM 0.99), lead ≈, manager Jev ahead ·
C2 engineer LLM better (Brier 0.13 vs 0.01) · C3 ✅ (7× faster, 17× cheaper) · C4: no fault design kept.

**Reading:** the 001 fixes worked for the evidence (per-service baselines took Jev from 0.34 to 0.80; the LLM was
already near-perfect). GAIA's faults are easy once the anomalous lines are shown. Where both see the same evidence,
the LLM separates "routine error at 2× its usual rate" from a fault much better than Jev, which reads any shown error
literally. Jev is fully consistent and wins on order robustness for the manager judgment. Q1 (an explicit "can't tell")
is Jev's best single lever (+0.06), but below the pre-registered bar.

### 11.2 Held-out results (run once, 2026-10-12; aggregates in `runs/002/test_results.json`)
932 questions (233 windows: Aug 25–31 + July, webservice1 logs only in July); frozen E1/Q7; identical input 100%.

| System | Macro-F1 [95% CI] | Fault recall | "No fault" on memory | False "no fault" on faults | Root service | Brier | p50 | $ / 1k |
|---|---|---|---|---|---|---|---|---|
| Jev E1/Q7 | **0.85** [0.74, 0.93] | 0.84 | 0.93 | 0.16 | 0.64 | 0.13 | 237 ms | $0.05 |
| LLM E1/Q7 (identical input) | **0.90** [0.81, 0.96] | 0.84 | 0.99 | 0.16 | 0.64 | 0.09 | 1,792 ms | $0.90 |
| LLM on raw logs (wording 0) | 0.38 [0.32, 0.45] | 0.87 | 0.31 | 0.13 | 0.60 | 1.05 | 2,485 ms | $23.55 |
| Classifier (trained on all dev) | 0.67 [0.58, 0.76] | 0.71 | 0.77 | 0.22 | — | 0.36 | ~0 | needs labels |
| Keyword rules (not a fair baseline) | 0.76 [0.62, 0.87] | 0.64 | 1.00 | 0.36 | 0.64 | 0.15 | 0 | 0 |

- By month (macro-F1): Jev Aug 0.83 / July 0.86; LLM Aug 0.98 / July 0.87; classifier Aug 1.00 / July 0.60; rules Aug 1.00 / July 0.61.
- Consistency: same answer across wordings Jev 1.00, LLM 0.98; held-out-only wording accuracy Jev 0.92, LLM 0.95.
- "Auto" at the dev-tuned threshold: Jev 0.92 selective accuracy at 99.8% coverage; LLM 0.95 at 100%.
- Lead (120 pairs): same-problem F1 Jev 0.85, LLM 0.87 (broad-taxonomy grouping 0.87 both, same-top-pattern rule 0.87);
  repeat-or-new (43) Jev 0.84, LLM 0.81.
- Manager (12 pairs): both 100% agreement with the impact rule and 100% order-robust; impact Score ranking 100% both.

**Criteria (held-out):** R1 fault F1 ✅ both, root service ❌ both (0.64 < 0.70: July's db faults have no db logs, so
the root service is invisible) · R2 memory ✅ both, false "no fault" ❌ both (0.16 > 0.10, same cause) · R3 ✅ both ·
R4 ✅ both · R5 ✅ both · R6 ✅ both (Jev +0.05 vs dev, LLM −0.07) · C1 ❌ by 0.002 (0.849 vs 0.901 − 0.05; CIs overlap)
· C2 LLM better (Brier 0.09 vs 0.13) · C3 ✅ (7.6× faster, 19.6× cheaper).

**Reading:** this time the dev conclusions held: the CV-chosen evidence generalized (Jev rose to 0.85, the LLM fell to
0.90, the gap narrowed from 0.17 to 0.05). Both models fail the same July cases: with only webservice1's logs, a db
permission fault looks like downstream errors at the web tier, so "where" is unknowable from the given logs. The raw-logs
LLM and the classifier collapse on July (new month, partial telemetry); the SereneDB evidence is what carries both
judgment models. The lead and manager slices are near-saturated on GAIA and cannot separate the methods.
**Experiment 002 is closed; held-out is not re-run (D14).**

### 11.3 Amendment 4 (2026-10-12, post-hoc, DEV ONLY, requested by the user): numbers vs words
Question: does Jev do better if the evidence has no raw counts, only the computed comparison in words? Variant **E1w** =
E1's selection with `lines` ("14 in this window (usually about 6)") removed and the window summary in words. Q0, both
models, all 657 dev questions, same folds (`experiments/002_gaia/ablation_words.py`, `runs/002/ablation_words.json`).
Held-out is not touched (D14); the frozen config does not change.

| | Jev macro-F1 | Jev Brier | LLM macro-F1 | LLM Brier |
|---|---|---|---|---|
| E1 (counts + phrase) | 0.804 | 0.134 | 0.969 | 0.024 |
| E1w (phrase only) | 0.804 | 0.147 | 0.969 | 0.030 |

- Jev gives the **same answer on every question** (582 right, 63 wrong in both); only its probabilities shift (Brier
  slightly worse). LLM: 4 questions flip one way, 5 the other.
- **Conclusion:** raw counts are not the cause of Jev's false alarms. The phrase "about 2x its usual rate" on a routine
  ERROR item is enough to trigger them.

**Follow-up analysis of the frozen E1/Q7 dev rows (no new calls):**
- 474 of 645 dev questions have **zero** evidence items after the E1 filter; all are truly "no fault" and Jev gets all
  right → a deterministic rule ("no unusual pattern → no fault visible") would skip ~73% of model calls at no accuracy cost.
- Of the 171 questions with ≥ 1 item: 93 real faults (Jev 93/93 right) and 78 quiet windows (Jev 15/78 right). A rule
  "any item → fault" is almost as good as Jev; the LLM rejects most of the 78. That is the whole engineer gap.
- Key evidence: Jev cites the top-ranked item in 135/156 fault answers; "cite the top item" is a deterministic stand-in,
  and the key-evidence "none" option duplicates the fault answer's "no fault visible".
- **Design idea for 003:** code decides "no items → no fault" and the citation; Jev gets one narrow per-item question
  ("real fault or routine behaviour?", Q4 in the ideas doc) aimed at exactly these noise cases, then the type Choice.
