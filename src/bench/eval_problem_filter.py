"""Plan 006: which "problem pattern" filter matches real alerts? Pattern level, TUNE PART ONLY (ts < 2005-12-05).
Labels are used here as an evaluation check only, never as tool input. Run: .venv/bin/python bench/eval_problem_filter.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src/mcp_server"))
from core import query

rows = query("""
WITH t AS (
    SELECT l.pattern_id, count(*) AS lines, count(b.label) AS alert_lines,
           count(*) FILTER (WHERE l.severity IN ('FATAL','FAILURE','SEVERE','ERROR')) AS problem_lines
    FROM logs l LEFT JOIN labels b ON b.dataset = 'bgl' AND b.line_id = l.line_id
    WHERE l.dataset = 'bgl' AND l.ts < TIMESTAMP '2005-12-05' GROUP BY 1)
SELECT t.*, j.p_fault, j.p_dump, j.p_corrected, j.kind,
       (SELECT count(*) FROM bursts b WHERE b.dataset = 'bgl' AND b.pattern_id = t.pattern_id
        AND b.start_ts < TIMESTAMP '2005-12-05') AS bursts
FROM t JOIN pattern_judgments j ON j.dataset = 'bgl' AND j.pattern_id = t.pattern_id""", {})

FILTERS = {
    "severity (FATAL/FAILURE/SEVERE/ERROR)": lambda r: r["problem_lines"] > 0,
    "jev p_fault >= 0.5": lambda r: r["p_fault"] >= 0.5,
    "jev p_fault x (1 - p_dump) >= 0.5": lambda r: r["p_fault"] * (1 - r["p_dump"]) >= 0.5,
    "severity AND jev p_fault >= 0.5": lambda r: r["problem_lines"] > 0 and r["p_fault"] >= 0.5,
    "severity AND jev p_fault x (1 - p_dump) >= 0.5": lambda r: r["problem_lines"] > 0 and r["p_fault"] * (1 - r["p_dump"]) >= 0.5,
}
alert = [r for r in rows if r["alert_lines"] > 0]
print(f"tune part: {len(rows)} patterns, {len(alert)} carry alerts\n")
print(f"{'filter':<48} {'flagged':>7} {'prec':>6} {'recall':>6} {'F1':>6} {'burst-prec':>10}")
for name, f in FILTERS.items():
    flagged = [r for r in rows if f(r)]
    tp = [r for r in flagged if r["alert_lines"] > 0]
    p = len(tp) / len(flagged) if flagged else 0
    rc = len(tp) / len(alert)
    f1 = 2 * p * rc / (p + rc) if p + rc else 0
    bp = sum(r["bursts"] for r in tp) / max(1, sum(r["bursts"] for r in flagged))  # share of flagged bursts that are alert patterns
    print(f"{name:<48} {len(flagged):>7} {p:>6.2f} {rc:>6.2f} {f1:>6.2f} {bp:>10.2f}")
