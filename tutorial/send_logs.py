"""Send a small, realistic mini-incident to SereneDB over OTLP/HTTP (JSON).

Story: a tiny shop with 3 services. At 14:00 everything is normal. At 14:05 the
payment provider starts timing out, so checkout fails and customers see errors.
At 14:12 it recovers.

Usage: python3 tutorial/send_logs.py   (SereneDB must be running: docker compose up -d)
"""
import base64
import json
import random
import urllib.request
from datetime import datetime, timedelta, timezone

ENDPOINT = "http://127.0.0.1:4318/v1/logs"
AUTH = "Basic " + base64.b64encode(b"otel:otel").decode()

# OTel severity numbers: INFO=9, WARN=13, ERROR=17
SEVERITY = {"INFO": 9, "WARN": 13, "ERROR": 17}

random.seed(7)
start = datetime(2026, 10, 9, 14, 0, tzinfo=timezone.utc)


def record(t, level, body, trace_id=None, **attrs):
    rec = {
        "timeUnixNano": str(int(t.timestamp()) * 10**9 + t.microsecond * 1000),
        "severityText": level,
        "severityNumber": SEVERITY[level],
        "body": {"stringValue": body},
        "attributes": [{"key": k, "value": {"stringValue": str(v)}} for k, v in attrs.items()],
    }
    if trace_id:
        rec["traceId"] = trace_id
    return rec


logs = {"frontend": [], "checkout": [], "payment": []}
for minute in range(15):
    for _ in range(4):  # 4 orders per minute
        t = start + timedelta(minutes=minute, seconds=random.randint(0, 59))
        trace = "%032x" % random.getrandbits(128)  # one trace id = one customer request across services
        order = f"A-{random.randint(1000, 9999)}"
        incident = 5 <= minute < 12
        logs["frontend"].append(record(t, "INFO", f"POST /checkout order={order}", trace, http_route="/checkout"))
        logs["checkout"].append(record(t, "INFO", f"creating payment for order {order}", trace, order_id=order))
        if incident:
            # the timeout happens first (deep in payment), then bubbles up: checkout, then frontend
            ms = timedelta(milliseconds=1)
            logs["payment"].append(record(t + 15_000 * ms, "WARN", "stripe /v1/charges slow response, retrying (attempt 2/3)", trace))
            logs["payment"].append(record(t + 30_000 * ms, "ERROR", "Timeout after 30000ms calling stripe /v1/charges (attempt 3/3)", trace, provider="stripe"))
            logs["checkout"].append(record(t + 30_005 * ms, "ERROR", f"payment failed for order {order}: upstream timeout", trace, order_id=order))
            logs["frontend"].append(record(t + 30_010 * ms, "ERROR", f"POST /checkout 502 Bad Gateway order={order}", trace, http_status_code=502))
        else:
            logs["payment"].append(record(t, "INFO", f"charge succeeded for order {order}", trace, provider="stripe"))
            logs["frontend"].append(record(t, "INFO", f"POST /checkout 200 OK order={order}", trace, http_status_code=200))
    # background noise
    logs["frontend"].append(record(start + timedelta(minutes=minute), "INFO", "GET /healthcheck 200 OK"))

payload = {
    "resourceLogs": [
        {
            "resource": {"attributes": [
                {"key": "service.name", "value": {"stringValue": svc}},
                {"key": "deployment.environment", "value": {"stringValue": "prod"}},
            ]},
            "scopeLogs": [{"scope": {"name": "tutorial"}, "logRecords": recs}],
        }
        for svc, recs in logs.items()
    ]
}

req = urllib.request.Request(
    ENDPOINT, data=json.dumps(payload).encode(), method="POST",
    headers={"Content-Type": "application/json", "Authorization": AUTH},
)
with urllib.request.urlopen(req) as resp:
    n = sum(len(v) for v in logs.values())
    print(f"sent {n} log records -> HTTP {resp.status}")
