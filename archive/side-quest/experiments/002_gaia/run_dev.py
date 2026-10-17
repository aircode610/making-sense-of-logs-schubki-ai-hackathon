"""Experiment 002 on the DEV side only (plans/002-gaia-question-design.md).

    .venv/bin/python experiments/002_gaia/run_dev.py ingest     # rollup + rows into SereneDB
    .venv/bin/python experiments/002_gaia/run_dev.py wave1      # engineer evidence E0-E3 x Q0, both models + B2/B3/B4, G1
    .venv/bin/python experiments/002_gaia/run_dev.py wave2      # engineer questions Q1/Q2/Q7 on frozen E, consistency, R3
    .venv/bin/python experiments/002_gaia/run_dev.py wave3      # lead L0/L1/L2 + baselines
    .venv/bin/python experiments/002_gaia/run_dev.py wave4      # manager M0/M1

Results: runs/002/wave*.json (+ per-question rows), runs/002/dev_results.md; traces in public.traces (run_id 002-dev-*).
"""
import json
import statistics
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core as C  # noqa: E402

ROOT = C.ROOT
OUT = ROOT / "runs" / "002"
EVIDENCE = ["E0", "E1", "E2", "E3"]          # E0 = reference (001's A4); E1 < E2 < E3 by complexity
DESIGNS = ["Q1", "Q2", "Q7"]


def make_run() -> C.Run:
    run = C.Run(schema="public", data=ROOT / "dataset" / "dev" / "gaia", container_data="/dataset/dev/gaia",
                cache=OUT / "cache", out=OUT, otlp_url=C.config.DEV_OTLP_URL, run_id=f"002-dev-{time.strftime('%Y%m%d-%H%M%S')}")
    run.windows = C.jl(run.data / "windows.jsonl")
    run.templates = json.loads((run.data / "templates.json").read_text()) if (run.data / "templates.json").exists() else {}
    return run


def setup(run):
    run.conn().execute(C.TRACE_DDL.format(s=run.schema))
    rows = C.query_rows(run, C.Q.CORPUS_PATTERN_WINDOWS)
    run.corpus_windows = {r["pattern_id"]: r["n_windows"] for r in rows}
    folds = C.make_folds(run.windows)
    wday = {w["wid"]: w["t1"][:10] for w in run.windows}
    return folds, wday


def save(name, obj):
    OUT.mkdir(parents=True, exist_ok=True)
    (OUT / f"{name}.json").write_text(json.dumps(obj, indent=1, default=str))


def load(name):
    return json.loads((OUT / f"{name}.json").read_text())


def fmt(v):
    if isinstance(v, float):
        return f"{v:.3f}"
    if isinstance(v, (list, tuple)) and len(v) == 2 and all(isinstance(x, float) for x in v):
        return f"[{v[0]:.2f}, {v[1]:.2f}]"
    return "—" if v is None else str(v)


def table(rows: dict, cols: list[str]) -> str:
    out = ["| system | " + " | ".join(cols) + " |", "|---|" + "---|" * len(cols)]
    out += [f"| {k} | " + " | ".join(fmt(v.get(c)) for c in cols) + " |" for k, v in rows.items()]
    return "\n".join(out)


ENG_COLS = ["n", "macro_f1", "macro_f1_ci95", "fold_mean", "fold_sd", "brier", "ece", "fault_recall",
            "no_fault_on_notrace", "false_none_on_fault", "abstain_rate", "root_top1", "latency_p50_ms", "cost_per_1k_usd"]


def freeze(scores: dict, order: list[str]) -> tuple[str, dict]:
    """Best average fold-mean macro-F1 of both models; a simpler variant within 1 fold-SD of it wins (lean rule)."""
    avg = {v: (scores[v]["jev"]["fold_mean"] + scores[v]["llm"]["fold_mean"]) / 2 for v in order}
    sd = {v: (scores[v]["jev"]["fold_sd"] + scores[v]["llm"]["fold_sd"]) / 2 for v in order}
    best = max(order, key=lambda v: avg[v])
    chosen = next(v for v in order if avg[best] - avg[v] < sd[best] or v == best)
    return chosen, {"avg_fold_mean_f1": avg, "avg_fold_sd": sd, "best_by_mean": best, "chosen": chosen}


# ------------------------------------------------------------------ waves -----------------------------------------
def wave1():
    run = make_run()
    folds, wday = setup(run)
    qs = C.jl(run.data / "questions.jsonl")
    res, scores, recall, fair = {}, {}, {}, {}
    for ev in EVIDENCE:
        t0 = time.time()
        rows = C.engineer(run, qs, ev, "Q0")
        res[ev] = rows
        scores[ev] = {m: C.score(C.mrows(rows, m), folds, wday) for m in ("jev", "llm")}
        recall[ev] = C.evidence_recall(run, rows, folds)
        fair[ev] = statistics.mean(r.get("fair", False) for r in rows)
        print(f"{ev}: Jev F1 {scores[ev]['jev']['macro_f1']:.3f} | LLM F1 {scores[ev]['llm']['macro_f1']:.3f} | "
              f"recall@K {recall[ev]:.2f} | fair {fair[ev]:.2f} | {time.time() - t0:.0f}s", flush=True)
    frozen, freeze_info = freeze(scores, ["E1", "E2", "E3"])
    b2 = C.b2_raw(run, qs)
    base_rows = [r for r in res[frozen]]
    b3 = C.b3_classifier(run, base_rows, folds)
    b4 = C.b4_rules(run, base_rows)
    base = {"B2 LLM raw logs (wording 0)": C.score(C.mrows(b2, "b2"), folds, wday),
            "B3 classifier (5-fold by day)": C.score(C.mrows(b3, "b3"), folds, wday),
            "B4 rules": C.score(C.mrows(b4, "b4"), folds, wday)}
    w0 = [r for r in res[frozen] if r["wording"] == 0]
    llm_w0 = C.score(C.mrows(w0, "llm"), folds, wday)
    g1 = {"llm_frozen_E_wording0_f1": llm_w0["macro_f1"], "b2_f1": base["B2 LLM raw logs (wording 0)"]["macro_f1"]}
    g1["pass"] = g1["llm_frozen_E_wording0_f1"] >= g1["b2_f1"] - 0.02
    print(f"frozen evidence: {frozen} ({freeze_info}); G1 {g1}", flush=True)
    save("wave1_rows", {"engineer": res, "b2": b2, "b3": b3, "b4": b4})
    save("wave1", {"scores": scores, "baselines": base, "evidence_recall": recall, "fairness": fair, "frozen": frozen,
                   "freeze": freeze_info, "g1": g1, "folds": folds, "run_id": run.run_id})


def wave2():
    run = make_run()
    folds, wday = setup(run)
    w1 = load("wave1")
    ev = w1["frozen"]
    qs = C.jl(run.data / "questions.jsonl")
    res, scores = {}, {}
    for d in ["Q0"] + DESIGNS:
        t0 = time.time()
        rows = C.engineer(run, qs, ev, d)
        res[d] = rows
        scores[d] = {m: C.score(C.mrows(rows, m), folds, wday) for m in ("jev", "llm")}
        print(f"{ev}/{d}: Jev F1 {scores[d]['jev']['macro_f1']:.3f} notrace {scores[d]['jev']['no_fault_on_notrace']} "
              f"root {scores[d]['jev']['root_top1']} | LLM F1 {scores[d]['llm']['macro_f1']:.3f} "
              f"notrace {scores[d]['llm']['no_fault_on_notrace']} root {scores[d]['llm']['root_top1']} | {time.time() - t0:.0f}s",
              flush=True)
    # C4: keep a fault design only if it beats Q0 by >= 1 fold-SD (average of both models) on F1, Brier or no-trace
    avg = lambda d, k: (scores[d]["jev"][k] + scores[d]["llm"][k]) / 2  # noqa: E731
    sd0 = avg("Q0", "fold_sd")
    gains = {d: {"f1": avg(d, "fold_mean") - avg("Q0", "fold_mean"), "brier": avg("Q0", "brier") - avg(d, "brier"),
                 "notrace": avg(d, "no_fault_on_notrace") - avg("Q0", "no_fault_on_notrace")} for d in ["Q1", "Q2"]}
    kept = [d for d, g in gains.items() if g["f1"] >= sd0 or g["brier"] >= 0.05 or g["notrace"] >= 0.10]
    fault_design = max(kept, key=lambda d: avg(d, "fold_mean")) if kept else "Q0"
    final = "Q7" if fault_design == "Q0" else f"{fault_design}+Q7"
    if final not in res:
        res[final] = C.engineer(run, qs, ev, final)
        scores[final] = {m: C.score(C.mrows(res[final], m), folds, wday) for m in ("jev", "llm")}
    rows = res[final]
    w0 = [q for q in qs if q["wording"] == 0]
    reps = [C.engineer(run, w0, ev, final, repeat=k) for k in (1, 2)]
    shuf = C.engineer(run, w0, ev, final, shuffle_seed=1)
    base = {r["qid"]: r for r in rows}
    cons = {}
    for m in ("jev", "llm"):
        cons[m] = {"repeat_3_runs": statistics.mean(len({base[a['qid']][m]['pred'], a[m]['pred'], b[m]['pred']}) == 1
                                                    for a, b in zip(*reps)),
                   "option_order": statistics.mean(base[s["qid"]][m]["pred"] == s[m]["pred"] for s in shuf),
                   "paraphrase": C.paraphrase_consistency(C.mrows(rows, m)),
                   "r3_cv": C.tune_threshold_cv(C.mrows(rows, m), folds)}
    print(f"final engineer config {ev}/{final}: consistency {json.dumps(cons, default=str)}", flush=True)
    save("wave2_rows", res)
    save("wave2", {"evidence": ev, "scores": scores, "gains_vs_Q0": gains, "kept": kept, "final": final,
                   "consistency": cons, "fairness": {d: statistics.mean(r.get("fair", False) for r in v) for d, v in res.items()},
                   "run_id": run.run_id})


def wave3():
    run = make_run()
    folds, wday = setup(run)
    ev = load("wave1")["frozen"]
    pairs = C.jl(run.data / "lead_same.jsonl")
    l0 = C.lead_same(run, pairs)
    wids = sorted({p["wa"] for p in pairs} | {p["wb"] for p in pairs})
    l1 = C.lead_broad(run, wids, ev)
    for r in l0:
        for m in ("jev", "llm"):
            a, b = l1[r["wa"]][m], l1[r["wb"]][m]
            same = a[0] == b[0] and a[0] != "no fault visible" and a[1] == b[1] and a[1] is not None
            r[f"l1_{m}"] = {"pred": same}
    # B4 lead: same top anomalous (service, pattern); B3 lead: cosine of anomaly vectors, threshold per fold
    fps = {wid: C.B.fingerprint(next(w for w in run.windows if w["wid"] == wid), run.ctx()) for wid in wids}
    top = {wid: ((fp["pattern_1"]["service"], fp["pattern_1"]["log_pattern"]) if isinstance(fp, dict) else None)
           for wid, fp in fps.items()}
    vec = {wid: {(x["service"], x["log_pattern"]) for x in fp.values()} if isinstance(fp, dict) else set() for wid, fp in fps.items()}
    for r in l0:
        r["b4_lead"] = {"pred": top[r["wa"]] is not None and top[r["wa"]] == top[r["wb"]]}
        a, b = vec[r["wa"]], vec[r["wb"]]
        r["_sim"] = len(a & b) / ((len(a) * len(b)) ** 0.5) if a and b else 0.0
    for k in sorted(set(folds.values())):
        train = [r for r in l0 if folds[r["wa"]] != k and folds[r["wb"]] != k]
        best_t = max([x / 20 for x in range(1, 20)], key=lambda t: C.pair_f1([{**r, "x": {"pred": r["_sim"] >= t}} for r in train], "x")["f1"]) if train else 0.5
        for r in l0:
            if folds[r["wa"]] == k:
                r["b3_lead"] = {"pred": r["_sim"] >= best_t}
    rep = C.lead_repeat(run, C.jl(run.data / "lead_repeat.jsonl"))
    asked = [r for r in rep if r["n_known"]]
    out = {"L0_same_problem": {m: C.pair_f1(l0, m) for m in ("jev", "llm")},
           "L1_broad_taxonomy_grouping": {m: C.pair_f1(l0, f"l1_{m}") for m in ("jev", "llm")},
           "B3_lead_cosine": C.pair_f1([r for r in l0 if "b3_lead" in r], "b3_lead"),
           "B4_lead_same_top_pattern": C.pair_f1(l0, "b4_lead"),
           "L2_repeat": {m: {"n": len(asked), "accuracy": statistics.mean(r[m]["pred"] == r["label"] for r in asked)}
                         for m in ("jev", "llm")} if asked else {},
           "L2_items_without_known_problems": len(rep) - len(asked),
           "fairness": {"L0": statistics.mean(r.get("fair", False) for r in l0),
                        "L2": statistics.mean(r.get("fair", False) for r in asked) if asked else None},
           "latency_p50_ms": {m: sorted(r[m]["latency_ms"] for r in l0)[len(l0) // 2] for m in ("jev", "llm")},
           "cost_per_1k_usd": {m: 1000 * statistics.mean(r[m]["cost_usd"] for r in l0) for m in ("jev", "llm")},
           "run_id": run.run_id}
    print(json.dumps(out, indent=1, default=str), flush=True)
    save("wave3_rows", {"l0": l0, "l1": {k: v for k, v in l1.items()}, "l2": rep})
    save("wave3", out)


def wave4():
    run = make_run()
    setup(run)
    weeks = C.jl(run.data / "manager_weeks.jsonl")
    res = C.manager(run, weeks)
    out = {"n_pairs": len(res["m0"]),
           "M0_fix_first": {m: {"agree_with_rule": statistics.mean(r[m]["pred"] == r["label"] for r in res["m0"]),
                                "order_robust": statistics.mean(r[m]["order_agree"] for r in res["m0"])}
                            for m in ("jev", "llm")} if res["m0"] else {},
           "M1_impact_score": {m: {"agree_with_rule": statistics.mean(r[m]["pred"] == r["label"] for r in res["m1"])}
                               for m in ("jev", "llm")} if res["m1"] else {},
           "run_id": run.run_id}
    print(json.dumps(out, indent=1), flush=True)
    save("wave4_rows", res)
    save("wave4", out)


def report_md():
    """runs/002/dev_results.md from the saved wave files."""
    md = ["# Experiment 002: dev results (grouped 5-fold CV by day)\n"]
    if (OUT / "wave1.json").exists():
        w1 = load("wave1")
        rows = {f"{m.upper()} {ev}/Q0": w1["scores"][ev][m] for ev in EVIDENCE for m in ("jev", "llm")}
        rows.update(w1["baselines"])
        md += ["## Wave 1: evidence (engineer, Q0)", table(rows, ENG_COLS),
               f"\nEvidence recall@K: {json.dumps({k: round(v, 3) for k, v in w1['evidence_recall'].items()})}",
               f"Fairness (identical input, share of pairs): {json.dumps(w1['fairness'])}",
               f"Frozen evidence: **{w1['frozen']}** ({json.dumps(w1['freeze'], default=str)})",
               f"G1 gate: {json.dumps(w1['g1'])}\n"]
    if (OUT / "wave2.json").exists():
        w2 = load("wave2")
        rows = {f"{m.upper()} {w2['evidence']}/{d}": w2["scores"][d][m] for d in w2["scores"] for m in ("jev", "llm")}
        md += ["## Wave 2: engineer question designs", table(rows, ENG_COLS),
               f"\nGains vs Q0: {json.dumps(w2['gains_vs_Q0'])}; kept {w2['kept']}; final **{w2['final']}**",
               f"Consistency + R3: {json.dumps(w2['consistency'], default=str)}",
               f"Fairness: {json.dumps(w2['fairness'])}\n"]
    if (OUT / "wave3.json").exists():
        md += ["## Wave 3: lead", "```json", json.dumps(load("wave3"), indent=1), "```\n"]
    if (OUT / "wave4.json").exists():
        md += ["## Wave 4: manager", "```json", json.dumps(load("wave4"), indent=1), "```\n"]
    (OUT / "dev_results.md").write_text("\n".join(md))
    print("\n".join(md))


if __name__ == "__main__":
    cmd = sys.argv[1] if len(sys.argv) > 1 else ""
    if cmd == "ingest":
        C.ingest(make_run(), None)
    elif cmd in ("wave1", "wave2", "wave3", "wave4"):
        globals()[cmd]()
        report_md()
    elif cmd == "report":
        report_md()
    else:
        sys.exit(__doc__)
