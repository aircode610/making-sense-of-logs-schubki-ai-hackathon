"""GAIA MicroSS: parse injection records (ground truth) and business-log rows. Generic parsing only, no labels in logs.

Business log message: "<ts> | <LEVEL> | <ip> | [<ip> |] <service> | [<file -> func -> line> |] [<trace id> |] <body>"
Injection record (run/ table): same prefix, body = what was injected, e.g. "[memory_anomalies] trigger ... start at <ts> ...".
"""
import csv
import re
import subprocess
import sys
from datetime import datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
STREAM = ROOT / "scripts" / "gaia_stream.sh"
RUN_TABLES = [ROOT / "dataset" / "gaia" / "run" / "run" / f"run_table_2021-0{m}.csv" for m in (7, 8)]
SEVERITY = {"DEBUG": 5, "INFO": 9, "WARNING": 13, "WARN": 13, "ERROR": 17, "CRITICAL": 21, "FATAL": 21}
TRACE_RE = re.compile(r"^[0-9a-f]{12,16}$")
TS_FMT = "%Y-%m-%d %H:%M:%S"

csv.field_size_limit(10**8)


def _ts(s: str) -> datetime:
    return datetime.strptime(s.strip()[:19], TS_FMT)


def parse_record(service: str, message: str) -> dict | None:
    """One business-log CSV row -> record, or None if malformed."""
    p = message.split("|")
    if len(p) < 4 or len(p[0].strip()) < 19:
        return None
    try:
        ts = datetime.strptime(p[0].strip()[:23].replace(",", "."), TS_FMT + ".%f")
    except ValueError:
        return None
    level = p[1].strip().upper()
    fields = [x.strip() for x in p[2:]]
    try:
        i = fields.index(service) + 1
    except ValueError:
        return None
    if i < len(fields) and "->" in fields[i]:
        i += 1                                   # code location (dbservice/logservice style)
    trace_id = ""
    if i < len(fields) - 1 and TRACE_RE.match(fields[i]):
        trace_id, i = fields[i], i + 1
    body = "|".join(p[2 + i:]).strip() if i < len(fields) else ""
    return {"ts": ts, "service": service, "severity_text": level, "severity_number": SEVERITY.get(level, 9),
            "trace_id": trace_id, "body": body}


def stream_rows(name: str):
    """Yields csv dict rows of business_table_<name>.csv, streamed (never extracted)."""
    proc = subprocess.Popen([str(STREAM), name], stdout=subprocess.PIPE, stderr=subprocess.DEVNULL, text=True,
                            encoding="utf-8", errors="replace")
    try:
        yield from csv.DictReader(proc.stdout)
    finally:
        proc.kill()


# ---------- injection records (ground truth) ----------
_SVC = r"\| (\w+) \| "
KINDS = [  # (kind, regex on message, start-time group regex, duration)
    ("file_missing", re.compile(_SVC + r"trigger the file moving program, start with (\S+ \S+), last for (\d+) seconds")),
    ("permission_denied", re.compile(_SVC + r"trigger an access permission denied exception, will lasts an hour")),
    ("memory", re.compile(_SVC + r"\[memory_anomalies\] trigger a high memory program, start at (\S+ \S+) and lasts (\d+) seconds")),
    ("cpu", re.compile(_SVC + r"\[cpu_anomalies\] trigger a parallel fast sorting program , start at (\S+ \S+) and lasts ([\d.]+) seconds")),
]


def load_injections(paths=RUN_TABLES) -> list[dict]:
    """All injections: {service, kind, start, end}. CPU is kept with its kind (callers decide); per-request login waits
    are not incidents and are skipped. Failed attempts ('exception injection failed', 10 in July) have no trigger
    record, so they never appear here."""
    out = []
    for path in paths:
        for row in csv.DictReader(open(path, encoding="utf-8")):
            msg = row["message"].strip()
            head = msg.split("|", 1)[0]
            for kind, rx in KINDS:
                m = rx.search(msg)
                if not m:
                    continue
                svc = m.group(1)
                if kind == "permission_denied":
                    start, dur = _ts(head), 3600.0
                else:
                    start, dur = datetime.strptime(m.group(2)[:19], TS_FMT), float(m.group(3))
                out.append({"service": svc, "kind": kind, "start": start, "end": start + timedelta(seconds=dur)})
                break
    out.sort(key=lambda d: d["start"])
    return out


if __name__ == "__main__":  # quick self-check on the run tables (no business logs)
    from collections import Counter
    inj = load_injections()
    print(Counter((i["start"].strftime("%Y-%m"), i["kind"]) for i in inj), file=sys.stderr)


# ---------- OTLP ingest (the generic input contract: service.name + severity + body + trace id) ----------
def otlp_payload(rows: list[dict], service_override: str | None = None) -> dict:
    """rows from make_split's rows.jsonl.gz -> OTLP/JSON. One resource per service; request id -> OTel traceId
    (GAIA ids are 12-16 hex chars; left-padded to the 32 hex chars OTLP expects)."""
    from collections import defaultdict
    from datetime import timezone
    by_svc = defaultdict(list)
    for r in rows:
        by_svc[service_override or r["service"]].append(r)
    attr = lambda k, v: {"key": k, "value": {"stringValue": str(v)}}  # noqa: E731
    out = []
    for svc, recs in by_svc.items():
        logs = []
        for r in recs:
            ts = datetime.fromisoformat(r["ts"]).replace(tzinfo=timezone.utc)
            rec = {"timeUnixNano": str(int(ts.timestamp() * 1000) * 10**6), "severityText": r["severity_text"],
                   "severityNumber": r["severity_number"], "body": {"stringValue": r["body"]},
                   "attributes": [attr("pattern_id", r["pattern_id"])]}
            if r["trace_id"]:
                rec["traceId"] = r["trace_id"].rjust(32, "0")
            logs.append(rec)
        out.append({"resource": {"attributes": [attr("service.name", svc)]},
                    "scopeLogs": [{"scope": {"name": "gaia"}, "logRecords": logs}]})
    return {"resourceLogs": out}
