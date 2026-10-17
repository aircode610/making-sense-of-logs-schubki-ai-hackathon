# Lessons from the side quest (experiments 001 Hadoop, 002 GAIA) — what to reuse, what to avoid

Full record: `archive/side-quest/` (plans, PIPELINE.md with results §11, reports, code). Product vision we agreed on
then: `archive/side-quest/docs/PRODUCT.md` (answer card, 4 bricks Pattern → Evidence → Verdict → Finding).

## Measured facts
- **Jev vs LLM on identical evidence:** 001 held-out macro-F1 Jev 0.32 vs LLM 0.42; 002 held-out Jev 0.85 vs LLM 0.90.
  Jev is **not** more accurate. It is **7–8× faster** (p50 ~0.24 s vs ~1.8 s), **17–20× cheaper**, more consistent across
  wordings (100% in 002) and more robust to option order (manager judgment 1.00 vs 0.89 on dev).
- **The evidence step is the biggest lever for every model.** 002: per-service 24 h baselines took Jev 0.34 → 0.80.
  An LLM on raw logs collapsed on new data (002 held-out 0.38, $23.55/1k vs $0.90 with our evidence).
- Dev-tuned evidence overfit in 001; CV-frozen evidence generalized in 002.
- **73% of questions need no model** (no unusual pattern → no fault). Code should decide those.
- Jev's failure mode: it reads a shown error literally and calls routine noise a fault (~2× usual rate = "fault"); the
  LLM rejects most of that noise. Fix idea: one narrow per-item question ("real fault or routine behaviour?").
- Removing raw counts (words only) changed no Jev answer → counts weren't the issue.
- No confidence threshold gave ≥ 90% "auto" accuracy in 001 (label/evidence limits); 002 Jev 0.91 @ 100% coverage.

## Rules we keep
- Numbers from SQL only; computed confidence only; every claim cites evidence; "don't know" is a feature.
- Templates/patterns first (Drain3 + generic masks), judge patterns not lines, dedupe before any model call.
- Jev: one snap judgment per question, fan out questions in one request, minimal state, `none` option, shuffle-check
  options, numbers/time in code. Read `docs/jev/NOTES.md` before writing any Jev question.
- Lean rule: a component stays only if it measurably helps.

## Reusable code (archive, copy what's useful, don't import)
- `archive/side-quest/pipeline/patterns.py` (Drain3 + masks), `db.py` (psycopg helpers), `models.py` (Jev + Gemini calls,
  cost/latency), `trace.py`, `metrics.py` (Brier/ECE/F1), `cache.py` (model-call cache).
- `archive/side-quest/apps/trace_viewer*.py` (Streamlit patterns). `tutorial/jev_capabilities.py` (verified Jev/SereneDB calls).
