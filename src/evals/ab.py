"""Blind A/B of the toolsets (plan 013): the same agent run twice per question, differing only in its MCP tools.

  old = per-role subsets of the 8 plan-010 tools (agent.graph.OLD_ROLE_TOOLS)
  new = the current per-role subsets (agent.graph.ROLE_TOOLS)
Both arms: same graph, model, composer, checker, budgets and the same tool-neutral prompt (prompts.NEUTRAL_RECIPES).

Judge = an agent (JUDGE_MODEL) with a read-only `sql` tool (DB role logs_manager: SELECT only, no labels table) that
grades both answers against the question's frozen answer key (eval/answer_keys/<id>.yaml), verifying key claims with
SQL. Blind: both answers as the same plain text, tool names → [tool], no evidence ids / check footer, X/Y random per
question (seeded), asked in both orders by fresh judge agents; only order-consistent wins count. A leak scan stops the
run if any tool name or evidence id reaches the judge.

  .venv/bin/python -m evals.ab --ids D-E01,D-L04          # smoke
  .venv/bin/python -m evals.ab                            # all questions in eval/dev_questions.yaml
  .venv/bin/python -m evals.ab --arms new,old --reuse <runs.json> --reuse-arm new   # B from an earlier run
  .venv/bin/python -m evals.ab --rejudge eval/results/ab-<t>.runs.json   # re-judge stored answers (no agent runs)
Plan 014: every question runs on an MCP server pinned to its dataset (LOGS_DATASET), as a user runs it on their own
logs; --unpinned restores the plan-013 multi-dataset setting.
Performance (per run): wall = llm + tool + other, from callback intervals (parallel calls merged, not summed):
llm = a model call in flight; tool = a tool call in flight while no model call is (client side, incl. MCP transport);
other = graph / Python. tool_db = the tools' own server-side elapsed_ms (SereneDB + tool code) and per-tool calls / ms.
The two arms of a question run one after the other (random order); --concurrency 1 for the cleanest timings.
Writes eval/results/ab-<time>.md / .json (scores, judge reasons, X/Y mapping) / .runs.json (answers + evidence).
"""
import argparse
import asyncio
import json
import os
import random
import re
import statistics
import sys
import threading
import time
from datetime import datetime
from pathlib import Path
from typing import Literal

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import psycopg
import yaml
from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain.chat_models import init_chat_model
from langchain_core.callbacks import AsyncCallbackHandler, get_usage_metadata_callback
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from pydantic import BaseModel, Field

from agent import prompts
from agent.graph import OLD_ROLE_TOOLS, ROLE_TOOLS, build_baseline, build_graph, gather_system, parse_envelope
from agent.run import mcp_config
from evals.judge import JUDGE_MODEL, ROLE_NEEDS
from evals.metrics import answer_text_from_card, golden_hits

# Arm = (tool subsets, recipes, neutral prompt). Plan 014: arms run on a server pinned to the question's dataset.
ARM_DEFS = {
    "new": (ROLE_TOOLS, prompts.NEUTRAL_RECIPES, True),           # current tools, tool-neutral prompt (plan 013 arm)
    "old": (OLD_ROLE_TOOLS, prompts.NEUTRAL_RECIPES, True),       # plan-010 tools, same prompt
    "product": (ROLE_TOOLS, prompts.RECIPES, False),              # current tools with the product recipes
    "baseline": (None, None, False),                              # the brief's reference ReAct agent, every tool (plan 017)
}
ARMS = ("new", "old")   # set from --arms in main(); first = A, second = B
KEYS = ROOT / "eval/answer_keys"
JUDGE_SQL_CALLS = 15
SQL_ROWS, SQL_TIMEOUT_S = 200, 60


# ---------------------------------------------------------------- arms

def _tokens(cb) -> tuple[int, int]:
    u = cb.usage_metadata.values()
    return sum(x.get("input_tokens", 0) for x in u), sum(x.get("output_tokens", 0) for x in u)


class Timer(AsyncCallbackHandler):
    """Wall-clock intervals of every LLM call and tool call in one run (parallel calls overlap, so totals are interval
    unions, not sums). Split: llm = any model call in flight; tool = a tool in flight while no model call is."""

    def __init__(self):
        self.open: dict = {}
        self.spans: dict[str, list] = {"llm": [], "tool": []}

    def _start(self, kind, run_id):
        self.open[run_id] = (kind, time.perf_counter())

    def _end(self, run_id):
        if run_id in self.open:
            kind, t = self.open.pop(run_id)
            self.spans[kind].append((t, time.perf_counter()))

    async def on_chat_model_start(self, serialized, messages, *, run_id, **kw):
        self._start("llm", run_id)

    async def on_llm_start(self, serialized, prompts, *, run_id, **kw):
        self._start("llm", run_id)

    async def on_llm_end(self, response, *, run_id, **kw):
        self._end(run_id)

    async def on_llm_error(self, error, *, run_id, **kw):
        self._end(run_id)

    async def on_tool_start(self, serialized, input_str, *, run_id, **kw):
        self._start("tool", run_id)

    async def on_tool_end(self, output, *, run_id, **kw):
        self._end(run_id)

    async def on_tool_error(self, error, *, run_id, **kw):
        self._end(run_id)


def _union(spans: list) -> list:
    out = []
    for a, b in sorted(spans):
        if out and a <= out[-1][1]:
            out[-1][1] = max(out[-1][1], b)
        else:
            out.append([a, b])
    return out


def _length(spans: list) -> float:
    return sum(b - a for a, b in spans)


def timing(t: Timer, wall: float, ledger: dict) -> dict:
    """llm_s + tool_s + other_s = wall_s. tool_db_s = the tools' own server-side elapsed_ms (SereneDB + Python, no
    transport). per_tool = calls and server ms by tool name."""
    llm = _union(t.spans["llm"])
    tool_all = _union(t.spans["tool"])
    tool_only = _length(tool_all) - _length(_union([[max(a, c), min(b, d)] for a, b in tool_all for c, d in llm
                                                     if min(b, d) > max(a, c)]))
    per_tool: dict = {}
    for ev in ledger.values():
        d = per_tool.setdefault(ev.get("tool", "?"), {"calls": 0, "db_ms": 0.0})
        d["calls"] += 1
        d["db_ms"] = round(d["db_ms"] + (ev.get("elapsed_ms") or 0), 1)
    return {"wall_s": round(wall, 2), "llm_s": round(_length(llm), 2), "tool_s": round(tool_only, 2),
            "other_s": round(wall - _length(llm) - tool_only, 2), "tool_calls_wall_s": round(_length(tool_all), 2),
            "tool_db_s": round(sum(ev.get("elapsed_ms") or 0 for ev in ledger.values()) / 1000, 2),
            "llm_calls": len(t.spans["llm"]), "per_tool": per_tool}


async def run_baseline(agent, q: dict) -> dict:
    """The reference ReAct agent: free-text answer, ledger = every tool envelope it received."""
    t0 = time.perf_counter()
    tm = Timer()
    try:
        with get_usage_metadata_callback() as cb:
            s = await agent.ainvoke({"messages": [HumanMessage(q["question"])]}, config={"recursion_limit": 40, "callbacks": [tm]})
        tin, tout = _tokens(cb)
        wall = time.perf_counter() - t0
        ledger = {env["evidence_id"]: env for m in s["messages"] if isinstance(m, ToolMessage)
                  for env in [parse_envelope(m)] if env}
        final = next(m for m in reversed(s["messages"]) if isinstance(m, AIMessage))
        text = final.content if isinstance(final.content, str) else "".join(
            b.get("text", "") for b in final.content if isinstance(b, dict))
        return {"text": text, "ledger": ledger, "tools_used": [m.name for m in s["messages"] if isinstance(m, ToolMessage)],
                "elapsed_s": round(wall, 1), "tokens_in": tin, "tokens_out": tout, "timing": timing(tm, wall, ledger)}
    except Exception as e:  # noqa: BLE001
        return {"text": "", "error": f"{type(e).__name__}: {e}"[:500], "elapsed_s": round(time.perf_counter() - t0, 1)}


async def run_arm(graph, q: dict) -> dict:
    if isinstance(graph, tuple):                                   # ("baseline", agent)
        return await run_baseline(graph[1], q)
    t0 = time.perf_counter()
    tm = Timer()
    try:
        with get_usage_metadata_callback() as cb:
            s = await graph.ainvoke({"question": q["question"], "role": q["role"], "messages": [HumanMessage(q["question"])]},
                                    config={"recursion_limit": 60, "callbacks": [tm]})
        tin, tout = _tokens(cb)
        wall = time.perf_counter() - t0
        return {"text": answer_text_from_card(s["card"]), "card": s["card"], "check": s["check"],
                "ledger": s.get("ledger", {}), "tools_used": s.get("tools_used", []),
                "elapsed_s": round(wall, 1), "tokens_in": tin, "tokens_out": tout,
                "timing": timing(tm, wall, s.get("ledger", {}))}
    except Exception as e:  # noqa: BLE001  (a failed run loses the comparison; recorded, not hidden)
        return {"text": "", "error": f"{type(e).__name__}: {e}"[:500], "elapsed_s": round(time.perf_counter() - t0, 1)}


# ---------------------------------------------------------------- blinding

def _tool_re(n: str) -> str:
    """Tool names with '_' anywhere; one-word names (trend, spread, facet ...) only in code form: `trend` or trend(."""
    if "_" in n:
        return rf"`?(?<![\w-]){re.escape(n)}(?![\w-])`?"
    return rf"`{re.escape(n)}`|(?<![\w-]){re.escape(n)}(?=\()"


def blind(text: str, tool_names: set[str], tool_titles: set[str]) -> str:
    for n in sorted(tool_names, key=len, reverse=True):
        text = re.sub(_tool_re(n), "[tool]", text, flags=re.I)
    for t in tool_titles:
        text = text.replace(t, "[tool]")
    text = re.sub(r"\s*`?\[(?:\s*ev-[\w-]+\s*,?)+\]`?", "", text)       # citation groups [ev-1, ev-2]
    return re.sub(r"`?\bev-[\w-]+`?", "", text)


def leaks(text: str, tool_names: set[str]) -> list[str]:
    hits = [n for n in tool_names if re.search(_tool_re(n), text, re.I)]
    return hits + (["evidence id"] if re.search(r"\bev-[\w-]+", text) else [])


# ---------------------------------------------------------------- judge

def _sql(query: str) -> str:
    q = query.strip().rstrip(";")
    if ";" in q or not re.match(r"(?is)^\s*(select|with)\b", q):
        return "refused: one SELECT or WITH statement only"
    conn = psycopg.connect(host=os.getenv("PGHOST", "localhost"), port=os.getenv("PGPORT", "7890"),
                           user=os.getenv("PGUSER", "postgres"), dbname=os.getenv("PGDATABASE", "postgres"), autocommit=True)
    timer = threading.Timer(SQL_TIMEOUT_S, conn.cancel)
    try:
        conn.execute("SET ROLE logs_manager")      # database-enforced read-only (load/99_roles.py)
        conn.execute("SET sdb_scan_split = 'never'")
        timer.start()
        cur = conn.execute(q)
        cols = [d.name for d in cur.description or []]
        rows = cur.fetchmany(SQL_ROWS + 1)
        out = {"columns": cols, "rows": [list(map(str, r)) for r in rows[:SQL_ROWS]], "truncated": len(rows) > SQL_ROWS}
        return json.dumps(out)[:20000]
    except Exception as e:  # noqa: BLE001
        return f"error: {type(e).__name__}: {str(e)[:400]}"
    finally:
        timer.cancel()
        conn.close()


@tool
async def sql(query: str) -> str:
    """Run ONE read-only SELECT / WITH query on the log database and get up to 200 rows back (truncated flag says if
    there were more). Tables: logs (dataset, line_id, ts, component, severity, node, location, request_id, object_id,
    status, duration_ms, body, pattern_id; full-text: body @@ websearch_to_tsquery('...')), ownership, patterns,
    pattern_templates, bursts, episodes, datasets. Always filter logs on dataset and a time range or id (large tables,
    hdfs has 11M lines). 60 s timeout."""
    return await asyncio.to_thread(_sql, query)


class AnswerGrade(BaseModel):
    claims_correct: int = Field(ge=0, description="Key claims of this answer that the answer key or your SQL confirms.")
    claims_wrong: int = Field(ge=0, description="Claims the key or your SQL contradicts (wrong number, wrong owner, "
                                                "wrong scope, a cause stated as fact, accepting a false premise).")
    claims_unverifiable: int = Field(ge=0, description="Factual claims neither the key nor your SQL can settle.")
    wrong_claims: list[str] = Field(description="Each wrong claim, quoted, with why it is wrong.")
    found_problem: int = Field(ge=0, le=2, description="0 = missed the real answer in the key (or accepted a false "
                                                       "premise); 1 = partly; 2 = reached the key's answer_summary.")
    role_fit: int = Field(ge=1, le=5)
    next_step: int = Field(ge=1, le=5)
    evidence_use: int = Field(ge=1, le=5)
    separation: int = Field(ge=1, le=5, description="facts / hypotheses / unknowns separated and labelled")
    clarity: int = Field(ge=1, le=5)


class Verdict(BaseModel):
    x: AnswerGrade
    y: AnswerGrade
    winner: Literal["X", "Y", "tie"]
    reasons: str = Field(description="3-6 sentences: what decided it, referring to the key and your queries.")


def judge_system(role: str) -> str:
    return (f"You are an expert log investigator grading two answers (X and Y) to the same question, written for a "
            f"{role.upper()} who needs to {ROLE_NEEDS[role]}\n\nYou get the question's ANSWER KEY: the true answer, "
            "established beforehand with SQL over the full logs and ground-truth labels. Treat the key as the truth; "
            "its `judging` field (if any) and its notes on accepted readings override your own view. A golden value "
            "computed by a ranking tool is not truth: grade substance (right problem, owner, scope), not exact order "
            "or wording. Any reading of an ambiguous window or definition that an answer states explicitly is fine.\n\n"
            f"Use the sql tool (at most {JUDGE_SQL_CALLS} queries) to verify the answers' key claims that the key does "
            "not already settle, especially numbers and claims the key does not mention. Then grade each answer and "
            "pick the one that serves this person better: correct against the key, reaches the real problem, grounded, "
            "honest about unknowns, avoids the key's traps, useful next step. Ignore length, style and formatting. "
            "Lines are not incidents. Inventing money, downtime or customer impact is wrong.\n\nThe order of X and Y "
            "is random and means nothing. Pick X or Y only when one is clearly better on correctness against the key "
            "(wrong claims, found_problem) or on what this role needs; if they differ only in minor details or style, "
            "answer tie.")


async def compare(q: dict, key_text: str, a: str, b: str, model) -> dict:
    agent = create_agent(model, [sql], system_prompt=judge_system(q["role"]), response_format=Verdict,
                         middleware=[ToolCallLimitMiddleware(run_limit=JUDGE_SQL_CALLS)], name="ab-judge")
    msg = (f"Dataset: {q['dataset']}\nQuestion: {q['question']}\n\nANSWER KEY (YAML):\n{key_text}\n\n"
           f"ANSWER X:\n{a}\n\nANSWER Y:\n{b}")
    s = await agent.ainvoke({"messages": [HumanMessage(msg)]}, config={"recursion_limit": 2 * JUDGE_SQL_CALLS + 10})
    v: Verdict = s["structured_response"]
    return {**v.model_dump(), "sql_calls": sum(1 for m in s["messages"] if getattr(m, "type", "") == "tool")}


async def judge_pair(q: dict, texts: dict, seed: int, model) -> dict:
    """texts = {arm_a: blinded, arm_b: blinded}. Order 1: X/Y random (seeded); order 2: swapped."""
    rnd = random.Random(f"{seed}-{q['id']}")
    a, b = list(texts)
    first = rnd.choice([b, a])
    order = [first, a if first == b else b]                      # order[0] is X in round 1
    key_text = (KEYS / f"{q['id']}.yaml").read_text()
    r1, r2 = await asyncio.gather(compare(q, key_text, texts[order[0]], texts[order[1]], model),
                                  compare(q, key_text, texts[order[1]], texts[order[0]], model))
    pick = lambda r, xy: {"X": xy[0], "Y": xy[1], "tie": "tie"}[r["winner"]]  # noqa: E731
    w1, w2 = pick(r1, order), pick(r2, order[::-1])
    grades = {order[0]: [r1["x"], r2["y"]], order[1]: [r1["y"], r2["x"]]}
    return {"x_in_round1": order[0], "round1": r1, "round2": r2, "winner1": w1, "winner2": w2,
            "result": w1 if w1 == w2 else "inconsistent", "grades": grades}


# ---------------------------------------------------------------- report

RUBRIC = ("role_fit", "next_step", "evidence_use", "separation", "clarity")


def arm_stats(rows: list[dict], arm: str) -> dict:
    g = [x for r in rows if r.get("judge") for x in r["judge"]["grades"][arm]]
    runs = [r["runs"][arm] for r in rows]
    ok = [x for x in runs if not x.get("error")]
    tm = [x for x in ok if x.get("timing")]
    mean = lambda xs: round(statistics.mean(xs), 3) if xs else None  # noqa: E731
    c, w = sum(x["claims_correct"] for x in g), sum(x["claims_wrong"] for x in g)
    return {"runs": len(runs), "failed": len(runs) - len(ok),
            "claim_accuracy": round(c / (c + w), 3) if c + w else None, "claims_wrong": w,
            "found_problem": mean([x["found_problem"] for x in g]),
            "rubric": mean([statistics.mean(x[k] for k in RUBRIC) for x in g]),
            "E1": mean([r["E1"][arm] for r in rows if r["E1"][arm] is not None]),
            "tool_calls": mean([len(x["tools_used"]) for x in ok]), "llm_calls": mean([x["timing"]["llm_calls"] for x in tm]),
            "wall_s": mean([x["timing"]["wall_s"] for x in tm]), "llm_s": mean([x["timing"]["llm_s"] for x in tm]),
            "tool_s (client, not overlapping llm)": mean([x["timing"]["tool_s"] for x in tm]),
            "other_s": mean([x["timing"]["other_s"] for x in tm]),
            "tool_db_s (server)": mean([x["timing"]["tool_db_s"] for x in tm]),
            "db_ms per tool call": round(1000 * sum(x["timing"]["tool_db_s"] for x in tm)
                                         / max(1, sum(sum(v["calls"] for v in x["timing"]["per_tool"].values()) for x in tm)), 1),
            "tokens_in": mean([x["tokens_in"] for x in ok]), "tokens_out": mean([x["tokens_out"] for x in ok])}


def per_tool_table(rows: list[dict]) -> list[dict]:
    """Calls, total and median server ms per tool name and arm (same tool in both arms = same code: compare counts)."""
    acc: dict = {}
    for r in rows:
        for arm in ARMS:
            for ev in (r["runs"][arm].get("ledger") or {}).values():
                acc.setdefault((ev.get("tool", "?"), arm), []).append(ev.get("elapsed_ms") or 0)
    return sorted([{"tool": t, "arm": arm, "calls": len(v), "total_s": round(sum(v) / 1000, 2),
                    "median_ms": round(statistics.median(v), 1), "max_ms": round(max(v), 1)}
                   for (t, arm), v in acc.items()], key=lambda d: (-d["total_s"], d["tool"]))


def tally(rows: list[dict]) -> dict:
    t = {ARMS[0]: 0, ARMS[1]: 0, "tie": 0, "inconsistent": 0}
    for r in rows:
        if r.get("judge"):
            t[r["judge"]["result"]] += 1
    return t


def tsplit(run: dict) -> str:
    t = run.get("timing")
    return f"{t['wall_s']} / {t['llm_s']} / {t['tool_s']}" if t else "-"


def render_md(rep: dict) -> str:
    rows, A, B = rep["rows"], ARMS[0], ARMS[1]
    L = [f"# A/B: {A} vs {B} — {rep['stamp']}", "",
         f"git {rep['git']} · agent {rep['agent_model']} · judge {rep['judge_model']} · seed {rep['seed']} · "
         f"{len(rows)} questions · server pinned to each question's dataset: {rep.get('pinned')} · "
         f"prompts identical across arms: {rep['prompts_identical']} · leaks: {rep['leaks'] or 'none'}"
         + (f" · {B} answers reused from {rep['reuse']}" if rep.get("reuse") else ""),
         "", "## Wins (order-consistent only)", "", f"| slice | {A} | {B} | tie | inconsistent |", "|---|---|---|---|---|"]
    t = tally(rows)
    L.append(f"| all | {t[A]} | {t[B]} | {t['tie']} | {t['inconsistent']} |")
    for dim in ("role", "dataset"):
        for v in sorted({r[dim] for r in rows}):
            t = tally([r for r in rows if r[dim] == v])
            L.append(f"| {dim} {v} | {t[A]} | {t[B]} | {t['tie']} | {t['inconsistent']} |")
    L += ["", "## Per arm", "", f"| metric | {A} | {B} |", "|---|---|---|"]
    for k in rep["arms"][A]:
        L.append(f"| {k} | {rep['arms'][A][k]} | {rep['arms'][B].get(k)} |")
    L += ["", "## Where the time goes (mean seconds per run; llm + tool + other = wall)", "",
          "| arm | wall | llm | tool (client) | other | tool db (server) | tool calls | llm calls |", "|---|---|---|---|---|---|---|---|"]
    for arm in (A, B):
        m = rep["arms"][arm]
        L.append(f"| {arm} | {m['wall_s']} | {m['llm_s']} | {m['tool_s (client, not overlapping llm)']} | {m['other_s']} | "
                 f"{m['tool_db_s (server)']} | {m['tool_calls']} | {m['llm_calls']} |")
    L += ["", "## Tool time by tool (server-side elapsed_ms)", "", "| tool | arm | calls | total s | median ms | max ms |",
          "|---|---|---|---|---|---|"]
    L += [f"| {d['tool']} | {d['arm']} | {d['calls']} | {d['total_s']} | {d['median_ms']} | {d['max_ms']} |" for d in rep["per_tool"]]
    L += ["", "## Per question", "", f"| id | role | dataset | result | {A} found / wrong | {B} found / wrong | {A} tools | {B} tools | "
          f"{A} wall / llm / tool s | {B} wall / llm / tool s |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        j = r.get("judge") or {}
        f = lambda a: "/".join(str(sum(g[k] for g in j["grades"][a])) for k in ("found_problem", "claims_wrong")) if j else "-"  # noqa: E731
        L.append(f"| {r['id']} | {r['role']} | {r['dataset']} | {j.get('result', 'not judged')} | {f(A)} | {f(B)} | "
                 f"{len(r['runs'][A].get('tools_used', []))} | {len(r['runs'][B].get('tools_used', []))} | "
                 f"{tsplit(r['runs'][A])} | {tsplit(r['runs'][B])} |")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- main

async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--questions", default=str(ROOT / "eval/dev_questions.yaml"))
    ap.add_argument("--ids", help="comma-separated question ids")
    ap.add_argument("--concurrency", type=int, default=3, help="questions in flight (each = 2 agent runs + 2 judges)")
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--arms", default="new,old", help=f"two of {sorted(ARM_DEFS)}: A,B (B may be reused, see --reuse)")
    ap.add_argument("--reuse", metavar="RUNS_JSON", help="take arm B's answers from an earlier run (its arm named --reuse-arm)")
    ap.add_argument("--reuse-arm", default=None, help="arm name inside RUNS_JSON to use as B (default: B's name)")
    ap.add_argument("--rejudge", metavar="RUNS_JSON", help="judge stored answers of BOTH arms (no agent runs)")
    ap.add_argument("--unpinned", action="store_true", help="multi-dataset server (plan 013 setting) instead of pinned")
    ap.add_argument("--no-judge", action="store_true")
    a = ap.parse_args()
    global ARMS
    ARMS = tuple(a.arms.split(","))
    assert len(ARMS) == 2 and all(x in ARM_DEFS for x in ARMS), f"--arms: two of {sorted(ARM_DEFS)}"
    qs = yaml.safe_load(Path(a.questions).read_text())
    if a.ids:
        keep = set(a.ids.split(","))
        qs = [q for q in qs if q["id"] in keep]
    missing = [q["id"] for q in qs if not (KEYS / f"{q['id']}.yaml").exists()]
    if missing:
        sys.exit(f"no answer key for {missing}")

    # Plan 014: one MCP server per dataset, pinned to it (how a user runs it on their own logs)
    datasets = sorted({q["dataset"] for q in qs})
    toolsets = {}
    for ds in ([None] if a.unpinned else datasets):
        toolsets[ds] = await MultiServerMCPClient(mcp_config(ds)).get_tools()
    tools_for = (lambda ds: toolsets[None]) if a.unpinned else (lambda ds: toolsets[ds])  # noqa: E731
    names = {t.name for ts in toolsets.values() for t in ts}
    titles = {t.description.split("\n")[0].strip().rstrip("?.") for ts in toolsets.values() for t in ts if t.description} - {""}
    titles = {x for x in titles if len(x) > 25}                        # long first lines only (not common words)
    pin = None if a.unpinned else datasets[0]
    shared = [arm for arm in ARMS if ARM_DEFS[arm][1] is ARM_DEFS[ARMS[0]][1] and arm != "baseline"]
    prompts_identical = len(shared) == 2 and all(
        gather_system(r, ARM_DEFS[ARMS[0]][1], ARM_DEFS[ARMS[0]][2], pin) ==
        gather_system(r, ARM_DEFS[ARMS[1]][1], ARM_DEFS[ARMS[1]][2], pin) for r in ROLE_TOOLS)
    for arm in ARMS:
        if ARM_DEFS[arm][2]:          # neutral prompt must not name tools
            leak = sorted({n for r in ROLE_TOOLS for n in names
                           if re.search(rf"\b{re.escape(n)}\b", gather_system(r, ARM_DEFS[arm][1], True, pin))})
            if leak:
                sys.exit(f"tool names in the {arm} prompt: {leak}")
    graphs = {}

    def graph_for(arm: str, ds: str, role: str = ""):
        if arm == "baseline":
            key = (arm, ds, role)
            if key not in graphs:
                graphs[key] = ("baseline", build_baseline(tools_for(ds), role, dataset=None if a.unpinned else ds))
            return graphs[key]
        key = (arm, None if a.unpinned else ds)
        if key not in graphs:
            rt, rec, neutral = ARM_DEFS[arm]
            graphs[key] = build_graph(tools_for(ds), role_tools=rt, recipes=rec, neutral=neutral,
                                      dataset=None if a.unpinned else ds)
        return graphs[key]

    stored = {}
    src = a.rejudge or a.reuse
    if src:
        rename = {(a.reuse_arm or ARMS[1]): ARMS[1]} if a.reuse else {}
        stored = {(r["id"], rename.get(arm, arm)): run for r in json.loads(Path(src).read_text()) for arm, run in r["runs"].items()}
    judge_model = init_chat_model(JUDGE_MODEL, max_tokens=8000)
    sem = asyncio.Semaphore(a.concurrency)
    all_leaks: list[str] = []

    async def one(q: dict) -> dict:
        async with sem:
            runs = {}
            if a.rejudge:
                runs = {arm: stored[(q["id"], arm)] for arm in ARMS}
            else:
                if a.reuse:
                    runs[ARMS[1]] = stored[(q["id"], ARMS[1])]
                rnd = random.Random(f"{a.seed}-run-{q['id']}")
                order = sorted([x for x in ARMS if x not in runs], key=lambda _: rnd.random())  # random first arm
                for arm in order:                                     # sequential: the two arms never share the DB
                    runs[arm] = await run_arm(graph_for(arm, q["dataset"], q["role"]), q)
            row = {"id": q["id"], "role": q["role"], "dataset": q["dataset"], "runs": runs,
                   "E1": {arm: (golden_hits(q, runs[arm]["text"])[0] / len(q["golden"]) if q.get("golden") and runs[arm]["text"] else None)
                          for arm in ARMS}}
            texts = {arm: blind(runs[arm]["text"], names, titles) or "(the system failed and returned no answer)" for arm in ARMS}
            bad = [f"{q['id']}/{arm}: {h}" for arm in ARMS for h in leaks(texts[arm], names)]
            if bad:
                all_leaks.extend(bad)
                row["judge_skipped"] = f"leak: {bad}"
            elif not a.no_judge:
                try:
                    row["judge"] = await judge_pair(q, texts, a.seed, judge_model)
                except Exception as e:  # noqa: BLE001
                    row["judge_error"] = f"{type(e).__name__}: {e}"[:500]
            print(f"{q['id']:<6} {row.get('judge', {}).get('result', row.get('judge_skipped') or row.get('judge_error') or '-')}"
                  + "".join(f"  {arm} {runs[arm].get('elapsed_s')}s/{len(runs[arm].get('tools_used', []))} tools" for arm in ARMS),
                  flush=True)
            return row

    rows = await asyncio.gather(*(one(q) for q in qs))
    import subprocess
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    rep = {"stamp": stamp, "git": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                                                 text=True).stdout.strip(),
           "agent_model": os.environ.get("AGENT_MODEL", "anthropic:claude-sonnet-5-5"), "judge_model": JUDGE_MODEL,
           "seed": a.seed, "prompts_identical": prompts_identical, "leaks": all_leaks,
           "tally": tally(rows), "arms": {arm: arm_stats(rows, arm) for arm in ARMS},
           "pinned": not a.unpinned, "reuse": a.reuse, "arm_defs": {arm: ({"tools": "all read-only", "recipes": "reference ReAct (brief)"} if arm == "baseline" else
                                                                  {"tools": "plan-010" if ARM_DEFS[arm][0] is OLD_ROLE_TOOLS
                                                                   else "current", "recipes": "neutral" if ARM_DEFS[arm][2]
                                                                   else "product"}) for arm in ARMS},
           "per_tool": per_tool_table(rows),
           "rows": [{k: v for k, v in r.items() if k != "runs"} | {"tools": {arm: r["runs"][arm].get("tools_used", [])
                                                                             for arm in ARMS}} for r in rows]}
    out = ROOT / "eval/results"
    out.mkdir(exist_ok=True)
    (out / f"ab-{stamp}.json").write_text(json.dumps(rep, indent=1, default=str))
    (out / f"ab-{stamp}.runs.json").write_text(json.dumps(
        [{"id": r["id"], "runs": {arm: {k: v for k, v in run.items()} for arm, run in r["runs"].items()}} for r in rows],
        default=str))
    md = render_md(rep | {"rows": [r | {"runs": r["runs"]} for r in rows]})
    (out / f"ab-{stamp}.md").write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
