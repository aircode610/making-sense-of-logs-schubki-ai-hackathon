"""Detect an unseen log file's format from the lnav format definitions and build its loader SQL (plan 057 part 3 by
Konark, made a library in plan 016 so the MCP server and the CLI share it).

How (unchanged from scripts/ingest.py): the first 2,000 lines are scored inside SereneDB against every regex of every
vendored lnav format (formats/lnav/*.json, BSD-2, github.com/tstack/lnav), converted from PCRE to RE2 (named groups
kept, unnamed made non-capturing, duplicate names renamed; look-around → that regex is skipped and counted). The format
matching the most lines wins (tie → more named fields), only if it covers >= min_coverage of the sample (else nothing is
loaded: no guessed timestamps). Fields come from lnav's own roles (timestamp, level-field + level map, body-field,
module-field, opid-field) and common field names; the timestamp format is the one that parses most sample timestamps;
a format without a year gets `year` (stated). Lines the format does not match are kept as continuation lines and listed
in `ingest_unparsed`.

Plan 016: the lines come from any SQL relation with columns (line_id, line): `read_csv('/data/…')` for a file under the
repo's data/ (the reproducible committed loaders in load/gen/), or a table the server streamed the user's file into
(COPY … FROM STDIN; works for a file anywhere on the user's disk and for a remote SereneDB).
"""
import json
import re
from dataclasses import dataclass, field
from pathlib import Path
from typing import Optional

import psycopg

ROOT = Path(__file__).resolve().parents[2]
FORMATS = ROOT / "src/formats/lnav"
SAMPLE = 2000
LEVELS = {"fatal": "FATAL", "critical": "CRITICAL", "error": "ERROR", "warning": "WARNING", "info": "INFO",
          "stats": "INFO", "notice": "NOTICE", "debug": "DEBUG", "debug2": "DEBUG", "debug3": "DEBUG",
          "debug4": "DEBUG", "debug5": "DEBUG", "trace": "TRACE"}
ROLE_NAMES = {  # first present wins; lnav's own *-field settings come first (see build())
    "component": ["log_procname", "tag", "app_name", "module", "component", "logger", "class", "category", "service",
                  "procname", "proc", "src"],
    "node": ["log_hostname", "hostname", "host", "server", "s_ip"],
    "request_id": ["opid", "request_id", "trace_id", "session_id", "log_syslog_tag", "pid", "app_pid", "log_pid"],
    "status": ["sc_status", "status", "http_status", "response_code"],
}
TS_FORMATS = ["%Y-%m-%d %H:%M:%S.%f", "%Y-%m-%d %H:%M:%S,%g", "%Y-%m-%d %H:%M:%S.%g", "%Y-%m-%d %H:%M:%S",
              "%Y-%m-%dT%H:%M:%S.%f%z", "%Y-%m-%dT%H:%M:%S%z", "%Y-%m-%dT%H:%M:%S.%f", "%Y-%m-%dT%H:%M:%S",
              "%d/%b/%Y:%H:%M:%S %z", "%a %b %d %H:%M:%S %Y", "%y/%m/%d %H:%M:%S", "%Y/%m/%d %H:%M:%S",
              "%b %d %H:%M:%S", "%m-%d %H:%M:%S.%g", "%m-%d %H:%M:%S", "%m.%d %H:%M:%S", "%H:%M:%S.%g", "%H:%M:%S"]


def to_re2(p: str) -> tuple[str, list[str]]:
    """PCRE (lnav) → RE2: keep named groups as (?P<name>…), make unnamed groups non-capturing, rename duplicate names
    (name, name__2, …). Returns the pattern and the group names in order (= regexp_extract's group order)."""
    out, names, i, in_class = [], [], 0, False
    while i < len(p):
        c = p[i]
        if c == "\\":
            out.append(p[i:i + 2]); i += 2; continue
        if in_class:
            if c == "]":
                in_class = False
            out.append(c); i += 1; continue
        if c == "[":
            in_class = True
            out.append(c); i += 1
            if i < len(p) and p[i] == "^":
                out.append("^"); i += 1
            if i < len(p) and p[i] == "]":
                out.append("]"); i += 1
            continue
        if c == "(":
            m = re.match(r"\(\?P?<([A-Za-z_]\w*)>", p[i:])
            if m:
                n, k = m.group(1), 2
                while n in names:
                    n = f"{m.group(1)}__{k}"; k += 1
                names.append(n)
                out.append(f"(?P<{n}>"); i += m.end(); continue
            if not p.startswith("(?", i):
                out.append("(?:"); i += 1; continue
        out.append(c); i += 1
    return "".join(out), names


def lit(s: str) -> str:
    return "'" + s.replace("'", "''") + "'"


@dataclass
class Detection:
    ok: bool
    reason: str = ""                    # why nothing is loaded (ok = False)
    sample_lines: int = 0
    candidates: list = field(default_factory=list)   # [(format, coverage)] best first
    regexes_skipped: int = 0
    format: str = ""
    format_title: str = ""
    coverage: float = 0.0
    ts_format: str = ""
    year_assumed: Optional[int] = None
    field_map: dict = field(default_factory=dict)
    stage_sql: str = ""                 # CREATE TEMP TABLE stage AS … (from the given relation)
    hits: int = 0


def detect(c: psycopg.Connection, relation: str, year: Optional[int] = None, min_coverage: float = 0.95) -> Detection:
    """Score every lnav format on the first SAMPLE lines of `relation` (columns line_id, line) and build the stage SQL."""
    c.execute("DROP TABLE IF EXISTS ingest_sample")
    c.execute(f"CREATE TEMP TABLE ingest_sample AS SELECT line FROM {relation} ORDER BY line_id LIMIT {SAMPLE}")
    n = c.execute("SELECT count(*) FROM ingest_sample").fetchone()[0]
    if not n:
        return Detection(False, "the file has no lines")

    results, skipped = [], []
    for f in sorted(FORMATS.glob("*.json")):
        d = json.loads(f.read_text())
        fname = next(k for k in d if not k.startswith("$"))
        fmt = d[fname]
        pats = []
        for rname, r in (fmt.get("regex") or {}).items():
            pat, names = to_re2(r.get("pattern", ""))
            try:
                c.execute(f"SELECT regexp_matches('', {lit(pat)})")
                pats.append((rname, pat, names))
            except psycopg.Error as e:
                skipped.append(f"{fname}.{rname}: {str(e).splitlines()[0][:70]}")
        if not pats:
            continue
        cond = " OR ".join(f"regexp_matches(line, {lit(p)})" for _, p, _ in pats)
        hits = c.execute(f"SELECT count(*) FILTER (WHERE {cond}) FROM ingest_sample").fetchone()[0]
        if hits:
            results.append({"format": fname, "title": fmt.get("title", fname), "fmt": fmt, "patterns": pats,
                            "hits": hits, "fields": len({x for _, _, ns in pats for x in ns})})
    results.sort(key=lambda r: (-r["hits"], -r["fields"], r["format"]))
    cands = [(r["format"], round(r["hits"] / n, 3)) for r in results[:5]]
    det = Detection(False, sample_lines=n, candidates=cands, regexes_skipped=len(skipped))
    if not results or results[0]["hits"] / n < min_coverage:
        best = results[0]["hits"] / n if results else 0
        det.reason = (f"no known log format fits: best coverage {best:.1%} < {min_coverage:.0%} of a {n}-line sample "
                      f"({len(list(FORMATS.glob('*.json')))} lnav formats tried). Nothing loaded (no guessed timestamps).")
        return det
    best = results[0]
    fmt, pats = best["fmt"], best["patterns"]
    allnames = []
    for _, _, ns in pats:
        allnames += [x for x in ns if x not in allnames]

    def present(base: str) -> list[str]:  # every renamed copy of a field (name, name__2, …) across the patterns
        return [x for x in allnames if x == base or x.startswith(base + "__")]

    # ---- roles from lnav's own settings, then common names
    role = {"timestamp": fmt.get("timestamp-field", "timestamp"), "body": fmt.get("body-field", "body"),
            "level": fmt.get("level-field", "level")}
    for r, cands_ in ROLE_NAMES.items():
        own = {"component": fmt.get("module-field"), "request_id": fmt.get("opid-field")}.get(r)
        role[r] = next((x for x in ([own] if own else []) + cands_ if present(x)), None)

    def fld(base: Optional[str]) -> str:
        if not base or not present(base):
            return "NULL"
        return "nullif(coalesce(" + ", ".join(f"r{i}.{x}" for i, (_, _, ns) in enumerate(pats) for x in ns
                                               if x == base or x.startswith(base + "__")) + "), '')"  # unmatched group = ''

    ts_expr = fld(role["timestamp"])
    if ts_expr == "NULL":
        det.reason = f"the best format ({best['format']}) has no timestamp field. Nothing loaded."
        return det

    # ---- timestamp format: the one that parses most sample timestamps (lnav's own formats first)
    m_cols = ", ".join(f"CASE WHEN regexp_matches(line, {lit(p)}) THEN regexp_extract(line, {lit(p)}, "
                       f"[{', '.join(lit(x) for x in ns)}]) END AS r{i}" for i, (_, p, ns) in enumerate(pats))
    c.execute("DROP TABLE IF EXISTS ingest_ts")
    c.execute(f"CREATE TEMP TABLE ingest_ts AS SELECT regexp_replace(trim({ts_expr}), '\\s+', ' ', 'g') AS t "
              f"FROM (SELECT line, {m_cols} FROM ingest_sample) WHERE {ts_expr} IS NOT NULL")
    lnav_ts = [x.replace("%L", "%g").replace("%i", "%g") for x in (fmt.get("timestamp-format") or [])]
    best_ts, best_ok, year_used = None, 0, None
    for tf in dict.fromkeys(lnav_ts + TS_FORMATS):
        needs_year = not any(k in tf for k in ("%Y", "%y"))
        yr = (year or 2000) if needs_year else year
        expr = f"try_strptime({lit(str(yr) + ' ')} || t, {lit('%Y ' + tf)})" if needs_year else f"try_strptime(t, {lit(tf)})"
        try:
            ok = c.execute(f"SELECT count(*) FILTER (WHERE {expr} IS NOT NULL) FROM ingest_ts").fetchone()[0]
        except psycopg.Error:
            continue
        if ok > best_ok:
            best_ts, best_ok, year_used = tf, ok, (yr if needs_year else None)
    tsn = c.execute("SELECT count(*) FROM ingest_ts").fetchone()[0]
    if not best_ts or best_ok / max(tsn, 1) < min_coverage:
        det.reason = (f"format {best['format']} matched, but no timestamp format parses >= {min_coverage:.0%} of its "
                      f"timestamps (best {best_ts} {best_ok}/{tsn}). Nothing loaded.")
        return det

    # ---- level: lnav level map (regexes RE2 accepts) on the level field, else the value itself
    lvl_src = fld(role["level"]) if role["level"] != "body" else fld(role["body"])
    lvl = "NULL"
    if lvl_src != "NULL":
        cases = []
        for k, rx in (fmt.get("level") or {}).items():
            if k in LEVELS:
                try:
                    c.execute(f"SELECT regexp_matches('', {lit(rx)})")
                    cases.append(f"WHEN regexp_matches({lvl_src}, {lit(rx)}) THEN '{LEVELS[k]}'")
                except psycopg.Error:
                    det.regexes_skipped += 1
        order = list(LEVELS.values())
        cases.sort(key=lambda s: order.index(s.split("THEN '")[1].rstrip("'")))
        if cases:
            lvl = "CASE " + " ".join(cases) + " END"
        elif role["level"] != "body":
            lvl = f"upper({lvl_src})"

    ts_sql = (f"try_strptime({lit(str(year_used) + ' ')} || regexp_replace(trim({ts_expr}), '\\s+', ' ', 'g'), "
              f"{lit('%Y ' + best_ts)})" if year_used is not None else
              f"try_strptime(regexp_replace(trim({ts_expr}), '\\s+', ' ', 'g'), {lit(best_ts)})")
    body = fld(role["body"])
    # component: the format's field; when it is empty on a matched line (e.g. a logcat tag with '-' or '.'), the generic
    # "name: message" prefix of the body; never NULL on a matched line (NULL = continuation line in stage_to_logs.sql)
    comp = fld(role["component"])
    prefix = f"nullif(regexp_extract(coalesce({body}, line), '^([A-Za-z][\\w.$-]*): ', 1), '')"
    matched = " OR ".join(f"r{i} IS NOT NULL" for i in range(len(pats)))
    comp_sql = f"CASE WHEN {matched} THEN coalesce({comp + ', ' if comp != 'NULL' else ''}{prefix}, '-') END"
    node = fld(role["node"])
    status = fld(role["status"])
    status_sql = f"TRY_CAST({status} AS INTEGER)" if status != "NULL" else "NULL::INTEGER"
    fieldmap = {k: v for k, v in role.items() if v and (k != "level" or lvl != "NULL")}

    det.ok, det.format, det.format_title = True, best["format"], best["title"]
    det.hits, det.coverage, det.ts_format, det.year_assumed = best["hits"], best["hits"] / n, best_ts, year_used
    det.field_map = fieldmap
    det.stage_sql = f"""CREATE TEMP TABLE stage AS
WITH m AS (
    SELECT line_id, line, {m_cols}
    FROM {relation}
)
SELECT line_id,
       CASE WHEN {matched} THEN {ts_sql} END AS ts,
       {comp_sql}::VARCHAR AS component,
       {lvl}::VARCHAR AS severity,
       {node}::VARCHAR AS node,
       {node}::VARCHAR AS location,
       {status_sql} AS status,
       NULL::DOUBLE AS duration_ms,
       CASE WHEN {matched} THEN coalesce({body}, line) ELSE line END AS body,
       NULL::VARCHAR AS label,
       NULL::VARCHAR AS object_id,
       {fld(role['request_id'])}::VARCHAR AS request_id,
       ({matched}) AS parsed
FROM m"""
    return det


def loader_sql(det: Detection, name: str, file_label: str, pbase: int, title: Optional[str] = None) -> str:
    """A complete psql loader (run by loader.sqlrun or psql): stage from the detection + ingest report rows + the shared
    second half (lib/stage_to_logs.sql). `\\ir` is relative to load/gen/, where repo loaders are written."""
    n = det.sample_lines
    title = title or f"{Path(file_label).stem} ({det.format_title}, auto-detected)"
    desc = (f"Loaded by format auto-detection: lnav {det.format} ({det.format_title}), "
            f"{det.coverage:.1%} of a {n}-line sample matched; timestamp format {det.ts_format}"
            + (f"; the log has no year, {det.year_assumed} assumed" if det.year_assumed is not None else "")
            + f"; fields: {', '.join(f'{k} = {v}' for k, v in det.field_map.items())}. Unmatched lines are kept as "
              "continuation lines (ingest_report lists them).")
    role = det.field_map
    meanings = {"node": f"{role['node']} field of the {det.format} format" if role.get("node") else "",
                "location": "same as node" if role.get("node") else "",
                "request": f"{role['request_id']} field of the {det.format} format" if role.get("request_id") else "",
                "status": f"{role['status']} field" if role.get("status") else ""}
    return f"""-- Format: lnav {det.format} ({det.format_title}), {det.hits}/{n} sample lines matched ({det.coverage:.1%}).
-- Fields: {json.dumps(det.field_map)}; timestamp format {det.ts_format}{f'; year {det.year_assumed} assumed (not logged)' if det.year_assumed is not None else ''}.
-- Unmatched lines: body = whole line, time / component / level of the previous line (stage_to_logs.sql), listed in
-- ingest_unparsed. Patterns converted from PCRE to RE2 by loader/detect.py (formats/lnav/{det.format}.json).
\\timing on
{det.stage_sql};
INSERT INTO ingest_unparsed SELECT {lit(name)}, line_id FROM stage WHERE NOT parsed;
INSERT INTO ingest_runs VALUES ({lit(name)}, {lit(file_label)}, {lit(det.format)}, {lit(det.format_title)},
    {n}, {det.hits}, {lit(det.ts_format)}, {det.year_assumed if det.year_assumed is not None else 'NULL'}, {lit(json.dumps(det.field_map))},
    {lit(json.dumps([f'{f} {c:.3f}' for f, c in det.candidates]))}, {det.regexes_skipped});
\\set ds {name}
\\set pbase {pbase}
\\set title {lit(title)}
\\set description {lit(desc)}
\\set node_meaning {lit(meanings['node'])}
\\set location_meaning {lit(meanings['location'])}
\\set request_meaning {lit(meanings['request'])}
\\set status_meaning {lit(meanings['status'])}
\\ir ../lib/stage_to_logs.sql
"""
