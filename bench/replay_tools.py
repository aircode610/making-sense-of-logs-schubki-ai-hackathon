"""Replay every tool call recorded in an eval against the running backend (plan 010): same results? how fast?

  .venv/bin/python bench/replay_tools.py eval/results/<stamp>.json      # reads <stamp>.runs.json (or LangSmith)

Each distinct call (tool + params) found in the runs' evidence ledgers is sent through the MCP server's own tool
layer (FastMCP: same validation as the agent), and its result compared with the recorded one, ignoring what may
legitimately differ between backends (sql text, evidence_id, elapsed_ms). identical = same result in the same row
order; same rows = equal after sorting rows (ties ordered differently); different = anything else (listed).
A new backend (or a rewritten query) should be 100 % identical-or-same-rows before an end-to-end eval is worth running.
"""
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
sys.path.insert(0, str(ROOT / "mcp_server"))

from eval.run_eval import load_runs  # noqa: E402
from server import mcp  # noqa: E402

VOLATILE = {"sql", "evidence_id", "elapsed_ms"}


def _canon(env: dict, sort_rows: bool) -> str:
    e = {k: v for k, v in env.items() if k not in VOLATILE}
    if sort_rows:
        e = {k: sorted(v, key=lambda r: json.dumps(r, sort_keys=True, default=str))
             if isinstance(v, list) and v and isinstance(v[0], dict) else v for k, v in e.items()}
    return json.dumps(e, sort_keys=True, default=str)


def _p(xs: list[float], q: float) -> float:
    xs = sorted(xs)
    return round(xs[min(len(xs) - 1, int(q * len(xs)))], 1)


async def main(path: str) -> int:
    _, runs = load_runs(path)
    calls = {}
    for out in runs.values():
        for ev in out.get("ledger", {}).values():
            calls.setdefault(json.dumps([ev["tool"], ev.get("params", {})], sort_keys=True, default=str), ev)
    stats, diffs = {}, []
    for key, rec in calls.items():
        tool, params = json.loads(key)
        t0 = time.perf_counter()
        res = await mcp.call_tool(tool, params)
        wall = (time.perf_counter() - t0) * 1000
        blocks = res[0] if isinstance(res, tuple) else res
        new = json.loads("".join(getattr(b, "text", "") for b in blocks))
        s = stats.setdefault(tool, {"calls": 0, "identical": 0, "same_rows": 0, "different": 0, "ms": [], "wall_ms": [], "rec_ms": []})
        s["calls"] += 1
        s["ms"].append(new.get("elapsed_ms") or wall)
        s["wall_ms"].append(wall)
        s["rec_ms"].append(rec.get("elapsed_ms") or 0)
        if _canon(new, False) == _canon(rec, False):
            s["identical"] += 1
        elif _canon(new, True) == _canon(rec, True):
            s["same_rows"] += 1
        else:
            s["different"] += 1
            changed = sorted(k for k in set(new) | set(rec) if k not in VOLATILE and new.get(k) != rec.get(k))
            diffs.append(f"{tool} {json.dumps(params, default=str)[:160]} → differs in {', '.join(changed)}")
    print(f"{len(calls)} distinct tool calls from {path}\n")
    print("| tool | calls | identical | same rows (order differs) | different | p50 ms | p95 ms | recorded p50 ms |")
    print("|---|---|---|---|---|---|---|---|")
    tot = {"calls": 0, "identical": 0, "same_rows": 0, "different": 0}
    for tool, s in sorted(stats.items()):
        print(f"| {tool} | {s['calls']} | {s['identical']} | {s['same_rows']} | {s['different']} | {_p(s['ms'], .5)} | "
              f"{_p(s['ms'], .95)} | {_p(s['rec_ms'], .5)} |")
        for k in tot:
            tot[k] += s[k]
    allms = [m for s in stats.values() for m in s["ms"]]
    print(f"| **all** | {tot['calls']} | {tot['identical']} | {tot['same_rows']} | {tot['different']} | {_p(allms, .5)} | "
          f"{_p(allms, .95)} | {_p([m for s in stats.values() for m in s['rec_ms']], .5)} |")
    print(f"\nmatch rate (identical or same rows): {(tot['identical'] + tot['same_rows']) / max(tot['calls'], 1):.1%} · "
          f"total tool time {round(sum(allms) / 1000, 2)} s (mean {round(statistics.mean(allms), 1)} ms)")
    for d in diffs:
        print("  ✗", d)
    return 1 if tot["different"] else 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main(sys.argv[1])))
