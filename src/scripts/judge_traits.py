"""Jev pattern traits (plan 011): one multi-question ai_system_one call per pattern, inside SereneDB, stored as CSV.

  .venv/bin/python scripts/judge_traits.py [dataset ...]     # default: every dataset in the `datasets` table
  → data/pattern_traits_<dataset>.csv (committed; load/lib/build_dataset.sql loads it; a clean checkout needs no key)

Questions (calibrated probabilities, never LLM prose):
  threat     noul   security event (attack, intrusion attempt, failed / invalid authentication, unauthorized access)
                    → widens "problem" beyond hardware / software faults: p_problem = max(fault × (1 − dump), threat)
  cause      choice failure family (hardware, network or I/O, storage or filesystem, software or service, job or
                    application, configuration, security, not a failure)
  actionable score  does it point to something an operator can check or fix (no / maybe / yes)
  role       choice root problem vs consequence of another failure vs routine
  owner      choice which of THIS dataset's teams (ownership descriptions) should own it → cross-checks the table
Criteria are generic operations wording, never taken from one dataset's messages. Needs the typesafe secret
(./docker/secrets.sh).
"""
import csv
import json
import os
import sys
import time
from pathlib import Path

import psycopg
from psycopg.rows import dict_row

ROOT = Path(__file__).resolve().parents[2]

QUESTIONS = {
    "threat": {"type": "noul",
               "instructions": "Does `message` report a security event: an attack or intrusion attempt, failed or invalid "
                               "authentication, access by an unknown or unauthorized user, or a blocked suspicious request?",
               "criteria": {
                   "true": {"description": "Someone tried to get in, was refused, or behaved suspiciously.",
                            "examples": ["Failed password for invalid user admin from 10.0.0.5",
                                         "authentication failure for user root", "possible break-in attempt",
                                         "access denied: client not allowed", "too many login attempts, blocking address"]},
                   "false": {"description": "Normal operation or a technical fault without a security aspect.",
                             "examples": ["disk sda failed", "connection reset by peer", "service started",
                                          "user alice logged in successfully", "memory error corrected"]}}},
    "cause": {"type": "choice", "instructions": "Which kind of failure or event does `message` describe?",
              "criteria": {
                  "hardware": "physical components: memory, CPU, cache, board, power, cooling, disk hardware",
                  "network or I/O": "links, sockets, connections, timeouts between machines, network or I/O paths",
                  "storage or filesystem": "file systems, mounts, files or directories missing, disk space, snapshots",
                  "software or service": "a daemon, kernel or server process failing, crashing, panicking or misbehaving",
                  "job or application": "a user job or application crashing, timing out, being killed",
                  "configuration": "a wrong or missing setting, version or permission problem",
                  "security": "attacks, authentication failures, unauthorized access",
                  "not a failure": "routine status, progress, counters, diagnostic values, corrected or expected events"}},
    "actionable": {"type": "score",
                   "instructions": "Does `message` point to something an operator could check or fix (a component, a "
                                   "host, a file, a setting, an address)?",
                   "criteria": ["no", "maybe", "yes"]},
    "role": {"type": "choice", "instructions": "Is `message` more likely the root problem, or a consequence of another "
                                               "failure, or routine?",
             "criteria": {"root problem": "reports the failure itself (something broke here)",
                          "consequence": "reports an effect of a failure elsewhere (lost connection, aborted, retrying, "
                                         "shutting down because of an error)",
                          "routine": "normal operation, no failure"}},
}


def main(datasets: list[str]) -> None:
    env = os.environ.get
    with psycopg.connect(host=env("PGHOST", "localhost"), port=env("PGPORT", "7890"), user=env("PGUSER", "postgres"),
                         dbname=env("PGDATABASE", "postgres"), autocommit=True, row_factory=dict_row) as c:
        c.execute("SET sdb_scan_split = 'never'")
        c.execute(f"SET sdb_ai_max_api_calls_per_query = {int(os.environ.get('AI_CAP', 5000))}")  # plan 057: ingest.sh may raise it
        datasets = datasets or [r["dataset"] for r in c.execute("SELECT dataset FROM datasets ORDER BY pattern_base")]
        for ds in datasets:
            teams = c.execute("SELECT team, string_agg(DISTINCT description, '; ') AS d FROM ownership_raw "
                              "WHERE dataset = %(d)s GROUP BY 1 ORDER BY 1", {"d": ds}).fetchall()
            q = dict(QUESTIONS)
            if len(teams) >= 2:
                q["owner"] = {"type": "choice", "instructions": "Which team should own the problem in `message`?",
                              "criteria": {t["team"]: (t["d"] or t["team"])[:300] for t in teams}}
            t0 = time.time()
            qlit = "'" + json.dumps(q).replace("'", "''") + "'"  # must be a constant (not a bound parameter)
            own = ("(j).owner.choice AS owner_hint, round((j).owner.confidence, 4) AS owner_confidence"
                   if "owner" in q else "NULL AS owner_hint, NULL AS owner_confidence")
            rows = c.execute(
                "SELECT dataset, component, template, pattern_id, round((j).threat, 4) AS p_threat, "
                "(j).cause.choice AS cause, round((j).cause.confidence, 4) AS cause_confidence, "
                "round((j).actionable.score, 3) AS actionable, (j).role.choice AS role, " + own + " FROM ("
                "SELECT p.dataset, p.component, p.template, p.pattern_id, ai_system_one("
                "'component: ' || coalesce(p.component, '') || chr(10) || 'severity: ' || coalesce(p.severity, 'none') "
                "|| chr(10) || 'message template (numbers and ids masked): ' || p.template || chr(10) || "
                "'example message: ' || coalesce(l.body, ''), questions := " + qlit + "::JSON) AS j "
                "FROM patterns p LEFT JOIN logs l ON l.dataset = p.dataset AND l.line_id = p.example_line_id "
                "WHERE p.dataset = %(d)s) ORDER BY pattern_id", {"d": ds}).fetchall()
            out = ROOT / f"data/jev/pattern_traits_{ds}.csv"
            cols = ["dataset", "component", "template", "pattern_id", "p_threat", "cause", "cause_confidence",
                    "actionable", "role", "owner_hint", "owner_confidence"]
            with out.open("w", newline="") as fh:
                w = csv.writer(fh)
                w.writerow(cols)
                for r in rows:
                    w.writerow(["" if r[k] is None else r[k] for k in cols])
            print(f"{ds}: {len(rows)} patterns judged in {time.time() - t0:.1f} s → {out.relative_to(ROOT)}")


if __name__ == "__main__":
    main(sys.argv[1:])
