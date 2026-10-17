"""Shared plumbing for all MCP tools: DB connection, filters, and the result envelope.

Every tool result is an envelope: {tool, params, sql, filters, scope, rows, total_matches, truncated, elapsed_ms,
evidence_id}, so each number the agent cites can be traced to the query that produced it.
"""
import hashlib
import json
import os
import time
from datetime import datetime

import psycopg
from psycopg.rows import dict_row

MAX_ROWS = 50
MAX_BODY = 300  # chars per log message returned to the agent

_conn = None


def conn() -> psycopg.Connection:
    """One autocommit connection per server process; host/port/user from PG* env vars (defaults: local docker)."""
    global _conn
    if _conn is None or _conn.closed:
        env = os.environ.get
        _conn = psycopg.connect(host=env("PGHOST", "localhost"), port=env("PGPORT", "7890"),
                                user=env("PGUSER", "postgres"), dbname=env("PGDATABASE", "postgres"),
                                autocommit=True, row_factory=dict_row)
    return _conn


def query(sql: str, params: dict) -> list[dict]:
    return conn().execute(sql, params).fetchall()


def filters_sql(f: dict) -> tuple[str, dict]:
    """Equality / time-range filters → (`AND ...` clause, bound params). Only non-None values are applied."""
    clauses, params = [], {}
    for col in ("dataset", "component", "severity", "node", "midplane", "rack", "request_id", "instance_id", "pattern_id"):
        if f.get(col) is not None:
            clauses.append(f"{col} = %({col})s")
            params[col] = f[col]
    if f.get("start") is not None:
        clauses.append("ts >= %(start)s")
        params["start"] = f["start"]
    if f.get("end") is not None:
        clauses.append("ts < %(end)s")
        params["end"] = f["end"]
    return "".join(f" AND {c}" for c in clauses), params


def render(sql: str, params: dict) -> str:
    """SQL with parameters inlined, for display and re-running by hand (execution always binds)."""
    out = sql
    for k, v in sorted(params.items(), key=lambda kv: -len(kv[0])):
        lit = "'" + str(v).replace("'", "''") + "'" if isinstance(v, (str, datetime)) else str(v)
        out = out.replace(f"%({k})s", lit)
    return " ".join(out.split())


def clean_row(r: dict) -> dict:
    """JSON-friendly row: ISO timestamps, long bodies cut and flagged, NULL columns dropped."""
    out = {}
    for k, v in r.items():
        if v is None:
            continue
        if isinstance(v, datetime):
            v = v.isoformat(sep=" ")
        if k == "body" and len(v) > MAX_BODY:
            v, out["body_cut"] = v[:MAX_BODY] + "…", True
        out[k] = v
    return out


def envelope(tool: str, params: dict, sqls: list[str], filters: dict, scope: str, rows: list[dict],
             t0: float, **extra) -> dict:
    sql_text = "; ".join(sqls)
    eid = hashlib.sha1(json.dumps([tool, sql_text], default=str).encode()).hexdigest()[:10]
    return {"tool": tool, "params": {k: v for k, v in params.items() if v is not None},
            "sql": sqls, "filters": {k: v for k, v in filters.items() if v is not None}, "scope": scope,
            **extra, "rows": [clean_row(r) for r in rows],
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1), "evidence_id": f"ev-{eid}"}
