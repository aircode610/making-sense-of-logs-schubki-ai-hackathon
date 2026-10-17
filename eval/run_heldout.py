"""Held-out eval (docs/HELDOUT.md): the ONLY code that reads eval/heldout/. Same suite as eval/run_eval.py.

Run by the humans (Amirali / Konark), never by Claude on the real file:
  python3 eval/run_heldout.py                              # eval/heldout/questions.yaml, both systems + judge
  python3 eval/run_heldout.py --questions eval/dev_questions.yaml --no-judge   # self-test on the dev file

Prints AGGREGATES ONLY (per system and role, per metric; pairwise counts; E4). Questions, answers, judge reasons and
per-question scores go only to eval/heldout/out/ (gitignored) and to the LangSmith dataset `logs-heldout-<hash>`.
"""
import argparse
import asyncio
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
VENV_PY = ROOT / ".venv/bin/python"
if Path(sys.prefix).resolve() != (ROOT / ".venv").resolve() and VENV_PY.exists():  # run as plain `python3 …`
    import os
    os.execv(str(VENV_PY), [str(VENV_PY), *sys.argv])
sys.path.insert(0, str(ROOT))

import yaml

from eval.run_eval import ROWS, run_suite

DEFAULT = ROOT / "eval/heldout/questions.yaml"
OUT = ROOT / "eval/heldout/out"


def print_aggregates(rep: dict) -> None:
    a = rep["aggregates"]
    cols = [k for k in a if "/" in k and not k.endswith("/E4")]
    print(f"git {rep['git']} · judge {rep['judge_model']} · experiments {', '.join(rep['experiments'].values())}\n")
    print("| metric | " + " | ".join(cols) + " |")
    print("|---|" + "---|" * len(cols))
    for key, label, better in ROWS:
        print(f"| {label} {better} | " + " | ".join("—" if a[c].get(key) is None else str(a[c][key]) for c in cols) + " |")
    if "pairwise" in a:
        print(f"\npairwise (consistent only): {a['pairwise']}")
    for kind in ("ours", "baseline"):
        if f"{kind}/E4" in a:
            print(f"E4 {kind}: {a[f'{kind}/E4']}")


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--questions", default=str(DEFAULT))
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--systems", default="ours,baseline")
    a = ap.parse_args()
    qs = yaml.safe_load(Path(a.questions).read_text())
    missing = [q.get("id", "?") for q in qs for g in q.get("golden", []) if "value" not in g]
    if missing:
        print(f"{len(missing)} golden facts have no value yet: run eval/build_golden.py on the file first.")
        return 1
    rep = await run_suite(qs, "logs-heldout", OUT, judge=not a.no_judge, systems=tuple(a.systems.split(",")), quiet=True)
    print_aggregates(rep)
    print(f"\nfull report (per question): {OUT}/ — not shown here by design")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
