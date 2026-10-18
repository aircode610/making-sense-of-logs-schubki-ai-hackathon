"""Plan 005 check: top_patterns / priority_table numbers equal independent hand SQL on the raw tables, and every
priority score is reproduced from scratch (inputs recomputed here, percentiles + weights in plain Python).
Uses a tune-part period only (< 2005-12-05, held-out slice untouched). Run: .venv/bin/python bench/check_patterns.py"""
import statistics
import sys
from datetime import datetime
from decimal import ROUND_HALF_UP, Decimal
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src/mcp_server"))
from core import query
from patterns import WEIGHTS, priority_table, top_patterns

S, E, PS = datetime(2005, 11, 1), datetime(2005, 11, 29), datetime(2005, 10, 4)  # 4 weeks + previous 4 weeks
P = {"s": S, "e": E, "ps": PS}
fails, times = [], []


def check(name, got, want):
    ok = got == want
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"\n   got  {got}\n   want {want}"))
    if not ok:
        fails.append(name)


# Independent inputs, one simple query each (no CTE shared with the tool).
def per_pattern(sql):
    return {r["pattern_id"]: r["v"] for r in query(sql, P)}

lines = per_pattern("SELECT pattern_id, count(*) AS v FROM logs WHERE dataset='bgl' AND ts >= %(s)s AND ts < %(e)s GROUP BY 1")
problem = per_pattern("SELECT pattern_id, count(*) AS v FROM logs WHERE dataset='bgl' AND ts >= %(s)s AND ts < %(e)s "
                      "AND (severity IN ('FATAL','FAILURE','SEVERE','ERROR','CRITICAL','WARN','WARNING') OR severity IS NULL) GROUP BY 1")
nodes = per_pattern("SELECT pattern_id, count(DISTINCT node) AS v FROM logs WHERE dataset='bgl' AND ts >= %(s)s AND ts < %(e)s GROUP BY 1")
weeks = per_pattern("SELECT pattern_id, count(DISTINCT date_trunc('week', ts)) AS v FROM logs WHERE dataset='bgl' "
                    "AND ts >= %(s)s AND ts < %(e)s GROUP BY 1")
b_now = per_pattern("SELECT pattern_id, count(*) AS v FROM bursts WHERE dataset='bgl' AND start_ts >= %(s)s AND start_ts < %(e)s GROUP BY 1")
b_prev = per_pattern("SELECT pattern_id, count(*) AS v FROM bursts WHERE dataset='bgl' AND start_ts >= %(ps)s AND start_ts < %(s)s GROUP BY 1")
def round_sql(x, nd):  # SQL round(): half away from zero (Python's round() is half-to-even)
    return float(Decimal(repr(x)).quantize(Decimal(1).scaleb(-nd), rounding=ROUND_HALF_UP))


judg = {r["pattern_id"]: r for r in query("SELECT pattern_id, p_fault, p_dump, p_threat FROM pattern_judgments WHERE dataset='bgl'", {})}
p_problem = {p: max(judg[p]["p_fault"] * (1 - judg[p]["p_dump"]), judg[p]["p_threat"] or 0) for p in judg}
# default problem filter 'jev' (H18, plan 011): problem-severity lines AND max(p_fault × (1 − p_dump), p_threat) >= 0.5
cands = sorted(p for p in lines if problem.get(p, 0) > 0 and p_problem[p] >= 0.5)
n_weeks = 5  # 2005-11-01 (Tue) → 2005-11-28 (Mon) touches the calendar weeks of Oct 31, Nov 7, 14, 21, 28

inp = {p: {"frequency": b_now.get(p, 0), "trend": b_now.get(p, 0) - b_prev.get(p, 0), "spread": nodes[p],
           "persistence": round(weeks[p] / n_weeks, 3), "severity": round_sql(p_problem[p], 3)} for p in cands}


def cume_dist(key):
    vals = [inp[p][key] for p in cands]
    return {p: sum(v <= inp[p][key] for v in vals) / len(vals) for p in cands}

pct = {k: cume_dist(k) for k in WEIGHTS}
score = {p: round(100 * sum(WEIGHTS[k] * pct[k][p] for k in WEIGHTS), 1) for p in cands}

# priority_table
t = priority_table("bgl", start=S, end=E, limit=50)
times.append(t["elapsed_ms"])
check("candidates = problem-severity AND p_problem >= 0.5", t["total_matches"], len(cands))
check("previous period", t["previous_period"]["start"], "2005-10-04 00:00:00")
for it in t["items"]:
    p = it["pattern_id"]
    got = (it["inputs"]["bursts"], it["inputs"]["change"], it["inputs"]["nodes"], it["inputs"]["persistence"],
           it["inputs"]["severity_input"], it["inputs"]["lines"])
    want = (inp[p]["frequency"], inp[p]["trend"], inp[p]["spread"], inp[p]["persistence"], inp[p]["severity"], lines[p])
    if got != want or abs(it["score"] - score[p]) > 0.11:
        check(f"item {p} inputs / score", (got, it["score"]), (want, score[p]))
check("50 items: inputs + scores reproduced independently", len([f for f in fails if f.startswith("item")]), 0)
check("ranking order = independent scores", [i["pattern_id"] for i in t["items"]][:10],
      sorted(cands, key=lambda p: (-score[p], -inp[p]["frequency"], p))[:10])
check("contributions sum to score", all(abs(sum(i["contributions"].values()) - i["score"]) <= 0.3 for i in t["items"]), True)
roll = {r["team"]: r for r in t["team_rollup"]}
check("team roll-up bursts = sum over candidates", sum(r["bursts"] for r in roll.values()), sum(b_now.get(p, 0) for p in cands))

# top_patterns
r = top_patterns("bgl", start=S, end=E, rank_by="bursts", limit=50)
times.append(r["elapsed_ms"])
check("top_patterns candidates", r["total_matches"], len(cands))
check("top_patterns rows equal hand SQL",
      [(x["lines"], x["bursts"], x["bursts_prev"], x["nodes"], x["weeks_active"]) for x in r["rows"]],
      [(lines[x["pattern_id"]], b_now.get(x["pattern_id"], 0), b_prev.get(x["pattern_id"], 0), nodes[x["pattern_id"]],
        weeks[x["pattern_id"]]) for x in r["rows"]])
r = top_patterns("bgl", start=S, end=E, problem_only=False, team="hpc-workloads", limit=50)
times.append(r["elapsed_ms"])
check("team filter: only hpc-workloads (APP)", {x["team"] for x in r["rows"]} | {x["component"] for x in r["rows"]},
      {"hpc-workloads", "APP"})
for _ in range(10):
    times.append(priority_table("bgl", start=S, end=E)["elapsed_ms"])
    times.append(top_patterns("bgl", start=S, end=E)["elapsed_ms"])
times.sort()
print(f"\n{len(times)} calls: median {statistics.median(times):.0f} ms, p95 {times[int(len(times) * .95) - 1]:.0f} ms, max {times[-1]:.0f} ms")
sys.exit(1 if fails else 0)
