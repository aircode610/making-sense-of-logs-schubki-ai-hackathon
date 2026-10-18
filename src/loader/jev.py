"""Jev judgments for a dataset added at run time (plan 016), computed INSIDE SereneDB and written straight into the
tables the tools read (pattern_judgments, pattern_traits, component_areas, pattern_index.emb), then ownership is rebuilt
for that dataset. Same questions as the scripts that produce the committed CSVs (no copy of any prompt):
  scripts/judge_patterns.sql (fault / dump / corrected / kind), scripts/judge_traits.py (threat / cause / actionable /
  role / owner), scripts/judge_areas.py (functional area per component), scripts/embed_patterns.py (template vectors).
Needs the typesafe secret (Jev) and, for vectors, the gemini secret; each step is skipped (and reported) when its secret
is missing or the call fails. A dataset without judgments stays usable: the tools use the level rule for it.
"""
import json
import re
import sys
import time
from pathlib import Path
from typing import Callable

import psycopg

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "src/scripts"))
from judge_traits import QUESTIONS as TRAIT_QUESTIONS  # noqa: E402

from loader.sqlrun import run_file  # noqa: E402


def secrets(c: psycopg.Connection) -> set[str]:
    """Names of the AI secrets registered in SereneDB (typesafe, gemini)."""
    try:
        return {r[0] for r in c.execute("SELECT * FROM sdb_secrets()").fetchall()}
    except psycopg.Error:
        return set()


def _judge_select() -> str:
    """The SELECT inside scripts/judge_patterns.sql's COPY (…) TO STDOUT, with :where left as a placeholder."""
    text = (ROOT / "src/scripts/judge_patterns.sql").read_text()
    m = re.search(r"COPY \((.*)\) TO STDOUT", text, re.S)
    return m.group(1)


def judge(c: psycopg.Connection, ds: str, log: Callable[[str], None] = print) -> dict:
    """Judge every pattern of `ds`; returns {step: 'done N in s' | 'skipped: why'}."""
    out = {}
    have = secrets(c)
    n = c.execute("SELECT count(*) FROM patterns WHERE dataset = %s", (ds,)).fetchone()[0]
    c.execute(f"SET sdb_ai_max_api_calls_per_query = {n + 100}")  # one Jev call per pattern (default cap 5000)
    lit = "'" + ds.replace("'", "''") + "'"
    if "typesafe" not in have:
        reason = "skipped: no typesafe secret (TYPESAFE_API_KEY in .env)"
        return {"judgments": reason, "traits": reason, "areas": reason, **_embed(c, ds, have, log)}

    # ---- fault / dump / corrected / kind → pattern_judgments (p_threat filled after the traits)
    t0 = time.time()
    try:
        sel = _judge_select().replace(":where", f"p.dataset = {lit}")
        rows = c.execute(sel).fetchall()
        c.execute("DELETE FROM pattern_judgments WHERE dataset = %s", (ds,))
        with c.cursor().copy("COPY pattern_judgments (dataset, pattern_id, p_fault, p_dump, p_corrected, kind, "
                             "kind_confidence) FROM STDIN") as cp:
            for r in rows:  # dataset, component, template, pattern_id, p_fault, p_dump, p_corrected, kind, kind_conf
                cp.write_row([r[0], r[3], r[4], r[5], r[6], r[7], r[8]])
        out["judgments"] = f"done: {len(rows)} patterns in {time.time() - t0:.0f} s"
    except psycopg.Error as e:
        out["judgments"] = f"failed: {str(e).splitlines()[0][:160]}"
    log(f"jev judgments: {out['judgments']}")

    # ---- traits (threat / cause / actionable / role / owner among the dataset's curated teams) → pattern_traits
    t0 = time.time()
    try:
        teams = c.execute("SELECT team, string_agg(DISTINCT description, '; ') FROM ownership_raw WHERE dataset = %s "
                          "GROUP BY 1 ORDER BY 1", (ds,)).fetchall()
        q = dict(TRAIT_QUESTIONS)
        if len(teams) >= 2:
            q["owner"] = {"type": "choice", "instructions": "Which team should own the problem in `message`?",
                          "criteria": {t: (d or t)[:300] for t, d in teams}}
        qlit = "'" + json.dumps(q).replace("'", "''") + "'"
        own = ("(j).owner.choice, round((j).owner.confidence, 4)" if "owner" in q else "NULL, NULL")
        c.execute("DELETE FROM pattern_traits WHERE dataset = %s", (ds,))
        c.execute(
            "INSERT INTO pattern_traits SELECT dataset, pattern_id, round((j).threat, 4), (j).cause.choice, "
            "round((j).cause.confidence, 4), round((j).actionable.score, 3), (j).role.choice, " + own + " FROM ("
            "SELECT p.dataset, p.pattern_id, ai_system_one("
            "'component: ' || coalesce(p.component, '') || chr(10) || 'severity: ' || coalesce(p.severity, 'none') "
            "|| chr(10) || 'message template (numbers and ids masked): ' || p.template || chr(10) || "
            "'example message: ' || coalesce(l.body, ''), questions := " + qlit + "::JSON) AS j "
            "FROM patterns p LEFT JOIN logs l ON l.dataset = p.dataset AND l.line_id = p.example_line_id "
            f"WHERE p.dataset = {lit})")
        out["traits"] = f"done in {time.time() - t0:.0f} s"
    except psycopg.Error as e:
        out["traits"] = f"failed: {str(e).splitlines()[0][:160]}"
    log(f"jev traits: {out['traits']}")
    # p_threat + p_problem = max(fault × (1 − dump), threat) (DECISIONS H18), as load/lib/build_dataset.sql
    c.execute("UPDATE pattern_judgments j SET p_threat = t.p_threat FROM pattern_traits t "
              "WHERE j.dataset = %s AND t.dataset = j.dataset AND t.pattern_id = j.pattern_id", (ds,))
    c.execute("UPDATE pattern_judgments SET p_problem = greatest(p_fault * (1 - p_dump), coalesce(p_threat, 0)) "
              "WHERE dataset = %s", (ds,))

    # ---- functional area per component → component_areas (ownership chain step 5)
    t0 = time.time()
    try:
        import csv
        with (ROOT / "data/config/area_teams.csv").open() as fh:
            areas = {r["area"]: r["description"].replace(" (fictional default team)", "") for r in csv.DictReader(fh)}
        qa = {"area": {"type": "choice",
                       "instructions": "Which functional area of an IT system does the software `component` belong to?",
                       "criteria": areas}}
        qlit = "'" + json.dumps(qa).replace("'", "''") + "'"
        c.execute("DELETE FROM component_areas WHERE dataset = %s", (ds,))
        c.execute(
            "INSERT INTO component_areas WITH ex AS (SELECT p.component, l.body, row_number() OVER (PARTITION BY p.component "
            "ORDER BY p.lines DESC, p.pattern_id) AS rk FROM patterns p "
            "JOIN logs l ON l.dataset = p.dataset AND l.line_id = p.example_line_id "
            f"WHERE p.dataset = {lit} AND p.component IS NOT NULL), "
            "cc AS (SELECT component, string_agg(left(body, 200), chr(10) ORDER BY rk) AS examples "
            "FROM ex WHERE rk <= 3 GROUP BY 1) "
            f"SELECT {lit}, component, (j).area.choice, round((j).area.confidence, 4) "
            "FROM (SELECT cc.component, ai_system_one('component: ' || cc.component || chr(10) || 'system: ' || "
            "d.title || chr(10) || 'example messages:' || chr(10) || coalesce(cc.examples, ''), "
            "questions := " + qlit + "::JSON) AS j FROM cc, datasets d WHERE d.dataset = " + lit + ")")
        out["areas"] = f"done in {time.time() - t0:.0f} s"
    except psycopg.Error as e:
        out["areas"] = f"failed: {str(e).splitlines()[0][:160]}"
    log(f"jev areas: {out['areas']}")
    out.update(_embed(c, ds, have, log))
    run_file(c, ROOT / "src/sql/lib/ownership_dataset.sql", {"ds": ds})
    return out


def _embed(c: psycopg.Connection, ds: str, have: set, log) -> dict:
    """Template vectors for find_patterns(mode='semantic') / similar_patterns (gemini-embedding-001, 768 dims)."""
    if "gemini" not in have:
        return {"embeddings": "skipped: no gemini secret (GOOGLE_API_KEY in .env); lexical pattern search still works"}
    t0 = time.time()
    lit = "'" + ds.replace("'", "''") + "'"
    try:
        c.execute("DELETE FROM pattern_index WHERE dataset = %s", (ds,))
        c.execute("INSERT INTO pattern_index SELECT dataset, pattern_id, component, template, "
                  "ai_embed(coalesce(component, '') || ': ' || template, 'gemini-embedding-001', 'gemini', 768)::FLOAT[768] "
                  f"FROM patterns WHERE dataset = {lit}")
        c.execute("VACUUM (REFRESH_TABLE) pattern_index")
        r = f"done in {time.time() - t0:.0f} s"
    except psycopg.Error as e:  # keep the text-only rows so lexical find_patterns works
        c.execute("DELETE FROM pattern_index WHERE dataset = %s", (ds,))
        c.execute("INSERT INTO pattern_index SELECT dataset, pattern_id, component, template, NULL "
                  f"FROM patterns WHERE dataset = {lit}")
        c.execute("VACUUM (REFRESH_TABLE) pattern_index")
        r = f"failed: {str(e).splitlines()[0][:160]}"
    log(f"embeddings: {r}")
    return {"embeddings": r}
