"""Role-free MCP benchmark (plan 012): can a plain agent that has ONLY our MCP server answer free-form questions?

Same setup as handing the server to Claude Code: every tool, a one-line system prompt, no recipes, no roles. Per
question: first substantive tool (discovery tools skipped) in the acceptable set, required tool groups used, invalid
calls (tool errors), calls, tokens, time, and golden facts found in the answer (facts from hand-written SQL, run fresh).

  .venv/bin/python bench/tool_use.py --label before                     # Opus + Sonnet, all questions
  .venv/bin/python bench/tool_use.py --models anthropic:claude-sonnet-5-5 --only T-B1,T-S1 --label smoke
Writes bench/results/tool_use-<stamp>-<label>.json and .md.
"""
import argparse
import asyncio
import json
import statistics
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
import psycopg
import yaml
from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain.chat_models import init_chat_model
from langchain_core.callbacks import get_usage_metadata_callback
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient

from agent.run import MCP
from evals.metrics import golden_hits

MODELS = ["anthropic:claude-opus-5-5", "anthropic:claude-sonnet-5-5"]
DISCOVERY = {"describe_corpus", "list_values", "suggest_terms", "explain_search"}
SYSTEM = ("Answer the user's question about system logs using the tools of the `logs` server. Dig until the evidence "
          "answers the question, then reply concisely; copy numbers exactly from tool results.")
MAX_CALLS = 25


def facts(qs: list[dict]) -> None:
    """Run each fact's reference SQL now (golden values never go stale) → q['golden'] in eval.metrics format."""
    with psycopg.connect(host="localhost", port=7890, user="postgres", dbname="postgres", autocommit=True) as c:
        c.execute("SET sdb_scan_split = 'never'")
        for q in qs:
            q["golden"] = []
            for f in q.get("facts", []):
                v = f["value"] if "value" in f else c.execute(f["sql"]).fetchone()[0]
                q["golden"].append({"fact": f["fact"], "value": v, "match": f.get("match", "number")})


def score_facts(q: dict, answer: str) -> tuple[int, int, list[str]]:
    """evals.metrics.golden_hits, but a date fact counts when its day and its HH:MM both appear (answers write
    '2017-05-16 at 22:51' or '22:51:16 on 2017-05-16'; the strict rule penalized wording, not knowledge)."""
    strict = [g for g in q["golden"] if g["match"] != "date"]
    hits, _, miss = golden_hits({"golden": strict}, answer)
    for g in q["golden"]:
        if g["match"] == "date":
            day, _, hm = str(g["value"]).partition(" ")
            ok = day in answer and (not hm or hm in answer)
            hits += ok
            miss += [] if ok else [f"{g['fact']} = {g['value']}"]
    return hits, len(q["golden"]), miss


def _text(m: AIMessage) -> str:
    return m.content if isinstance(m.content, str) else "".join(
        b.get("text", "") for b in m.content if isinstance(b, dict) and b.get("type") == "text")


async def server_instructions() -> str:
    """The MCP server's `instructions` (initialize result), which clients such as Claude Code put in the model's
    context; passed the same way here so the benchmark sees what a real client sees."""
    async with MultiServerMCPClient(MCP).session("logs") as session:
        init = getattr(session, "_init_result", None)
        if init is None:  # langchain-mcp-adapters keeps no handle: ask the server module directly
            import importlib
            sys.path.insert(0, str(ROOT / "src/mcp_server"))
            return importlib.import_module("server").mcp.instructions or ""
        return init.instructions or ""


async def run_one(q: dict, model_name: str, tools, sem, system: str) -> dict:
    async with sem:
        agent = create_agent(init_chat_model(model_name, max_tokens=8000), tools, system_prompt=system,
                             middleware=[ToolCallLimitMiddleware(run_limit=MAX_CALLS)])
        t0 = time.perf_counter()
        try:
            with get_usage_metadata_callback() as cb:
                state = await agent.ainvoke({"messages": [HumanMessage(q["question"])]}, config={"recursion_limit": 80})
            err = None
        except Exception as e:  # noqa: BLE001 (a crashed run scores 0)
            state, err, cb = {"messages": []}, f"{type(e).__name__}: {e}"[:500], None
        msgs = state["messages"]
        calls = [{"name": tc["name"], "args": tc["args"]} for m in msgs if isinstance(m, AIMessage) for tc in m.tool_calls]
        errors = [{"name": m.name, "error": str(m.content)[:300]} for m in msgs
                  if isinstance(m, ToolMessage) and (m.status == "error" or str(m.content).startswith("Error"))]
        answer = next((_text(m) for m in reversed(msgs) if isinstance(m, AIMessage) and _text(m)), "")
        usage = (cb.usage_metadata if cb else {}) or {}
        names = [c["name"] for c in calls]
        first = next((n for n in names if n not in DISCOVERY), None)
        hits, n, miss = score_facts(q, answer)
        return {"id": q["id"], "dataset": q.get("dataset"), "model": model_name, "question": q["question"],
                "answer": answer, "calls": calls, "errors": errors, "run_error": err,
                "first_tool": first, "first_ok": first in q["first"],
                "need_ok": all(any(t in names for t in g) for g in q["need"]),
                "facts": hits, "facts_total": n, "facts_missed": miss,
                "n_calls": len(calls), "n_errors": len(errors),
                "tokens_in": sum(v.get("input_tokens", 0) for v in usage.values()),
                "tokens_out": sum(v.get("output_tokens", 0) for v in usage.values()),
                "elapsed_s": round(time.perf_counter() - t0, 1)}


def summary(rs: list[dict]) -> dict:
    ft = sum(r["facts_total"] for r in rs)
    return {"questions": len(rs), "first_ok": round(sum(r["first_ok"] for r in rs) / len(rs), 3),
            "need_ok": round(sum(r["need_ok"] for r in rs) / len(rs), 3),
            "facts": round(sum(r["facts"] for r in rs) / ft, 3) if ft else None,
            "errors_per_q": round(sum(r["n_errors"] for r in rs) / len(rs), 2),
            "calls_per_q": round(statistics.mean(r["n_calls"] for r in rs), 1),
            "tokens_in_per_q": int(statistics.mean(r["tokens_in"] for r in rs)),
            "seconds_per_q": round(statistics.mean(r["elapsed_s"] for r in rs), 1),
            "crashed": sum(bool(r["run_error"]) for r in rs)}


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--models", default=",".join(MODELS))
    ap.add_argument("--only", help="comma-separated question ids")
    ap.add_argument("--questions", default=str(ROOT / "src/bench/tool_use_questions.yaml"))
    ap.add_argument("--label", default="run")
    ap.add_argument("--parallel", type=int, default=4)
    ap.add_argument("--rescore", help="re-score a saved results .json with the current facts (no agent runs)")
    ap.add_argument("--no-instructions", action="store_true", help="do not pass the server instructions (as before plan 012)")
    a = ap.parse_args()
    qs = yaml.safe_load(open(a.questions))
    if a.only:
        qs = [q for q in qs if q["id"] in a.only.split(",")]
    facts(qs)
    if a.rescore:
        old = json.load(open(a.rescore))
        byid = {q["id"]: q for q in qs}
        results = [r for r in old["results"] if r["id"] in byid]
        for r in results:
            q = byid[r["id"]]
            r["facts"], r["facts_total"], r["facts_missed"] = score_facts(q, r["answer"])
            r["first_ok"], r["need_ok"] = r["first_tool"] in q["first"], all(
                any(t in [c["name"] for c in r["calls"]] for t in g) for g in q["need"])
        a.models = ",".join(dict.fromkeys(r["model"] for r in results))
        a.label = a.label if a.label != "run" else old["label"] + "-rescored"
    else:
        tools = await MultiServerMCPClient(MCP).get_tools()
        system = SYSTEM if a.no_instructions else SYSTEM + "\n\n<server name=\"logs\">\n" + await server_instructions() + "\n</server>"
        sem = asyncio.Semaphore(a.parallel)
        results = await asyncio.gather(*[run_one(q, m, tools, sem, system) for m in a.models.split(",") for q in qs])

    out = ROOT / "src/bench/results" / f"tool_use-{datetime.now():%Y%m%d-%H%M%S}-{a.label}"
    out.parent.mkdir(parents=True, exist_ok=True)
    by_model = {m: summary([r for r in results if r["model"] == m]) for m in a.models.split(",")}
    out.with_suffix(".json").write_text(json.dumps({"label": a.label, "summary": by_model, "results": results},
                                                   indent=1, default=str, ensure_ascii=False))
    lines = [f"# Tool-use benchmark: {a.label} ({len(qs)} questions)\n", "| model | " + " | ".join(next(iter(by_model.values()))) + " |",
             "|---" * (1 + len(next(iter(by_model.values())))) + "|"]
    lines += [f"| {m} | " + " | ".join(str(v) for v in s.values()) + " |" for m, s in by_model.items()]
    lines += ["", "| id | model | first | first ok | need ok | facts | calls | errors | tools |", "|---" * 9 + "|"]
    lines += [f"| {r['id']} | {r['model'].split('-')[-3]} | {r['first_tool']} | {int(r['first_ok'])} | {int(r['need_ok'])} | "
              f"{r['facts']}/{r['facts_total']} | {r['n_calls']} | {r['n_errors']} | {' '.join(c['name'] for c in r['calls'])} |"
              for r in results]
    out.with_suffix(".md").write_text("\n".join(lines) + "\n")
    print("\n".join(lines[:3 + len(by_model)]))
    print(f"\nwrote {out.relative_to(ROOT)}.json/.md")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
