"""Load logs into SereneDB with no psql and no reload script (plan 016). Used by the MCP server (load_logs tool, in a
background thread) and by the CLI (`uv run python -m loader …`); one code path for both.

  ensure_schema()            first use of an empty database: load/00_schema.sql + load/01_derived.sql + macros + roles
  register_secrets()         AI keys from .env into SereneDB (secrets are not persisted across container restarts)
  load(source, name)         source = a catalog name (data/catalog.csv: the brief's Loghub table) → download per the
                             brief + our loader; or a path to any log file → streamed in, format auto-detected (lnav)
                             → per-dataset build (patterns, bursts, ownership, Jev, pattern index) → roles
  remove(name)               delete one dataset everywhere
  reload(names)              drop and rebuild everything (what load/reload.sh does)
SQL lives in load/*.sql (the readable "supplied loader"); loader/sqlrun.py runs it like psql would.
"""
import csv
import os
import re
import shutil
import subprocess
import tarfile
import time
import urllib.request
import zipfile
from pathlib import Path
from typing import Callable, Optional

import psycopg

from loader import detect as det_mod
from loader import jev
from loader.sqlrun import run_file

ROOT = Path(__file__).resolve().parent.parent
LOAD = ROOT / "load"
RAW = ROOT / "data/raw"
ZENODO = "https://zenodo.org/records/8196385/files/{}?download=1"  # the brief's links (Loghub, Zenodo record 8196385)
LARGE_LINES = 20_000_000  # catalog entries above this need confirm_large (download size, load time on emulated amd64)

Log = Callable[[str], None]


def _env(name: str, default: str) -> str:
    return os.environ.get(name) or default


def connect() -> psycopg.Connection:
    c = psycopg.connect(host=_env("PGHOST", "localhost"), port=_env("PGPORT", "7890"), user=_env("PGUSER", "postgres"),
                        dbname=_env("PGDATABASE", "postgres"), autocommit=True)
    c.execute("SET sdb_scan_split = 'never'")  # TsDict facet counts off by one with split segments (plan 011)
    return c


def load_dotenv() -> None:
    """Keys from the repo's .env (optional; never printed). Existing environment variables win."""
    f = ROOT / ".env"
    if not f.exists():
        return
    for line in f.read_text().splitlines():
        m = re.match(r"\s*([A-Z_][A-Z0-9_]*)\s*=\s*(.*)$", line)
        if m and m.group(2).strip() and m.group(1) not in os.environ:
            os.environ[m.group(1)] = m.group(2).strip().strip('"').strip("'")


def register_secrets(c: psycopg.Connection) -> list[str]:
    """docker/secrets.sh in Python: typesafe (Jev, ai_system_one) and gemini (ai_embed / ai_generate) when their keys
    are set. Idempotent; returns the names registered."""
    load_dotenv()
    done = []
    key = os.environ.get("TYPESAFE_API_KEY")
    if key:
        c.execute("DROP SECRET IF EXISTS typesafe")
        c.execute(f"CREATE SECRET typesafe (TYPE typesafe, api_key {_q(key)})")
        c.execute("SET GLOBAL sdb_ai_system_one_default_secret = 'typesafe'")
        done.append("typesafe")
    key = os.environ.get("GOOGLE_API_KEY")
    if key:
        model = os.environ.get("GEMINI_SQL_MODEL", "gemini-2.5-flash")
        c.execute("DROP SECRET IF EXISTS gemini")
        c.execute("CREATE SECRET gemini (TYPE openai, base_url 'https://generativelanguage.googleapis.com/v1beta/openai', "
                  f"chat_path '/chat/completions', embeddings_path '/embeddings', api_key {_q(key)}, model {_q(model)})")
        c.execute("SET GLOBAL sdb_ai_text_default_secret = 'gemini'")
        c.execute("SET GLOBAL sdb_ai_embedding_default_secret = 'gemini'")
        done.append("gemini")
    return done


def _q(v: str) -> str:
    return "'" + v.replace("'", "''") + "'"


def tables(c: psycopg.Connection) -> set[str]:
    return {r[0] for r in c.execute("SELECT table_name FROM information_schema.tables WHERE table_schema = 'public'")}


SCHEMA_VERSION = 16  # bump when load/00_schema.sql or load/01_derived.sql change shape (plan number)


def schema_version(c: psycopg.Connection) -> int:
    try:
        return c.execute("SELECT max(version) FROM schema_version").fetchone()[0] or 0
    except psycopg.Error:
        return 0


def ensure_schema(c: psycopg.Connection, log: Log = print) -> bool:
    """Create the schema on an empty database, or rebuild it when it is older than SCHEMA_VERSION (the old rows cannot
    be kept: search tables cannot be ALTERed); True when it was (re)created. An up-to-date database is never touched."""
    v = schema_version(c)
    if v == SCHEMA_VERSION:
        return False
    if v or "logs" in tables(c):
        log(f"database schema is older than this code (version {v} < {SCHEMA_VERSION}): recreating it; loaded "
            "datasets must be loaded again")
    else:
        log("creating the schema (first use of this database)")
    _cleanup(c)
    run_file(c, LOAD / "00_schema.sql")
    run_file(c, LOAD / "01_derived.sql")
    _otel_role(c)
    run_file(c, LOAD / "98_macros.sql")
    c.execute("DROP TABLE IF EXISTS schema_version")
    c.execute(f"CREATE TABLE schema_version AS SELECT {SCHEMA_VERSION} AS version")
    roles(c)
    return True


def _otel_role(c: psycopg.Connection) -> None:
    """docker/init.sql, idempotent: a login role for SereneDB's built-in OTLP/HTTP receiver (scripts/otlp_replay.py)."""
    if not c.execute("SELECT 1 FROM pg_roles WHERE rolname = 'otel'").fetchone():
        c.execute("CREATE ROLE otel LOGIN PASSWORD 'otel'")
    for t in ("otel_logs", "otel_traces", "otel_metrics_gauge", "otel_metrics_sum", "otel_metrics_histogram",
              "otel_metrics_exponential_histogram", "otel_metrics_summary"):
        try:
            c.execute(f"GRANT INSERT, SELECT ON {t} TO otel")
        except psycopg.Error:
            pass


def _cleanup(c: psycopg.Connection) -> None:
    """Was load/00_cleanup.py: workspaces and team schemas depend on the tables a schema rebuild drops."""
    names = tables(c)
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


def roles(c: psycopg.Connection) -> None:
    """load/99_roles.py (idempotent): role grants + one view schema per team; re-run after every dataset change."""
    import importlib.util
    spec = importlib.util.spec_from_file_location("roles99", LOAD / "99_roles.py")
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    m.main()


# ---------------------------------------------------------------- catalog + download (the brief's steps)

def catalog() -> dict[str, dict]:
    """data/catalog.csv: the brief's Loghub table (name, Zenodo archive, lines, size), our loader if we wrote one, and
    base = 1 for the base corpus the brief supplies (BGL + OpenStack)."""
    with (ROOT / "data/catalog.csv").open() as fh:
        return {r["name"]: r for r in csv.DictReader(fh)}


def base_corpus() -> list[str]:
    return [n for n, e in catalog().items() if e["base"]]


def download(name: str, log: Log = print) -> Path:
    """Download one Loghub archive exactly as the brief says (curl -L "…?download=1": follows Zenodo's redirect) into
    data/raw/ and unpack it; idempotent. Returns the main log file."""
    e = catalog()[name]
    target = ROOT / e["log_file"] if e["log_file"] else RAW / name
    if e["log_file"] and target.exists():
        return target
    dest = RAW if name == "bgl" else RAW / name
    dest.mkdir(parents=True, exist_ok=True)
    arc = dest / e["archive"]
    url = ZENODO.format(e["archive"])
    log(f"downloading {e['archive']} ({e['size']}) from {url}")
    t0 = time.time()
    if shutil.which("curl"):  # the brief's own command: curl -L -o <file> "<url>?download=1"
        subprocess.run(["curl", "-L", "--fail", "-sS", "-o", str(arc), url], check=True)
    else:
        with urllib.request.urlopen(url) as r, arc.open("wb") as fh:
            shutil.copyfileobj(r, fh, 1 << 20)
    log(f"downloaded {arc.stat().st_size / 1e6:.0f} MB in {time.time() - t0:.0f} s; unpacking")
    if arc.suffix == ".zip":
        with zipfile.ZipFile(arc) as z:
            z.extractall(dest)
    else:
        with tarfile.open(arc) as t:
            t.extractall(dest, filter="data")
    arc.unlink()
    if e["log_file"]:
        if not target.exists():
            raise FileNotFoundError(f"{e['archive']} unpacked, but {e['log_file']} is not in it")
        return target
    logs = sorted(dest.rglob("*.log"), key=lambda p: -p.stat().st_size)
    if not logs:
        raise FileNotFoundError(f"no *.log file in {e['archive']}")
    return logs[0]


# ---------------------------------------------------------------- one dataset

def loaded(c: psycopg.Connection) -> list[str]:
    return [r[0] for r in c.execute("SELECT dataset FROM datasets ORDER BY pattern_base")]


def remove(c: psycopg.Connection, name: str, log: Log = print, refresh_roles: bool = True) -> int:
    """Delete every row of one dataset (base and derived tables); returns the log lines removed."""
    n = c.execute("SELECT count(*) FROM logs WHERE dataset = %s", (name,)).fetchone()[0]
    for t in ("logs", "labels", "pattern_templates", "datasets", "ingest_runs", "ingest_unparsed", "dataset_examples",
              "ownership", "episodes", "bursts", "patterns", "pattern_traits", "pattern_judgments", "component_areas",
              "pattern_index", "burst_summaries"):
        c.execute(f"DELETE FROM {t} WHERE dataset = %s", (name,))
    for t in ("logs", "labels", "pattern_index"):
        c.execute(f"VACUUM (REFRESH_TABLE) {t}")
    if refresh_roles:
        roles(c)
    log(f"removed {name}: {n:,} log lines")
    return n


def _publish(c: psycopg.Connection, compact: bool = False) -> None:
    """Make new rows visible to the inverted index before the derived steps read them. compact=True (full reload) also
    runs load/90_publish.sql's COMPACT_TABLE, which rewrites the whole table (~40 s at 17M rows, even for a small
    insert); one added dataset skips it: SereneDB's background compaction merges the new segments (plan 016)."""
    if compact:
        run_file(c, LOAD / "90_publish.sql")
    else:
        c.execute("VACUUM (REFRESH_TABLE) logs")
        c.execute("VACUUM (REFRESH_TABLE) labels")


def _next_pbase(c: psycopg.Connection, name: str) -> int:
    """pattern_id base for a new dataset: above every loaded dataset and every loader file's (ids never collide)."""
    bases = [r[0] for r in c.execute("SELECT pattern_base FROM datasets WHERE dataset <> %s", (name,))]
    for f in list(LOAD.glob("*.sql")) + list((LOAD / "gen").glob("*.sql")):
        if f.stem != name:
            bases += [int(x) for x in re.findall(r"^\\set pbase (\d+)", f.read_text(), re.M)]
    return max(bases + [800000]) + 100000


def stream_file(c: psycopg.Connection, path: Path, table: str = "ingest_lines", log: Log = print) -> int:
    """COPY a local file into a fresh table (line_id, line), line by line as read_csv would: no /data mount needed, so
    a file anywhere on the user's disk works (and so does a remote SereneDB). Bytes that are not UTF-8 are read as
    latin-1 (raw attack bytes in auth logs etc.); NUL bytes are dropped (Postgres text cannot hold them)."""
    c.execute(f"DROP TABLE IF EXISTS {table}")
    c.execute(f"CREATE TABLE {table} (line_id BIGINT, line VARCHAR)")
    n, t0, buf = 0, time.time(), []
    with c.cursor().copy(f"COPY {table} (line_id, line) FROM STDIN") as cp, path.open("rb") as fh:
        for raw in fh:
            n += 1
            raw = raw.rstrip(b"\r\n").replace(b"\x00", b"")
            try:
                s = raw.decode("utf-8")
            except UnicodeDecodeError:
                s = raw.decode("latin-1")
            buf.append(f"{n}\t" + s.replace("\\", "\\\\").replace("\t", "\\t").replace("\r", "\\r") + "\n")
            if len(buf) >= 20000:
                cp.write("".join(buf)); buf = []
                if n % 1_000_000 == 0:
                    log(f"streamed {n:,} lines")
        cp.write("".join(buf))
    log(f"streamed {n:,} lines in {time.time() - t0:.1f} s")
    return n


def load_file(c: psycopg.Connection, path: Path, name: str, year: Optional[int] = None, title: Optional[str] = None,
              log: Log = print) -> dict:
    """Any log file → detected format → dataset `name`. Returns the detection report (ok False = nothing loaded)."""
    in_repo_data = (ROOT / "data") in path.resolve().parents
    if in_repo_data:  # read by SereneDB itself from the /data mount (fastest; same SQL as a committed loader)
        rel = path.resolve().relative_to(ROOT / "data")
        relation = (f"(SELECT row_number() OVER () AS line_id, line FROM read_csv('/data/{rel}', columns = "
                    f"{{'line': 'VARCHAR'}}, header = false, delim = E'\\x01', quote = '', escape = '', "
                    f"auto_detect = false{_encoding(c, rel)}))")
    else:
        stream_file(c, path, log=log)
        relation = "ingest_lines"
    d = det_mod.detect(c, relation, year=year)
    report = {"ok": d.ok, "format": d.format, "coverage": round(d.coverage, 4), "candidates": d.candidates,
              "sample_lines": d.sample_lines, "year_assumed": d.year_assumed, "fields": d.field_map}
    if not d.ok:
        report["reason"] = d.reason
        c.execute("DROP TABLE IF EXISTS ingest_lines")
        return report
    log(f"format: lnav {d.format} ({d.coverage:.1%} of the sample), timestamp {d.ts_format}"
        + (f", year {d.year_assumed} assumed" if d.year_assumed else ""))
    pbase = _next_pbase(c, name)
    label = f"data/{path.resolve().relative_to(ROOT / 'data')}" if in_repo_data else str(path)
    sql = det_mod.loader_sql(d, name, label, pbase, title)
    gen = LOAD / "gen"
    gen.mkdir(exist_ok=True)
    if in_repo_data:  # reproducible: committed next to the hand-written loaders, run by every full reload
        out = gen / f"{name}.sql"
        out.write_text(f"-- requires: {label}\n-- GENERATED by loader/detect.py on {time.strftime('%Y-%m-%d %H:%M')} "
                       f"(plan 057 / 016); edit by re-running `python -m loader load {label} --name {name}`.\n" + sql)
        f = out
    else:  # a user's file outside the repo: run once from a temporary file (the lines are already in ingest_lines)
        f = gen / f".{name}.tmp.sql"
        f.write_text(sql)
    remove(c, name, log=lambda _: None, refresh_roles=False)
    try:
        run_file(c, f)
    finally:
        if f.name.startswith("."):
            f.unlink(missing_ok=True)
        c.execute("DROP TABLE IF EXISTS ingest_lines")
    return report


def _encoding(c: psycopg.Connection, rel: Path) -> str:
    try:  # the whole file must decode as UTF-8, else latin-1 (stated in the description by the caller)
        c.execute(f"SELECT count(*) FROM read_csv('/data/{rel}', columns = {{'line': 'VARCHAR'}}, header = false, "
                  f"delim = E'\\x01', quote = '', escape = '', auto_detect = false)")
        return ""
    except psycopg.Error:
        return ", encoding = 'latin-1'"


def build(c: psycopg.Connection, name: str, log: Log = print) -> None:
    """Everything derived from one dataset's lines (load/lib/build_dataset.sql), after publishing the new rows."""
    _publish(c)
    run_file(c, LOAD / "lib/build_dataset.sql", {"ds": name}, log=lambda m: log(f"built {name}: {m}"))


def load(source: str, name: Optional[str] = None, year: Optional[int] = None, judge: str = "auto",
         confirm_large: bool = False, log: Log = print, title: Optional[str] = None) -> dict:
    """Load one dataset end to end. source = catalog name or file path. judge: 'auto' (live Jev for datasets without
    committed judgments when a key works), 'never'. Returns a report dict."""
    t0 = time.time()
    c = connect()
    ensure_schema(c, log)
    have_secrets = register_secrets(c)
    cat = catalog()
    report: dict = {"source": source}
    if source in cat:
        name = name or source
        e = cat[source]
        if int(e["lines"]) > LARGE_LINES and not confirm_large:
            return {"ok": False, "reason": f"{source} is large ({int(e['lines']):,} lines, {e['size']} download); "
                                           "pass confirm_large=true to load it"}
        if e["loader"] and (ROOT / e["loader"]).exists():
            download(source, log)
            log(f"loading {name} with {e['loader']}")
            remove(c, name, log=lambda _: None, refresh_roles=False)
            run_file(c, ROOT / e["loader"], log=log)
            report.update(ok=True, loader=e["loader"])
        else:
            f = download(source, log)
            r = load_file(c, f, name, year=year, title=e["title"], log=log)
            report.update(r, loader="format auto-detection")
            if not r["ok"]:
                return report
    else:
        path = Path(os.path.expanduser(source))
        if not path.is_file():
            return {"ok": False, "reason": f"{source!r} is neither a file nor a dataset name ({', '.join(cat)})"}
        name = name or re.sub(r"[^a-z0-9_]+", "_", path.stem.lower()).strip("_") or "logs"
        if not re.fullmatch(r"[a-z][a-z0-9_]*", name):
            return {"ok": False, "reason": "name: lower case letters, digits and _ (start with a letter)"}
        r = load_file(c, path, name, year=year, title=title, log=log)
        report.update(r, loader="format auto-detection")
        if not r["ok"]:
            return report
    build(c, name, log)
    judged = c.execute("SELECT count(*) FROM pattern_judgments WHERE dataset = %s", (name,)).fetchone()[0]
    if not judged and judge == "auto":
        log("no committed Jev judgments for this dataset: judging it now inside SereneDB")
        report["jev"] = jev.judge(c, name, log)
    elif judged:
        report["jev"] = {"judgments": f"committed: {judged} patterns (data/pattern_judgments_{name}.csv)"}
    roles(c)
    s = c.execute("SELECT count(*), min(ts), max(ts) FROM logs WHERE dataset = %s", (name,)).fetchone()
    p = c.execute("SELECT count(*), count(*) FILTER (WHERE j.p_problem >= 0.5) FROM patterns pt LEFT JOIN "
                  "pattern_judgments j USING (dataset, pattern_id) WHERE pt.dataset = %s", (name,)).fetchone()
    report.update(ok=True, dataset=name, lines=s[0], first_ts=str(s[1]), last_ts=str(s[2]), patterns=p[0],
                  judged=bool(c.execute("SELECT 1 FROM pattern_judgments WHERE dataset = %s LIMIT 1", (name,)).fetchone()),
                  problem_patterns_jev=p[1], seconds=round(time.time() - t0, 1), ai_secrets=have_secrets)
    log(f"{name}: {s[0]:,} lines, {p[0]:,} patterns, {time.time() - t0:.0f} s")
    return report


def reload(names: Optional[list[str]] = None, log: Log = print) -> dict:
    """Drop everything and load `names` (default: every catalog dataset whose raw file is present, plus OTel with
    LOAD_OTEL=1), the way load/reload.sh did; Jev only from committed CSVs (no live calls)."""
    c = connect()
    t0 = time.time()
    _cleanup(c)
    run_file(c, LOAD / "00_schema.sql")
    run_file(c, LOAD / "01_derived.sql")
    _otel_role(c)
    c.execute("DROP TABLE IF EXISTS schema_version")
    c.execute(f"CREATE TABLE schema_version AS SELECT {SCHEMA_VERSION} AS version")
    # catalog datasets whose raw file is present (in catalog order: base corpus first), then the optional OTel slice
    files = [(n, ROOT / e["loader"]) for n, e in catalog().items()
             if e["loader"] and (ROOT / e["loader"]).exists() and (ROOT / e["log_file"]).exists()]
    if os.environ.get("LOAD_OTEL") == "1":
        files.append(("otel", LOAD / "40_otel_demo.sql"))
    files = [(n, f) for n, f in files if not names or n in names]
    for ds, f in files:
        run_file(c, f, log=log)
    _publish(c, compact=True)
    for ds, _ in files:
        run_file(c, LOAD / "lib/build_dataset.sql", {"ds": ds}, log=lambda m, ds=ds: log(f"built {ds}: {m}"))
    run_file(c, LOAD / "98_macros.sql")
    roles(c)
    log(f"reload: {len(files)} datasets in {time.time() - t0:.0f} s")
    return {"datasets": [d for d, _ in files], "seconds": round(time.time() - t0, 1)}
