# pipeline/: question → evidence → verdict → finding

Full explanation, glossary and references: `docs/PIPELINE.md`.

Plain Python, one small file per concern. Read top to bottom in this order:

| File | Role |
|---|---|
| `config.py` | **every number** (`[KNOB]` = calibration knob): Drain3 settings, severity cutoff, top-K, confidence threshold, model pins, prices |
| `prompts.py` | **every Jev question + LLM prompt**, class definitions (structured vs plain), shuffles |
| `queries.py` | **every SereneDB query** (`{s}` = schema) |
| `hadoop.py` | parse raw logs → records (stack traces glued to their line) |
| `patterns.py` | Pattern brick: Drain3 + generic masks (`[KNOB]` MASKS) |
| `ingest.py` | records → OTLP JSON → SereneDB `otel_logs` (pattern id in `log_attributes.pattern_id`) |
| `bricks.py` | the 4 bricks: `pattern_brick` (SQL) → `evidence_brick` (rank + numbers→words) → `verdict_brick` (ONE Jev request) → `finding_brick` (badge) |
| `chain.py` | LangChain wiring; each brick = one traced step |
| `trace.py` | callback that writes each step's input/output/latency to `<schema>.traces` |
| `baselines.py` | B1 LLM same evidence · B2 LLM raw logs · B3 TF-IDF+LR · B4 keyword rules |
| `metrics.py` | accuracy, macro-F1 (+bootstrap CI), Brier, ECE, selective accuracy, latency, cost |
| `cache.py` / `models.py` / `db.py` | disk cache of model calls · Jev + Gemini wrappers · psycopg helpers |

## Calibration knobs, by brick
| Brick | Knob | Where |
|---|---|---|
| Pattern | Drain3 `sim_th`, `depth`; generic masks | `config.py`, `patterns.py` |
| Evidence | evidence mode (`basic`/`full`/`rarity`=A4), severity cutoff, rare threshold, top-K, example line length, ranking order, wording of timing/rarity/duration buckets | `config.py`, `bricks.evidence_brick`, `_timing_words`, `_rarity_words`, `_duration_words` |
| Verdict | question instructions, class definitions (plain/structured), key-evidence question, # shuffles | `prompts.py`, `config.VARIANT` |
| Finding | auto/needs-review threshold (tuned on dev, frozen before held-out) | `config.AUTO_THRESHOLD` |

## GAIA modules (experiment 002)
| File | Role |
|---|---|
| `gaia.py` | parse GAIA injection records + business-log rows, stream the split zip, OTLP payload |
| `gaia_queries.py` | every GAIA SQL query: window vs the same service's last 24 h, per-service error table, spikes, failed requests |
| `gaia_bricks.py` | evidence variants E0–E3, numbers → words, exact state, `ask()` for Jev and the LLM mirror, findings |
| `gaia_prompts.py` | every Jev question per role (engineer, lead, manager) + the LLM form built from them |

How they fit together: `experiments/002_gaia/README.md`.

## Debugging one example
1. `.venv/bin/streamlit run apps/trace_viewer.py` → pick run + example → see each brick's exact input/output,
   the SQL used, Jev's full request (state + questions) and probabilities, baselines side by side.
2. Re-run one example in a REPL: build `bricks.Ctx(...)`, then `chain.run(chain.build(ctx), x, ctx, "debug")`
   (see the smoke test in `experiments/001_hadoop/run_dev.py`).
3. Model responses are cached in `runs/<exp>/cache/`; delete it to re-ask the models live.
