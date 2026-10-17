"""Amendment 3 (plans/001): can any confidence signal make "auto" answers >= 90% accurate? Analysis only.

Re-scores the dev traces of the latest mirrored session for BOTH models alike. No model calls.
    .venv/bin/python experiments/001_hadoop/h4_confidence.py
Writes runs/001/h4_results.md.
"""
import json
import re
import statistics
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from pipeline import db  # noqa: E402

FROZEN, SHUF = "A4_rarity_evidence_structured", "A3_structured_plus_3_shuffles"


def load(conn, run_id, step=None):
    sql = "SELECT qid, input_json, output_json FROM traces WHERE run_id = %s" + (" AND step = %s" if step else "")
    rows = conn.execute(sql, (run_id, step) if step else (run_id,)).fetchall()
    return {r["qid"]: (json.loads(r["input_json"]), json.loads(r["output_json"])) for r in rows}


def wording_agreement(answers: dict) -> dict:
    """qid -> share of the job's 3 wordings that gave the same answer as this one (asks 3x at inference)."""
    by_job = defaultdict(list)
    for qid, a in answers.items():
        by_job[qid.split("#")[0]].append(a)
    return {qid: by_job[qid.split("#")[0]].count(a) / len(by_job[qid.split("#")[0]]) for qid, a in answers.items()}


def risk_coverage(rows):
    """rows: (score, correct). Sort by score desc; returns list of (coverage, selective accuracy) and AURC."""
    rows = sorted(rows, key=lambda r: -r[0])
    curve, ok = [], 0
    for i, (_, c) in enumerate(rows, start=1):
        ok += c
        curve.append((i / len(rows), ok / i))
    aurc = statistics.mean(1 - acc for _, acc in curve)
    return curve, aurc


def best_cov(rows, target):
    """Largest coverage whose selective accuracy >= target, using only thresholds between distinct scores."""
    rows = sorted(rows, key=lambda r: -r[0])
    best, ok = (0.0, None), 0
    for i, (s, c) in enumerate(rows, start=1):
        ok += c
        nxt = rows[i][0] if i < len(rows) else None
        if (nxt is None or nxt < s) and ok / i >= target:
            best = (i / len(rows), s)
    return best


def main():
    with db.connect() as conn:
        sid = conn.execute("SELECT max(substr(run_id,1,23)) AS s FROM traces WHERE run_id LIKE %s",
                           (f"%{FROZEN}-LLM",)).fetchone()["s"]
        jv = load(conn, f"{sid}-{FROZEN}", "Verdict")
        jf = load(conn, f"{sid}-{FROZEN}", "Finding")
        lv = load(conn, f"{sid}-{FROZEN}-LLM")
        js = load(conn, f"{sid}-{SHUF}", "Verdict")
        ls = load(conn, f"{sid}-{SHUF}-LLM")
    label = {q: x["label"] for q, (x, _) in jv.items()}
    jans = {q: o["class"] for q, (_, o) in jv.items()}
    lans = {q: o["class"] for q, (_, o) in lv.items()}
    jw, lw = wording_agreement(jans), wording_agreement(lans)

    def jev_consistent(o):
        return (o["key_evidence"] == "none") == (o["class"] == "normal")

    signals = {"Jev": {}, "LLM": {}}
    for q, (_, o) in jv.items():
        p = sorted(o["probabilities"].values(), reverse=True)
        c = jans[q] == label[q]
        add = lambda k, v: signals["Jev"].setdefault(k, []).append((v, c))  # noqa: E731
        add("computed confidence (current)", o["confidence"])
        add("top probability", p[0])
        add("top-two margin", p[0] - p[1])
        add("key-evidence confidence", o["key_evidence_confidence"])
        add("confidence × answer/citation consistent", o["confidence"] * jev_consistent(o))
        add("confidence × A3 shuffle agreement", o["confidence"] * js[q][1]["shuffle_agreement"])
        add("confidence × wording agreement (3 asks)", o["confidence"] * jw[q])
    for q, (_, o) in lv.items():
        c = lans[q] == label[q]
        conf = o["probabilities"].get(o["class"], 0)
        add = lambda k, v: signals["LLM"].setdefault(k, []).append((v, c))  # noqa: E731
        add("self-reported confidence (current)", conf)
        add("confidence × A3 shuffle agreement", conf * ls[q][1]["shuffle_agreement"])
        add("confidence × wording agreement (3 asks)", conf * lw[q])

    lines = [f"# H4 confidence signals (dev, session {sid}, frozen {FROZEN})", "",
             "Coverage = share of the 105 questions answered automatically; the rest go to \"needs review\".",
             "Thresholds are picked on dev (optimistic); held-out validates once.", "",
             "| Model | Signal | Accuracy if answering all | Max coverage @ ≥90% acc | Max coverage @ ≥80% acc | AURC ↓ |",
             "|---|---|---|---|---|---|"]
    for model, sig in signals.items():
        for name, rows in sig.items():
            _, aurc = risk_coverage(rows)
            c90, t90 = best_cov(rows, 0.9)
            c80, t80 = best_cov(rows, 0.8)
            fmt = lambda c, t: f"{c:.0%}" + (f" (t={t:.2f})" if t is not None else "")  # noqa: E731
            lines.append(f"| {model} | {name} | {statistics.mean(r[1] for r in rows):.0%} | {fmt(c90, t90)} | "
                         f"{fmt(c80, t80)} | {aurc:.3f} |")
    out = "\n".join(lines) + "\n"
    (ROOT / "runs" / "001" / "h4_results.md").write_text(out)
    print(out)


if __name__ == "__main__":
    main()
