"""Plan 018: Claude Code WITH our MCP server vs plain Claude Code on the raw log files, on the 50 answer keys.

Both arms = headless `claude -p <question> --bare` (no CLAUDE.md, hooks, memory, skills), same model, empty working
directory outside the repo, no system prompt beyond Claude Code's own.
  mcp  = only our `logs` MCP server, pinned to the question's dataset (LOGS_DATASET), no built-in tools
  bare = no MCP; Bash / Read / Grep / Glob over ./logs/ = hard links to that dataset's raw log files (no label files);
         the question gets one line appended saying where the files are.
Judge, answer keys, blinding, both-orders rule and scores are eval/ab.py's, unchanged (judge_pair, blind, leaks).
Bare transcripts are scanned: a run that touched the database or the repo is flagged invalid.

  .venv/bin/python -m eval.cc_ab --ids D-E01,D-L05,D-M01      # smoke
  .venv/bin/python -m eval.cc_ab                              # all 50
  .venv/bin/python -m eval.cc_ab --rejudge eval/results/cc-<t>.runs.json
Writes eval/results/cc-<time>.md / .json / .runs.json (full stream-json transcripts in runs/cc_ab/).
"""
import argparse
import asyncio
import json
import os
import random
import re
import shutil
import statistics
import subprocess
import sys
import tempfile
import time
from datetime import datetime
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
import yaml
from langchain.chat_models import init_chat_model
from langchain_mcp_adapters.client import MultiServerMCPClient

from agent.run import mcp_config
from eval import ab
from eval.ab import KEYS, RUBRIC, blind, judge_pair, leaks, tally
from eval.judge import JUDGE_MODEL
from eval.metrics import golden_hits

ARMS = ("mcp", "bare")
ab.ARMS = ARMS                                  # tally() reads it
RAW = ROOT / "data/raw"
# raw log files per dataset, as a user would have them (label / template files left out)
# BGL: Loghub prefixes every line with its ground-truth alert label (KERNPAN, APPSEV, ...); the bare arm gets a copy
# with that column cut (runs/cc_ab/raw/bgl, `sed -E 's/^[^ ]+ //'`), as real logs carry no labels and our tools never
# show them. OpenStack: neutral file names (Loghub's say which file holds the anomalies). (src, name in ./logs)
FILES = {"bgl": [str(ROOT / "runs/cc_ab/raw/bgl/BGL.log")],
         "openstack": [("openstack/openstack_abnormal.log", "nova-1.log"), ("openstack/openstack_normal1.log", "nova-2.log"),
                       ("openstack/openstack_normal2.log", "nova-3.log")],
         "zookeeper": ["zookeeper/Zookeeper.log"], "apache": ["apache/Apache.log"], "ssh": ["ssh/SSH.log"],
         "hdfs": ["hdfs/HDFS.log"], "linux": ["linux/Linux.log"], "healthapp": ["healthapp/HealthApp.log"],
         "otel": [str(ROOT / "runs/cc_ab/raw/otel/otel_logs.jsonl")]}   # the loaded slice, exported (plan 018 §3)
WHERE = "\n\nThe log files are in ./logs/."
FORBIDDEN = re.compile(r"psql|7890|postgres|answer_keys|dev_questions|" + re.escape(str(ROOT)) + "|making-sense", re.I)
TRANSCRIPTS = ROOT / "runs/cc_ab"
TIMEOUT_S = 1500


def claude_cmd(arm: str, question: str, model: str, cfg: str | None) -> list[str]:
    base = ["claude", "-p", question, "--bare", "--output-format", "stream-json", "--verbose", "--model", model,
            "--no-session-persistence", "--max-turns", "60", "--strict-mcp-config"]
    if arm == "mcp":
        return base + ["--tools", "", "--mcp-config", cfg, "--allowedTools", "mcp__logs__*"]
    return base + ["--tools", "Bash,Read,Grep,Glob", "--allowedTools", "Bash,Read,Grep,Glob"]


def parse(stdout: str) -> dict:
    events = [json.loads(x) for x in stdout.splitlines() if x.strip().startswith("{")]
    calls, errors, answer, res = [], [], "", {}
    for e in events:
        msg = e.get("message") or {}
        content = msg.get("content") if isinstance(msg.get("content"), list) else []
        for b in content:
            if b.get("type") == "tool_use":
                calls.append({"name": b["name"].removeprefix("mcp__logs__"), "args": b.get("input")})
            if b.get("type") == "tool_result" and b.get("is_error"):
                errors.append(str(b.get("content"))[:300])
        if e.get("type") == "result":
            res = e
            answer = e.get("result") or ""
    return {"events": events, "calls": calls, "errors": errors, "answer": answer, "result": res}


def run_one(arm: str, q: dict, model: str) -> dict:
    """One headless Claude Code run in a fresh temp dir. Returns answer, calls, timing, tokens, cost."""
    wd = Path(tempfile.mkdtemp(prefix=f"cc-{q['id']}-{arm}-"))
    cfg = None
    try:
        if arm == "mcp":
            cfg = str(wd.parent / f"{wd.name}.mcp.json")
            Path(cfg).write_text(json.dumps({"mcpServers": {"logs": {
                "command": str(ROOT / ".venv/bin/python"), "args": [str(ROOT / "mcp_server/server.py")],
                "cwd": str(ROOT), "env": {"LOGS_DATASET": q["dataset"]}}}}))
            prompt = q["question"]
        else:
            (wd / "logs").mkdir()
            for f in FILES[q["dataset"]]:
                f, name = f if isinstance(f, tuple) else (f, Path(f).name)
                os.link(Path(f) if f.startswith("/") else RAW / f, wd / "logs" / name)   # hard link: no path back to the repo
            prompt = q["question"] + WHERE
        env = {k: v for k, v in os.environ.items() if k not in ("ANTHROPIC_BASE_URL", "ANTHROPIC_AUTH_TOKEN")}
        t0 = time.perf_counter()
        try:
            p = subprocess.run(claude_cmd(arm, prompt, model, cfg), cwd=wd, capture_output=True, text=True,
                               timeout=TIMEOUT_S, env=env)
            out, err = p.stdout, p.stderr
        except subprocess.TimeoutExpired as e:
            out = e.stdout.decode() if isinstance(e.stdout, bytes) else (e.stdout or "")
            err = f"timeout after {TIMEOUT_S} s"
        wall = time.perf_counter() - t0
        r = parse(out)
        TRANSCRIPTS.mkdir(parents=True, exist_ok=True)
        (TRANSCRIPTS / f"{q['id']}-{arm}.jsonl").write_text(out)
        res, u = r["result"], r["result"].get("usage") or {}
        bad = sorted({FORBIDDEN.search(json.dumps(c["args"])).group(0) for c in r["calls"]
                      if FORBIDDEN.search(json.dumps(c["args"] or {}))}) if arm == "bare" else []
        failed = not r["answer"] or res.get("is_error") or res.get("subtype") not in (None, "success")
        run = {"text": r["answer"], "tools_used": [c["name"] for c in r["calls"]], "calls": r["calls"],
               "tool_errors": r["errors"], "elapsed_s": round(wall, 1), "duration_api_s": round((res.get("duration_api_ms") or 0) / 1000, 1),
               "turns": res.get("num_turns"), "cost_usd": res.get("total_cost_usd"),
               "tokens_in": (u.get("input_tokens") or 0) + (u.get("cache_read_input_tokens") or 0)
               + (u.get("cache_creation_input_tokens") or 0), "tokens_out": u.get("output_tokens") or 0,
               "integrity": bad, "stderr": err[-1500:]}
        if failed:
            run["error"] = f"{res.get('subtype') or 'no result'}: {err[-300:]}"
            run["text"] = run["text"] if not res.get("is_error") else ""
        return run
    finally:
        shutil.rmtree(wd, ignore_errors=True)
        if cfg:
            Path(cfg).unlink(missing_ok=True)


def clean(text: str) -> str:
    """Drop the session-report link lines (they name our product), then the usual blinding."""
    text = re.sub(r"(?im)^.*(see every step|127\.0\.0\.1|localhost:\d+).*$", "", text)
    return text.strip()


def arm_stats(rows: list[dict], arm: str) -> dict:
    g = [x for r in rows if r.get("judge") for x in r["judge"]["grades"][arm]]
    runs = [r["runs"][arm] for r in rows]
    ok = [x for x in runs if not x.get("error")]
    mean = lambda xs: round(statistics.mean(xs), 3) if xs else None  # noqa: E731
    med = lambda xs: round(statistics.median(xs), 1) if xs else None  # noqa: E731
    c, w = sum(x["claims_correct"] for x in g), sum(x["claims_wrong"] for x in g)
    return {"runs": len(runs), "failed (scored 0)": len(runs) - len(ok),
            "integrity flags": sum(1 for x in runs if x.get("integrity")),
            "claim_accuracy": round(c / (c + w), 3) if c + w else None, "claims_correct": c, "claims_wrong": w,
            "found_problem (0-2)": mean([x["found_problem"] for x in g]),
            "rubric (1-5)": mean([statistics.mean(x[k] for k in RUBRIC) for x in g]),
            "E1 golden facts": mean([r["E1"][arm] for r in rows if r["E1"][arm] is not None]),
            "wall_s mean": mean([x["elapsed_s"] for x in runs]), "wall_s median": med([x["elapsed_s"] for x in runs]),
            "wall_s max": max((x["elapsed_s"] for x in runs), default=None),
            "turns": mean([x["turns"] for x in ok if x.get("turns")]),
            "tool_calls": mean([len(x["tools_used"]) for x in ok]),
            "tool_errors": sum(len(x.get("tool_errors", [])) for x in runs),
            "tokens_in": mean([x["tokens_in"] for x in ok]), "tokens_out": mean([x["tokens_out"] for x in ok]),
            "cost_usd per answer": mean([x["cost_usd"] for x in runs if x.get("cost_usd") is not None]),
            "cost_usd total": round(sum(x.get("cost_usd") or 0 for x in runs), 2)}


def render_md(rep: dict, rows: list[dict]) -> str:
    A, B = ARMS
    L = [f"# Claude Code + logs MCP ({A}) vs plain Claude Code on raw files ({B}) — {rep['stamp']}", "",
         f"git {rep['git']} · Claude Code {rep['cc_version']} · model {rep['model']} (both arms, --bare) · judge "
         f"{rep['judge_model']} (eval/ab.py, unchanged) · seed {rep['seed']} · {len(rows)} questions · leaks: "
         f"{rep['leaks'] or 'none'}", "", "## Wins (blind judge, both orders, only order-consistent wins count)", "",
         f"| slice | {A} | {B} | tie | inconsistent |", "|---|---|---|---|---|"]
    t = tally(rows)
    L.append(f"| all | {t[A]} | {t[B]} | {t['tie']} | {t['inconsistent']} |")
    for dim in ("role", "dataset"):
        for v in sorted({r[dim] for r in rows}):
            t = tally([r for r in rows if r[dim] == v])
            L.append(f"| {dim} {v} | {t[A]} | {t[B]} | {t['tie']} | {t['inconsistent']} |")
    L += ["", "## Per arm", "", f"| metric | {A} | {B} |", "|---|---|---|"]
    L += [f"| {k} | {rep['arms'][A][k]} | {rep['arms'][B].get(k)} |" for k in rep["arms"][A]]
    L += ["", "## Per question", "", f"| id | role | dataset | result | {A} found / wrong | {B} found / wrong | "
          f"{A} s / calls / $ | {B} s / calls / $ |", "|---|---|---|---|---|---|---|---|"]
    for r in rows:
        j = r.get("judge") or {}
        f = lambda a: "/".join(str(sum(g[k] for g in j["grades"][a])) for k in ("found_problem", "claims_wrong")) if j else "-"  # noqa: E731
        s = lambda a: (f"{r['runs'][a]['elapsed_s']} / {len(r['runs'][a]['tools_used'])} / "  # noqa: E731
                       f"{round(r['runs'][a].get('cost_usd') or 0, 2)}" + (" ⚠" if r["runs"][a].get("error") else ""))
        L.append(f"| {r['id']} | {r['role']} | {r['dataset']} | {j.get('result', r.get('judge_skipped', 'not judged'))} | "
                 f"{f(A)} | {f(B)} | {s(A)} | {s(B)} |")
    return "\n".join(L) + "\n"


async def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--questions", default=str(ROOT / "eval/dev_questions.yaml"))
    ap.add_argument("--ids")
    ap.add_argument("--model", default="sonnet")
    ap.add_argument("--concurrency", type=int, default=3)
    ap.add_argument("--seed", type=int, default=13)
    ap.add_argument("--rejudge", metavar="RUNS_JSON")
    ap.add_argument("--no-judge", action="store_true")
    a = ap.parse_args()
    qs = yaml.safe_load(Path(a.questions).read_text())
    if a.ids:
        keep = set(a.ids.split(","))
        qs = [q for q in qs if q["id"] in keep]
    assert all((KEYS / f"{q['id']}.yaml").exists() for q in qs)
    tools = await MultiServerMCPClient(mcp_config("bgl")).get_tools()
    names = {t.name for t in tools}
    titles = {x for x in {t.description.split("\n")[0].strip().rstrip("?.") for t in tools if t.description} if len(x) > 25}
    stored = {r["id"]: r["runs"] for r in json.loads(Path(a.rejudge).read_text())} if a.rejudge else {}
    judge_model = init_chat_model(JUDGE_MODEL, max_tokens=8000)
    sem = asyncio.Semaphore(a.concurrency)
    all_leaks: list[str] = []

    async def one(q: dict) -> dict:
        async with sem:
            if a.rejudge:
                runs = stored[q["id"]]
            else:
                runs = {}
                rnd = random.Random(f"{a.seed}-run-{q['id']}")
                for arm in sorted(ARMS, key=lambda _: rnd.random()):
                    runs[arm] = await asyncio.to_thread(run_one, arm, q, a.model)
            row = {"id": q["id"], "role": q["role"], "dataset": q["dataset"], "runs": runs,
                   "E1": {arm: (golden_hits(q, runs[arm]["text"])[0] / len(q["golden"]) if q.get("golden") and runs[arm]["text"] else
                                (0.0 if q.get("golden") else None)) for arm in ARMS}}
            texts = {arm: blind(clean(runs[arm]["text"]), names, titles) or "(the system failed and returned no answer)"
                     for arm in ARMS}
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
                  + "".join(f"  {arm} {runs[arm]['elapsed_s']}s/{len(runs[arm]['tools_used'])} calls/${runs[arm].get('cost_usd') or 0:.2f}"
                            + (f" ERR {runs[arm]['error'][:60]}" if runs[arm].get("error") else "")
                            + (f" INTEGRITY {runs[arm]['integrity']}" if runs[arm].get("integrity") else "") for arm in ARMS),
                  flush=True)
            return row

    rows = await asyncio.gather(*(one(q) for q in qs))
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    rep = {"stamp": stamp, "git": subprocess.run(["git", "rev-parse", "--short", "HEAD"], cwd=ROOT, capture_output=True,
                                                 text=True).stdout.strip(),
           "cc_version": subprocess.run(["claude", "--version"], capture_output=True, text=True).stdout.strip(),
           "model": a.model, "judge_model": JUDGE_MODEL, "seed": a.seed, "leaks": all_leaks, "rejudge": a.rejudge,
           "tally": tally(rows), "arms": {arm: arm_stats(rows, arm) for arm in ARMS},
           "rows": [{k: v for k, v in r.items() if k != "runs"} | {"tools": {arm: r["runs"][arm]["tools_used"] for arm in ARMS}}
                    for r in rows]}
    out = ROOT / "eval/results"
    (out / f"cc-{stamp}.json").write_text(json.dumps(rep, indent=1, default=str))
    (out / f"cc-{stamp}.runs.json").write_text(json.dumps([{"id": r["id"], "runs": r["runs"]} for r in rows], default=str))
    md = render_md(rep, rows)
    (out / f"cc-{stamp}.md").write_text(md)
    print(md)
    return 0


if __name__ == "__main__":
    sys.exit(asyncio.run(main()))
