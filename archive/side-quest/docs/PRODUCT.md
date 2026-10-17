# Product vision (agreed 2026-10-09) — keep us on this track

## Reading of the brief
- **question → evidence → recommendation**: question-driven core (interactive), not an alerting system.
- **Three roles** (engineer / team lead / manager) must all appear in the final demo. Engineer-only is fine for experiments.
- **One workflow**: same pipeline, different lens/depth per role.
- **SereneDB is the backbone**: showcase for SereneDB customers ("send your logs to SereneDB, get role-based insights"),
  not an internal SereneDB tool. Build generalized.
- AI **explains + recommends on top of evidence**; it never produces the evidence or the numbers.

## ⚠️ RELIABILITY IS THE CORE PRINCIPLE — NUMBERS, NOT VIBES
"Calculate reliable summaries" is the most important phrase in the brief. Rules:
1. **Every number shown comes from SQL in SereneDB** (counts, rates, durations, time spans, recurrence). The LLM never
   computes or invents a number; it can only quote numbers handed to it, and every quoted number is traceable to its query.
2. **Every confidence shown is a computed quantity**, not self-reported. Jev's `confidence`/probabilities are derived from
   its output distribution (documented formulas) and *calibrated* → usable. An LLM saying "I'm 90% sure" is essentially
   hallucinated → we do not display LLM self-reported confidence.
3. **Every claim cites evidence IDs** (log rows / templates / query results). Uncited claims are rejected (Jev citation-check pattern).
4. **"I don't know" is a feature**: low confidence → say so / route to human, never guess.
5. **We benchmark reliability, not only accuracy.** Every approach (Jev, LLM, classifier, rules) is measured on:
   - accuracy / F1 / top-k vs ground truth
   - **calibration**: Brier score, ECE, reliability diagram (does 0.8 confidence mean 80% correct?)
   - **selective accuracy**: accuracy vs coverage when abstaining below a confidence threshold
   - **self-consistency**: same input N times → same answer?
   - **option-order robustness** (Jev leans to first option), prompt-paraphrase robustness
   - latency, $ per 1k questions / per 1M log lines
   - **groundedness**: % of LLM explanation claims/numbers that match SQL/evidence

## ⚖️ FAIRNESS RULE (agreed 2026-10-11, D11)
Our goal is a fair comparison, not to make Jev win. Every change (evidence, prompts, class options, shuffles) is applied
to Jev and the LLM baseline alike; both receive identical evidence; both models' exact inputs are traced and checked;
variants are chosen by the average score of both models. If a technique helps only one model, we report that.

## Product shape
- **Interactive Q&A** is primary (engineer investigates). **Scheduled digests** (lead: weekly recurring issues;
  manager: priority report) = same pipeline + canned question on a cron. No real paging/alerting system.
- **Inputs**: (1) logs in SereneDB in OTel shape (`otel_logs`; OTLP native ingest → zero custom parsing = generalization);
  (2) optional tiny service catalog (service → team, criticality, customer-facing) — required for lead/manager answers;
  (3) a natural-language question (+ role, can be inferred by Jev).
- **Output = answer card**, never a raw row dump:
  ```
  ANSWER (1–2 sentences) + computed confidence badge (auto / needs review / don't know)
  KEY NUMBERS   ← SQL, each clickable to its query
  EVIDENCE      ← 3–5 items: template × count × time span + 1 real example line
  RECOMMENDATION← LLM, must cite evidence IDs
  DRILL-DOWN    ← raw rows + SQL
  ```
  Depth per role: engineer = raw lines / stack traces / exact times; lead = patterns / recurrence / trend;
  manager = impact / priority / effort.
- **Demo narrative**: one incident walked through all three roles in ~90 s.

## Pipeline
```
OTLP/CSV ─► SereneDB otel_logs
             └─ on insert: log template + Jev triage generated column (is_error, category, user_impact)
question ─► Jev intent/role Choice + code extracts time window
         ─► SereneDB role-specific SQL evidence library (counts, rates, spikes, significant terms, BM25)
         ─► Jev selects/ranks evidence (evidence-in-choices) + confidence gate
         ─► LLM explains + recommends with evidence-ID citations
         ─► answer card (UI / Slack digest)
```

## Why Jev (pitch)
Zero-shot on any company's logs (no per-customer labeled training like a classifier) + **calculated, calibrated
confidence** (vs LLM's hallucinated certainty) + cheap enough to run on every log template.

## Risks to watch
1. Evaluation data that's metric-heavy (OpenRCA) can pull the product away from logs → keep demo **logs-first**.
2. Lead/manager need multi-week data + catalog overlay (OpenRCA lacks it).
3. Jev is our edge, not the deliverable — judges score the end-to-end product.
4. 48 h: one polished workflow > three half-built ones.

## Generalization principle (agreed 2026-10-09)
- **Deterministic = generic only.** Keep: generic masking (numbers, hex ids, UUIDs, IPs, paths, emails) → template mining
  (Drain-style or MinHash, learned from data); all numbers (counts, rates, ordering, first-seen, spikes) in SQL; OTel
  standard fields (severity_number). Drop: dataset-specific regexes and domain keyword rules — meaning is Jev's job.
- **The question never gates evidence.** Question → scope (time window, service) only. Evidence = what's anomalous in scope
  (error-rate spikes, new templates, significant terms, earliest error in chain), independent of query wording. Question text
  only *ranks* evidence (hybrid vector+BM25, then Jev relevance). Zero keyword matches must still produce evidence.
- **Nothing qualifies → say so** (Jev `none` option / low confidence → "logs in this window don't show the cause").

## Lean architecture rule (agreed 2026-10-09)
**A component stays only if an ablation shows it improves accuracy or calibration enough to justify its latency/cost/complexity.**
Experiments start minimal (index filters → templates → one Jev Choice with evidence-in-choices + `none`) and add one component
at a time (significant terms, hybrid/vector, shuffles, structured criteria, trace chain, metrics) → ablation table:
Δaccuracy, ΔECE/Brier, Δlatency, Δ$. No measured gain → cut.

Default performance choices (revisit only with measurements):
- `otel_logs`: keep the built-in inverted index unchanged (timestamp, body, severity_text, severity_number, service_name,
  event_name, trace_id; body dict = frequency+position+norm, no offset). Covers all hot filters. No extra/expression indexes.
- Templates table: inverted index on `template` with frequency+norm only (add position only if phrase queries earn it).
- Embeddings: no IVF/HNSW initially — exact cosine scan over a few thousand templates is ms-fast with perfect recall; and
  embeddings only if hybrid beats BM25+Jev-rerank in ablation.
- Jev: judge templates/candidates, never raw rows; one request per question; only decision-driving questions; shuffle re-ask
  only when confidence is low; structured criteria only where ambiguity measured; numbers/time computed in SQL, passed as words.

## Core data model: the "Lego bricks" (agreed 2026-10-09)
**Template / Pattern** = a log line with its variable parts masked (the source-code print statement that produced it), e.g.
`payment failed for order <*>: upstream timeout`. Gives compression (millions of rows → hundreds), identity (count, recurrence,
"new" detection) and cost control (Jev judges a pattern once).

Four bricks, each a SereneDB table, each built from the previous one; every layer is `SELECT`-able in the demo:
```
LogLine (otel_logs) → PATTERN → EVIDENCE → VERDICT → FINDING
```
| Brick | Meaning | Key fields | Made by | Trust source |
|---|---|---|---|---|
| Pattern | one kind of event | pattern_id, text, services, severity, count, first_seen, last_seen, example_line_ids | SQL + template mining | deterministic |
| Evidence | one reproducible fact in a scope | evidence_id, kind (spike/new_pattern/unusual_term/first_error/trace_chain/recurrence), subject, value, window, **sql** | SQL only | re-runnable query stored with it |
| Verdict | one typed judgment | verdict_id, question, answer, probabilities, confidence, model_version, evidence_ids | Jev | calibrated probability |
| Finding | answer to a person's question | finding_id, question, role, scope, answer, confidence_badge, evidence_ids, verdict_ids, recommendation | code + LLM (prose only) | every claim cites bricks |

- Drill-down in the UI: sentence → Verdict (probabilities) → Evidence (SQL) → Pattern → raw lines.
- Roles reuse the same bricks: engineer = one Finding drilled to raw lines; lead = Patterns over weeks (recurrence Evidence);
  manager = Findings ranked by impact Verdicts with role-specific weights.
- Bricks are cached and reused (a Pattern is judged once). Each brick = one stage of the ablation table.
- Pitch: "Every answer is assembled from Patterns, Evidence and Verdicts. Click any claim down to the raw log line and the SQL."
