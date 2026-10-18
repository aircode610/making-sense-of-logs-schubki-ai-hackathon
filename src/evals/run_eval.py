"""Eval: our agent vs the baseline ReAct agent on a question set, as LangSmith experiments (plan 009).

  .venv/bin/python -m evals.run_eval                       # all dev questions, both systems, deterministic + judge
  .venv/bin/python -m evals.run_eval --ids D-E01,D-L01     # a subset (dry run)
  .venv/bin/python -m evals.run_eval --no-judge            # deterministic metrics only (no judge cost)
  Iterating on our pipeline (plan 010, docs/EVAL.md "How to iterate"):
  .venv/bin/python -m evals.run_eval --systems ours --reuse-baseline eval/results/<last>.json --compare eval/results/<last>.json
  .venv/bin/python -m evals.run_eval --repeat 3            # run-to-run spread (the noise floor)
  .venv/bin/python -m evals.run_eval --rejudge eval/results/<x>.json   # judge changed: re-score stored answers

LangSmith: dataset `logs-dev-<hash>` (one example per question, golden facts as reference outputs), experiments
`ours-<sha>` and `baseline-<sha>` (compare them side by side in the UI); every metric is feedback on its run.
Writes eval/results/<time>.md (table), .json (every run's scores, judge reasons, unverified numbers) and .runs.json
(every answer with its card and evidence: what --reuse-baseline / --compare / --rejudge / bench/replay_tools.py read).
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

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src"))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")

import yaml
from langchain_core.callbacks import get_usage_metadata_callback
from langchain_core.messages import AIMessage, HumanMessage, ToolMessage
from langchain_mcp_adapters.client import MultiServerMCPClient
from langsmith import Client, aevaluate

from agent.graph import build_baseline, build_graph, parse_envelope, tools_called
from agent.run import MCP
from evals import judge as J
from evals.metrics import answer_text_from_card, failed_run, role_distinctness, score_run


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
    if not outputs.get("text"):
        return {"results": [{"key": "run_failed", "score": 1.0}]}
    s = score_run(reference_outputs["q"], outputs)
    res = [{"key": k, "score": float(v)} for k, v in s.items()
           if k.startswith(("E1_correct", "E2a_ledger", "E2b_", "E2d_", "E7_", "E8_tool", "E8_elapsed")) and isinstance(v, (int, float, bool))]
    # LangSmith caps feedback scores at 1e5: tokens as thousands
    res += [{"key": f"E8_ktokens_{d}", "score": round(s[f"E8_tokens_{d}"] / 1000, 1)} for d in ("in", "out") if s.get(f"E8_tokens_{d}")]
    res.append({"key": "E5_forbidden_claims", "score": len(s["E5_forbidden"]), "comment": ", ".join(s["E5_forbidden"])})
    res.append({"key": "E2a_unverified", "score": len(s["E2a_unverified"]), "comment": ", ".join(s["E2a_unverified"][:20])})
    return {"results": res}


def _judge_results(cs: dict, rb: dict) -> list[dict]:
    res = [{"key": "E2c_claim_support", "score": cs["score"],
            "comment": json.dumps(cs["unsupported_claims"][:5], ensure_ascii=False)[:1500]},
           {"key": "E3_causes_as_fact", "score": rb["causes_as_fact"]},
           {"key": "E5_judge_invented_impact", "score": float(rb["invented_impact"])},
           {"key": "Q_rubric_mean", "score": rb["mean"], "comment": rb["reasons"]}]
    res += [{"key": f"Q_{k}", "score": rb[k]} for k in ("role_fit", "next_step", "evidence_use", "separation", "clarity")]
    return res


async def judged(inputs: dict, outputs: dict) -> dict:
    if not outputs.get("text"):   # failed run: scored 0 by failed_run, nothing to judge
        return {"results": []}
    cs, rb = await asyncio.gather(J.claim_support(inputs["question"], inputs["role"], outputs["text"], outputs["ledger"]),
                                  J.rubric(inputs["question"], inputs["role"], outputs["text"]))
    outputs["_judge"] = {"claim_support": cs, "rubric": rb}
    return {"results": _judge_results(cs, rb)}


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


def load_runs(results_json: str | Path) -> tuple[dict, dict]:
    """(report, runs) of an earlier eval; runs = {(qid, kind, rep): outputs incl. text, card, ledger}. Read from the
    `<stamp>.runs.json` written next to the report; older reports (no runs file) are fetched from their LangSmith
    experiments (rep 0 only)."""
    p = Path(results_json)
    rep = json.loads(p.read_text())
    rp = p.with_suffix(".runs.json")
    if rp.exists():
        return rep, {(k.split("|")[0], k.split("|")[1], int(k.split("|")[2])): v for k, v in json.loads(rp.read_text()).items()}
    client, runs = Client(), {}
    for kind, exp in rep["experiments"].items():
        for r in client.list_runs(project_name=exp, is_root=True):
            inp = r.inputs.get("inputs", r.inputs)
            if inp.get("qid") and r.outputs and r.outputs.get("text"):
                runs[(inp["qid"], kind, 0)] = {**r.outputs, "run_id": str(r.id)}
    return rep, runs


def _stored_judge(rep: dict) -> dict:
    return {(r["id"], r["kind"], r.get("rep", 0)): r.get("judge", {}) for r in rep["per_run"]}


def _judge_view(out: dict) -> dict:
    j = out["_judge"]
    return {r["key"]: {"score": r["score"], "comment": r.get("comment")} for r in _judge_results(j["claim_support"], j["rubric"])}


async def run_suite(questions: list[dict], dataset_prefix: str, out_dir: Path, judge: bool = True,
                    systems=("ours", "baseline"), concurrency: int = 3, quiet: bool = False, repeat: int = 1,
                    reuse: dict | None = None, rejudge: bool = False, compare: str | None = None) -> dict:
    """Run every system on every question (`repeat` times), score, write results; returns the report.

    reuse = {kind: results.json}: take that system's answers from an earlier eval instead of running it (the baseline
    does not change when our pipeline does); its judge scores are reused too unless `rejudge`. compare = results.json
    of an earlier eval of OUR system: per-metric deltas, per-question regressions and a new-vs-old pairwise judge."""
    client = Client()
    by_id = {q["id"]: q for q in questions}
    reuse = reuse or {}
    runs, judges, experiments, fresh = {}, {}, {}, set()
    for kind in systems:
        if kind in reuse:
            old, old_runs = load_runs(reuse[kind])
            experiments[kind] = f"{old['experiments'].get(kind)} (reused)"
            stored = _stored_judge(old)
            mine = {key: out for key, out in old_runs.items() if key[1] == kind and key[0] in by_id}
            runs.update(mine)
            judges.update({key: stored.get(key, {}) for key in mine})
            if judge and rejudge:
                sem = asyncio.Semaphore(concurrency * 2)

                async def rj(key, out):
                    async with sem:
                        await judged({"question": by_id[key[0]]["question"], "role": by_id[key[0]]["role"]}, out)
                        if out.get("_judge"):
                            judges[key] = _judge_view(out)
                await asyncio.gather(*(rj(k, o) for k, o in mine.items()))
            continue
        tools = await MultiServerMCPClient(MCP).get_tools()
        dataset = ensure_dataset(client, questions, dataset_prefix)
        sha = git_sha()
        res = await aevaluate(make_targets(tools)[kind], data=dataset, evaluators=[deterministic] + ([judged] if judge else []),
                              experiment_prefix=f"{kind}-{sha}", max_concurrency=concurrency, num_repetitions=repeat,
                              metadata={"system": kind, "git": sha, "judge_model": J.JUDGE_MODEL if judge else None})
        experiments[kind] = res.experiment_name
        seen = {}
        async for row in res:
            out = row["run"].outputs or {}
            qid = row["example"].inputs["qid"]
            rp = seen[qid] = seen.get(qid, -1) + 1
            fresh.add((qid, kind, rp))
            if not out.get("text"):
                runs[(qid, kind, rp)] = {"kind": kind, "role": by_id[qid]["role"], "text": "", "ledger": {}, "tools_used": [],
                                         "error": str(row["run"].error or "no answer")[:300]}
                continue
            out["run_id"] = str(row["run"].id)
            runs[(qid, kind, rp)] = out
            judges[(qid, kind, rp)] = {r.key: {"score": r.score, "comment": r.comment}
                                       for r in row["evaluation_results"]["results"] if r.key.startswith(("E2c", "E3_", "E5_judge", "Q_"))}

    first = {(qid, kind): r for (qid, kind, rp), r in runs.items() if rp == 0}   # pairwise and E4 use repetition 0
    pairwise = {}
    if judge and set(systems) == {"ours", "baseline"} and not (reuse.keys() >= {"ours", "baseline"} and not rejudge):
        async def pw(qid):
            a, b = first.get((qid, "ours")), first.get((qid, "baseline"))
            if a and b and a.get("text") and b.get("text"):
                pairwise[qid] = await J.pairwise(by_id[qid]["question"], by_id[qid]["role"], a["text"], b["text"])
                if (qid, "ours", 0) in fresh:
                    score = {"ours": 1.0, "baseline": 0.0, "tie": 0.5, "inconsistent": 0.5}[pairwise[qid]["result"]]
                    client.create_feedback(a["run_id"], key="Q_pairwise_vs_baseline", score=score,
                                           comment=f"{pairwise[qid]['result']}: " + " | ".join(pairwise[qid]["reasons"])[:1500])
        await asyncio.gather(*(pw(q["id"]) for q in questions))

    per_run = []
    for (qid, kind, rp), r in sorted(runs.items()):
        row = score_run(by_id[qid], r) if r.get("text") else failed_run(by_id[qid], kind, r.get("error", "no answer"))
        per_run.append({**row, "rep": rp, "judge": row.get("judge") or judges.get((qid, kind, rp), {}),
                        "error": r.get("error") if not r.get("text") else None})
    e4 = role_distinctness(questions, first)
    agg = aggregate(per_run, pairwise, e4)
    if repeat > 1:
        agg["noise"] = noise(per_run, pairwise, e4, repeat)
    report = {"dataset": f"{dataset_prefix} ({len(questions)} questions)", "experiments": experiments, "git": git_sha(),
              "judge_model": J.JUDGE_MODEL if judge else None, "repeat": repeat,
              "aggregates": agg, "e4": e4, "pairwise": pairwise, "per_run": per_run}
    if compare:
        report["compare"] = await compare_to(report, runs, by_id, compare, judge)
    out_dir.mkdir(parents=True, exist_ok=True)
    stamp = f"{datetime.now():%Y%m%d-%H%M%S}"
    (out_dir / f"{stamp}.json").write_text(json.dumps(report, indent=1, default=str, ensure_ascii=False))
    (out_dir / f"{stamp}.runs.json").write_text(json.dumps(
        {f"{q}|{k}|{rp}": {kk: v for kk, v in r.items() if kk != "_judge"} for (q, k, rp), r in runs.items()},
        default=str, ensure_ascii=False))
    (out_dir / f"{stamp}.md").write_text(render_md(report))
    if not quiet:
        print(render_md(report))
        print(f"\nwritten {out_dir / stamp}.md/.json/.runs.json")
    return report


# A per-question drop larger than this is listed as a regression (set from the measured noise, docs/EVAL.md).
REGRESSION = {"E1_correct": 0.01, "E2a_ledger_grounded": 0.05, "E2c_claim_support": 0.15, "Q_rubric_mean": 0.6}


def _per_question(per_run: list[dict], kind: str = "ours") -> dict:
    """{qid: {metric: mean over repetitions}} for one system."""
    out = {}
    for r in per_run:
        if r["kind"] != kind:
            continue
        d = out.setdefault(r["id"], {k: [] for k in REGRESSION} | {"errors": 0})
        d["errors"] += bool(r.get("error"))
        for k in REGRESSION:
            v = r["judge"].get(k, {}).get("score") if k.startswith(("E2c", "Q_")) else r.get(k)
            if v is not None:
                d[k].append(float(v))
    return {q: {k: (round(statistics.mean(v), 3) if v else None) if k != "errors" else v for k, v in d.items()}
            for q, d in out.items()}


async def compare_to(report: dict, runs: dict, by_id: dict, old_path: str, judge: bool) -> dict:
    """New ours vs an earlier eval's ours: deltas per aggregate, questions that got worse, pairwise new vs old."""
    old, old_runs = load_runs(old_path)
    # re-score the old answers with the CURRENT questions (golden facts may have changed); keep their judge scores
    old_rows = []
    for r in old["per_run"]:
        out = old_runs.get((r["id"], r["kind"], r.get("rep", 0)))
        if r["id"] in by_id and out and out.get("text"):
            r = {**r, **score_run(by_id[r["id"]], out)}
        old_rows.append(r)
    old = {**old, "per_run": old_rows, "aggregates": aggregate(old_rows, old.get("pairwise", {}), old.get("e4", []))}
    new_a, old_a = report["aggregates"], old["aggregates"]
    delta = {}
    for col in ("ours/all", "ours/engineer", "ours/lead", "ours/manager"):
        if col in new_a and col in old_a:
            delta[col] = {k: round(new_a[col][k] - old_a[col][k], 3) for k, _, _ in ROWS
                          if isinstance(new_a[col].get(k), (int, float)) and isinstance(old_a[col].get(k), (int, float))}
    new_q, old_q = _per_question(report["per_run"]), _per_question(old["per_run"])
    regressions = []
    for qid, n in new_q.items():
        o = old_q.get(qid)
        if not o:
            continue
        worse = {k: (o[k], n[k]) for k, lim in REGRESSION.items()
                 if n[k] is not None and o[k] is not None and o[k] - n[k] > lim}
        if n["errors"] > o["errors"]:
            worse["errors"] = (o["errors"], n["errors"])
        if worse:
            regressions.append({"id": qid, "worse": worse})
    pairwise = {}
    if judge:
        async def pw(qid):
            a, b = runs.get((qid, "ours", 0)), old_runs.get((qid, "ours", 0))
            if a and b and a.get("text") and b.get("text"):
                p = await J.pairwise(by_id[qid]["question"], by_id[qid]["role"], a["text"], b["text"])
                pairwise[qid] = {**p, "result": {"ours": "new", "baseline": "old"}.get(p["result"], p["result"])}
        await asyncio.gather(*(pw(qid) for qid in by_id))
    res = [p["result"] for p in pairwise.values()]
    return {"against": f"{old_path} (git {old.get('git')})", "delta": delta, "regressions": regressions,
            "pairwise_new_vs_old": {k: res.count(k) for k in ("new", "old", "tie", "inconsistent")} if pairwise else None,
            "pairwise_detail": pairwise}


def noise(per_run: list[dict], pairwise: dict, e4: list[dict], repeat: int) -> dict:
    """Run-to-run spread: max − min over repetitions of each system's overall aggregate (what two single runs of the
    same code can differ by)."""
    reps = [aggregate([r for r in per_run if r["rep"] == i], {}, []) for i in range(repeat)]
    out = {}
    for col in ("ours/all", "baseline/all"):
        vals = [a[col] for a in reps if col in a]
        if len(vals) > 1:
            out[col] = {k: round(max(v[k] for v in vals) - min(v[k] for v in vals), 3) for k, _, _ in ROWS
                        if all(isinstance(v.get(k), (int, float)) for v in vals)}
    return out


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
                "n": len(rs), "error_rate": _mean(bool(r.get("error")) for r in rs),
                "E1_correct": _mean(r["E1_correct"] for r in rs),
                "E2a_ledger_grounded": _mean(r["E2a_ledger_grounded"] for r in rs),
                "E2b_citation_grounded": _mean(r["E2b_citation_grounded"] for r in rs),
                "E2d_jev_support": _mean(r.get("E2d_jev_support") for r in rs),
                "E2c_claim_support": j("E2c_claim_support"),
                "E3_causes_as_fact": j("E3_causes_as_fact"),
                "E3_unknowns_stated": _mean(r["E3_separation"]["unknowns"] for r in rs),
                "E5_forbidden_runs": sum(bool(r["E5_forbidden"]) for r in rs),
                "E5_must_not_runs": sum(bool(r.get("E5_must_not")) for r in rs),
                "E5_judge_invented_impact": j("E5_judge_invented_impact"),
                "E7_required_tools": _mean(r["E7_required_tools"] for r in rs),
                "E7_first_tool": _mean(r["E7_first_tool"] for r in rs),
                "Q_rubric_mean": j("Q_rubric_mean"), "Q_role_fit": j("Q_role_fit"), "Q_next_step": j("Q_next_step"),
                "mentions": _mean(r["mentions"] for r in rs),
                "E8_tool_calls": _mean(r["E8_tool_calls"] for r in rs),
                "E8_elapsed_s": _mean(r["E8_elapsed_s"] for r in rs),
                "E8_tool_s": _mean(r.get("E8_tool_s") for r in rs), "E8_other_s": _mean(r.get("E8_other_s") for r in rs),
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


ROWS = [("error_rate", "runs failed (scored 0)", "↓"), ("E1_correct", "E1 golden facts in answer (incl. E6 ranking order)", "↑"), ("E2a_ledger_grounded", "E2a numbers found in the run's results", "↑"),
        ("E2b_citation_grounded", "E2b numbers found in the cited result", "↑"),
        ("E2d_jev_support", "E2d Jev: fact supported by its evidence (mean p)", "↑"), ("E2c_claim_support", "E2c claims supported (judge)", "↑"),
        ("E3_causes_as_fact", "E3 causes stated as fact (judge, per answer)", "↓"), ("E3_unknowns_stated", "E3 unknowns stated", "↑"),
        ("E5_forbidden_runs", "E5 answers with invented impact (regex)", "↓"), ("E5_judge_invented_impact", "E5 invented impact (judge)", "↓"),
        ("E5_must_not_runs", "E5 answers with a must_not term", "↓"),
        ("E7_required_tools", "E7 required tools called", "↑"), ("E7_first_tool", "E7 expected first tool", "↑"),
        ("mentions", "must-mention terms present", "↑"), ("Q_rubric_mean", "Q rubric mean 1-5 (judge)", "↑"),
        ("Q_role_fit", "Q role fit 1-5 (judge)", "↑"), ("Q_next_step", "Q next-step specificity 1-5 (judge)", "↑"),
        ("E8_tool_calls", "E8 tool calls", ""), ("E8_elapsed_s", "E8 seconds per answer", "↓"),
        ("E8_tool_s", "E8 of which inside tools (DB)", "↓"), ("E8_other_s", "E8 of which LLM + overhead", "↓"),
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
    if a.get("noise"):
        lines += ["", f"**Run-to-run spread ({rep['repeat']} repetitions, max − min of the overall mean):**", "",
                  "| Metric | ours | baseline |", "|---|---|---|"]
        for key, label, _ in ROWS:
            cell = lambda k: a["noise"].get(k, {}).get(key, "—")
            lines.append(f"| {label} | {cell('ours/all')} | {cell('baseline/all')} |")
    if rep.get("compare"):
        c = rep["compare"]
        cols = list(c["delta"])
        lines += ["", f"## Compared with {c['against']}", "", "| Δ metric (new − old) | " + " | ".join(cols) + " |",
                  "|---|" + "---|" * len(cols)]
        for key, label, better in ROWS:
            if any(key in c["delta"][col] for col in cols):
                lines.append(f"| {label} {better} | " + " | ".join(str(c["delta"][col].get(key, "—")) for col in cols) + " |")
        if c["pairwise_new_vs_old"]:
            p = c["pairwise_new_vs_old"]
            lines += ["", f"**Pairwise new vs old (judge, both orders):** new {p['new']} · old {p['old']} · tie {p['tie']} · "
                          f"inconsistent {p['inconsistent']}"]
        lines += ["", f"**Regressions ({len(c['regressions'])} questions, drop beyond {REGRESSION}):**"]
        lines += [f"- {r['id']}: " + ", ".join(f"{k} {o} → {n}" for k, (o, n) in r["worse"].items()) for r in c["regressions"]] or ["- none"]
    lines += ["", "| Question | system | E1 | E2a | E2b | E2c | rubric | tools | s | missed golden / unverified |", "|---|---|---|---|---|---|---|---|---|---|"]
    for r in rep["per_run"]:
        j = r["judge"]
        lines.append(f"| {r['id']}{'#' + str(r['rep']) if r.get('rep') else ''} | {r['kind']}{' FAILED' if r.get('error') else ''} | {r['E1_correct']} | {round(r['E2a_ledger_grounded'], 2)} | "
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
    ap.add_argument("--repeat", type=int, default=1, help="run each question k times; reports run-to-run spread")
    ap.add_argument("--reuse-baseline", metavar="RESULTS_JSON", help="take the baseline's answers + scores from an earlier eval")
    ap.add_argument("--rejudge", metavar="RESULTS_JSON", help="re-judge an earlier eval's answers (no agent runs)")
    ap.add_argument("--compare", metavar="RESULTS_JSON", help="compare our system with an earlier eval of it")
    a = ap.parse_args()
    qs = yaml.safe_load(Path(a.questions).read_text())
    if a.ids:
        keep = set(a.ids.split(","))
        qs = [q for q in qs if q["id"] in keep]
    systems = tuple(a.systems.split(","))
    reuse = {k: a.rejudge for k in systems} if a.rejudge else {}
    if a.reuse_baseline:
        reuse["baseline"] = a.reuse_baseline
        systems = tuple(dict.fromkeys(systems + ("baseline",)))
    await run_suite(qs, "logs-dev", ROOT / "eval/results", judge=not a.no_judge, systems=systems,
                    concurrency=a.concurrency, repeat=a.repeat, reuse=reuse, rejudge=bool(a.rejudge), compare=a.compare)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
