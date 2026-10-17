"""Eval: our agent vs the baseline ReAct agent on a question set, as LangSmith experiments (plan 009).

  .venv/bin/python -m eval.run_eval                       # all dev questions, both systems, deterministic + judge
  .venv/bin/python -m eval.run_eval --ids D-E01,D-L01     # a subset (dry run)
  .venv/bin/python -m eval.run_eval --no-judge            # deterministic metrics only (no judge cost)

LangSmith: dataset `logs-dev-<hash>` (one example per question, golden facts as reference outputs), experiments
`ours-<sha>` and `baseline-<sha>` (compare them side by side in the UI); every metric is feedback on its run.
Writes eval/results/<time>.md (table) and .json (every run's scores, judge reasons, unverified numbers).
"""
import argparse
import asyncio
import hashlib
import json
import statistics
import subprocess
import sys
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import yaml
from langchain_core.callbacks import get_usage_metadata_callback
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langsmith import Client, aevaluate

from agent.graph import build_baseline, build_graph, parse_envelope, tools_called
from agent.run import MCP
from eval import judge as J
from eval.metrics import answer_text_from_card, role_distinctness, score_run


def git_sha() -> str:
    try:
        return subprocess.check_output(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, text=True).strip()
    except Exception:  # noqa: BLE001
        return "nogit"


def _tokens(cb) -> tuple[int, int]:
    u = cb.usage_metadata or {}
    return sum(v.get("input_tokens", 0) for v in u.values()), sum(v.get("output_tokens", 0) for v in u.values())


def make_targets(tools):
    graph = build_graph(tools)

    async def ours(inputs: dict) -> dict:
        t0 = time.perf_counter()
        with get_usage_metadata_callback() as cb:
            s = await graph.ainvoke({"question": inputs["question"], "role": inputs["role"],
                                     "messages": [HumanMessage(inputs["question"])]}, config={"recursion_limit": 60})
        tin, tout = _tokens(cb)
        return {"kind": "ours", "role": s["role"], "text": answer_text_from_card(s["card"]), "card": s["card"],
                "check": s["check"], "ledger": s.get("ledger", {}), "tools_used": s.get("tools_used", []),
                "elapsed_s": round(time.perf_counter() - t0, 1), "tokens_in": tin, "tokens_out": tout}

    async def baseline(inputs: dict) -> dict:
        t0 = time.perf_counter()
        agent = build_baseline(tools, inputs["role"])
        with get_usage_metadata_callback() as cb:
            s = await agent.ainvoke({"messages": [HumanMessage(inputs["question"])]}, config={"recursion_limit": 40})
        tin, tout = _tokens(cb)
        final = next(m for m in reversed(s["messages"]) if isinstance(m, AIMessage) and not m.tool_calls)
        text = final.content if isinstance(final.content, str) else "".join(
            b.get("text", "") for b in final.content if isinstance(b, dict))
        ledger = {e["evidence_id"]: e for m in s["messages"] if isinstance(m, ToolMessage) for e in [parse_envelope(m)] if e}
        return {"kind": "baseline", "role": inputs["role"], "text": text, "ledger": ledger,
                "tools_used": tools_called(s["messages"]), "elapsed_s": round(time.perf_counter() - t0, 1),
                "tokens_in": tin, "tokens_out": tout}

    return {"ours": ours, "baseline": baseline}


def deterministic(inputs: dict, outputs: dict, reference_outputs: dict) -> dict:
    s = score_run(reference_outputs["q"], outputs)
    res = [{"key": k, "score": float(v)} for k, v in s.items()
           if k.startswith(("E1_correct", "E2a_ledger", "E2b_", "E7_", "E8_tool", "E8_elapsed")) and isinstance(v, (int, float, bool))]
    # LangSmith caps feedback scores at 1e5: tokens as thousands
    res += [{"key": f"E8_ktokens_{d}", "score": round(s[f"E8_tokens_{d}"] / 1000, 1)} for d in ("in", "out") if s.get(f"E8_tokens_{d}")]
    res.append({"key": "E5_forbidden_claims", "score": len(s["E5_forbidden"]), "comment": ", ".join(s["E5_forbidden"])})
    res.append({"key": "E2a_unverified", "score": len(s["E2a_unverified"]), "comment": ", ".join(s["E2a_unverified"][:20])})
    return {"results": res}


async def judged(inputs: dict, outputs: dict) -> dict:
    cs, rb = await asyncio.gather(J.claim_support(inputs["question"], inputs["role"], outputs["text"], outputs["ledger"]),
                                  J.rubric(inputs["question"], inputs["role"], outputs["text"]))
    outputs["_judge"] = {"claim_support": cs, "rubric": rb}
    res = [{"key": "E2c_claim_support", "score": cs["score"],
            "comment": json.dumps(cs["unsupported_claims"][:5], ensure_ascii=False)[:1500]},
           {"key": "E3_causes_as_fact", "score": rb["causes_as_fact"]},
           {"key": "E5_judge_invented_impact", "score": float(rb["invented_impact"])},
           {"key": "Q_rubric_mean", "score": rb["mean"], "comment": rb["reasons"]}]
    res += [{"key": f"Q_{k}", "score": rb[k]} for k in ("role_fit", "next_step", "evidence_use", "separation", "clarity")]
    return {"results": res}


def ensure_dataset(client: Client, questions: list[dict], name_prefix: str) -> str:
    h = hashlib.sha1(json.dumps(questions, sort_keys=True, default=str).encode()).hexdigest()[:8]
    name = f"{name_prefix}-{h}"
    if not client.has_dataset(dataset_name=name):
        ds = client.create_dataset(name, description="Log questions per role with golden facts from hand-checked SQL (plan 009).")
        client.create_examples(dataset_id=ds.id, examples=[
            {"inputs": {"qid": q["id"], "question": q["question"], "role": q["role"]},
             "outputs": {"q": q}, "metadata": {"role": q["role"], "topic": q.get("topic"), "dataset": q["dataset"]}}
            for q in questions])
    return name


async def run_suite(questions: list[dict], dataset_prefix: str, out_dir: Path, judge: bool = True,
                    systems=("ours", "baseline"), concurrency: int = 3, quiet: bool = False) -> dict:
    """Run every system on every question, score, write results; returns {per_run, aggregates, e4, pairwise}."""
    client = Client()
    tools = await MultiServerMCPClient(MCP).get_tools()
    targets = make_targets(tools)
    dataset = ensure_dataset(client, questions, dataset_prefix)
    sha = git_sha()
    by_id = {q["id"]: q for q in questions}
    runs, experiments = {}, {}
    for kind in systems:
        res = await aevaluate(targets[kind], data=dataset, evaluators=[deterministic] + ([judged] if judge else []),
                              experiment_prefix=f"{kind}-{sha}", max_concurrency=concurrency,
                              metadata={"system": kind, "git": sha, "judge_model": J.JUDGE_MODEL if judge else None})
        experiments[kind] = res.experiment_name
        async for row in res:
            out = row["run"].outputs or {}
            qid = row["example"].inputs["qid"]
            if not out.get("text"):
                runs[(qid, kind)] = {"kind": kind, "role": by_id[qid]["role"], "error": str(row["run"].error)[:300],
                                     "text": "", "ledger": {}, "tools_used": []}
                continue
            out["run_id"] = str(row["run"].id)
            out["judge"] = {r.key: {"score": r.score, "comment": r.comment}
                            for r in row["evaluation_results"]["results"] if r.key.startswith(("E2c", "E3_", "E5_judge", "Q_"))}
            runs[(qid, kind)] = out

    pairwise = {}
    if judge and set(systems) == {"ours", "baseline"}:
        async def pw(qid):
            a, b = runs.get((qid, "ours")), runs.get((qid, "baseline"))
            if a and b and a.get("text") and b.get("text"):
                pairwise[qid] = await J.pairwise(by_id[qid]["question"], by_id[qid]["role"], a["text"], b["text"])
                score = {"ours": 1.0, "baseline": 0.0, "tie": 0.5, "inconsistent": 0.5}[pairwise[qid]["result"]]
                client.create_feedback(a["run_id"], key="Q_pairwise_vs_baseline", score=score,
                                       comment=f"{pairwise[qid]['result']}: " + " | ".join(pairwise[qid]["reasons"])[:1500])
        await asyncio.gather(*(pw(q["id"]) for q in questions))

    per_run = [dict(score_run(by_id[qid], r), judge=r.get("judge", {}), error=r.get("error"))
               for (qid, kind), r in sorted(runs.items()) if r.get("text")]
    e4 = role_distinctness(questions, runs)
    agg = aggregate(per_run, pairwise, e4)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
    report = {"dataset": dataset, "experiments": experiments, "git": sha, "judge_model": J.JUDGE_MODEL if judge else None,
              "aggregates": agg, "e4": e4, "pairwise": pairwise, "per_run": per_run}
    (out_dir / f"{stamp}.json").write_text(json.dumps(report, indent=1, default=str, ensure_ascii=False))
    (out_dir / f"{stamp}.md").write_text(render_md(report))
    if not quiet:
        print(render_md(report))
        print(f"\nwritten {out_dir / stamp}.md/.json")
    return report


def _mean(xs):
    xs = [float(x) for x in xs if x is not None]
    return round(statistics.mean(xs), 3) if xs else None


def aggregate(per_run: list[dict], pairwise: dict, e4: list[dict]) -> dict:
    agg = {}
    for kind in ("ours", "baseline"):
        for role in ("all", "engineer", "lead", "manager"):
            rs = [r for r in per_run if r["kind"] == kind and (role == "all" or r["role"] == role)]
            if not rs:
                continue
            j = lambda k: _mean(r["judge"].get(k, {}).get("score") for r in rs)
            agg[f"{kind}/{role}"] = {
                "n": len(rs),
                "E1_correct": _mean(r["E1_correct"] for r in rs),
                "E2a_ledger_grounded": _mean(r["E2a_ledger_grounded"] for r in rs),
                "E2b_citation_grounded": _mean(r["E2b_citation_grounded"] for r in rs),
                "E2c_claim_support": j("E2c_claim_support"),
                "E3_causes_as_fact": j("E3_causes_as_fact"),
                "E3_unknowns_stated": _mean(r["E3_separation"]["unknowns"] for r in rs),
                "E5_forbidden_runs": sum(bool(r["E5_forbidden"]) for r in rs),
                "E5_judge_invented_impact": j("E5_judge_invented_impact"),
                "E7_required_tools": _mean(r["E7_required_tools"] for r in rs),
                "E7_first_tool": _mean(r["E7_first_tool"] for r in rs),
                "Q_rubric_mean": j("Q_rubric_mean"), "Q_role_fit": j("Q_role_fit"), "Q_next_step": j("Q_next_step"),
                "mentions": _mean(r["mentions"] for r in rs),
                "E8_tool_calls": _mean(r["E8_tool_calls"] for r in rs),
                "E8_elapsed_s": _mean(r["E8_elapsed_s"] for r in rs),
                "E8_tokens_in": _mean(r["E8_tokens_in"] for r in rs), "E8_tokens_out": _mean(r["E8_tokens_out"] for r in rs),
            }
    if pairwise:
        res = [p["result"] for p in pairwise.values()]
        agg["pairwise"] = {k: res.count(k) for k in ("ours", "baseline", "tie", "inconsistent")}
    for kind in ("ours", "baseline"):
        rows = [e for e in e4 if e["kind"] == kind]
        if rows:
            agg[f"{kind}/E4"] = {"tools_jaccard": _mean(e["tools_jaccard"] for e in rows),
                                 "evidence_jaccard": _mean(e["evidence_jaccard"] for e in rows)}
    return agg


ROWS = [("E1_correct", "E1 golden facts in answer", "↑"), ("E2a_ledger_grounded", "E2a numbers found in the run's results", "↑"),
        ("E2b_citation_grounded", "E2b numbers found in the cited result", "↑"), ("E2c_claim_support", "E2c claims supported (judge)", "↑"),
        ("E3_causes_as_fact", "E3 causes stated as fact (judge, per answer)", "↓"), ("E3_unknowns_stated", "E3 unknowns stated", "↑"),
        ("E5_forbidden_runs", "E5 answers with invented impact (regex)", "↓"), ("E5_judge_invented_impact", "E5 invented impact (judge)", "↓"),
        ("E7_required_tools", "E7 required tools called", "↑"), ("E7_first_tool", "E7 expected first tool", "↑"),
        ("mentions", "must-mention terms present", "↑"), ("Q_rubric_mean", "Q rubric mean 1-5 (judge)", "↑"),
        ("Q_role_fit", "Q role fit 1-5 (judge)", "↑"), ("Q_next_step", "Q next-step specificity 1-5 (judge)", "↑"),
        ("E8_tool_calls", "E8 tool calls", ""), ("E8_elapsed_s", "E8 seconds per answer", "↓"),
        ("E8_tokens_in", "E8 input tokens", "↓"), ("E8_tokens_out", "E8 output tokens", "↓")]


def render_md(rep: dict) -> str:
    a = rep["aggregates"]
    lines = [f"# Eval results ({rep['git']})", "",
             f"Dataset `{rep['dataset']}` · experiments {', '.join(f'`{v}`' for v in rep['experiments'].values())} · "
             f"judge `{rep['judge_model']}`", "",
             "| Metric | | ours | baseline | ours eng | ours lead | ours mgr | base eng | base lead | base mgr |",
             "|---|---|---|---|---|---|---|---|---|---|"]
    for key, label, better in ROWS:
        cell = lambda k: "—" if a.get(k, {}).get(key) is None else str(a[k][key])
        lines.append(f"| {label} | {better} | **{cell('ours/all')}** | **{cell('baseline/all')}** | " +
                     " | ".join(cell(f"{k}/{r}") for k in ("ours", "baseline") for r in ("engineer", "lead", "manager")) + " |")
    if "pairwise" in a:
        p = a["pairwise"]
        lines += ["", f"**Pairwise (judge, both orders, consistent only):** ours {p['ours']} · baseline {p['baseline']} · "
                      f"tie {p['tie']} · inconsistent {p['inconsistent']}"]
    for kind in ("ours", "baseline"):
        if f"{kind}/E4" in a:
            lines.append(f"**E4 role distinctness ({kind}, same topic across roles, lower = more distinct):** "
                         f"tools Jaccard {a[f'{kind}/E4']['tools_jaccard']} · evidence Jaccard {a[f'{kind}/E4']['evidence_jaccard']}")
    lines += ["", "| Question | system | E1 | E2a | E2b | E2c | rubric | tools | s | missed golden / unverified |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rep["per_run"]:
        j = r["judge"]
        lines.append(f"| {r['id']} | {r['kind']} | {r['E1_correct']} | {round(r['E2a_ledger_grounded'], 2)} | "
                     f"{r['E2b_citation_grounded'] if r['E2b_citation_grounded'] is None else round(r['E2b_citation_grounded'], 2)} | "
                     f"{j.get('E2c_claim_support', {}).get('score', '—') if not isinstance(j.get('E2c_claim_support', {}).get('score'), float) else round(j['E2c_claim_support']['score'], 2)} | "
                     f"{j.get('Q_rubric_mean', {}).get('score', '—')} | {r['E8_tool_calls']} | {r['E8_elapsed_s']} | "
                     f"{'; '.join(r['E1_missed'])[:80]} {('/ ' + ', '.join(r['E2a_unverified'][:4])) if r['E2a_unverified'] else ''} |")
    return "\n".join(lines)


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--questions", default=str(ROOT / "eval/dev_questions.yaml"))
    ap.add_argument("--ids", help="comma-separated question ids")
    ap.add_argument("--systems", default="ours,baseline")
    ap.add_argument("--no-judge", action="store_true")
    ap.add_argument("--concurrency", type=int, default=3)
    a = ap.parse_args()
    qs = yaml.safe_load(Path(a.questions).read_text())
    if a.ids:
        keep = set(a.ids.split(","))
        qs = [q for q in qs if q["id"] in keep]
    await run_suite(qs, "logs-dev", ROOT / "eval/results", judge=not a.no_judge,
                    systems=tuple(a.systems.split(",")), concurrency=a.concurrency)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
