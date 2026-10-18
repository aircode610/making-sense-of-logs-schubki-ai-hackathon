"""Plan 012: hand our MCP server to Claude Code itself (headless) and ask benchmark questions, the way a user would.

Claude Code runs with ONLY the `logs` server (--strict-mcp-config, no built-in tools, --bare: no CLAUDE.md, hooks or
memory), so every step it takes goes through our tool descriptions and server instructions. Per question: the tool
calls it made, tool errors, the answer, and the golden facts found (same scoring as bench/tool_use.py).
  .venv/bin/python bench/claude_code_run.py --only T-B1,T-S1 [--model sonnet]
Writes bench/results/claude_code-<stamp>.json/.md (full transcripts in the .json).
"""
import argparse
import json
import os
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
import yaml

sys.path.insert(0, str(ROOT / "src/bench"))
from tool_use import DISCOVERY, facts, score_facts

DEFAULT = "T-B1,T-B6,T-O2,T-S1,T-Z3,T-A3,T-H1,T-T2,U-L1,U-H1"


def ask(question: str, model: str, cfg: str) -> dict:
    cmd = ["claude", "-p", question, "--bare", "--tools", "", "--mcp-config", cfg, "--strict-mcp-config",
           "--allowedTools", "mcp__logs__*", "--output-format", "stream-json", "--verbose", "--model", model,
           "--no-session-persistence", "--max-turns", "40"]
    t0 = time.perf_counter()
    with tempfile.TemporaryDirectory() as wd:  # empty working directory: nothing to read but the MCP tools
        p = subprocess.run(cmd, cwd=wd, capture_output=True, text=True, timeout=1200, env=os.environ.copy())
    events = [json.loads(x) for x in p.stdout.splitlines() if x.strip().startswith("{")]
    calls, errors, answer, usage = [], [], "", {}
    for e in events:
        msg = e.get("message") or {}
        for b in msg.get("content") or [] if isinstance(msg.get("content"), list) else []:
            if b.get("type") == "tool_use":
                calls.append({"name": b["name"].removeprefix("mcp__logs__"), "args": b.get("input")})
            if b.get("type") == "tool_result" and b.get("is_error"):
                errors.append(str(b.get("content"))[:300])
        if e.get("type") == "result":
            answer, usage = e.get("result") or "", e.get("usage") or {}
    return {"calls": calls, "errors": errors, "answer": answer, "usage": usage, "stderr": p.stderr[-2000:],
            "elapsed_s": round(time.perf_counter() - t0, 1), "events": events}


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--only", default=DEFAULT)
    ap.add_argument("--model", default="sonnet")
    a = ap.parse_args()
    qs = [q for q in yaml.safe_load(open(ROOT / "src/bench/tool_use_questions.yaml")) if q["id"] in a.only.split(",")]
    facts(qs)
    cfg = {"mcpServers": {"logs": {"command": str(ROOT / ".venv/bin/python"), "args": [str(ROOT / "src/mcp_server/server.py")],
                                   "cwd": str(ROOT)}}}
    with tempfile.NamedTemporaryFile("w", suffix=".json", delete=False) as f:
        json.dump(cfg, f)
    out = []
    for q in qs:
        r = ask(q["question"], a.model, f.name)
        names = [c["name"] for c in r["calls"]]
        first = next((n for n in names if n not in DISCOVERY), None)
        hits, n, miss = score_facts(q, r["answer"])
        out.append({"id": q["id"], "question": q["question"], **r, "first_tool": first, "first_ok": first in q["first"],
                    "need_ok": all(any(t in names for t in g) for g in q["need"]), "facts": hits, "facts_total": n,
                    "facts_missed": miss})
        print(f"{q['id']}: {len(names)} calls ({' '.join(names)}), errors {len(r['errors'])}, facts {hits}/{n}, "
              f"{r['elapsed_s']} s", flush=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    base = ROOT / "src/bench/results" / f"claude_code-{stamp}"
    base.with_suffix(".json").write_text(json.dumps(out, indent=1, default=str, ensure_ascii=False))
    ft = sum(r["facts_total"] for r in out)
    lines = [f"# Claude Code (headless, model {a.model}) with only the logs MCP server: {len(out)} questions\n",
             f"first tool ok {sum(r['first_ok'] for r in out)}/{len(out)}, required tools {sum(r['need_ok'] for r in out)}/"
             f"{len(out)}, facts {sum(r['facts'] for r in out)}/{ft}, tool errors {sum(len(r['errors']) for r in out)}, "
             f"calls/question {sum(len(r['calls']) for r in out) / len(out):.1f}\n",
             "| id | calls | errors | facts | tools |", "|---|---|---|---|---|"]
    lines += [f"| {r['id']} | {len(r['calls'])} | {len(r['errors'])} | {r['facts']}/{r['facts_total']} | "
              f"{' '.join(c['name'] for c in r['calls'])} |" for r in out]
    lines += ["", "## Answers", ""] + [f"### {r['id']}: {r['question']}\n\n{r['answer']}\n" for r in out]
    base.with_suffix(".md").write_text("\n".join(lines))
    print("\n".join(lines[:2]))
    print(f"wrote {base.relative_to(ROOT)}.json/.md")
    return 0


if __name__ == "__main__":
    sys.exit(main())
