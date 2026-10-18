"""Replay a loaded dataset as OpenTelemetry logs into SereneDB's built-in OTLP/HTTP receiver (plan 011, idea J1):
any OTel SDK or collector can feed this system; the rows land in `otel_logs` (full-text indexed, BM25) without a
collector. Mapping: service.name = component, severity = severity, body = message, resource attributes = dataset /
node / location, log attributes = pattern_id / line_id, trace id = request_id when it is 32 hex chars.

  .venv/bin/python scripts/otlp_replay.py zookeeper 2000      # first 2000 lines of the dataset
Endpoint: OTLP_ENDPOINT (default http://localhost:4318/v1/logs), basic auth OTLP_USER/OTLP_PASSWORD (default otel:otel).
"""
import base64
import json
import os
import sys
import time
import urllib.request

import psycopg
from psycopg.rows import dict_row

SEV = {"TRACE": 1, "DEBUG": 5, "INFO": 9, "INFORMATION": 9, "NOTICE": 10, "WARN": 13, "WARNING": 13, "ERROR": 17,
       "SEVERE": 18, "CRITICAL": 21, "FAILURE": 21, "FATAL": 21}


def attr(k, v):
    return {"key": k, "value": {"stringValue": str(v)}}


def main(ds: str, n: int, batch: int = 500) -> None:
    env = os.environ.get
    url = env("OTLP_ENDPOINT", "http://localhost:4318/v1/logs")
    auth = base64.b64encode(f"{env('OTLP_USER', 'otel')}:{env('OTLP_PASSWORD', 'otel')}".encode()).decode()
    with psycopg.connect(host=env("PGHOST", "localhost"), port=env("PGPORT", "7890"), user=env("PGUSER", "postgres"),
                         dbname=env("PGDATABASE", "postgres"), autocommit=True, row_factory=dict_row) as c:
        rows = c.execute("SELECT line_id, ts, component, severity, node, location, request_id, pattern_id, body "
                         "FROM logs WHERE dataset = %(d)s ORDER BY ts, line_id LIMIT %(n)s", {"d": ds, "n": n}).fetchall()
    t0, sent = time.time(), 0
    for i in range(0, len(rows), batch):
        by_service = {}
        for r in rows[i:i + batch]:
            rec = {"timeUnixNano": str(int(r["ts"].timestamp() * 1e9)), "severityText": r["severity"] or "",
                   "severityNumber": SEV.get((r["severity"] or "").upper(), 0), "body": {"stringValue": r["body"] or ""},
                   "attributes": [attr("line_id", r["line_id"]), attr("pattern_id", r["pattern_id"])]}
            rid = (r["request_id"] or "").replace("-", "")
            if len(rid) == 32 and all(ch in "0123456789abcdef" for ch in rid.lower()):
                rec["traceId"] = rid.lower()
            by_service.setdefault((r["component"] or ds, r["node"], r["location"]), []).append(rec)
        payload = {"resourceLogs": [{"resource": {"attributes": [attr("service.name", svc), attr("dataset", ds)]
                                                  + ([attr("host.name", node)] if node else [])
                                                  + ([attr("location", loc)] if loc else [])},
                                     "scopeLogs": [{"scope": {"name": "otlp_replay"}, "logRecords": recs}]}
                                    for (svc, node, loc), recs in by_service.items()]}
        req = urllib.request.Request(url, data=json.dumps(payload).encode(), method="POST",
                                     headers={"Content-Type": "application/json", "Authorization": f"Basic {auth}"})
        with urllib.request.urlopen(req, timeout=60) as resp:
            assert resp.status == 200, resp.status
        sent += len(rows[i:i + batch])
    print(f"{sent} {ds} lines sent as OTLP to {url} in {time.time() - t0:.1f} s")


if __name__ == "__main__":
    main(sys.argv[1], int(sys.argv[2]) if len(sys.argv) > 2 else 2000)
