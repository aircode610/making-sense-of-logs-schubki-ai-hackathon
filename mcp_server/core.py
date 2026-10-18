"""Shared plumbing for all MCP tools: DB connection, filters, and the result envelope.

Every tool result is an envelope: {tool, params, sql, filters, scope, rows, total_matches, truncated, elapsed_ms,
evidence_id}, so each number the agent cites can be traced to the query that produced it.
"""
import hashlib
import json
import os
import time
from datetime import datetime
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
        # Plan 016: AI keys from .env into SereneDB on every server start (its secrets are not persisted across container
        # restarts; replaces ./docker/secrets.sh). Before SET ROLE: needs the admin connection. No key → AI steps skip.
        try:
            import sys as _sys
            _sys.path.insert(0, str(__import__("pathlib").Path(__file__).resolve().parent.parent))
            from loader.core import register_secrets
            register_secrets(_conn)
        except Exception:  # noqa: BLE001  (a read-only user cannot create secrets: AI tools then say so)
            pass
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

# Plan 016: the server works on ONE dataset at a time (the user's own logs), chosen at run time: LOGS_DATASET (or the
# first loaded dataset) at start, then load_logs / use_dataset switch it. Tools have no `dataset` parameter; the
# wrapper in server.py passes the active one. LOGS_DATASET='*' = the multi-dataset server (every tool takes `dataset`;
# kept for the eval harness / comparisons, plan 011-013).
_active: Optional[str] = None
_reg_cache: Optional[dict] = None


def single() -> bool:
    """True = one active dataset, no `dataset` parameter (the shipped mode); False = LOGS_DATASET='*'."""
    return os.environ.get("LOGS_DATASET") != "*"


def active() -> Optional[str]:
    """The dataset every tool works on (None = nothing loaded yet: tools ask to load first)."""
    global _active
    if not single():
        return None
    if _active is None:
        loaded = _registry_all_cached()
        want = os.environ.get("LOGS_DATASET")
        _active = want if want in loaded else next(iter(loaded), None)
    return _active


def set_active(dataset: Optional[str]) -> None:
    global _active
    _active = dataset


def pinned() -> Optional[str]:
    """Plan 014 name, kept for callers: the active dataset in single-dataset mode."""
    return active()


def refresh() -> None:
    """Re-read the dataset registry (after load_logs / remove_dataset); keeps the active dataset if it still exists."""
    global _reg_cache, _active
    _reg_cache = None
    if _active is not None and _active not in _registry_all_cached():
        _active = None


def _registry_all_cached() -> dict:
    global _reg_cache
    if _reg_cache is None:
        try:
            _reg_cache = _registry_all()
        except psycopg.errors.UndefinedTable:  # an empty database: no schema yet (load_logs creates it)
            _reg_cache = {}
    return _reg_cache


def registry() -> dict:
    """The loaded datasets; in single-dataset mode only the active one ({} before anything is loaded)."""
    reg = _registry_all_cached()
    if single():
        a = active()
        return {a: reg[a]} if a in reg else {}
    return reg


def loaded_datasets() -> dict:
    """Every loaded dataset (for setup_status / use_dataset), whatever the mode."""
    return _registry_all_cached()


def need_dataset() -> str:
    """The active dataset, or a clear error telling the client how to get one."""
    a = active()
    if a is None:
        names = ", ".join(_registry_all_cached()) or "none"
        raise ValueError("No dataset is loaded yet. Call load_logs(source='bgl') and load_logs(source='openstack') for the "
                         "base corpus, or load_logs(source='/path/to/your.log'); loaded: " + names)
    return a


def _registry_all() -> dict:
    """{dataset: {title, description, <field>_meaning, first_ts, last_ts, lines, components[], severities[], teams[],
    examples{field: value}, entity_kinds[]}} read once per server process from the `datasets` / `dataset_examples`
    tables and the data itself (plan 012: what each generic field means per dataset lives in data, not code)."""
    out = {}
    for d in query("SELECT * FROM datasets ORDER BY pattern_base", {}):
        out[d["dataset"]] = dict(d, examples={}, entity_kinds=[])
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
    try:  # load/93_examples.sql (absent on an old database: descriptions just show no examples)
        for r in query("SELECT dataset, field, example FROM dataset_examples ORDER BY dataset, n_values DESC", {}):
            if r["dataset"] in out:
                out[r["dataset"]]["examples"][r["field"]] = r["example"]
                if r["field"].startswith("entity:"):
                    out[r["dataset"]]["entity_kinds"].append(r["field"][7:])
    except Exception:  # noqa: BLE001
        pass
    return out


def dataset_names() -> tuple[str, ...]:
    try:
        return tuple(registry()) or ("none",)
    except Exception:  # noqa: BLE001  (server started without a database: tools fail on call, not at import)
        return ("none",)


def _short(xs: list, n: int = 8) -> str:
    xs = xs or []
    return ", ".join(map(str, xs[:n])) + (f", … ({len(xs)} in all)" if len(xs) > n else "")


def _reg() -> dict:
    try:
        return registry()
    except Exception:  # noqa: BLE001
        return {}


def vocab_text(key: str, n: int = 8) -> str:
    """'<dataset>: most frequent values, …; …' for tool descriptions (values read from the data)."""
    return "; ".join(f"{d}: {_short(v.get(key), n)}" for d, v in _reg().items() if v.get(key))


# generic field → (datasets.<meaning column>, dataset_examples.field)
FIELD_META = {"node": ("node_meaning", "node"), "location": ("location_meaning", "location"),
              "request": ("request_meaning", "request_id"), "object": ("object_meaning", "object_id"),
              "status": ("status_meaning", "status"), "duration": ("duration_meaning", "duration_ms")}


def field_text(field: str, with_example: bool = True) -> str:
    """What a generic field means in each dataset that fills it, with a real example value, and which datasets leave it
    empty, e.g. "<dataset> = <meaning> (e.g. <value>); … Not logged in: <datasets>"."""
    mcol, ecol = FIELD_META[field]
    have, missing = [], []
    for d, v in _reg().items():
        meaning, ex = v.get(mcol), v["examples"].get(ecol)
        if meaning or ex:
            have.append(f"{d} = {meaning or 'filled'}" + (f" (e.g. {ex})" if with_example and ex else ""))
        else:
            missing.append(d)
    return "; ".join(have) + (f". Not logged in: {', '.join(missing)}" if missing and have else "")


def durations_in() -> str:
    """'<dataset>, <dataset>' = the datasets whose lines carry a duration (for tool descriptions)."""
    return ", ".join(d for d, v in _reg().items() if v.get("duration_meaning")) or "none loaded"


def field_guide() -> str:
    """Per dataset, what to pass for each filter: span, levels, top components, and the meaning + a real example of every
    field it fills (node, location, request_id, object_id, status, duration, entity kinds). Written ONCE into the server
    instructions (and returned by describe_corpus) instead of into every parameter description: token budget."""
    lines = []
    for d, v in _reg().items():
        span = f"{v['first_ts']:%Y-%m-%d} → {v['last_ts']:%Y-%m-%d}" if v.get("first_ts") else "no rows"
        parts = [f"{d} ({span}, {v.get('lines', 0):,} lines): {v['title']}",
                 "levels " + (", ".join(v.get("severitys") or []) or "none (severity is NULL)"),
                 "components " + _short(v.get("components"), 5)]
        for f in ("node", "location", "request", "object", "status", "duration"):
            mcol, ecol = FIELD_META[f]
            if v.get(mcol) or v["examples"].get(ecol):
                ex = v["examples"].get(ecol)
                parts.append(f"{ecol if f in ('request', 'object') else f} = {v.get(mcol) or 'filled'}"
                             + (f" (e.g. {ex})" if ex and f != "duration" else ""))
        if v.get("teams"):
            parts.append("teams " + ", ".join(v["teams"]))
        if v["entity_kinds"]:
            parts.append("entities " + ", ".join(f"{k} (e.g. {v['examples'].get('entity:' + k)})" for k in v["entity_kinds"][:3]))
        lines.append("- " + "; ".join(parts))
    return "\n".join(lines)


def entity_text() -> str:
    """Entity kinds per dataset with a real example: '<dataset>: ip (e.g. ip:…); …'."""
    reg = _reg()
    return "; ".join(f"{d}: " + ", ".join(f"{k} (e.g. {v['examples'].get('entity:' + k)})" for k in v["entity_kinds"][:3])
                     for d, v in reg.items() if v["entity_kinds"])


def corpus_text() -> str:
    """One line per dataset (title, span, size): MCP instructions + agent prompts."""
    reg = _reg()
    if not reg:
        return "datasets: see describe_corpus"
    parts = []
    for d, v in reg.items():
        span = (f"{v['first_ts']:%Y-%m-%d} → {v['last_ts']:%Y-%m-%d}" if v.get("first_ts") else "no rows")
        parts.append(f"{d}: {v['title']} ({span}, {v.get('lines', 0):,} lines)")
    return " · ".join(parts)


def node_note(dataset: Optional[str]) -> str:
    """'' or a warning that `nodes` is 0 because the dataset logs no node / host (spread is unknown, not 'one node')."""
    if dataset and _reg().get(dataset, {}).get("has_node") is False:
        return f"; {dataset} logs no node / host, so nodes = 0 means unknown spread"
    return ""


def check_dataset(dataset: Optional[str]) -> Optional[str]:
    if dataset is not None and dataset not in dataset_names():
        raise ValueError(f"Unknown dataset {dataset!r}; loaded: {', '.join(dataset_names())} (describe_corpus).")
    return dataset


# ---------------------------------------------------------------- shared parameter types (plan 012): one description
# per concept, written once and reused by every tool, with the per-dataset meaning and real example values from the
# registry, so the model knows what to pass for the dataset it is working on.

# JSON-schema enum of the datasets loaded at start (multi-dataset mode only; in the shipped single-dataset mode the
# parameter is removed from every tool and the datasets can change while the server runs)
DatasetName = str if single() else Literal[dataset_names()]
_DS_HELP = "Dataset (log source); see the field guide."
Dataset = Annotated[DatasetName, Field(description=_DS_HELP)]
DatasetOpt = Annotated[Optional[DatasetName], Field(description=_DS_HELP + " Omit to cover all datasets.")]
Start = Annotated[Optional[datetime], Field(
    description="Inclusive start time, 'YYYY-MM-DD HH:MM[:SS]', in the dataset's own clock (each dataset has its own "
                "span). Omit for the dataset's beginning.")]
End = Annotated[Optional[datetime], Field(
    description="Exclusive end time, same format. Omit for the dataset's end.")]
_GUIDE = " Per dataset: field guide."
Component = Annotated[Optional[str], Field(
    description="Exact component (program / service / class that logged the line; case-sensitive). Per dataset: "
                "field guide; all values: list_values.")]
Severity = Annotated[Optional[str], Field(description="Exact log level, upper case (e.g. ERROR)." + _GUIDE)]
Node = Annotated[Optional[str], Field(description="Exact node / host that logged the line." + _GUIDE)]
Location = Annotated[Optional[str], Field(
    description="Location path ('/'-separated, coarse → fine), matched at ANY level: the first level(s) filter a "
                "whole group." + _GUIDE)]
RequestId = Annotated[Optional[str], Field(
    description="Exact request / session / trace / block id: all lines of one unit of work." + _GUIDE)]
ObjectId = Annotated[Optional[str], Field(
    description="Exact id of a long-lived object followed across requests (e.g. a VM)." + _GUIDE)]
Entity = Annotated[Optional[str], Field(
    description="One typed value extracted from the message text, 'kind:value', e.g. 'ip:10.0.0.7', 'path:/var/log', "
                "'uuid:…'. top_entities ranks them.")]
Status = Annotated[Optional[int], Field(description="Exact status code (e.g. HTTP 503) where the dataset logs one." + _GUIDE)]
Team = Annotated[Optional[str], Field(
    description="Owning team, or 'unowned' (component without an owner). Teams per dataset: field guide.")]
PatternIdOpt = Annotated[Optional[int], Field(
    description="Log pattern id (a kind of message; rows of most tools carry one).")]


def is_problem(j: str, problem_lines: str, error_lines: str, ds: str) -> str:
    """SQL condition "this pattern is a problem" (DECISIONS H18 + plan 016 fallback). Judged dataset: problem-level lines
    (error-or-worse, WARN, 5xx, or no level) AND stored Jev p_problem >= 0.5. Dataset never judged (added without an AI
    key): at least one explicit error-or-worse / WARN / 5xx line (a line with no level cannot be judged without Jev);
    results say so via judged_note. j = pattern_judgments alias; the others are SQL expressions."""
    return (f"(CASE WHEN EXISTS (SELECT 1 FROM pattern_judgments jx WHERE jx.dataset = {ds}) "
            f"THEN {problem_lines} > 0 AND {j}.p_problem >= 0.5 ELSE {error_lines} > 0 END)")


def judged(dataset: Optional[str]) -> bool:
    """Whether the dataset's patterns carry Jev judgments (False → problem tools use the level rule)."""
    return dataset is None or bool(query("SELECT 1 AS x FROM pattern_judgments WHERE dataset = %(d)s LIMIT 1",
                                         {"d": dataset}))


def judged_note(dataset: Optional[str]) -> list[str]:
    """[] or the hint every problem-ranking result carries for an unjudged dataset."""
    if judged(dataset):
        return []
    return [f"{dataset} has no Jev judgments (added without an AI key): problem = a pattern with error-or-worse / "
            "WARN / 5xx lines, not a judged real fault (diagnostic dumps and corrected errors may be included; lines "
            "without a level are not counted). Say so in the answer."]


def filters_sql(f: dict) -> tuple[str, dict]:
    """Equality / time-range filters → (`AND ...` clause, bound params). Only non-None values are applied."""
    clauses, params = [], {}
    check_dataset(f.get("dataset"))
    for col in ("dataset", "component", "severity", "node", "request_id", "object_id", "status", "pattern_id"):
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
    if f.get("location") is not None:  # any level of the path: 'a', 'a/b', or a full location
        clauses.append(f"location @@ ts_tokenize({lit(f['location'])}, 'keyword')")
    if f.get("entity") is not None:    # one extracted value, e.g. 'ip:10.0.0.1'
        clauses.append(f"entities @@ ts_tokenize({lit(f['entity'])}, 'keyword')")
    return "".join(f" AND {c}" for c in clauses), params


# ---------------------------------------------------------------- full-text query builder (plan 011)

MatchMode = Literal["web", "all", "any", "phrase", "near", "fuzzy", "prefix", "at_least", "synonyms"]
MATCH_HELP = ("How query_text matches: 'web' (default: all words, \"phrase\", a OR b, -word); 'all'; 'any' (one "
              "word is enough); 'phrase' (adjacent, in order); 'near' (within `slop` words); 'fuzzy' (up to `distance` "
              "typos per word); 'prefix' (`sever` → severed); 'at_least' (`min_match` of the words); 'synonyms' (a "
              "word or its log-jargon synonym: fail/error/fault, lost/severed, denied/refused, …).")


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


def filter_hints(f: dict) -> list[str]:
    """Deterministic next-step hints when filters match nothing (plan 012): a component / severity that is not a value of
    the dataset, with the closest real values, so the agent corrects the call instead of concluding 'absent'."""
    import difflib
    out = []
    reg = _reg()
    scope = [reg[f["dataset"]]] if f.get("dataset") in reg else list(reg.values())
    for key, col in (("component", "components"), ("severity", "severitys")):
        v = f.get(key)
        if v is None:
            continue
        values = sorted({x for d in scope for x in d.get(col) or []})
        if v not in values:
            close = difflib.get_close_matches(v, values, n=3, cutoff=0.3) or values[:5]
            out.append(f"{key} {v!r} does not occur" + (f" in {f['dataset']}" if f.get("dataset") else "")
                       + (f"; closest values: {', '.join(close)}" if close else "; this dataset logs no " + key)
                       + f" (list_values field='{key}').")
    return out


def search_hints(total: int, truncated: bool, f: dict, query_text: Optional[str], rows: list[dict]) -> list[str]:
    """Next-step hints for a search-like result (plan 012). Deterministic, short, never a conclusion."""
    h = filter_hints(f) if not total else []
    if not total and query_text:
        h.append("0 matches: try match='fuzzy' (typos) or match='synonyms', suggest_terms for the logged wording, "
                 "find_patterns to search by meaning, or fewer filters / a wider time range.")
    if truncated:
        h.append(f"rows are a sample of {total:,} matches: use total_matches / first_ts / last_ts for counts; count_by, "
                 f"facet or trend with the same filters for breakdowns.")
    pids = list(dict.fromkeys(r.get("pattern_id") for r in rows if r.get("pattern_id") is not None))[:3]
    if pids:
        h.append(f"pattern_id {', '.join(map(str, pids))} = the kind(s) of message found: pattern_history / spread / "
                 f"precursors(pattern_id) for their history, reach and what precedes them.")
    return h


def envelope(tool: str, params: dict, sqls: list[str], filters: dict, scope: str, rows: list[dict],
             t0: float, **extra) -> dict:
    sql_text = "; ".join(sqls)
    eid = hashlib.sha1(json.dumps([tool, sql_text], default=str).encode()).hexdigest()[:10]
    env = {"tool": tool, "params": plain({k: v for k, v in params.items() if v is not None}, "T"),
           "sql": sqls, "filters": plain({k: v for k, v in filters.items() if v is not None}, "T"), "scope": scope,
           **plain(extra, "T"), "rows": [clean_row(r) for r in rows],
           "elapsed_ms": round((time.perf_counter() - t0) * 1000, 1), "evidence_id": f"ev-{eid}"}
    # Plan 014: a truncated result says how much is missing and how to get it, so a small but important row (a rare
    # new error, one IP) is not silently cut. Totals stay exact either way.
    total = extra.get("total_matches")
    if extra.get("truncated") and rows and isinstance(total, int) and total > len(rows):
        env["truncation"] = {"shown": len(rows), "of": total,
                             "how_to_see_more": f"raise limit (max {MAX_ROWS}) or narrow the filters / period; "
                                                "group with count_by / facet for the full distribution"}
    return env
