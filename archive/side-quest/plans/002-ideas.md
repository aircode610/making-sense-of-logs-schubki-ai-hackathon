# 002: ideas and lessons (input for the next plan, NOT an approved plan)

- **Status:** ideas. Turn into `plans/002-<name>.md` from `TEMPLATE.md` and get approval before any work.
- **Inputs:** experiment 001 results (`docs/PIPELINE.md` §11, `reports/001-hadoop.html`), decisions D1–D12.
- **Date:** 2026-10-11

---

## Part A: why held-out went badly in 001, and how 002 tests each reason

Held-out macro-F1: Jev 0.32, LLM with identical input 0.42, LLM on raw logs 0.54, classifier trained on dev 0.66
(dev: Jev 0.51, LLM 0.49). These are **hypotheses**: Claude never inspected held-out data, so each is backed only by dev
facts, split metadata and aggregate results. Ordered by how likely and how big each one is.

| # | Hypothesis | Evidence we have | How to test / fix in 002 |
|---|---|---|---|
| H-1 | **Domain shift from the split design.** Dev was 71% WordCount (25/35 jobs); held-out was 100% PageRank. In dev, network and disk faults existed only on WordCount jobs. | Split metadata (plan 001 §3); dev app mix (checked 2026-10-11) | Stratify the split so each side has a similar mix of job types / services, and add novelty in a controlled dimension. Report results **per job type**. |
| H-2 | **Duration baseline ignored the job type.** A4 compares each job to the corpus-wide median ("shorter than a typical job"). PageRank jobs are much shorter (normal: 4.9 min vs WordCount 13.1), so a failing PageRank job can look "shorter than typical", which reads like "normal". | Dev durations by app type | Compare a job with **jobs of the same type/service** (generic: group by `service_name` or a job-type attribute). Ablate "no duration" vs "global" vs "per-type" baselines. |
| H-3 | **Evidence settings overfit to dev.** A4's rarity cutoff (25%), top-12, ranking order and word buckets were chosen from one dev score; nothing was cross-validated. | Dev → held-out drop for both Jev (0.51 → 0.32) and the LLM with the same evidence (0.49 → 0.42) | Choose evidence settings by **grouped cross-validation** on dev (folds = runs/incidents), plus small sensitivity sweeps of each knob. |
| H-4 | **Evidence selection drops useful information.** On held-out the LLM did better on raw logs (0.54) than on our selected evidence (0.42). | Held-out aggregates | Measure **evidence recall**: run the LLM on (a) selected evidence, (b) raw logs, (c) evidence + raw WARN/ERROR lines, under the same CV. Selection must not lose to raw logs. Consider more items (top-K), per-service summaries, and the cross-job evidence in H-6. |
| H-5 | **Rarity is relative to the corpus it's computed in.** In held-out, rarity used 55 jobs (dev + held-out) instead of 35, shifting what counts as "rare" and "common". | Design of the eval script | Make rarity relative to a **fixed history window** (e.g. all jobs before this one, or the previous N hours), the way a production system would see it. |
| H-6 | **One job's logs miss the cluster-level picture.** A dead or disconnected machine affects every job using it; evidence only looked inside the asked job. | Dev diagnosis (machine down vs network confusion, 21/60) | **Cross-job, time-window evidence** in SQL: what other jobs/services logged on the same hosts in the same minutes ("3 other jobs lost containers on node X at 14:05"). |
| H-7 | **Failure labels with no trace in the job's logs.** 5 dev jobs labelled as failures look normal; both models confidently say "normal". | H4 analysis (amendment 3) | GAIA labels name the affected service and time window, so scope can follow the label. Add an explicit **"not visible in these logs"** answer (Part B). |
| H-8 | **Literal reading of noisy rare lines.** "lack of space for maps" (scheduler slots) → "disk full". | Walkthrough example | Per-evidence-item judgments (Part B, B-2) so one misleading line can be outvoted; class definitions that state what a class does **not** cover (with examples). |
| H-9 | **Classifier advantage may include leakage.** Cluster run 1445182159119 was split by job type across dev and held-out; shared run-specific templates can help a trained model. | Split design | Split by **whole runs / incidents / time windows**, never inside a run. |
| H-10 | **Small n.** 20 held-out jobs; all intervals overlap. | CIs in §11.5 | GAIA: hundreds of incidents. Report bootstrap CIs for every comparison. |

**Process lessons (D12):** never freeze on a single dev score; always keep the raw-logs LLM and the classifier as
references; stratify splits; one held-out run per experiment, as in 001.

---

## Part B: exploring Jev's question design (the main new direction)

**Today (001):** one request, 2 fixed questions:
`root_cause` = Choice over 4 fixed classes, and `key_evidence` = Choice over E1…Ek + none.
That uses a small part of what Jev offers. Its docs recommend **many narrow, atomic questions in one request,
combined in code**, and fan-out is nearly free (11 questions cost +30 ms in our tutorial test).

### Question-design families to try (each is a variant `Q*`, mirrored for the LLM, D11)
| ID | Design | What it asks | Why it might help |
|---|---|---|---|
| **Q0** | Baseline (001) | root_cause Choice (4) + key_evidence Choice | reference |
| **Q1** | **Abstain option** | add "the logs show no sign of the fault / can't tell" to the Choice | H-7: lets the model say "not visible" instead of a confident "normal"; directly targets H4 |
| **Q2** | **Two-stage: fault or not?** | Noul "Do the logs show an infrastructure fault?", then Choice among fault types (same request, used conditionally in code) | Separates "is something wrong" from "what"; "normal vs fault" was the biggest error |
| **Q3** | **Symptom Nouls** (decomposition) | ~8–12 observable yes/no questions: "a host stopped responding", "tasks were killed or re-run elsewhere", "connections timed out or were refused", "writes failed for lack of disk space", "a job ran much longer than its peers", … | Jev is strongest on atomic judgments; code (or a tiny model) maps symptoms → class. Symptoms transfer across datasets better than class labels |
| **Q4** | **Per-evidence-item judgments** | for each E_i (fan-out): "Is this item a sign of a failure?" + Choice "which fault does it point to?" | One misleading line (H-8) no longer decides; aggregate in code (vote / max / weighted by rarity) |
| **Q5** | **Score questions** | Score per dimension: severity, customer impact, "how strongly does the evidence point to a host problem / network / disk" (ordered levels) | Graded strength instead of a forced choice; feeds composite scoring and confidence |
| **Q6** | **Broader, generic fault taxonomy** | Choice over a richer, dataset-independent taxonomy (host crash, network partition, disk full, memory pressure, config error, application bug, dependency failure, permission denied, none, can't tell) mapped to dataset labels in code | Generalization: the same questions work on Hadoop, GAIA (memory, login, file missing, permission) and BGL |
| **Q7** | **Entity localization (evidence-in-choices for entities)** | SQL lists candidate hosts/services/containers; Choice "which one is the root cause?" | GAIA needs *where*, not only *what*; the candidates come from data, not a fixed list |
| **Q8** | **Instruction ensembles** | the same judgment asked with 2–3 differently worded instructions (and option orders) in one request; average probabilities | Smooths wording sensitivity; may improve calibration (H4) at almost no latency cost |
| **Q9** | **Few-shot criteria** | add 1–2 examples per option inside the structured criteria (from training folds only) | Sharpened probabilities in the tutorial (+0.35 separation); must be checked under grouped CV to avoid overfitting |
| **Q10** | **Jev answers as features** | all Q3–Q5 answers → a small logistic-regression model trained per fold | Hybrid of zero-shot judgments + a little supervision; compare to the pure classifier |

### Fairness for question designs (D11)
For each Q-variant the LLM gets the **same questions**, as one JSON form to fill in (same wording, same options, same
evidence), so we compare the models on the same task. Where a design only fits Jev's interface (e.g. per-item fan-out
of 100 questions), the LLM gets the equivalent form in one call, and we report the cost/latency difference.

### How to evaluate
- Grouped cross-validation on dev (folds = incidents/runs), every Q-variant on both models.
- Metrics as in 001, plus **per-symptom accuracy** where labels allow, and **abstention quality** (does "can't tell"
  fire on the no-trace cases?).
- Lean rule: keep a question only if it moves macro-F1, Brier/ECE, or abstention quality.
- Track tokens and latency per variant (more questions = more input tokens, roughly the same latency).

---

## Part C: proposed shape of experiment 002
1. **Dataset:** GAIA MicroSS (main). Stream with `scripts/gaia_stream.sh`; ingest a set of injected-fault windows +
   normal windows. Ground truth from the `run/` injection records: service, fault type, start, duration.
2. **Questions:** "What went wrong in the system between T1 and T2?" / "Why did <service> fail around T?" + paraphrases.
3. **Split:** stratified by fault type and service, grouped by time window (no window on both sides); held-out with
   controlled novelty (e.g. one fault type on a service it never hit in dev).
4. **Evidence fixes:** per-service baselines (H-2), fixed history window for rarity (H-5), cross-service / time-window
   evidence (H-6), evidence-recall check vs raw logs (H-4).
5. **Ablation families:** evidence variants (E*) × question designs (Q*), each mirrored for the LLM; grouped CV; then
   freeze, then one held-out run.
6. **Baselines:** LLM on identical input, LLM on raw logs, classifier, rules (as in 001).
