"""Build the judges' eval dashboard (plan 017): ONE static page from the committed eval results, no server, no keys.

  uv run python scripts/build_dashboard.py                      # the newest product-vs-baseline A/B run
  uv run python scripts/build_dashboard.py eval/results/ab-<stamp>.json
Writes docs/dashboard.html. Every number on the page is read from a result file in eval/results/ (named on the page).
"""
import glob
import html
import json
import sys
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "eval/results"


def latest(pattern: str, arms: tuple[str, str]) -> Path:
    for p in sorted(glob.glob(str(RES / pattern)), reverse=True):
        if p.endswith(".runs.json"):
            continue
        d = json.loads(Path(p).read_text())
        if tuple(d.get("arms", {})) == arms:
            return Path(p)
    raise SystemExit(f"no {pattern} with arms {arms}")


def main() -> None:
    final = Path(sys.argv[1]) if len(sys.argv) > 1 else latest("cc-*.json", ("mcp", "bare"))
    F = json.loads(final.read_text())
    for st in F["arms"].values():                       # cc runs (plan 018) name a few stats differently
        st.setdefault("wall_s", st.get("wall_s mean"))
        st.setdefault("E1", st.get("E1 golden facts"))
        st.setdefault("found_problem", st.get("found_problem (0-2)"))
        st.setdefault("rubric", st.get("rubric (1-5)"))
    F.setdefault("agent_model", "Claude Code " + str(F.get("model", "")))
    A, B = list(F["arms"])
    qs = {q["id"]: q for q in yaml.safe_load((ROOT / "eval/dev_questions.yaml").read_text())}
    runs = {r["id"]: r["runs"] for r in json.loads(final.with_suffix("").with_suffix(".runs.json").read_text())}

    rows = []
    for r in F["rows"]:
        j = r.get("judge") or {}
        g = j.get("grades", {})
        reasons = (j.get("round1") or {}).get("reasons", "")
        def arm(a):
            gg = g.get(a) or []
            run = runs.get(r["id"], {}).get(a, {})
            return {"found": sum(x["found_problem"] for x in gg) / max(1, len(gg)) if gg else None,
                    "wrong": sum(x["claims_wrong"] for x in gg) / max(1, len(gg)) if gg else None,
                    "wrong_claims": sorted({c for x in gg for c in x.get("wrong_claims", [])})[:4],
                    "tools": r.get("tools", {}).get(a, []), "s": run.get("elapsed_s"),
                    "answer": (run.get("text") or run.get("error") or "")[:6000]}
        rows.append({"id": r["id"], "role": r["role"], "dataset": r["dataset"],
                     "question": qs.get(r["id"], {}).get("question", ""), "result": j.get("result", "not judged"),
                     "reasons": reasons, "a": arm(A), "b": arm(B)})

    # history: earlier committed runs (each step names its file)
    hist = []
    old_ab = sorted(glob.glob(str(RES / "ab-*.json"))) + sorted(glob.glob(str(RES / "cc-*.json")))
    for p in old_ab:
        if p.endswith(".runs.json") or Path(p) == final:
            continue
        d = json.loads(Path(p).read_text())
        if len(d.get("rows", [])) < 50:                    # pilots and smoke tests are not history steps
            continue
        a1, a2 = list(d["arms"])
        hist.append({"file": Path(p).name, "arms": [a1, a2], "tally": d["tally"],
                     "acc": [d["arms"][a1]["claim_accuracy"], d["arms"][a2]["claim_accuracy"]],
                     "wrong": [d["arms"][a1]["claims_wrong"], d["arms"][a2]["claims_wrong"]],
                     "found": [d["arms"][a1]["found_problem"], d["arms"][a2]["found_problem"]]})
    dev = json.loads((RES / "20261018-043511.json").read_text())["aggregates"]
    data = {"final": {"file": final.name, "git": F["git"], "agent": F["agent_model"], "judge": F["judge_model"],
                      "arms": [A, B], "tally": F["tally"], "stats": F["arms"], "n": len(F["rows"]),
                      "slices": slices(F["rows"], A, B)},
            "rows": rows, "hist": hist,
            "dev25": {k: dev[k] for k in ("ours/all", "baseline/all")}}
    page = (ROOT / "scripts/dashboard.template.html").read_text().replace(
        "/*DATA*/null", json.dumps(data, default=str).replace("</", "<\\/"))
    out = ROOT / "docs/dashboard.html"
    out.write_text(page)
    print(f"{out.relative_to(ROOT)} from {final.name}: {F['tally']}")


def slices(rows, A, B):
    out = {}
    for dim in ("role", "dataset"):
        for v in sorted({r[dim] for r in rows}):
            t = {A: 0, B: 0, "tie": 0, "inconsistent": 0}
            for r in rows:
                if r[dim] == v and r.get("judge"):
                    t[r["judge"]["result"]] += 1
            out[f"{dim}:{v}"] = t
    base = ("bgl", "openstack")                                    # the brief's base corpus vs the other datasets
    for name, keep in (("base corpus (BGL + OpenStack)", lambda r: r["dataset"] in base),
                       ("other 7 datasets", lambda r: r["dataset"] not in base)):
        t = {A: 0, B: 0, "tie": 0, "inconsistent": 0}
        for r in rows:
            if keep(r) and r.get("judge"):
                t[r["judge"]["result"]] += 1
        out[f"scope:{name}"] = t
    return out


if __name__ == "__main__":
    main()
