"""Jev functional area per component (plan 057): one ai_system_one choice per (dataset, component), inside SereneDB.

  .venv/bin/python scripts/judge_areas.py [dataset ...]     # default: every dataset in the `datasets` table
  → data/component_areas_<dataset>.csv (committed; load/96b_ownership_inferred.sql loads it; a clean checkout needs no key)

Input per component: its name, the dataset's title and up to 3 example messages (from its most frequent patterns).
Choices = the areas of data/area_teams.csv with their descriptions (generic operations wording, no dataset text).
The area is used for ownership only when no curated row exists and no name rule matches, and only at p >= 0.6.
Needs the typesafe secret (./docker/secrets.sh).
"""
import csv
import json
import os
import sys
import time
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parent.parent


def main(datasets: list[str]) -> None:
    with (ROOT / "data/area_teams.csv").open() as fh:
        areas = {r["area"]: r["description"].replace(" (fictional default team)", "") for r in csv.DictReader(fh)}
    q = {"area": {"type": "choice",
                  "instructions": "Which functional area of an IT system does the software `component` belong to?",
                  "criteria": areas}}
    qlit = "'" + json.dumps(q).replace("'", "''") + "'"  # must be a constant (not a bound parameter)
    env = os.environ.get
    with psycopg.connect(host=env("PGHOST", "localhost"), port=env("PGPORT", "7890"), user=env("PGUSER", "postgres"),
                         dbname=env("PGDATABASE", "postgres"), autocommit=True, row_factory=dict_row) as c:
        c.execute("SET sdb_scan_split = 'never'")
        c.execute("SET sdb_ai_max_api_calls_per_query = 5000")
        datasets = datasets or [r["dataset"] for r in c.execute("SELECT dataset FROM datasets ORDER BY pattern_base")]
        for ds in datasets:
            t0 = time.time()
            rows = c.execute(
                "WITH ex AS (SELECT p.component, l.body, row_number() OVER (PARTITION BY p.component "
                "ORDER BY p.lines DESC, p.pattern_id) AS rk FROM patterns p "
                "JOIN logs l ON l.dataset = p.dataset AND l.line_id = p.example_line_id "
                "WHERE p.dataset = %(d)s AND p.component IS NOT NULL), "
                "c AS (SELECT component, string_agg(left(body, 200), chr(10) ORDER BY rk) AS examples "
                "FROM ex WHERE rk <= 3 GROUP BY 1) "
                "SELECT %(d)s AS dataset, component, (j).area.choice AS area, round((j).area.confidence, 4) AS confidence "
                "FROM (SELECT c.component, ai_system_one('component: ' || c.component || chr(10) || 'system: ' || "
                "d.title || chr(10) || 'example messages:' || chr(10) || coalesce(c.examples, ''), "
                "questions := " + qlit + "::JSON) AS j FROM c, datasets d WHERE d.dataset = %(d)s) "
                "ORDER BY component", {"d": ds}).fetchall()
            out = ROOT / f"data/component_areas_{ds}.csv"
            cols = ["dataset", "component", "area", "confidence"]
            with out.open("w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(cols)
                for r in rows:
                    w.writerow(["" if r[k] is None else r[k] for k in cols])
            print(f"{ds}: {len(rows)} components judged in {time.time() - t0:.1f} s → {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1:])
