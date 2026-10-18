"""Reload pre-step (plan 011): remove what a reload invalidates and what depends on the tables it recreates —
workspaces (focus-index tables ws_*, remote-index views rws_*, the registry) and the team schemas of load/99_roles.py
(recreated at the end of the reload). Idempotent; a fresh database has nothing to remove."""
import os

import psycopg

env = os.environ.get
with psycopg.connect(host=env("PGHOST", "localhost"), port=env("PGPORT", "7890"), user=env("PGUSER", "postgres"),
                     dbname=env("PGDATABASE", "postgres"), autocommit=True) as c:
    names = {r[0] for r in c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")}
    for t in sorted(n for n in names if n.startswith("ws_")):
        c.execute(f"DROP TABLE IF EXISTS {t} CASCADE")
    for idx in [r[0] for r in c.execute("SELECT index_name FROM sdb_indexes()") if r[0].startswith("rws_")]:
        c.execute(f"DROP INDEX IF EXISTS {idx}")
    for v in sorted(n for n in names if n.startswith("rws_")):
        c.execute(f"DROP VIEW IF EXISTS {v}")
    c.execute("DROP TABLE IF EXISTS workspaces")
    for s in [r[0] for r in c.execute("SELECT schema_name FROM information_schema.schemata WHERE schema_name LIKE 'team_%'")]:
        for v in [r[0] for r in c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = %s", (s,))]:
            c.execute(f"DROP VIEW IF EXISTS {s}.{v}")
        c.execute(f"DROP SCHEMA IF EXISTS {s}")
print("cleanup done")
