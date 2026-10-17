"""Ask the agent a question. One LangSmith trace per question (named, tagged, with metadata and the check results).

  .venv/bin/python -m agent.run --role engineer "What failed on R43-M0-NC-I:J18-U01 around 2005-08-19 13:56?"
  .venv/bin/python -m agent.run "Which problems recurred most in November 2005, and who owns them?"   # Jev picks the role
  .venv/bin/python -m agent.run --baseline --role manager "What should we prioritise?"            # reference ReAct agent

Prints the answer card (Markdown) and the trace URL; saves card + check + ledger to runs/agent/<time>-<role>.json.
"""
import argparse
import asyncio
import json
import os
import subprocess
import sys
import time
import uuid
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tracers.langchain import wait_for_all_tracers
from langchain_mcp_adapters.client import MultiServerMCPClient
from langsmith import traceable
from langsmith.run_helpers import get_current_run_tree

from agent.card import render
from agent.graph import build_baseline, build_graph, parse_envelope

MCP = {"logs": {"transport": "stdio", "command": str(ROOT / ".venv/bin/python"),
                "args": [str(ROOT / "mcp_server/server.py")], "cwd": str(ROOT)}}


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return "unknown"


def _annotate(**meta) -> str | None:
    """Attach metadata to the current LangSmith run (no-op when tracing is off); returns the trace URL."""
    rt = get_current_run_tree()
    if rt is None:
        return None
    rt.metadata.update(meta)
    try:
        return rt.get_url()
    except Exception:  # noqa: BLE001 (URL is a convenience)
        return None


@traceable(name="ask", run_type="chain")
async def ask(question: str, role: str | None, tools, run_id: str) -> dict:
    graph = build_graph(tools)
    t0 = time.perf_counter()
    state = await graph.ainvoke(
        {"question": question, "role": role, "messages": [HumanMessage(question)]},
        config={"run_name": "logs-agent", "recursion_limit": 60,
                "tags": ["ours", role or "routed"], "metadata": {"question": question, "run": run_id}},
    )
    check = state["check"]
    url = _annotate(role=state["role"], route=state["route"], tool_calls=state.get("tool_calls", 0),
              evidence_ids=list(state.get("ledger", {})), numbers_total=check["numbers_total"],
              numbers_verified=check["numbers_verified"], confidence=check["confidence"], passed=check["passed"],
              revisions=state.get("revisions", 0), nudges=state.get("nudges", 0),
              elapsed_s=round(time.perf_counter() - t0, 1))
    return {"role": state["role"], "route": state["route"], "card": state["card"], "check": check, "trace": url,
            "ledger": state.get("ledger", {}), "tool_calls": state.get("tool_calls", 0),
            "elapsed_s": round(time.perf_counter() - t0, 1)}


@traceable(name="ask-baseline", run_type="chain")
async def ask_baseline(question: str, role: str, tools, run_id: str) -> dict:
    agent = build_baseline(tools, role)
    t0 = time.perf_counter()
    state = await agent.ainvoke({"messages": [HumanMessage(question)]},
                                config={"run_name": "baseline-react", "recursion_limit": 40,
                                        "tags": ["baseline", role], "metadata": {"question": question, "run": run_id}})
    ledger = {env["evidence_id"]: env for m in state["messages"] if isinstance(m, ToolMessage)
              for env in [parse_envelope(m)] if env}
    final = next(m for m in reversed(state["messages"]) if isinstance(m, AIMessage))
    text = final.content if isinstance(final.content, str) else "".join(
        b.get("text", "") for b in final.content if isinstance(b, dict))
    url = _annotate(role=role, tool_calls=len(ledger), evidence_ids=list(ledger), elapsed_s=round(time.perf_counter() - t0, 1))
    return {"role": role, "answer": text, "trace": url, "ledger": ledger, "tool_calls": len(ledger),
            "elapsed_s": round(time.perf_counter() - t0, 1)}


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("question")
    ap.add_argument("--role", choices=["engineer", "lead", "manager"], help="omit to let Jev route the question")
    ap.add_argument("--baseline", action="store_true", help="run the reference ReAct agent instead (needs --role)")
    a = ap.parse_args()
    if a.baseline and not a.role:
        ap.error("--baseline needs --role")

    tools = await MultiServerMCPClient(MCP).get_tools()
    run_id = uuid.uuid4().hex[:8]
    kind = "baseline" if a.baseline else "ours"
    extra = {"name": f"{kind}:{a.role or 'routed'}", "tags": [kind, a.role or "routed", os.getenv("AGENT_MODEL", "")],
             "metadata": {"question": a.question, "model": os.getenv("AGENT_MODEL"), "git": git_sha(), "run": run_id},
             "run_id": uuid.uuid4()}
    if a.baseline:
        out = await ask_baseline(a.question, a.role, tools, run_id, langsmith_extra=extra)
        print(out["answer"])
    else:
        out = await ask(a.question, a.role, tools, run_id, langsmith_extra=extra)
        print(render(out["card"], out["check"], out["ledger"], out["role"]))
        print(f"\nrole: {out['role']} ({out['route'].get('source')}) · tool calls {out['tool_calls']} · "
              f"{out['elapsed_s']} s · checker {'passed' if out['check']['passed'] else 'FAILED: ' + json.dumps(out['check']['unverified'])[:300]}")

    path = ROOT / "runs/agent" / f"{datetime.now():%Y%m%d-%H%M%S}-{kind}-{out['role']}.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps({"question": a.question, "kind": kind, **out}, default=str, indent=1, ensure_ascii=False))
    print(f"saved {path.relative_to(ROOT)}")

    if os.getenv("LANGSMITH_TRACING", "").lower() == "true":
        wait_for_all_tracers()  # flush before exit so the trace is complete
        print("trace:", out.get("trace") or "(tracing on, url unavailable)")
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
