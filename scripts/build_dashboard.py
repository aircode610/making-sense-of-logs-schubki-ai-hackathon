"""Build the judges' eval dashboard: ONE static page from the committed eval results, no server, no keys.

  uv run python scripts/build_dashboard.py
Reads the newest 50-question run of each comparison in eval/results/:
  cc-*.json   Claude Code + our MCP vs plain Claude Code on the raw files (eval/cc_ab.py)
  ab-*.json   our LangGraph agent vs the brief's reference ReAct agent (eval/ab.py --arms product,baseline)
and every 50-question run as history. Writes docs/dashboard.html (tabs: Overview, Breakdown, Questions, History, Run it).
"""
import glob
import json
import re
from pathlib import Path

import yaml

ROOT = Path(__file__).resolve().parent.parent
RES = ROOT / "eval/results"
BASE = ("bgl", "openstack")                       # the brief's base corpus


def runs_of(pattern: str) -> list[Path]:
    """Committed 50-question result files, newest first (pilots and smoke tests excluded)."""
    out = []
    for p in sorted(glob.glob(str(RES / pattern)), reverse=True):
        if p.endswith(".runs.json"):
            continue
        if len(json.loads(Path(p).read_text()).get("rows", [])) >= 50:
            out.append(Path(p))
    return out


def norm(st: dict) -> dict:
    """cc runs name a few stats differently from ab runs."""
    st = dict(st)
    for a, b in (("wall_s", "wall_s mean"), ("E1", "E1 golden facts"), ("found_problem", "found_problem (0-2)"), ("rubric", "rubric (1-5)")):
        st.setdefault(a, st.get(b))
    return st


def tally(rows, A, B, keep=lambda r: True) -> dict:
    t = {A: 0, B: 0, "tie": 0, "inconsistent": 0}
    for r in rows:
        if keep(r) and r.get("judge"):
            t[r["judge"]["result"]] += 1
    return t


def comparison(path: Path, names: dict, qs: dict) -> dict:
    F = json.loads(path.read_text())
    A, B = list(F["arms"])
    runs = {r["id"]: r["runs"] for r in json.loads(path.with_suffix("").with_suffix(".runs.json").read_text())}
    slices = {"Base corpus (BGL + OpenStack)": tally(F["rows"], A, B, lambda r: r["dataset"] in BASE),
              "Other 7 datasets": tally(F["rows"], A, B, lambda r: r["dataset"] not in BASE)}
    roles = {v: tally(F["rows"], A, B, lambda r, v=v: r["role"] == v) for v in ("engineer", "lead", "manager")}
    datasets = {v: tally(F["rows"], A, B, lambda r, v=v: r["dataset"] == v) for v in sorted({r["dataset"] for r in F["rows"]})}
    rows = []
    for r in F["rows"]:
        j = r.get("judge") or {}
        g = j.get("grades", {})

        def arm(a):
            gg = g.get(a) or []
            run = runs.get(r["id"], {}).get(a, {})
            return {"found": sum(x["found_problem"] for x in gg) / len(gg) if gg else None,
                    "wrong": sum(x["claims_wrong"] for x in gg) / len(gg) if gg else None,
                    "s": run.get("elapsed_s"), "tools": len(r.get("tools", {}).get(a, []) or []),
                    "answer": (run.get("text") or run.get("error") or "")[:6000]}
        # round 1 showed x_in_round1 as "X": name the systems instead of X / Y
        x = j.get("x_in_round1")
        nx, ny = (names[A], names[B]) if x == A else (names[B], names[A])
        reason = re.sub(r"\bX\b", nx, re.sub(r"\bY\b", ny, (j.get("round1") or {}).get("reasons", ""))) if x else ""
        rows.append({"id": r["id"], "role": r["role"], "dataset": r["dataset"], "question": qs.get(r["id"], {}).get("question", ""),
                     "result": j.get("result", "not judged"), "reason": reason, "a": arm(A), "b": arm(B)})
    return {"file": path.name, "git": F["git"], "judge": F["judge_model"], "model": F.get("agent_model") or f"Claude Code {F.get('model', '')}",
            "arms": [A, B], "names": [names[A], names[B]], "tally": F["tally"], "stats": {A: norm(F["arms"][A]), B: norm(F["arms"][B])},
            "slices": slices, "roles": roles, "datasets": datasets, "rows": rows}


def main() -> None:
    qs = {q["id"]: q for q in yaml.safe_load((ROOT / "eval/dev_questions.yaml").read_text())}
    names = {"mcp": "Claude Code + our MCP", "bare": "Plain Claude Code", "product": "Our agent", "baseline": "Reference agent",
             "new": "40 tools", "old": "8 tools"}
    cc = runs_of("cc-*.json")
    ab = [p for p in runs_of("ab-*.json") if list(json.loads(p.read_text())["arms"]) == ["product", "baseline"]]
    comps = {}
    if cc:
        comps["cc"] = {"title": "Claude Code: with vs without our MCP", **comparison(cc[0], names, qs)}
    if ab:
        comps["ab"] = {"title": "Our agent vs the reference agent", **comparison(ab[0], names, qs)}
    hist = []                                     # every committed 50-question run, oldest first
    for p in sorted(runs_of("ab-*.json") + runs_of("cc-*.json"), key=lambda p: json.loads(p.read_text())["stamp"]):
        d = json.loads(p.read_text())
        a, b = list(d["arms"])
        hist.append({"file": p.name, "a": names.get(a, a), "b": names.get(b, b), "wins": [d["tally"][a], d["tally"][b]],
                     "wrong": [d["arms"][a]["claims_wrong"], d["arms"][b]["claims_wrong"]]})
    data = {"comps": comps, "hist": hist}
    page = (ROOT / "scripts/dashboard.template.html").read_text().replace(
        "/*DATA*/null", json.dumps(data, default=str).replace("</", "<\\/"))
    out = ROOT / "docs/dashboard.html"
    out.write_text(page)
    print(f"{out.relative_to(ROOT)}: " + ", ".join(f"{k} {c['file']} {c['tally']}" for k, c in comps.items()))


if __name__ == "__main__":
    main()
