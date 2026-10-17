"""Extract recorded DEV cases (exact Jev request + answers, LLM answers, latency) for the demo presentation.

    .venv/bin/python experiments/002_gaia/demo_cases.py   -> runs/002/demo_cases.json

Dev traces only (schema public). Every value is a real recorded call; nothing is re-generated.
"""
import json
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import core as C  # noqa: E402
from pipeline import db, gaia_bricks as B, gaia_queries as Q  # noqa: E402

ROOT = C.ROOT
CASES = {"w0187": "File fault on webservice1", "w0378": "Permission fault on dbservice",
         "w0381": "Memory fault (invisible in logs)", "w0063": "Quiet window: Jev false alarm fixed by 'cannot tell'",
         "w0009": "Quiet window: Jev still raises a false alarm"}
VARIANTS = ["E0/Q0", "E1/Q0", "E1/Q1", "E1/Q2", "E1/Q7"]
c = db.connect()


def last(step, qid):
    r = c.execute("SELECT input_json, output_json, latency_ms FROM traces WHERE run_id LIKE '002-dev-%%' AND step = %s "
                  "AND qid = %s ORDER BY started_at DESC LIMIT 1", (step, qid)).fetchone()
    return (json.loads(r["input_json"]), json.loads(r["output_json"]), r["latency_ms"]) if r else (None, None, None)


qs = {json.loads(l)["qid"]: json.loads(l) for l in open(ROOT / "dataset/dev/gaia/questions.jsonl")}
wins = {json.loads(l)["wid"]: json.loads(l) for l in open(ROOT / "dataset/dev/gaia/windows.jsonl")}
run = C.Run(schema="public", data=ROOT / "dataset/dev/gaia", container_data="", cache=ROOT / "runs/002/cache",
            out=ROOT / "runs/002", otlp_url="")
run.windows = list(wins.values())
run.templates = json.loads((run.data / "templates.json").read_text())
out = {"cases": [], "lead": [], "manager": [], "sql": {"WINDOW_PATTERNS": Q.WINDOW_PATTERNS, "WINDOW_SERVICES": Q.WINDOW_SERVICES}}
for wid, title in CASES.items():
    qid = f"{wid}#w0"
    q, w = qs[qid], wins[wid]
    f = B.window_facts(w, run.ctx())
    raw = [f"{r['service']} {r['severity_text']} {r['body'][:160]}" for r in f["raw_warn"] if r["severity_text"] == "ERROR"][:12]
    case = {"wid": wid, "title": title, "question": q["question"], "truth": q["label"], "slice": q["slice"],
            "raw": {"lines": sum(s["n_window"] for s in f["services"]), "errors": sum(s["err_window"] for s in f["services"]),
                    "warn_plus": len(f["raw_warn"]), "sample_errors": raw},
            "variants": {}}
    for v in VARIANTS:
        ji, jo, jl = last(f"jev:{v}", qid)
        li, lo, ll = last(f"llm:{v}", qid)
        if not ji:
            continue
        case["variants"][v] = {"state": ji["state"], "questions": ji["questions"],
                               "jev": {"answers": jo["answers"], "finding": jo["finding"], "latency_ms": jl},
                               "llm": {"answers": lo["answers"], "finding": lo["finding"], "latency_ms": ll,
                                       "prompt_chars": len(li["prompt"]),
                                       **({"prompt": li["prompt"]} if wid == "w0187" and v == "E1/Q7" else {})}}
    out["cases"].append(case)
l0 = json.loads((ROOT / "runs/002/wave3_rows.json").read_text())["l0"]
for want in (True, False):
    r = next(x for x in l0 if x["label"] == want and isinstance(B.fingerprint(wins[x["wa"]], run.ctx()), dict)
             and isinstance(B.fingerprint(wins[x["wb"]], run.ctx()), dict))
    ji, jo, jl = last("jev:L0", r["pid"])
    li, lo, ll = last("llm:L0", r["pid"])
    out["lead"].append({"label": want, "state": ji["state"], "questions": ji["questions"],
                        "jev": {"answers": jo, "latency_ms": jl}, "llm": {"answers": lo, "latency_ms": ll}})
m0 = json.loads((ROOT / "runs/002/wave4_rows.json").read_text())["m0"]
for r in [m0[15], m0[5], m0[0]]:   # LLM flips with order · LLM disagrees with the rule · both agree
    entry = {"pair": r["pair"], "label": r["label"], "orders": {}}
    for order in ("AB", "BA"):
        ji, jo, jl = last(f"jev:M0:{order}", r["pair"])
        li, lo, ll = last(f"llm:M0:{order}", r["pair"])
        entry["state"] = ji["state"]
        entry["orders"][order] = {"questions": ji["questions"], "jev": {"answers": jo, "latency_ms": jl},
                                  "llm": {"answers": lo, "latency_ms": ll}}
    out["manager"].append(entry)
m1 = c.execute("SELECT qid, input_json, output_json, latency_ms FROM traces WHERE run_id LIKE '002-dev-%%' AND step = 'jev:M1' AND qid LIKE '%%webservice%%' "
               "ORDER BY started_at DESC LIMIT 1").fetchone()
l1 = c.execute("SELECT output_json, latency_ms FROM traces WHERE run_id LIKE '002-dev-%%' AND step = 'llm:M1' AND qid = %s "
               "ORDER BY started_at DESC LIMIT 1", (m1["qid"],)).fetchone()
out["score_example"] = {"state": json.loads(m1["input_json"])["state"], "questions": json.loads(m1["input_json"])["questions"],
                        "jev": {"answers": json.loads(m1["output_json"]), "latency_ms": m1["latency_ms"]},
                        "llm": {"answers": json.loads(l1["output_json"]), "latency_ms": l1["latency_ms"]}}
(ROOT / "runs/002/demo_cases.json").write_text(json.dumps(out, indent=1, default=str, ensure_ascii=False))
print("cases", len(out["cases"]), "lead", len(out["lead"]), "manager", len(out["manager"]),
      "bytes", len(json.dumps(out, default=str)))
