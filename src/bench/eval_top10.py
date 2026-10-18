"""Plan 005/006 measurement: how many of the top 10 patterns carry real alerts, per ranking and problem filter.
TUNE PERIOD ONLY (2005-11-01 → 11-29); labels are an evaluation check, never tool input. Run: .venv/bin/python bench/eval_top10.py"""
import sys
from datetime import datetime
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src/mcp_server"))
from core import query
from patterns import priority_table, top_patterns

S, E = datetime(2005, 11, 1), datetime(2005, 11, 29)
alert = {r["pattern_id"] for r in query(
    "SELECT DISTINCT l.pattern_id FROM logs l JOIN labels b ON b.dataset = 'bgl' AND b.line_id = l.line_id "
    "WHERE l.dataset = 'bgl' AND l.ts >= %(s)s AND l.ts < %(e)s", {"s": S, "e": E})}

print(f"period {S:%Y-%m-%d} → {E:%Y-%m-%d}: alert-carrying patterns in the top 10\n")
print(f"{'ranking':<30} {'severity filter':>16} {'jev filter':>11}")
for name, fn in [("priority_table (score)", lambda f: [i["pattern_id"] for i in priority_table("bgl", start=S, end=E, problem_filter=f)["items"]]),
                 ("top_patterns by bursts", lambda f: [r["pattern_id"] for r in top_patterns("bgl", start=S, end=E, problem_filter=f, limit=10)["rows"]]),
                 ("top_patterns by nodes", lambda f: [r["pattern_id"] for r in top_patterns("bgl", start=S, end=E, problem_filter=f, rank_by="nodes", limit=10)["rows"]]),
                 ("top_patterns by lines", lambda f: [r["pattern_id"] for r in top_patterns("bgl", start=S, end=E, problem_filter=f, rank_by="lines", limit=10)["rows"]])]:
    print(f"{name:<30} {sum(p in alert for p in fn('severity')):>14}/10 {sum(p in alert for p in fn('jev')):>9}/10")
