"""Parse Loghub Hadoop container logs into plain records (no labels, nothing that leaks the answer).

Line format: `2015-10-17 15:37:56,547 INFO [main] org.apache...MRAppMaster: message`
Lines without that prefix are continuations (stack traces) and are appended to the previous record's body.
"""
import re
from datetime import datetime
from pathlib import Path

LINE = re.compile(r"^(\d{4}-\d{2}-\d{2} \d{2}:\d{2}:\d{2},\d{3}) (TRACE|DEBUG|INFO|WARN|ERROR|FATAL) \[([^\]]*)\] ([^:]+): ?(.*)$")
SEVERITY = {"TRACE": 1, "DEBUG": 5, "INFO": 9, "WARN": 13, "ERROR": 17, "FATAL": 21}  # OTel severity numbers


def parse_job(job_dir: Path) -> list[dict]:
    """All records of one job (= one application_* directory), across its container logs."""
    records = []
    for log_file in sorted(job_dir.glob("*.log")):
        container = log_file.stem
        current = None
        for raw in log_file.read_text(errors="ignore").splitlines():
            m = LINE.match(raw)
            if m:
                ts, level, thread, logger, msg = m.groups()
                current = {
                    "ts": datetime.strptime(ts, "%Y-%m-%d %H:%M:%S,%f"),
                    "level": level, "severity": SEVERITY[level],
                    "thread": thread, "logger": logger.strip(),
                    "message": msg, "body": msg,
                    "job": job_dir.name, "container": container,
                }
                records.append(current)
            elif current is not None and raw.strip():
                current["body"] += "\n" + raw          # stack-trace continuation
    return records
