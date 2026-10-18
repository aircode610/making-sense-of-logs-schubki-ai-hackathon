"""Detect the format of an unseen log file and write a loader for it (plan 057 part 3). No hand-written parse query.

  .venv/bin/python scripts/ingest.py data/raw/<dir>/<file>.log <name> [--year 2017] [--title "…"] [--min-coverage 0.95]
  → load/gen/<name>.sql (a normal loader: readable, committed, run by load/reload.sh) + a report on stdout.
  scripts/ingest.sh does this, reloads, runs the Jev / area judgments and prints the result.

How: the first 2,000 lines go into SereneDB (read_csv, as every loader). Every regex of every lnav format definition
(formats/lnav/*.json, BSD-2, github.com/tstack/lnav) is converted to RE2 (named groups kept, unnamed groups made
non-capturing, duplicate names renamed; look-around is not supported by RE2 → that regex is skipped and listed) and
counted on the sample inside SereneDB. The format matching the most lines wins (tie → more named fields); it is used
only if it covers >= --min-coverage of the sample, otherwise nothing is loaded (no guessed timestamps).
Fields come from lnav's own roles (timestamp, level-field + level map, body-field, module-field, opid-field) and
common field names (log_hostname → node, log_procname / tag / app_name → component, …); the timestamp format is the
one that parses most sample timestamps in SereneDB (lnav's timestamp-format first, then common formats); a format
without a year gets --year (stated in the dataset description). Lines the format does not match are kept: they become
continuation lines (body = whole line, time of the previous line) and are listed in `ingest_unparsed`.
"""
import argparse
import json
import os
import re
import sys
from datetime import datetime
from pathlib import Path

import psycopg

ROOT = Path(__file__).resolve().parent.parent
SAMPLE = 2000
LEVELS = {"fatal": "FATAL", "critical": "CRITICAL", "error": "ERROR", "warning": "WARNING", "info": "INFO",
          "stats": "INFO", "notice": "NOTICE", "debug": "DEBUG", "debug2": "DEBUG", "debug3": "DEBUG",
          "debug4": "DEBUG", "debug5": "DEBUG", "trace": "TRACE"}
ROLE_NAMES = {  # first present wins; lnav's own *-field settings come first (see fields())
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


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("file"); ap.add_argument("name")
    ap.add_argument("--year", type=int, help="year for formats that do not log one (stated in the dataset row)")
    ap.add_argument("--title"); ap.add_argument("--min-coverage", type=float, default=0.95)
    a = ap.parse_args()
    src = Path(a.file).resolve()
    rel = src.relative_to(ROOT / "data")  # SereneDB sees ./data as /data
    if not re.fullmatch(r"[a-z][a-z0-9_]*", a.name):
        sys.exit("name: lower case letters, digits, _")
    env = os.environ.get
    c = psycopg.connect(host=env("PGHOST", "localhost"), port=env("PGPORT", "7890"), user=env("PGUSER", "postgres"),
                        dbname=env("PGDATABASE", "postgres"), autocommit=True)
    encoding = ""
    try:  # the whole file must decode: UTF-8, else latin-1 (raw bytes in attack payloads etc.; stated in the loader)
        c.execute(f"SELECT count(*) FROM read_csv('/data/{rel}', columns = {{'line': 'VARCHAR'}}, header = false, "
                  f"delim = E'\\x01', quote = '', escape = '', auto_detect = false)")
    except psycopg.Error:
        encoding = ", encoding = 'latin-1'"
        print("NOTE: not valid UTF-8; reading as latin-1")
    read = (f"read_csv('/data/{rel}', columns = {{'line': 'VARCHAR'}}, header = false, delim = E'\\x01', quote = '', "
            f"escape = '', auto_detect = false{encoding})")
    c.execute("DROP TABLE IF EXISTS ingest_sample")
    c.execute(f"CREATE TEMP TABLE ingest_sample AS SELECT line FROM {read} LIMIT {SAMPLE}")
    n = c.execute("SELECT count(*) FROM ingest_sample").fetchone()[0]

    # ---- score every lnav format on the sample, inside SereneDB
    results, skipped = [], []
    for f in sorted((ROOT / "formats/lnav").glob("*.json")):
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
    print(f"sample: {n} lines of {rel}; {sum(1 for _ in (ROOT / 'formats/lnav').glob('*.json'))} lnav formats, "
          f"{len(skipped)} regexes skipped (RE2 lacks the feature)")
    for r in results[:5]:
        print(f"  {r['format']:<22} {r['hits'] / n:6.1%}  ({r['fields']} fields)")
    if not results or results[0]["hits"] / n < a.min_coverage:
        print(f"NOT LOADED: best coverage {results[0]['hits'] / n if results else 0:.1%} < {a.min_coverage:.0%}; "
              "no known format fits (no guessed timestamps). Write a loader by hand (README: a new log source).")
        return 2
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
    for r, cands in ROLE_NAMES.items():
        own = {"component": fmt.get("module-field"), "request_id": fmt.get("opid-field")}.get(r)
        role[r] = next((x for x in ([own] if own else []) + cands if present(x)), None)

    def field(base: str | None) -> str:
        if not base or not present(base):
            return "NULL"
        return "nullif(coalesce(" + ", ".join(f"r{i}.{x}" for i, (_, _, ns) in enumerate(pats) for x in ns
                                               if x == base or x.startswith(base + "__")) + "), '')"  # unmatched group = 

    ts_expr = field(role["timestamp"])
    if ts_expr == "NULL":
        print("NOT LOADED: the format has no timestamp field."); return 2

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
        if needs_year and not a.year:
            yr = 2000
        else:
            yr = a.year
        expr = f"try_strptime({lit(str(yr) + ' ')} || t, {lit('%Y ' + tf)})" if needs_year else f"try_strptime(t, {lit(tf)})"
        try:
            ok = c.execute(f"SELECT count(*) FILTER (WHERE {expr} IS NOT NULL) FROM ingest_ts").fetchone()[0]
        except psycopg.Error:
            continue
        if ok > best_ok:
            best_ts, best_ok, year_used = tf, ok, (yr if needs_year else None)
    tsn = c.execute("SELECT count(*) FROM ingest_ts").fetchone()[0]
    if not best_ts or best_ok / max(tsn, 1) < a.min_coverage:
        print(f"NOT LOADED: no timestamp format parses >= {a.min_coverage:.0%} of the timestamps "
              f"(best {best_ts} {best_ok}/{tsn})."); return 2
    if year_used is not None and not a.year:
        print("NOTE: the format logs no year; assuming 2000. Pass --year to set it.")

    # ---- level: lnav level map (regexes RE2 accepts) on the level field, else the value itself
    lvl_src = field(role["level"]) if role["level"] != "body" else field(role["body"])
    lvl = "NULL"
    if lvl_src != "NULL":
        cases = []
        for k, rx in (fmt.get("level") or {}).items():
            if k in LEVELS:
                try:
                    c.execute(f"SELECT regexp_matches('', {lit(rx)})")
                    cases.append(f"WHEN regexp_matches({lvl_src}, {lit(rx)}) THEN '{LEVELS[k]}'")
                except psycopg.Error:
                    skipped.append(f"{best['format']}.level.{k}: not RE2")
        order = list(LEVELS.values())
        cases.sort(key=lambda s: order.index(s.split("THEN '")[1].rstrip("'")))
        if cases:
            lvl = "CASE " + " ".join(cases) + " END"
        elif role["level"] != "body":
            lvl = f"upper({lvl_src})"

    ts_sql = (f"try_strptime({lit(str(year_used) + ' ')} || regexp_replace(trim({ts_expr}), '\\s+', ' ', 'g'), "
              f"{lit('%Y ' + best_ts)})" if year_used is not None else
              f"try_strptime(regexp_replace(trim({ts_expr}), '\\s+', ' ', 'g'), {lit(best_ts)})")
    body = field(role["body"])
    # component: the format's field; when it is empty on a matched line (e.g. a logcat tag with '-' or '.'), the generic
    # "name: message" prefix of the body; never NULL on a matched line (NULL = continuation line in stage_to_logs.sql)
    comp = field(role["component"])
    prefix = f"nullif(regexp_extract(coalesce({body}, line), '^([A-Za-z][\\w.$-]*): ', 1), '')"
    comp_sql = f"CASE WHEN {{matched}} THEN coalesce({comp + ', ' if comp != 'NULL' else ''}{prefix}, '-') END"
    matched = " OR ".join(f"r{i} IS NOT NULL" for i in range(len(pats)))
    node = field(role["node"])
    status = field(role["status"])
    status_sql = f"TRY_CAST({status} AS INTEGER)" if status != "NULL" else "NULL::INTEGER"
    fieldmap = {k: v for k, v in role.items() if v and (k != "level" or lvl != "NULL")}
    coverage = best["hits"] / n

    # ---- pattern base: unique, after every existing loader's
    bases = [int(x) for f in list((ROOT / "load").glob("*.sql")) + list((ROOT / "load/gen").glob("*.sql"))
             if f.stem != a.name for x in re.findall(r"^\\set pbase (\d+)", f.read_text(), re.M)]
    pbase = max(bases + [800000]) + 100000
    title = a.title or f"{src.stem} ({best['title']}, auto-detected)"
    desc = (f"Loaded by scripts/ingest.py: format auto-detected as lnav {best['format']} ({best['title']}), "
            f"{coverage:.1%} of a {n}-line sample matched; timestamp format {best_ts}"
            + (f"; the log has no year, {year_used} assumed" if year_used is not None else "")
            + f"; fields: {', '.join(f'{k} = {v}' for k, v in fieldmap.items())}. Unmatched lines are kept as continuation "
              "lines (ingest_report lists them).")
    out = ROOT / "load/gen" / f"{a.name}.sql"
    out.parent.mkdir(exist_ok=True)
    meanings = {"node": f"{role['node']} field of the {best['format']} format" if node != "NULL" else "",
                "location": "same as node" if node != "NULL" else "",
                "request": f"{role['request_id']} field of the {best['format']} format" if role["request_id"] else "",
                "status": f"{role['status']} field" if status != "NULL" else ""}
    sql = f"""-- requires: data/{rel}
-- GENERATED by scripts/ingest.py on {datetime.now():%Y-%m-%d %H:%M} (plan 057 part 3); edit by re-running it, not by hand.
-- Format: lnav {best['format']} ({best['title']}), {best['hits']}/{n} sample lines matched ({coverage:.1%}).
-- Fields: {json.dumps(fieldmap)}; timestamp format {best_ts}{f'; year {year_used} assumed (not logged)' if year_used is not None else ''}.
-- Unmatched lines: body = whole line, time / component / level of the previous line (stage_to_logs.sql), listed in
-- ingest_unparsed. Patterns converted from PCRE to RE2 by scripts/ingest.py (formats/lnav/{best['format']}.json).
\\timing on
CREATE TEMP TABLE stage AS
WITH raw AS (
    SELECT row_number() OVER () AS line_id, line FROM {read}
), m AS (
    SELECT line_id, line, {m_cols}
    FROM raw
)
SELECT line_id,
       CASE WHEN {matched} THEN {ts_sql} END AS ts,
       {comp_sql.format(matched=matched)}::VARCHAR AS component,
       {lvl}::VARCHAR AS severity,
       {node}::VARCHAR AS node,
       {node}::VARCHAR AS location,
       {status_sql} AS status,
       NULL::DOUBLE AS duration_ms,
       CASE WHEN {matched} THEN coalesce({body}, line) ELSE line END AS body,
       NULL::VARCHAR AS label,
       NULL::VARCHAR AS object_id,
       {field(role['request_id'])}::VARCHAR AS request_id,
       ({matched}) AS parsed
FROM m;
INSERT INTO ingest_unparsed SELECT {lit(a.name)}, line_id FROM stage WHERE NOT parsed;
INSERT INTO ingest_runs VALUES ({lit(a.name)}, {lit('data/' + str(rel))}, {lit(best['format'])}, {lit(best['title'])},
    {n}, {best['hits']}, {lit(best_ts)}, {year_used if year_used is not None else 'NULL'}, {lit(json.dumps(fieldmap))},
    {lit(json.dumps([r['format'] + ' ' + format(r['hits'] / n, '.3f') for r in results[:5]]))}, {len(skipped)});
\\set ds {a.name}
\\set pbase {pbase}
\\set title {lit(title)}
\\set description {lit(desc)}
\\set node_meaning {lit(meanings['node'])}
\\set location_meaning {lit(meanings['location'])}
\\set request_meaning {lit(meanings['request'])}
\\set status_meaning {lit(meanings['status'])}
\\ir ../lib/stage_to_logs.sql
"""
    out.write_text(sql)
    print(f"format: {best['format']} ({coverage:.1%}), timestamp {best_ts}, fields {fieldmap}"
          + (f", year {year_used} assumed" if year_used is not None else ""))
    print(f"wrote {out.relative_to(ROOT)} (pattern base {pbase})")
    return 0


if __name__ == "__main__":
    sys.exit(main())
