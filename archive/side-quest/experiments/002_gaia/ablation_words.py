"""Plan 002 amendment 4 (post-hoc, DEV ONLY): does removing raw counts from the evidence help?
E1 (counts + phrase) vs E1w (phrase only), question design Q0, both models, same folds. Held-out is not touched (D14).

    .venv/bin/python experiments/002_gaia/ablation_words.py   -> runs/002/ablation_words.json
"""
import json
import statistics
import sys
from collections import Counter
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core as C  # noqa: E402
import run_dev as R  # noqa: E402

run = R.make_run()
run.run_id = run.run_id.replace("002-dev-", "002-dev-ablation-words-")
folds, wday = R.setup(run)
qs = C.jl(run.data / "questions.jsonl")
rows = {v: C.engineer(run, qs, v, "Q0") for v in ("E1", "E1w")}
out = {"scores": {}, "paired": {}, "fairness": {}}
for v, rr in rows.items():
    out["scores"][v] = {m: C.score(C.mrows(rr, m), C.make_folds(run.windows), wday) for m in ("jev", "llm")}
    out["fairness"][v] = statistics.mean(r.get("fair", False) for r in rr)
a, b = {r["qid"]: r for r in rows["E1"]}, {r["qid"]: r for r in rows["E1w"]}
for m in ("jev", "llm"):
    c = Counter()
    for q in a:
        if a[q]["overlap"]:
            continue
        ok_a, ok_b = a[q][m]["pred"] == a[q]["label"], b[q][m]["pred"] == b[q]["label"]
        c["both right" if ok_a and ok_b else "only E1 right" if ok_a else "only E1w right" if ok_b else "both wrong"] += 1
    out["paired"][m] = dict(c)
(R.OUT / "ablation_words.json").write_text(json.dumps(out, indent=1, default=str))
cols = ["macro_f1", "fold_mean", "fold_sd", "brier", "no_fault_on_notrace", "fault_recall", "latency_p50_ms"]
for v in ("E1", "E1w"):
    for m in ("jev", "llm"):
        s = out["scores"][v][m]
        print(f"{v:4s} {m:4s} " + "  ".join(f"{k}={s[k]:.3f}" if isinstance(s[k], float) else f"{k}={s[k]}" for k in cols))
print("paired (per question):", json.dumps(out["paired"]))
print("fairness:", out["fairness"])
