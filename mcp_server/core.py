"""Shared plumbing for all MCP tools: DB connection, filters, and the result envelope.

Every tool result is an envelope: {tool, params, sql, filters, scope, rows, total_matches, truncated, elapsed_ms,
evidence_id}, so each number the agent cites can be traced to the query that produced it.
"""
import hashlib
import json
import os
import time
from datetime import datetime
from functools import lru_cache
from typing import Annotated, Literal, Optional

import psycopg
from psycopg.rows import dict_row
from pydantic import Field

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
        # Correctness workaround (plan 011): a GROUP BY on a keyword column with a document filter is answered from the
        # term dictionary (TsDict); when a segment is split across worker threads its counts came out off by one.
        _conn.execute("SET sdb_scan_split = 'never'")
        # Database-enforced access (plan 011, load/99_roles.py): LOGS_DB_ROLE=logs_engineer | logs_lead | logs_manager
        # | team_<team>. A team role reads its own schema's views (only its components' rows) under the same names.
        role = env("LOGS_DB_ROLE")
        if role:
            if not role.replace("_", "").isalnum():
                raise ValueError("LOGS_DB_ROLE: letters, digits and _ only")
            _conn.execute(f"SET ROLE {role}")
            if role.startswith("team_"):
                _conn.execute(f"SET search_path = {role}, public")
    return _conn


def team_scoped() -> bool:
    """True when the connection reads a team's views (LOGS_DB_ROLE=team_…): no BM25 / term dictionary there."""
    return (os.environ.get("LOGS_DB_ROLE") or "").startswith("team_")


def query(sql: str, params: Optional[dict]) -> list[dict]:
    # no params → no placeholder parsing, so literal '%' (LIKE patterns, rendered SQL) is safe
    return conn().execute(sql, params or None).fetchall()


def execute(sql: str, params: Optional[dict] = None) -> None:
    """DDL / writes (workspace tools): no result rows."""
    conn().execute(sql, params or None)


# ---------------------------------------------------------------- dataset registry (plan 011: nothing dataset-specific
# in tool code; names, components, severities and teams come from the loaded data, so a new dataset needs no change here)

@lru_cache(maxsize=1)
def registry() -> dict:
    """{dataset: {title, description, location_hint, id_fields, first_ts, last_ts, lines, components[], severities[],
    teams[]}} read once per server process from the `datasets` table and the data itself."""
    out = {}
    for d in query("SELECT * FROM datasets ORDER BY pattern_base", {}):
        out[d["dataset"]] = dict(d)
    for r in query("SELECT dataset, min(ts) AS first_ts, max(ts) AS last_ts, count(*) AS lines FROM logs GROUP BY 1", {}):
        if r["dataset"] in out:
            out[r["dataset"]].update(first_ts=r["first_ts"], last_ts=r["last_ts"], lines=r["lines"])
    for col in ("component", "severity"):
        for r in query(f"SELECT dataset, {col} AS v, count(*) AS n FROM logs WHERE {col} IS NOT NULL "
                       f"GROUP BY 1, 2 ORDER BY 1, 3 DESC", {}):
            if r["dataset"] in out:
                out[r["dataset"]].setdefault(col + "s", []).append(r["v"])
    for r in query("SELECT dataset, count(node) > 0 AS has_node FROM logs GROUP BY 1", {}):
        if r["dataset"] in out:
            out[r["dataset"]]["has_node"] = r["has_node"]
    for r in query("SELECT dataset, team FROM ownership GROUP BY 1, 2 ORDER BY 1, 2", {}):
        if r["dataset"] in out:
            out[r["dataset"]].setdefault("teams", []).append(r["team"])
    return out


def dataset_names() -> tuple[str, ...]:
    try:
        return tuple(registry()) or ("bgl",)
    except Exception:  # noqa: BLE001  (server started without a database: tools fail on call, not at import)
        return ("bgl",)


def _short(xs: list, n: int = 8) -> str:
    xs = xs or []
    return ", ".join(map(str, xs[:n])) + (f", … ({len(xs)} in all)" if len(xs) > n else "")


def vocab_text(key: str, n: int = 8) -> str:
    """'bgl: KERNEL, APP, …; openstack: nova-compute, …' for tool descriptions (most frequent first)."""
    try:
        return "; ".join(f"{d}: {_short(v.get(key), n)}" for d, v in registry().items() if v.get(key))
    except Exception:  # noqa: BLE001
        return ""


def all_teams() -> str:
    try:
        return ", ".join(sorted({t for v in registry().values() for t in v.get("teams", [])})) + ", unowned"
    except Exception:  # noqa: BLE001
        return "unowned"


def corpus_text() -> str:
    """One paragraph per dataset (title, span, size, what location means): MCP instructions + agent prompts."""
    try:
        parts = []
        for d, v in registry().items():
            span = (f"{v['first_ts']:%Y-%m-%d} → {v['last_ts']:%Y-%m-%d}" if v.get("first_ts") else "no rows")
            parts.append(f"{d}: {v['title']} ({span}, {v.get('lines', 0):,} lines"
                         + (f"; location = {v['location_hint']}" if v.get("location_hint") else "")
                         + (f"; ids: {v['id_fields']}" if v.get("id_fields") else "") + ")")
        return " · ".join(parts)
    except Exception:  # noqa: BLE001
        return "datasets: see describe_corpus"


def node_note(dataset: Optional[str]) -> str:
    """'' or a warning that `nodes` is 0 because the dataset logs no node / host (spread is unknown, not 'one node')."""
    try:
        if dataset and registry().get(dataset, {}).get("has_node") is False:
            return f"; {dataset} logs no node / host, so nodes = 0 means unknown spread"
    except Exception:  # noqa: BLE001
        pass
    return ""


def check_dataset(dataset: Optional[str]) -> Optional[str]:
    if dataset is not None and dataset not in dataset_names():
        raise ValueError(f"Unknown dataset {dataset!r}; loaded: {', '.join(dataset_names())}.")
    return dataset


DatasetName = Literal[dataset_names()]  # JSON-schema enum of the datasets loaded when the server started
Dataset = Annotated[DatasetName, Field(description="Dataset: " + ", ".join(dataset_names()) + ".")]
DatasetOpt = Annotated[Optional[DatasetName], Field(
    description="Restrict to one dataset (" + ", ".join(dataset_names()) + "); omit for all.")]


def filters_sql(f: dict) -> tuple[str, dict]:
    """Equality / time-range filters → (`AND ...` clause, bound params). Only non-None values are applied."""
    clauses, params = [], {}
    check_dataset(f.get("dataset"))
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
    # Token predicates: literal arguments, never bound (see lit()).
    if f.get("location") is not None:  # any level of the path: 'R02', 'R02/R02-M1', or a full location
        clauses.append(f"location @@ ts_tokenize({lit(f['location'])}, 'keyword')")
    if f.get("entity") is not None:    # one extracted value, e.g. 'ip:10.0.0.1'
        clauses.append(f"entities @@ ts_tokenize({lit(f['entity'])}, 'keyword')")
    return "".join(f" AND {c}" for c in clauses), params


# ---------------------------------------------------------------- full-text query builder (plan 011)

MatchMode = Literal["web", "all", "any", "phrase", "near", "fuzzy", "prefix", "at_least", "synonyms"]
MATCH_HELP = ("How query_text matches: 'web' (default) = web-search syntax (words all required, \"phrase\", a OR b, "
              "-word); 'all' = every word; 'any' = at least one word; 'phrase' = the words adjacent in order; 'near' = "
              "the words within `slop` positions of each other; 'fuzzy' = every word with up to `distance` typos "
              "(Levenshtein); 'prefix' = every word as a prefix (`sever` → severed, severity); 'at_least' = at least "
              "`min_match` of the words; 'synonyms' = any word or its log-jargon synonym (error/fail/fault, "
              "disconnected/severed/lost, denied/refused/invalid, …).")


def _words(text: str) -> list[str]:
    import re
    return [w.lower() for w in re.findall(r"[\w.:\-/]+", text)] or [text.lower()]


def lit(v) -> str:
    """A SQL string literal (quotes doubled). Used for ts_* constructor arguments: a BOUND text parameter inside
    ts_phrase / ts_tokenize / ts_levenshtein / … failed with "Invalid unicode (byte sequence mismatch)" whenever the
    statement also bound a timestamp (SereneDB parameter-typing bug, plan 011); websearch / plainto take bound params."""
    return "'" + str(v).replace("'", "''") + "'"


def tsquery_sql(text: str, match: str = "web", slop: int = 2, distance: int = 1, min_match: int = 2,
                exclude: Optional[str] = None, key: str = "q") -> tuple[str, dict]:
    """(TSQUERY SQL expression, params) for one text + match mode; `exclude` removes lines matching that web query.
    Every mode compiles to an inverted-index predicate (`body @@ <expr>`), never a scan."""
    p: dict = {}
    words = _words(text)
    if match == "web":
        expr, p[key] = f"websearch_to_tsquery(%({key})s)", text
    elif match == "all":
        expr, p[key] = f"plainto_tsquery(%({key})s)", text
    elif match == "any":
        expr = f"{lit(' '.join(words))}::tsquery"
    elif match == "phrase":
        expr = f"ts_phrase({lit(text)})"
    elif match == "near":
        expr = f"ts_phrase({lit(text)}, slop := {int(slop)})"
    elif match in ("fuzzy", "prefix"):
        parts = [f"ts_levenshtein({lit(w)}, {int(distance)})" if match == "fuzzy" else f"ts_starts_with({lit(w)})"
                 for w in words]
        expr = parts[0] if len(parts) == 1 else "ts_all([" + ", ".join(parts) + "])"
    elif match == "at_least":
        expr = "ts_any([" + ", ".join(lit(w) for w in words) + f"], {min(int(min_match), len(words))})"
    elif match == "synonyms":
        expr = f"ts_tokenize({lit(text)}, 'log_synonyms')"
    else:
        raise ValueError(f"unknown match mode {match!r}")
    if exclude:
        expr, p[key + "_x"] = f"(({expr}) && !!websearch_to_tsquery(%({key}_x)s))", exclude
    return expr, p


def render(sql: str, params: dict) -> str:
    """SQL with parameters inlined, for display and re-running by hand (execution always binds)."""
    out = sql
    for k, v in sorted(params.items(), key=lambda kv: -len(kv[0])):
        lit = "'" + str(v).replace("'", "''") + "'" if isinstance(v, (str, datetime)) else str(v)
        out = out.replace(f"%({k})s", lit)
    return " ".join(out.split())


def plain(v, sep: str = " "):
    """JSON-friendly value, recursively: Decimal → int / float, datetime → ISO text, timedelta → seconds."""
    from datetime import date, timedelta
    from decimal import Decimal
    if isinstance(v, Decimal):
        return int(v) if v == v.to_integral_value() else float(v)
    if isinstance(v, datetime):
        return v.isoformat(sep=sep)
    if isinstance(v, date):
        return v.isoformat()
    if isinstance(v, timedelta):
        return v.total_seconds()
    if isinstance(v, dict):
        return {k: plain(x, sep) for k, x in v.items()}
    if isinstance(v, (list, tuple)):
        return [plain(x, sep) for x in v]
    return v


def clean_row(r: dict) -> dict:
    """JSON-friendly row: ISO timestamps, long bodies cut and flagged, NULL columns dropped."""
    out = {}
    for k, v in r.items():
        if v is None:
            continue
        v = plain(v)
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
    return {"tool": tool, "params": plain({k: v for k, v in params.items() if v is not None}, "T"),
            "sql": sqls, "filters": plain({k: v for k, v in filters.items() if v is not None}, "T"), "scope": scope,
            **plain(extra, "T"), "rows": [clean_row(r) for r in rows],
            "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1), "evidence_id": f"ev-{eid}"}
