"""Blind A/B of the toolsets (plan 013): the same agent run twice per question, differing only in its MCP tools.

  old = per-role subsets of the 8 plan-010 tools (agent.graph.OLD_ROLE_TOOLS)
  new = the current per-role subsets (agent.graph.ROLE_TOOLS)
Both arms: same graph, model, composer, checker, budgets and the same tool-neutral prompt (prompts.NEUTRAL_RECIPES).

Judge = an agent (JUDGE_MODEL) with a read-only `sql` tool (DB role logs_manager: SELECT only, no labels table) that
grades both answers against the question's frozen answer key (eval/answer_keys/<id>.yaml), verifying key claims with
SQL. Blind: both answers as the same plain text, tool names → [tool], no evidence ids / check footer, X/Y random per
question (seeded), asked in both orders by fresh judge agents; only order-consistent wins count. A leak scan stops the
run if any tool name or evidence id reaches the judge.

  .venv/bin/python -m eval.ab --ids D-E01,D-L04          # smoke
  .venv/bin/python -m eval.ab                            # all questions in eval/dev_questions.yaml
  .venv/bin/python -m eval.ab --reuse eval/results/ab-<t>.runs.json   # re-judge stored answers (no agent runs)
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

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import psycopg
import yaml
from langchain.agents import create_agent
from langchain.agents.middleware import ToolCallLimitMiddleware
from langchain.chat_models import init_chat_model
from langchain_core.callbacks import AsyncCallbackHandler, get_usage_metadata_callback
from langchain_core.messages import HumanMessage
from langchain_core.tools import tool
from langchain_mcp_adapters.client import MultiServerMCPClient
from pydantic import BaseModel, Field

from agent import prompts
from agent.graph import OLD_ROLE_TOOLS, ROLE_TOOLS, build_graph, gather_system
from agent.run import MCP
from eval.judge import JUDGE_MODEL, ROLE_NEEDS
from eval.metrics import answer_text_from_card, golden_hits

ARMS = {"old": OLD_ROLE_TOOLS, "new": ROLE_TOOLS}
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


async def run_arm(graph, q: dict) -> dict:
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
    """texts = {'old': blinded, 'new': blinded}. Order 1: X/Y random (seeded); order 2: swapped."""
    rnd = random.Random(f"{seed}-{q['id']}")
    first = rnd.choice(["old", "new"])
    order = [first, "new" if first == "old" else "old"]          # order[0] is X in round 1
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
    t = {"new": 0, "old": 0, "tie": 0, "inconsistent": 0}
    for r in rows:
        if r.get("judge"):
            t[r["judge"]["result"]] += 1
    return t


def tsplit(run: dict) -> str:
    t = run.get("timing")
    return f"{t['wall_s']} / {t['llm_s']} / {t['tool_s']}" if t else "-"


def render_md(rep: dict) -> str:
    rows = rep["rows"]
    L = [f"# A/B toolsets: new (plan 011) vs old (plan 010) — {rep['stamp']}", "",
         f"git {rep['git']} · agent {rep['agent_model']} · judge {rep['judge_model']} · seed {rep['seed']} · "
         f"{len(rows)} questions · prompts identical across arms: {rep['prompts_identical']} · leaks: {rep['leaks'] or 'none'}",
         "", "## Wins (order-consistent only)", "", "| slice | new | old | tie | inconsistent |", "|---|---|---|---|---|"]
    t = tally(rows)
    L.append(f"| all | {t['new']} | {t['old']} | {t['tie']} | {t['inconsistent']} |")
    for dim in ("role", "dataset"):
        for v in sorted({r[dim] for r in rows}):
            t = tally([r for r in rows if r[dim] == v])
            L.append(f"| {dim} {v} | {t['new']} | {t['old']} | {t['tie']} | {t['inconsistent']} |")
    L += ["", "## Per arm", "", "| metric | new | old |", "|---|---|---|"]
    for k in rep["arms"]["new"]:
        L.append(f"| {k} | {rep['arms']['new'][k]} | {rep['arms']['old'][k]} |")
    L += ["", "## Where the time goes (mean seconds per run; llm + tool + other = wall)", "",
          "| arm | wall | llm | tool (client) | other | tool db (server) | tool calls | llm calls |", "|---|---|---|---|---|---|---|---|"]
    for arm in ("new", "old"):
        m = rep["arms"][arm]
        L.append(f"| {arm} | {m['wall_s']} | {m['llm_s']} | {m['tool_s (client, not overlapping llm)']} | {m['other_s']} | "
                 f"{m['tool_db_s (server)']} | {m['tool_calls']} | {m['llm_calls']} |")
    L += ["", "## Tool time by tool (server-side elapsed_ms)", "", "| tool | arm | calls | total s | median ms | max ms |",
          "|---|---|---|---|---|---|"]
    L += [f"| {d['tool']} | {d['arm']} | {d['calls']} | {d['total_s']} | {d['median_ms']} | {d['max_ms']} |" for d in rep["per_tool"]]
    L += ["", "## Per question", "", "| id | role | dataset | result | new found / wrong | old found / wrong | new tools | old tools | new wall / llm / tool s | old wall / llm / tool s |",
          "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rows:
        j = r.get("judge") or {}
        f = lambda a: "/".join(str(sum(g[k] for g in j["grades"][a])) for k in ("found_problem", "claims_wrong")) if j else "-"  # noqa: E731
        L.append(f"| {r['id']} | {r['role']} | {r['dataset']} | {j.get('result', 'not judged')} | {f('new')} | {f('old')} | "
                 f"{len(r['runs']['new'].get('tools_used', []))} | {len(r['runs']['old'].get('tools_used', []))} | "
                 f"{tsplit(r['runs']['new'])} | {tsplit(r['runs']['old'])} |")
    return "\n".join(L) + "\n"


# ---------------------------------------------------------------- main

async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--questions", default=str(ROOT / "eval/dev_questions.yaml"))
    ap.add_argument("--ids", help="comma-separated question ids")
    ap.add_argument("--concurrency", type=int, default=3, help="questions in flight (each = 2 agent runs + 2 judges)")
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--reuse", metavar="RUNS_JSON", help="judge stored answers of an earlier run (no agent runs)")
    ap.add_argument("--no-judge", action="store_true")
    a = ap.parse_args()
    qs = yaml.safe_load(Path(a.questions).read_text())
    if a.ids:
        keep = set(a.ids.split(","))
        qs = [q for q in qs if q["id"] in keep]
    missing = [q["id"] for q in qs if not (KEYS / f"{q['id']}.yaml").exists()]
    if missing:
        sys.exit(f"no answer key for {missing}")

    tools = await MultiServerMCPClient(MCP).get_tools()
    names = {t.name for t in tools}
    titles = {t.description.split("\n")[0].strip().rstrip("?.") for t in tools if t.description} - {""}
    titles = {x for x in titles if len(x) > 25}                        # long first lines only (not common words)
    prompts_identical = all(gather_system(r, prompts.NEUTRAL_RECIPES, neutral=True) ==
                            gather_system(r, prompts.NEUTRAL_RECIPES, neutral=True) for r in ROLE_TOOLS)
    prompt_leaks = sorted({n for r in ROLE_TOOLS for n in names
                           if re.search(rf"\b{re.escape(n)}\b", gather_system(r, prompts.NEUTRAL_RECIPES, neutral=True))})
    if prompt_leaks:
        sys.exit(f"tool names in the shared prompt: {prompt_leaks}")
    graphs = {arm: build_graph(tools, role_tools=rt, recipes=prompts.NEUTRAL_RECIPES, neutral=True) for arm, rt in ARMS.items()}
    stored = {}
    if a.reuse:
        stored = {(r["id"], arm): run for r in json.loads(Path(a.reuse).read_text()) for arm, run in r["runs"].items()}
    judge_model = init_chat_model(JUDGE_MODEL, max_tokens=8000)
    sem = asyncio.Semaphore(a.concurrency)
    all_leaks: list[str] = []

    async def one(q: dict) -> dict:
        async with sem:
            if stored:
                runs = {arm: stored[(q["id"], arm)] for arm in ARMS}
            else:
                rnd = random.Random(f"{a.seed}-run-{q['id']}")
                order = sorted(ARMS, key=lambda _: rnd.random())      # which arm runs first: random per question
                runs = {}
                for arm in order:                                     # sequential: the two arms never share the DB
                    runs[arm] = await run_arm(graphs[arm], q)
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
                  f"  new {runs['new'].get('elapsed_s')}s/{len(runs['new'].get('tools_used', []))} tools"
                  f"  old {runs['old'].get('elapsed_s')}s/{len(runs['old'].get('tools_used', []))} tools", flush=True)
            return row

    rows = await asyncio.gather(*(one(q) for q in qs))
    import subprocess
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    rep = {"stamp": stamp, "git": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                                                 text=True).stdout.strip(),
           "agent_model": os.environ.get("AGENT_MODEL", "anthropic:claude-sonnet-5-5"), "judge_model": JUDGE_MODEL,
           "seed": a.seed, "prompts_identical": prompts_identical, "leaks": all_leaks,
           "tally": tally(rows), "arms": {arm: arm_stats(rows, arm) for arm in ("new", "old")},
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
