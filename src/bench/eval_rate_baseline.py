"""Plan 055: how well does rate_vs_baseline point at real trouble? Hour level, BGL TUNE PART ONLY (< 2005-12-05).
Labels are an evaluation check only, never tool input. Rule fixed before running: an hour is "unusual" if
new_in_baseline, or ratio >= 3 and share of baseline hours at or above <= 5 %. Compared with flagging the same number
of hours by raw line count (the obvious alternative). Run: .venv/bin/python bench/eval_rate_baseline.py"""
import statistics
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src/mcp_server"))
from core import query
from counts import rate_vs_baseline

S, E = datetime(2005, 6, 10), datetime(2005, 12, 5)  # full 7-day baselines; held-out month never touched


def unusual(r):
    x = r["rows"][0]
    return r["new_in_baseline"] or ((x.get("ratio") or 0) >= 3 and (x.get("share_windows_at_or_above") or 0) <= 0.05)


def evaluate(name, flt, truth_sql):
    truth = {r["h"] for r in query(truth_sql, {"s": S, "e": E})}
    hours, flagged, counts, ms = [], set(), {}, []
    h = S
    while h < E:
        r = rate_vs_baseline(dataset="bgl", start=h, end=h + timedelta(hours=1), **flt)
        ms.append(r["elapsed_ms"])
        counts[h] = r["rows"][0]["window_lines"]
        if counts[h] and unusual(r):
            flagged.add(h)
        hours.append(h)
        h += timedelta(hours=1)
    active = [h for h in hours if counts[h]]
    by_volume = set(sorted(active, key=lambda h: -counts[h])[:len(flagged)])  # same alarm budget
    t_act = truth & set(active)

    def score(sel):
        tp = len(sel & truth)
        return len(sel), tp / len(sel) if sel else 0, tp / len(t_act) if t_act else 0

    base_rate = len(t_act) / len(active) if active else 0
    print(f"\n{name}: {len(hours)} hours, {len(active)} with matching lines, {len(t_act)} of those contain alert lines "
          f"(base rate {base_rate:.2f})")
    for label, sel in (("rate_vs_baseline 'unusual'", flagged), ("same number of busiest hours", by_volume)):
        n, p, rc = score(sel)
        print(f"  {label:<30} flagged {n:>5}  precision {p:.2f}  recall {rc:.2f}")
    ms.sort()
    print(f"  latency: median {statistics.median(ms):.0f} ms, p95 {ms[int(len(ms) * .95)]:.0f} ms ({len(ms)} calls)")


t0 = time.perf_counter()
ALERT_H = ("SELECT DISTINCT date_trunc('hour', l.ts) AS h FROM logs l JOIN labels b ON b.dataset = 'bgl' "
           "AND b.line_id = l.line_id WHERE l.dataset = 'bgl' AND l.ts >= %(s)s AND l.ts < %(e)s")
# Onset = an alert category's first line after >= 7 quiet days (what a "vs the previous 7 days" tool is meant to catch).
ONSET_H = ("WITH a AS (SELECT b.label, l.ts FROM logs l JOIN labels b ON b.dataset = 'bgl' AND b.line_id = l.line_id "
           "WHERE l.dataset = 'bgl' AND l.ts < %(e)s), g AS (SELECT label, ts, ts - lag(ts) OVER (PARTITION BY label "
           "ORDER BY ts) AS gap FROM a) SELECT DISTINCT date_trunc('hour', ts) AS h FROM g "
           "WHERE (gap IS NULL OR gap >= INTERVAL 7 DAY) AND ts >= %(s)s")
for name, flt in (("all lines", {}), ("FATAL lines", {"severity": "FATAL"})):
    evaluate(f"BGL {name} vs any alert in the hour", flt, ALERT_H)
    evaluate(f"BGL {name} vs alert ONSET in the hour", flt, ONSET_H)
print(f"\ntotal {time.perf_counter() - t0:.0f} s")
