"""Send parsed records to SereneDB over OTLP/HTTP JSON (the same path any OTel app would use).

One OTLP resource per container: service.name, application.id, container.id.
Per record: timestamp, severity, body (incl. stack trace), scope = Java logger, attributes thread + pattern_id.
"""
import base64
import json
import urllib.request
from collections import defaultdict
from datetime import timezone

from pipeline import config


def _attr(k, v):
    return {"key": k, "value": {"stringValue": str(v)}}


def _payload(records: list[dict]) -> dict:
    by_container = defaultdict(list)
    for r in records:
        by_container[(r["job"], r["container"])].append(r)
    resource_logs = []
    for (job, container), recs in by_container.items():
        resource_logs.append({
            "resource": {"attributes": [_attr("service.name", config.SERVICE_NAME),
                                        _attr("application.id", job), _attr("container.id", container)]},
            "scopeLogs": [{"scope": {"name": "hadoop"}, "logRecords": [{
                "timeUnixNano": str(int(r["ts"].replace(tzinfo=timezone.utc).timestamp()) * 10**9 + r["ts"].microsecond * 1000),
                "severityText": r["level"], "severityNumber": r["severity"],
                "body": {"stringValue": r["body"]},
                "attributes": [_attr("thread", r["thread"]), _attr("logger", r["logger"]),
                               _attr("pattern_id", r["pattern_id"])],
            } for r in recs]}],
        })
    return {"resourceLogs": resource_logs}


def send(records: list[dict], url: str, batch: int = 5000) -> None:
    auth = "Basic " + base64.b64encode(":".join(config.OTLP_AUTH).encode()).decode()
    for i in range(0, len(records), batch):
        body = json.dumps(_payload(records[i:i + batch])).encode()
        req = urllib.request.Request(url, data=body, method="POST",
                                     headers={"Content-Type": "application/json", "Authorization": auth})
        with urllib.request.urlopen(req) as resp:
            assert resp.status == 200, resp.status
