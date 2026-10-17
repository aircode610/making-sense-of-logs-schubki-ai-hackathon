"""Build the Jev demo deck: reports/templates/002-jev-demo.template.html + recorded data -> reports/002-jev-demo.html.

    .venv/bin/python experiments/002_gaia/build_demo.py

Inputs: runs/002/demo_cases.json (recorded dev calls), runs/002/wave1..4.json (dev metrics), and, once the one-time
test run is done, runs/002/test_results.json (aggregates only, copied from the evaluation's printed output).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
RUNS = ROOT / "runs" / "002"
load = lambda n: json.loads((RUNS / n).read_text())  # noqa: E731


def pick(s, keys=("macro_f1", "root_top1", "no_fault_on_notrace", "brier", "latency_p50_ms", "cost_per_1k_usd")):
    return {k: s.get(k) for k in keys}


def main():
    data = load("demo_cases.json")
    w1, w2, w3, w4 = load("wave1.json"), load("wave2.json"), load("wave3.json"), load("wave4.json")
    final = w2["final"]
    eng = {m: pick(w2["scores"][final][m]) for m in ("jev", "llm")}
    eng["b2"] = pick(w1["baselines"]["B2 LLM raw logs (wording 0)"])
    eng["b3"] = pick(w1["baselines"]["B3 classifier (5-fold by day)"])
    bench = {"n_dev": w2["scores"][final]["jev"]["n"], "eng": eng,
             "lead": {m: w3["L0_same_problem"][m]["f1"] for m in ("jev", "llm")},
             "repeat": {m: w3["L2_repeat"][m]["accuracy"] for m in ("jev", "llm")},
             "mgr": {m: w4["M0_fix_first"][m]["agree_with_rule"] for m in ("jev", "llm")},
             "mgr_order": {m: w4["M0_fix_first"][m]["order_robust"] for m in ("jev", "llm")}, "test": None}
    tp = RUNS / "test_results.json"
    if tp.exists():
        t = json.loads(tp.read_text())
        e = t["engineer"]
        name = lambda prefix: next(k for k in e if k.startswith(prefix))  # noqa: E731
        bench["test"] = {"n": t["n_questions"],
                         "eng": {"jev": pick(e[name("Jev")]), "llm": pick(e[name("LLM")]),
                                 "b2": pick(e[name("B2")]), "b3": pick(e[name("B3")])},
                         "lead": {m: t["lead"]["L0"][m]["f1"] for m in ("jev", "llm")},
                         "repeat": {m: t["lead"]["L2"][m]["accuracy"] for m in ("jev", "llm")} if t["lead"].get("L2") else {},
                         "mgr": {m: t["manager"]["M0"][m]["agree"] for m in ("jev", "llm")} if t["manager"].get("M0") else {},
                         "mgr_order": {m: t["manager"]["M0"][m]["order_robust"] for m in ("jev", "llm")} if t["manager"].get("M0") else {}}
        if t.get("takeaway"):
            bench["take"] = t["takeaway"]
    data["bench"] = bench
    # funnel on the frozen dev config: which questions need a model at all, and where the gap is
    rows = [r for r in load("wave2_rows.json")[final] if not r["overlap"]]
    ok = lambda rs, m: sum(r[m]["pred"] == r["label"] for r in rs)  # noqa: E731
    empty = [r for r in rows if not r["evidence_pattern_ids"]]
    items = [r for r in rows if r["evidence_pattern_ids"]]
    faults = [r for r in items if r["label"] != "none"]
    noise = [r for r in items if r["label"] == "none"]
    cites = [r for r in items if r["jev"]["pred"] != "none"]
    data["funnel"] = {"total": len(rows), "empty": len(empty), "empty_jev": ok(empty, "jev"), "empty_llm": ok(empty, "llm"),
                      "faults": len(faults), "faults_jev": ok(faults, "jev"), "faults_llm": ok(faults, "llm"),
                      "noise": len(noise), "noise_jev": ok(noise, "jev"), "noise_llm": ok(noise, "llm"),
                      "cite_top": sum(r["jev"]["key_evidence"] == "E1" for r in cites), "cites": len(cites)}
    tpl = (ROOT / "reports" / "templates" / "002-jev-demo.template.html").read_text()
    html = tpl.replace("/*__DATA__*/null", json.dumps(data, ensure_ascii=False, default=str).replace("</", "<\\/"))
    out = ROOT / "reports" / "002-jev-demo.html"
    out.write_text(html)
    print(f"wrote {out.relative_to(ROOT)} ({len(html) // 1024} KB), test results: {'yes' if bench['test'] else 'pending'}")


if __name__ == "__main__":
    main()
