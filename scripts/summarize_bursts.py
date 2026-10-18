"""Model summaries of the top problem bursts (plan 011), written INSIDE SereneDB by ai_summarize_agg and stored.

  .venv/bin/python scripts/summarize_bursts.py [per_dataset=8]   → data/burst_summaries.csv (committed)
Per dataset: the largest bursts (by lines) of the patterns Jev calls a real problem, one per pattern. Each summary
reads the distinct messages of the burst ± 300 s in time order (same query as the summarize_burst tool). Needs the chat
secret `gemini` (./docker/secrets.sh). Model text is context, never evidence.
"""
import csv
import os
import sys
import time
from datetime import timedelta
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mcp_server"))
MODEL = os.environ.get("GEMINI_SQL_MODEL", "gemini-2.5-flash")


def main(per: int) -> None:
    env = os.environ.get
    with psycopg.connect(host=env("PGHOST", "localhost"), port=env("PGPORT", "7890"), user=env("PGUSER", "postgres"),
                         dbname=env("PGDATABASE", "postgres"), autocommit=True, row_factory=dict_row) as c:
        c.execute("SET sdb_scan_split = 'never'")
        picks = c.execute(
            "SELECT * FROM (SELECT b.dataset, b.pattern_id, b.burst_no, b.start_ts, b.end_ts, b.lines, "
            "row_number() OVER (PARTITION BY b.dataset ORDER BY b.lines DESC) AS r FROM ("
            "SELECT DISTINCT ON (b.dataset, b.pattern_id) b.* FROM bursts b JOIN pattern_judgments j "
            "ON j.dataset = b.dataset AND j.pattern_id = b.pattern_id WHERE j.p_problem >= 0.5 "
            "ORDER BY b.dataset, b.pattern_id, b.lines DESC) b) WHERE r <= %(n)s ORDER BY dataset, r", {"n": per}).fetchall()
        out = []
        t0 = time.time()
        for b in picks:
            lo, hi = b["start_ts"] - timedelta(seconds=300), b["end_ts"] + timedelta(seconds=300)
            src = (f"SELECT body, ts FROM (SELECT DISTINCT ON (pattern_id) pattern_id, ts, body FROM logs "
                   f"WHERE dataset = '{b['dataset']}' AND ts >= TIMESTAMP '{lo:%Y-%m-%d %H:%M:%S.%f}' "
                   f"AND ts <= TIMESTAMP '{hi:%Y-%m-%d %H:%M:%S.%f}' ORDER BY pattern_id, ts) ORDER BY ts LIMIT 40")
            s = c.execute(f"SELECT ai_summarize_agg(body, max_tokens := 6000 ORDER BY ts) AS s FROM ({src})").fetchone()["s"]
            out.append([b["dataset"], b["pattern_id"], b["burst_no"], s, MODEL, time.strftime("%Y-%m-%d")])
            print(f"{b['dataset']} pattern {b['pattern_id']} burst {b['burst_no']}: {len(s or '')} chars")
        with (ROOT / "data/burst_summaries.csv").open("w", newline="") as fh:
            w = csv.writer(fh)
            w.writerow(["dataset", "pattern_id", "burst_no", "summary", "model", "created"])
            w.writerows(out)
        print(f"{len(out)} summaries in {time.time() - t0:.0f} s → data/burst_summaries.csv")


if __name__ == "__main__":
    main(int(sys.argv[1]) if len(sys.argv) > 1 else 8)
