"""Experiment 001 on the DEV split only (plans/001-hadoop-minimal.md).

    .venv/bin/python experiments/001_hadoop/run_dev.py ingest      # parse -> Drain3 -> OTLP into SereneDB
    .venv/bin/python experiments/001_hadoop/run_dev.py run         # ablations A0-A3 + baselines B1-B4 + metrics

Outputs: runs/001/ (drain state, templates, dev_results.md/json); traces in public.traces (see apps/trace_viewer.py).
"""
import json
import statistics
import sys
import threading
import time
from collections import defaultdict
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pipeline import baselines, bricks, chain, config, db, hadoop, ingest, metrics, patterns, trace  # noqa: E402

OUT = ROOT / "runs" / "001"
CACHE = OUT / "cache"
SCHEMA = config.DEV_SCHEMA
VARIANTS = {  # ablations, one component at a time (lean rule)
    "A0_basic_evidence_plain_labels": {"evidence": "basic", "criteria": "plain", "shuffles": 0},
    "A1_full_evidence_plain_labels": {"evidence": "full", "criteria": "plain", "shuffles": 0},
    "A2_full_evidence_structured": {"evidence": "full", "criteria": "structured", "shuffles": 0},
    "A3_structured_plus_3_shuffles": {"evidence": "full", "criteria": "structured", "shuffles": 3},
    "A4_rarity_evidence_structured": {"evidence": "rarity", "criteria": "structured", "shuffles": 0},  # amendment 1
}
WORKERS = 8


def ingest_dev():
    jobs = sorted((config.DEV_DIR / "jobs").iterdir())
    miner = patterns.new_miner()
    records = []
    for job in jobs:
        recs = hadoop.parse_job(job)
        patterns.assign(miner, recs)
        records += recs
    patterns.save(miner, OUT / "drain_dev.json")
    patterns.dump_templates(miner, OUT / "templates_dev.json")
    with db.connect() as conn:
        conn.execute(f"DELETE FROM {SCHEMA}.otel_logs WHERE service_name = %s", (config.SERVICE_NAME,))
        t0 = time.time()
        ingest.send(records, config.DEV_OTLP_URL)
        conn.execute(f"VACUUM (REFRESH_TABLE) {SCHEMA}.otel_logs")
        n = conn.execute(f"SELECT count(*) AS n FROM {SCHEMA}.otel_logs WHERE service_name = %s",
                         (config.SERVICE_NAME,)).fetchone()["n"]
    print(f"ingested {n} records from {len(jobs)} dev jobs in {time.time() - t0:.1f}s; "
          f"{len(patterns.templates(miner))} Drain3 templates")


def load_questions() -> list[dict]:
    return [json.loads(l) for l in (config.DEV_DIR / "questions.jsonl").read_text().splitlines()]


_local = threading.local()
FROZEN = ["A2_full_evidence_structured"]   # set to the best variant before baselines run


def _ctx(variant: dict) -> bricks.Ctx:
    """One DB connection per thread (psycopg connections are not shared across threads)."""
    if not hasattr(_local, "conn"):
        _local.conn = db.connect()
    ctx = bricks.Ctx(conn=_local.conn, schema=SCHEMA, templates=TEMPLATES, cache_dir=CACHE, variant=variant)
    ctx.pattern_jobs, ctx.total_jobs, ctx.typical_duration_s = STATS
    return ctx


def run_pipeline(examples, variant, run_id):
    def one(x):
        ctx = _ctx(variant)
        return chain.run(chain.build(ctx), dict(x), ctx, run_id)
    with ThreadPoolExecutor(WORKERS) as ex:
        return list(ex.map(one, examples))


def run_baseline(results, fn, name, run_id, variant=None):
    """Run a baseline on the examples produced by a Jev run; `variant` = the variant to mirror (default: frozen)."""
    from pipeline.trace import TraceHandler

    def one(x):
        ctx = _ctx(variant or VARIANTS[FROZEN[0]])
        cfg = {"callbacks": [TraceHandler(ctx.conn, SCHEMA, run_id, x["qid"])]}
        return baselines.runnable(fn, name, ctx).invoke(x, config=cfg)
    with ThreadPoolExecutor(WORKERS) as ex:
        return list(ex.map(one, results))


def rows_jev(results):
    return [{"label": r["label"], "class": r["verdict"]["class"], "probabilities": r["verdict"]["probabilities"],
             "confidence": r["finding"]["confidence"], "latency_ms": r["verdict"]["latency_ms"],
             "cost_usd": r["verdict"]["cost_usd"], "job": r["job"], "wording": r["wording"]} for r in results]


def rows_llm(results, preds):
    """LLM mirror rows: confidence = self-reported confidence x shuffle agreement (same rule as Jev's Finding)."""
    return [{"label": r["label"], **p, "confidence": p["probabilities"].get(p["class"], 0) * p["shuffle_agreement"],
             "job": r["job"], "wording": r["wording"]} for r, p in zip(results, preds)]


def rows_base(results, preds):
    return [{"label": r["label"], **p, "confidence": max(p["probabilities"].values()), "job": r["job"],
             "wording": r["wording"]} for r, p in zip(results, preds)]


def paraphrase_consistency(rows) -> float:
    by_job = defaultdict(set)
    for r in rows:
        by_job[r["job"]].add(r["class"])
    return statistics.mean(len(v) == 1 for v in by_job.values())


def tune_threshold(rows, target=0.9, min_cov=0.0):
    """Smallest confidence threshold whose selective accuracy on dev >= target (grid 0.30..0.99)."""
    for t in [x / 100 for x in range(30, 100)]:
        acc, cov = metrics.selective(rows, t)
        if cov > min_cov and acc == acc and acc >= target:
            return t, acc, cov
    return None, float("nan"), 0.0


def main_run():
    """Amendment 2: every variant runs on BOTH Jev and the LLM with identical evidence and class options."""
    examples = load_questions()
    run_stamp = time.strftime("%Y%m%d-%H%M%S")
    sid = f"001-dev-{run_stamp}"
    with db.connect() as conn:
        trace.ensure_table(conn, SCHEMA)
    summaries, per_variant, llm_per_variant, f1 = [], {}, {}, {}
    for name, variant in VARIANTS.items():
        t0 = time.time()
        res = run_pipeline(examples, variant, f"{sid}-{name}")
        llm = run_baseline(res, baselines.b1_llm_same_evidence, "B1_llm_same_evidence", f"{sid}-{name}-LLM", variant)
        per_variant[name], llm_per_variant[name] = res, llm
        sj = metrics.summary(f"Jev {name}", rows_jev(res), config.AUTO_THRESHOLD)
        sl = metrics.summary(f"LLM {name}", rows_llm(res, llm), config.AUTO_THRESHOLD)
        summaries += [sj, sl]
        f1[name] = (sj["macro_f1"] + sl["macro_f1"]) / 2
        print(f"{name}: Jev F1 {sj['macro_f1']:.3f} | LLM F1 {sl['macro_f1']:.3f} | {time.time() - t0:.0f}s")

    # freeze by the AVERAGE macro-F1 of both models (evidence choices must not be tuned to one model),
    # ties -> fewer components (dict order = complexity order)
    best = max(VARIANTS, key=lambda n: (round(f1[n], 3), -list(VARIANTS).index(n)))
    FROZEN[0] = best
    best_res, best_llm = per_variant[best], llm_per_variant[best]
    jev_rows, llm_rows = rows_jev(best_res), rows_llm(best_res, best_llm)
    t, acc, cov = tune_threshold(jev_rows)
    t_llm, acc_llm, cov_llm = tune_threshold(llm_rows)
    summaries.append(metrics.summary(f"Jev FROZEN={best} @t={t}", jev_rows, t))
    summaries.append(metrics.summary(f"LLM FROZEN={best} @t={t_llm}", llm_rows, t_llm))

    # baselines that don't depend on the variant's prompt: B2 raw logs, B3 classifier, B4 rules
    b2 = run_baseline(best_res, baselines.b2_llm_raw_logs, "B2_llm_raw_logs", f"{sid}-B2")
    b4 = run_baseline(best_res, baselines.b4_rules, "B4_rules", f"{sid}-B4")
    b3 = [None] * len(best_res)                       # leave-one-run-out
    for run in sorted({r["job"].split("_")[1] for r in best_res}):
        train = [r for r in best_res if r["job"].split("_")[1] != run]
        model = baselines.PatternClassifier().fit(train, [r["label"] for r in train])
        for i, r in enumerate(best_res):
            if r["job"].split("_")[1] == run:
                b3[i] = model.predict(r)
    from sklearn.model_selection import StratifiedKFold  # stratified 5-fold over jobs
    jobs = sorted({r["job"] for r in best_res})
    job_label = {r["job"]: r["label"] for r in best_res}
    b3s = [None] * len(best_res)
    for tr, te in StratifiedKFold(5, shuffle=True, random_state=0).split(jobs, [job_label[j] for j in jobs]):
        train_jobs, test_jobs = {jobs[i] for i in tr}, {jobs[i] for i in te}
        train = [r for r in best_res if r["job"] in train_jobs]
        model = baselines.PatternClassifier().fit(train, [r["label"] for r in train])
        for i, r in enumerate(best_res):
            if r["job"] in test_jobs:
                b3s[i] = model.predict(r)
    rows_b = {n: rows_base(best_res, p) for n, p in
              {"B2 LLM raw logs": b2, "B3 classifier (LORO-CV)": b3,
               "B3 classifier (stratified 5-fold CV)": b3s, "B4 rules": b4}.items()}
    for n, rows in rows_b.items():
        summaries.append(metrics.summary(n, rows, config.AUTO_THRESHOLD))

    # consistency on the frozen variant (wording 0): 2 extra repeats for BOTH models
    w0 = [r for r in best_res if r["wording"] == 0]
    rep_jev = [run_pipeline([dict(x, repeat=k) for x in w0], VARIANTS[best], f"{sid}-repeat{k}") for k in (1, 2)]
    rep_llm = [run_baseline([dict(x, repeat=k) for x in w0], baselines.b1_llm_same_evidence, "B1_llm_same_evidence",
                            f"{sid}-repeat{k}-LLM") for k in (1, 2)]
    llm_w0 = [p for r, p in zip(best_res, best_llm) if r["wording"] == 0]
    self_cons = {
        "jev": statistics.mean(len({x["verdict"]["class"], a["verdict"]["class"], b["verdict"]["class"]}) == 1
                               for x, a, b in zip(w0, *rep_jev)),
        "llm": statistics.mean(len({x["class"], a["class"], b["class"]}) == 1 for x, a, b in zip(llm_w0, *rep_llm))}
    order_agree = {"jev": statistics.mean(r["verdict"]["shuffle_agreement"] for r in per_variant["A3_structured_plus_3_shuffles"]),
                   "llm": statistics.mean(p["shuffle_agreement"] for p in llm_per_variant["A3_structured_plus_3_shuffles"])}

    extra = {
        "frozen_variant": best, "freeze_rule": "max average macro-F1 of Jev and LLM",
        "avg_macro_f1_per_variant": f1,
        "tuned_auto_threshold": {"jev": t, "llm": t_llm},
        "dev_selective_at_t": {"jev": [acc, cov], "llm": [acc_llm, cov_llm]},
        "paraphrase_consistency": {"jev": paraphrase_consistency(jev_rows), "llm": paraphrase_consistency(llm_rows),
                                   **{n: paraphrase_consistency(r) for n, r in rows_b.items()}},
        "self_consistency_3_runs": self_cons,
        "option_order_agreement_A3": order_agree,
    }
    md = metrics.table(summaries) + "\n\n```json\n" + json.dumps(extra, indent=1) + "\n```\n"
    (OUT / "dev_results.md").write_text(md)
    (OUT / "dev_results.json").write_text(json.dumps({"summaries": summaries, **extra}, indent=1, default=str))
    print(md)


TEMPLATES, STATS = {}, ({}, 0, 0.0)

if __name__ == "__main__":
    OUT.mkdir(parents=True, exist_ok=True)
    if sys.argv[1:] == ["ingest"]:
        ingest_dev()
    elif sys.argv[1:] == ["run"]:
        TEMPLATES = json.loads((OUT / "templates_dev.json").read_text())
        with db.connect() as c:
            cx = bricks.Ctx(conn=c, schema=SCHEMA, templates=TEMPLATES, cache_dir=CACHE)
            cx.load_corpus_stats()
            STATS = (cx.pattern_jobs, cx.total_jobs, cx.typical_duration_s)
        main_run()
    else:
        sys.exit(__doc__)
