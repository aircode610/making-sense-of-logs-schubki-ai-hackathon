"""Tracing: every named step (bricks + baselines) -> one row in <schema>.traces. Viewer: apps/trace_viewer.py."""
import json
import time
from datetime import datetime, timezone

from langchain_core.callbacks import BaseCallbackHandler

TRACED_STEPS = {"Pattern", "Evidence", "Verdict", "Finding",
                "B1_llm_same_evidence", "B2_llm_raw_logs", "B3_classifier", "B4_rules"}

DDL = """
CREATE TABLE IF NOT EXISTS {s}.traces (
    run_id VARCHAR, qid VARCHAR, step VARCHAR, started_at TIMESTAMP, latency_ms DOUBLE,
    input_json VARCHAR, output_json VARCHAR, error VARCHAR
)"""


def ensure_table(conn, schema: str) -> None:
    conn.execute(DDL.format(s=schema))


class TraceHandler(BaseCallbackHandler):
    """LangChain callback: records start/end of each traced step for one example."""

    def __init__(self, conn, schema: str, run_id: str, qid: str):
        self.conn, self.schema, self.run_id, self.qid = conn, schema, run_id, qid
        self.open = {}

    def on_chain_start(self, serialized, inputs, *, run_id, name=None, **kw):
        name = name or (serialized or {}).get("name")
        if name in TRACED_STEPS:
            self.open[run_id] = (name, time.perf_counter(), datetime.now(timezone.utc), inputs)

    def _write(self, run_id, output=None, error=None):
        if run_id not in self.open:
            return
        name, t0, started, inputs = self.open.pop(run_id)
        self.conn.execute(
            f"INSERT INTO {self.schema}.traces VALUES (%s, %s, %s, %s, %s, %s, %s, %s)",
            (self.run_id, self.qid, name, started.replace(tzinfo=None), (time.perf_counter() - t0) * 1000,
             json.dumps(inputs, default=str), json.dumps(output, default=str), error))

    def on_chain_end(self, outputs, *, run_id, **kw):
        self._write(run_id, output=outputs)

    def on_chain_error(self, error, *, run_id, **kw):
        self._write(run_id, error=repr(error))
