"""Database roles (plan 011; brief bonus "row-level security to control which records each role can access").

SereneDB has PostgreSQL roles and GRANTs but no row-level-security policies and no column privileges on search tables,
so access is enforced with roles + views, generated from the ownership table (generic: one team role per team):

  logs_engineer, logs_lead   read everything an agent tool reads; may create focus indexes (workspace tools)
  logs_manager               reads the same tables but may not create or drop anything (no workspace / remote_index)
  team_<team>                row-level: schema team_<team> holds views named logs, patterns, bursts, episodes, … that
                             contain only that team's components; the role may read ONLY those views. A connection that
                             does SET ROLE team_<team>; SET search_path = team_<team>, public sees one team's data with
                             unchanged tool SQL, and is refused (not leaked) anything else (term-dictionary tools on the
                             base index, BM25 ranking through a view).
The MCP server applies a role with LOGS_DB_ROLE=<role> (mcp_server/core.py). Labels (evaluation ground truth) are
granted to nobody. Run by load/reload.sh after the SQL steps; idempotent.
"""
import os
import re

import psycopg

READ_TABLES = ["logs", "datasets", "ownership", "ownership_raw", "patterns", "bursts", "episodes", "pattern_templates",
               "pattern_judgments", "pattern_traits", "pattern_index", "burst_summaries", "watchlist", "remote_sources",
               "dataset_examples", "ingest_runs", "ingest_unparsed", "component_areas", "schema_version"]
# per-team views: (name, SQL with {team}); rows are restricted to the team's (dataset, component) pairs
TEAM_VIEWS = {
    "logs": "SELECT l.* FROM public.logs l WHERE (l.dataset, l.component) IN ({own})",
    "patterns": "SELECT p.* FROM public.patterns p WHERE (p.dataset, p.component) IN ({own})",
    "pattern_templates": "SELECT p.* FROM public.pattern_templates p WHERE (p.dataset, p.component) IN ({own})",
    "bursts": "SELECT b.* FROM public.bursts b WHERE (b.dataset, b.pattern_id) IN ({pat})",
    "episodes": "SELECT e.* FROM public.episodes e WHERE (e.dataset, e.pattern_id) IN ({pat})",
    "pattern_judgments": "SELECT j.* FROM public.pattern_judgments j WHERE (j.dataset, j.pattern_id) IN ({pat})",
    "pattern_traits": "SELECT t.* FROM public.pattern_traits t WHERE (t.dataset, t.pattern_id) IN ({pat})",
    "ownership": "SELECT o.* FROM public.ownership o WHERE o.team = {lit}",
    "datasets": "SELECT d.* FROM public.datasets d WHERE d.dataset IN (SELECT dataset FROM public.ownership WHERE team = {lit})",
    "burst_summaries": "SELECT s.* FROM public.burst_summaries s WHERE (s.dataset, s.pattern_id) IN ({pat})",
    "watchlist": "SELECT w.* FROM public.watchlist w WHERE w.dataset IN (SELECT dataset FROM public.ownership WHERE team = {lit})",
}


def main() -> None:
    env = os.environ.get
    with psycopg.connect(host=env("PGHOST", "localhost"), port=env("PGPORT", "7890"), user=env("PGUSER", "postgres"),
                         dbname=env("PGDATABASE", "postgres"), autocommit=True) as c:
        existing = {r[0] for r in c.execute("SELECT rolname FROM pg_roles")}

        def role(name: str) -> None:
            if name not in existing:
                c.execute(f"CREATE ROLE {name}")
                existing.add(name)

        for r in ("logs_engineer", "logs_lead", "logs_manager"):
            role(r)
            for t in READ_TABLES:
                c.execute(f"GRANT SELECT ON {t} TO {r}")
        c.execute("CREATE TABLE IF NOT EXISTS workspaces (name VARCHAR, kind VARCHAR, dataset VARCHAR, source VARCHAR, "
                  "start_ts VARCHAR, end_ts VARCHAR, filters VARCHAR, rows BIGINT, build_ms DOUBLE, created VARCHAR)")
        for r in ("logs_engineer", "logs_lead"):
            c.execute(f"GRANT SELECT, INSERT, DELETE ON workspaces TO {r}")
            c.execute(f"GRANT CREATE ON SCHEMA public TO {r}")
        c.execute("GRANT SELECT ON workspaces TO logs_manager")
        teams = [r[0] for r in c.execute("SELECT DISTINCT team FROM ownership ORDER BY 1")]
        for team in teams:
            name = "team_" + re.sub(r"[^a-z0-9]+", "_", team.lower()).strip("_")
            role(name)
            lit = "'" + team.replace("'", "''") + "'"
            own = f"SELECT dataset, component FROM public.ownership WHERE team = {lit}"
            pat = f"SELECT dataset, pattern_id FROM public.patterns WHERE (dataset, component) IN ({own})"
            c.execute(f"CREATE SCHEMA IF NOT EXISTS {name}")
            c.execute(f"GRANT USAGE ON SCHEMA {name} TO {name}")
            for v, body in TEAM_VIEWS.items():
                c.execute(f"CREATE OR REPLACE VIEW {name}.{v} AS " + body.format(own=own, pat=pat, lit=lit))
                c.execute(f"GRANT SELECT ON {name}.{v} TO {name}")
        print(f"roles: logs_engineer, logs_lead, logs_manager + {len(teams)} team roles ({', '.join(teams)})")


if __name__ == "__main__":
    main()
