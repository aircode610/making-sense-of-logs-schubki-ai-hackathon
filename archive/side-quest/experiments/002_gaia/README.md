# Experiment 002 implementation: GAIA, three roles, one pipeline

Plan: `plans/002-gaia-question-design.md` (approved, amendments 1–2). Results: plan §11, `docs/PIPELINE.md` §11.6–11.7,
report `reports/002-gaia.html`. This file explains **how the code works**, in the order data flows through it.

## 1. Data flow at a glance
```
GAIA run/ injection records ──► make_split.py: windows, questions, lead pairs, manager weeks (per side, by day)
GAIA business logs (streamed) ─► make_split.py: Drain3 templates (dev only) ─► rows.jsonl.gz + rollup.csv.gz
                                                                           │
            run_dev.py ingest ─► SereneDB: otel_logs (raw window rows, OTLP)  gaia_rollup / gaia_error_traces (read_csv)
                                                                           │
question ─► window (t1, t2) ─► SQL facts (gaia_queries) ─► evidence E0–E3 (gaia_bricks) ─► state
          ─► questions per role (gaia_prompts) ─► Jev system_one  │  LLM: identical JSON form
          ─► finding: label + probabilities + computed confidence + citation ─► metrics (core.score, CV by day)
```

## 2. Files
| File | Role |
|---|---|
| `pipeline/gaia.py` | GAIA parsing: injection records → `{service, kind, start, end}`; business-log row → `{ts, service, severity, trace_id, body}`; streaming via `scripts/gaia_stream.sh`; OTLP payload (request id → `traceId`) |
| `scripts/make_split.py --dataset gaia` | Sanctioned. Builds windows from injection records only, assigns whole days to dev/held-out, one chronological pass over the logs (Drain3 learns on dev days only), writes per-side files, prints aggregates |
| `pipeline/gaia_queries.py` | **Every number**: window vs last-24 h per (service, severity, pattern); per-service error table + first spike minute; examples; raw lines; corpus rarity (E0); extra failed requests (manager) |
| `pipeline/gaia_bricks.py` | Numbers → words, evidence variants E0–E3, the exact `state`, Q7 candidates, incident fingerprints, `ask()` for both models, LLM answer normalization, engineer finding |
| `pipeline/gaia_prompts.py` | **Every Jev question** per role (engineer Q0/Q1/Q2/Q7, broad taxonomy, lead L0/L2, manager M0/M1) and the LLM mirror form built from the Jev questions |
| `experiments/002_gaia/core.py` | Shared by dev and held-out: ingest, tracing, engineer/lead/manager runners, baselines B2–B4, folds by day, metrics, fairness check |
| `experiments/002_gaia/run_dev.py` | `ingest`, `wave1`…`wave4`, `report` (writes `runs/002/wave*.json`, `dev_results.md`) |
| `scripts/eval_heldout.py --dataset gaia` | Sanctioned. Same code on schema `heldout`, frozen config read from `runs/002/wave1.json` + `wave2.json`, run once, aggregates only |
| `experiments/002_gaia/demo_cases.py` | Exports recorded dev cases (exact requests + answers) for the demo presentation |
| `apps/trace_viewer_002.py` | Streamlit: one question, Jev and LLM inputs/outputs side by side, fairness check |

## 3. Units and labels
- **Question window** = 15 minutes of the whole system. Fault windows start 0–5 min (seeded) before an injection;
  memory ("no-trace") windows contain a memory injection; normal windows contain no injection ±30 min.
- Label = fault type (`file_missing`, `permission_denied`, `none`) + root-cause service. Memory windows are `none`
  (they leave no trace in the logs; checked on 122 windows).
- Lead: pairs of windows (same problem = same fault type + same service) and "repeat or new" items (last 7 days).
  Manager: weeks with ≥ 2 problems; truth = pre-registered impact rule (extra failed requests × 2 if customer-facing).

## 4. SereneDB tables (schema `public` = dev, `heldout` = held-out)
| Table | Filled by | Used for |
|---|---|---|
| `otel_logs` | OTLP `/v1/logs` (all levels inside each window, WARN+ ±30 min) | example lines, raw lines (E3, B2) |
| `gaia_rollup(minute, service, severity_text, pattern_id, n)` | `read_csv` of `rollup.csv.gz` (whole period) | 24 h baselines, rarity, spikes |
| `gaia_error_traces(minute, service, n_error_traces)` | `read_csv` | failed requests (manager) |
| `gaia_windows`, `gaia_catalog` | runner | E0 corpus rarity; customer-facing flag |
| `traces` | every model call | trace viewer, demo export |

## 5. Evidence variants (the main lever)
| ID | What the state contains | Result (dev macro-F1 Jev / LLM) |
|---|---|---|
| E0 | 001's A4: every WARN+ or corpus-rare pattern, "seen in k of N windows" | 0.34 / 0.99 |
| **E1** | only patterns **new in 24 h** or **≥ 2× their usual rate** (≥ 3 lines), each with "N in this window (usually about M)", "change", "first seen", example line | **0.80 / 0.97 (frozen)** |
| E2 | E1 + per-service table (lines, error lines vs usual, spike) + earliest spiking service | 0.81 / 0.99 |
| E3 | E2 + up to 60 raw WARN/ERROR lines (dedup by service + pattern) | 0.80 / 0.99 |

## 6. Jev techniques used (and how each is mirrored for the LLM)
| Technique | Where | Mirror |
|---|---|---|
| Numbers turned into words by SQL + code (Jev never computes) | `gaia_bricks.change_words`, `when_words` | same state |
| Structured criteria: definition / covers / does_not_cover per option | `gaia_prompts.FAULT_DEFINITIONS` | same definitions in the form |
| Fan-out: several questions in one request | every design | one JSON form with all questions |
| Evidence-in-choices: options are evidence ids / services described by SQL | `key_evidence`, `root_service` (Q7) | same options |
| Abstain option | Q1 "cannot tell from these logs" | same option |
| Two-stage Noul → Choice, combined in code | Q2 | yes/no + confidence |
| Noul for identity judgments | lead L0 | yes/no |
| Score with ordered levels, ranking in code | manager M1 | ordered levels |
| Option-order robustness | `gaia_prompts.shuffled`, manager both orders | same shuffled order |
| Computed confidence `(p_max − 1/n)/(1 − 1/n)` | `gaia_bricks.choice_confidence` | applied to the LLM's distribution too |

## 7. Re-running
```
.venv/bin/python experiments/002_gaia/run_dev.py ingest      # once per SereneDB start (data), ~2 min
.venv/bin/python experiments/002_gaia/run_dev.py wave1       # cached calls are free; delete runs/002/cache to re-ask
.venv/bin/streamlit run apps/trace_viewer_002.py
```
Keys: `eval "$(grep -E '^export (TYPESAFE_API_KEY|GOOGLE_API_KEY)=' ~/.zshrc)"` first.
