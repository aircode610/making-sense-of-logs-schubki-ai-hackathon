"""Session report (plan 015): what happened inside the client's session, end to end, on one local page.

One MCP server process = one client session (Claude Code starts one per conversation). Every tool call is recorded to
runs/sessions/<session>.jsonl (local, gitignored): tool, args, SQL, totals, truncation, a few rows, server ms. The
`session_report` tool returns a link to a page served by a stdlib HTTP server on 127.0.0.1 (daemon thread). The page
can re-run a recorded step's SQL to verify it (/verify): only that stored SQL, through a read-only database role.
"""
import functools
import json
import os
import re
import threading
import time
import uuid
from datetime import datetime
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from pathlib import Path
from typing import Annotated, Optional

from pydantic import Field

ROOT = Path(__file__).resolve().parent.parent
DIR = ROOT / "runs" / "sessions"
SESSION = datetime.now().strftime("%Y%m%d-%H%M%S-") + uuid.uuid4().hex[:4]
_lock = threading.Lock()
_verify_lock = threading.Lock()  # verify swaps core's connection: one at a time
_server: Optional[ThreadingHTTPServer] = None
ROWS_KEPT = 50   # = the tools' own row cap: the session file holds what the client saw


def _path(session: str) -> Path:
    if not re.fullmatch(r"[\w-]{6,40}", session):
        raise ValueError("bad session id")
    return DIR / f"{session}.jsonl"


def _write(rec: dict) -> None:
    DIR.mkdir(parents=True, exist_ok=True)
    with _lock, _path(SESSION).open("a") as f:
        f.write(json.dumps(rec, default=str) + "\n")


def _short(env: dict) -> dict:
    """What the client saw, capped: every field of the result (nested objects such as pattern_history's `pattern`
    included), lists cut to ROWS_KEPT items, long strings cut. The page shows a few rows; Jev support and the number
    check read all of it."""
    def cap(v, depth=0):
        if isinstance(v, list):
            return [cap(x, depth + 1) for x in v[:ROWS_KEPT]]
        if isinstance(v, dict):
            return {k: cap(x, depth + 1) for k, x in v.items()} if depth < 4 else str(v)[:300]
        if isinstance(v, str) and len(v) > 2000:
            return v[:2000] + "…"
        return v
    keep = {k: cap(v) for k, v in env.items() if k != "session_report"}
    rows = env.get("rows") if isinstance(env.get("rows"), list) else env.get("items") or []
    keep["rows"] = cap(rows)
    keep["rows_returned"] = len(rows)
    keep["sql"] = env.get("sql") or []
    return keep


def record(fn):
    """Wrap a tool so every call lands in the session file (the result is returned unchanged)."""
    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        t0, err, out = time.perf_counter(), None, None
        try:
            out = fn(*args, **kwargs)
            if isinstance(out, dict):  # the live page is up from the first call; remind the client how to finish
                out = {**out, "session_report": f"when you have answered, call session_report(question, answer) and "
                                                f"give the user the link (live now: http://127.0.0.1:{serve()}/latest)"}
            return out
        except Exception as e:  # noqa: BLE001  (recorded, then re-raised to the client)
            err = f"{type(e).__name__}: {e}"[:400]
            raise
        finally:
            try:
                _write({"kind": "call", "ts": datetime.now().isoformat(timespec="milliseconds"), "tool": fn.__name__,
                        "args": {k: v for k, v in kwargs.items() if v is not None}, "dataset": _active(),
                        "wall_ms": round((time.perf_counter() - t0) * 1000, 1), "error": err,
                        "result": _short(out) if isinstance(out, dict) else None})
            except Exception:  # noqa: BLE001  (recording must never break a tool)
                pass
    wrapper.__wrapped_tool__ = fn
    return wrapper


def _active():
    """The dataset the call ran on (plan 016: it can change during a session), so Verify re-runs on the same one."""
    import core
    return core.active() if core.single() else None


WRITE_TOOLS = {"load_logs", "remove_dataset", "use_dataset", "create_focus_index", "drop_focus_index", "remote_index"}


def load(session: str) -> dict:
    p = _path(session)
    if not p.exists():
        return {"session": session, "calls": [], "report": None}
    calls, report = [], None
    for line in p.read_text().splitlines():
        r = json.loads(line)
        if r["kind"] == "call":
            calls.append(r)
        elif r["kind"] == "report":
            report = r
    datasets = list(dict.fromkeys(c.get("dataset") for c in calls if c.get("dataset")))  # plan 016: in order of use
    return {"session": session, "calls": calls, "report": report,
            "dataset": ", ".join(datasets) or os.environ.get("LOGS_DATASET")}


# ---------------------------------------------------------------- number check (same rule as the agent's checker)

def numbers_check(answer: str, calls: list[dict]) -> list[dict]:
    """Each number in the answer → which step's result contains it (first match), or None (not found in any result).
    Rules from agent/checker.py: rounding to the written decimals, '35%' = 0.35, small integers and dates skipped."""
    import sys
    sys.path.insert(0, str(ROOT))
    from agent.checker import CALENDAR, DATE, NUM, _ledger_values, _matches
    per_step = []
    for c in calls:
        nums, texts = set(), []
        if c.get("result"):
            _ledger_values(c["result"], nums, texts)
        per_step.append((nums, " ".join(texts)))
    out = []
    masked = CALENDAR.sub(lambda m: " " * len(m.group()), DATE.sub(lambda m: " " * len(m.group()), answer))
    masked = re.sub(r"\d+\.\d+\.\d+\.\d+(?::\d+)?|\b[A-Za-z]+\d*[-_:][\w:.-]*\d[\w:.-]*|\b\d{2}:\d{2}(?::\d{2}(?:\.\d+)?)?",
                    lambda m: " " * len(m.group()), masked)   # IPs, ids (R77-M0-NC-I:J18-U11), clock times
    for m in NUM.finditer(masked):
        tok = m.group()
        try:
            v = float(tok.replace(",", "").rstrip("%"))
        except ValueError:
            continue
        plain_int = "%" not in tok and "." not in tok
        if plain_int and (0 <= v <= 10 or ("," not in tok and 1990 <= v <= 2035)):  # checker rule: ranks, years
            continue
        step = next((i for i, (nums, txt) in enumerate(per_step) if _matches(tok, nums) or tok in txt), None)
        out.append({"start": m.start(), "end": m.end(), "text": tok, "step": step})
    return out


# ---------------------------------------------------------------- answer → cards

SECTION = re.compile(r"(?m)^(?:#{1,4}\s+([^\n]{2,80}?)\s*\n|(?:\*\*)?([A-Z][A-Za-z ,'/()-]{2,48}?)(?:\*\*)?\s*:(?:\*\*)?\s+)")
HYPO = re.compile(r"\b(hypothes|reading|likely|possible cause|suggests|may have|might)\w*", re.I)


def sections(answer: str) -> list[dict]:
    """Split an answer into cards at 'Label:' starts of lines / paragraphs ('What failed:', '**Where it started:**',
    '### Next steps'). The text before the first label is the headline. kind = 'hypothesis' when the label says so
    (Reading, Hypothesis, Likely cause …), 'steps' when it holds a numbered list, else 'fact'."""
    text = answer.strip()
    marks = [m for m in SECTION.finditer(text) if m.start() == 0 or text[m.start() - 1] == "\n"]
    out, pos = [], 0
    if not marks or marks[0].start() > 0:
        head = text[:marks[0].start() if marks else len(text)].strip()
        if head:
            out.append({"title": None, "body": head, "start": 0})
    for i, m in enumerate(marks):
        end = marks[i + 1].start() if i + 1 < len(marks) else len(text)
        body = text[m.end():end].strip()
        title = (m.group(1) or m.group(2)).strip().rstrip(":")
        out.append({"title": title, "body": body, "start": m.end()})
    for sct in out:
        t = (sct["title"] or "").lower()
        n_items = max(len(re.findall(r"(?:^|\s)\d\.\s", sct["body"])), len(re.findall(r"(?:^|\s)[-•]\s+(?=\S)", sct["body"])))
        sct["kind"] = ("hypothesis" if HYPO.search(t) or "cause" in t and "root" not in t or t.startswith("conclusion")
                       else "steps" if n_items >= 2 else "fact")
    return out


# ---------------------------------------------------------------- Jev: stored judgments of the patterns a session touched

def jev_patterns(calls: list[dict]) -> dict:
    """{pattern_id: stored Jev judgment + traits} for every pattern id in the session's results / args (computed once
    per pattern at load time by Jev in SereneDB: p_fault, p_dump, p_problem, kind, cause, owner hint, threat)."""
    ids = set()
    for c in calls:
        for v in [c.get("args", {}).get("pattern_id")] + [r.get("pattern_id") for r in (c.get("result") or {}).get("rows") or []
                                                          if isinstance(r, dict)]:
            if isinstance(v, int):
                ids.add(v)
    if not ids:
        return {}
    import core
    ds = os.environ.get("LOGS_DATASET")
    rows = core.query(
        "SELECT j.pattern_id, p.template, round(j.p_problem, 2) AS p_problem, round(j.p_fault, 2) AS p_fault, "
        "round(j.p_dump, 2) AS p_dump, j.kind, round(j.kind_confidence, 2) AS kind_confidence, t.cause, "
        "round(t.cause_confidence, 2) AS cause_confidence, round(t.p_threat, 2) AS p_threat, t.owner_hint, "
        "round(t.owner_confidence, 2) AS owner_confidence "
        "FROM pattern_judgments j JOIN patterns p USING (dataset, pattern_id) "
        "LEFT JOIN pattern_traits t USING (dataset, pattern_id) "
        f"WHERE j.pattern_id IN ({', '.join(str(i) for i in sorted(ids))})" + (" AND j.dataset = %(d)s" if ds else ""),
        {"d": ds} if ds else None)
    return {r["pattern_id"]: {k: core.plain(v) for k, v in r.items()} for r in rows}


_support_cache: dict = {}


SENT = re.compile(r"(?<=[.!?])\s+(?=[A-Z0-9\"(])")


def claims(section: dict) -> list[str]:
    """A section's checkable claims: its sentences (numbered steps split first), short fragments dropped."""
    body = re.sub(r"(?:^|\s)\d\.\s", "\n", section["body"])
    out = []
    for part in body.split("\n"):
        out += [x.strip() for x in SENT.split(part) if len(x.strip()) > 25]
    return out


def jev_section_support(session: str, secs: list[dict], calls: list[dict]) -> list:
    """Jev (calibrated, in SereneDB): per answer section, each sentence's probability that the tool results its numbers
    come from support it (all steps when it has no traced number). One SQL call for the whole answer, cached.
    Returns per section {claims: [{text, p}], supported (p >= .5), total, min}."""
    import hashlib
    import sys
    key = hashlib.sha1((session + json.dumps([x["body"] for x in secs])).encode()).hexdigest()
    if key in _support_cache:
        return _support_cache[key]
    sys.path.insert(0, str(ROOT))
    from agent.support import jev_support
    noise = ("session_report", "hints", "truncation", "sql", "evidence_id", "elapsed_ms", "rows_returned")
    ledger = {f"s{i}": {"tool": c["tool"], "asked": c.get("args", {}),
                        **{k: v for k, v in c["result"].items() if k not in noise}}
              for i, c in enumerate(calls) if c.get("result")}
    texts = {k: json.dumps(v, default=str) for k, v in ledger.items()}
    facts, owner = [], []
    for k, x in enumerate(secs):
        for cl in claims(x):
            # every step whose result contains one of the claim's numbers, times or ids (not just the first match)
            # whole tokens: IPs, ids (R73-M1, blk_…), times, numbers (1,008 → 1008), and quoted / capitalised words
            toks = set(re.findall(r"\d+\.\d+\.\d+\.\d+|[A-Za-z]+[_-][\w:.-]+|\d{2}:\d{2}(?::\d{2})?|\d[\d,]*(?:\.\d+)?", cl))
            toks = {t.replace(",", "") if re.fullmatch(r"[\d,.]+", t) else t for t in toks}
            toks = {t for t in toks if len(t) >= 2 and not (t.isdigit() and 1990 <= int(t) <= 2035)}
            score = {sid: sum(t in txt for t in toks) for sid, txt in texts.items()}
            # the best 2 steps only: more evidence gets cut to the size limit and dilutes the one that settles it
            ids = [sid for sid, n in sorted(score.items(), key=lambda kv: -kv[1]) if n > 0][:2]
            facts.append({"statement": cl, "evidence_ids": ids or list(ledger)})
            owner.append(k)
    ps = jev_support({"facts": facts}, ledger)
    out = []
    for k in range(len(secs)):
        cs = [{"text": f["statement"], "p": p} for f, p, o in zip(facts, ps, owner) if o == k]
        got = [c["p"] for c in cs if c["p"] is not None]
        out.append({"claims": cs, "supported": sum(p >= .5 for p in got), "inferred": sum(.2 <= p < .5 for p in got),
                    "total": len(got), "min": min(got) if got else None} if cs else None)
    if any(o and o["total"] for o in out):
        _support_cache[key] = out
    return out


# ---------------------------------------------------------------- verify: re-run a recorded step's SQL

ROW_KEYS = ("line_id", "pattern_id", "evidence_id", "entity", "team", "component", "node", "bucket_start", "value",
            "dataset", "rank")


def _typed(fn, args: dict) -> dict:
    """Recorded args are JSON (datetimes became strings): give datetime parameters their type back."""
    import inspect
    from datetime import datetime as dt
    sig = inspect.signature(fn, eval_str=True).parameters
    out = {}
    for k, v in args.items():
        ann = str(sig[k].annotation) if k in sig else ""
        out[k] = dt.fromisoformat(v) if isinstance(v, str) and "datetime" in ann else v
    return out


def verify(session: str, step: int) -> dict:
    """Re-run one recorded step and compare with what the client saw: the same tool with the same arguments (so
    composite tools — hybrid search, multi-query rankings — are re-run exactly), on a fresh read-only connection.
    Compared: total_matches / total_lines and the key column of the returned rows (line_id, pattern_id, …)."""
    s = load(session)
    if not 0 <= step < len(s["calls"]):
        raise ValueError("no such step")
    c = s["calls"][step]
    rec = c.get("result") or {}
    import server  # the registered (pinned, recorded) tools; the import is cheap after the first call
    fn = getattr(server.TOOLS.get(c["tool"]), "__wrapped_tool__", None) or server.TOOLS.get(c["tool"])
    if fn is None or c.get("error"):
        return {"step": step, "status": "skipped", "detail": "this step failed or the tool is gone"}
    if c["tool"] in WRITE_TOOLS:
        return {"step": step, "status": "skipped", "detail": "a setup / write step: not re-run (verify re-runs reads only)"}
    import core
    t0 = time.perf_counter()
    with _verify_lock, _readonly():
        prev = core.active() if core.single() else None
        if c.get("dataset") and core.single():  # the dataset the step ran on, not the one active now
            core.set_active(c["dataset"])
        try:
            fresh = fn(**_typed(fn, c.get("args", {})))
        finally:
            if core.single():
                core.set_active(prev)
    ms = round((time.perf_counter() - t0) * 1000, 1)
    compared, ok = [], True     # [{what, recorded, rerun, same}]: the page shows this table
    for k in ("total_matches", "total_lines", "distinct_nodes", "first_ts", "last_ts", "nodes", "top_node_share"):
        if rec.get(k) is not None:
            same = str(fresh.get(k)) == str(rec.get(k))
            ok &= same
            compared.append({"what": k.replace("_", " "), "recorded": rec.get(k), "rerun": fresh.get(k), "same": same})
    new_rows = fresh.get("rows") if isinstance(fresh.get("rows"), list) else fresh.get("items") or []
    old_rows = rec.get("rows") or []
    key = next((k for k in ROW_KEYS if old_rows and k in old_rows[0] and new_rows and k in new_rows[0]), None)
    # a second column worth comparing per row: the first numeric one both sides have (lines, bursts, n, …)
    val = next((k for k in (old_rows[0] if old_rows else {}) if k != key and isinstance(old_rows[0].get(k), (int, float))
                and new_rows and k in new_rows[0]), None)
    if key:
        for i, r in enumerate(old_rows):
            n = new_rows[i] if i < len(new_rows) else {}
            rv = f"{r.get(key)}" + (f" · {val} {r.get(val)}" if val else "")
            nv = f"{n.get(key)}" + (f" · {val} {n.get(val)}" if val else "") if n else "(missing)"
            same = rv == nv
            ok &= same
            compared.append({"what": f"row {i + 1}", "recorded": rv, "rerun": nv, "same": same})
    n_same = sum(c["same"] for c in compared)
    detail = (f"{n_same} of {len(compared)} values identical" if compared
              else "re-ran without error (nothing countable recorded)")
    return {"step": step, "status": "match" if ok else "changed", "detail": detail, "ms": ms,
            "recorded_ms": rec.get("elapsed_ms"), "compared": compared, "key": key,
            "sql": (fresh.get("sql") or [""])[0][:3000], "ran_at": datetime.now().isoformat(timespec="seconds"),
            "role": "logs_manager (read-only)"}


class _readonly:
    """Run the re-call on its own read-only connection (load/99_roles.py), whatever role the server uses."""
    def __enter__(self):
        import core
        self.saved = core._conn
        env = os.environ.get
        import psycopg
        from psycopg.rows import dict_row
        core._conn = psycopg.connect(host=env("PGHOST", "localhost"), port=env("PGPORT", "7890"),
                                     user=env("PGUSER", "postgres"), dbname=env("PGDATABASE", "postgres"),
                                     autocommit=True, row_factory=dict_row)
        core._conn.execute("SET sdb_scan_split = 'never'")
        core._conn.execute("SET ROLE logs_manager")
        return self

    def __exit__(self, *exc):
        import core
        core._conn.close()
        core._conn = self.saved


# ---------------------------------------------------------------- HTTP server

class _Handler(BaseHTTPRequestHandler):
    def log_message(self, *a):  # keep the MCP stdio clean
        pass

    def _send(self, code: int, body: bytes, ctype: str) -> None:
        self.send_response(code)
        self.send_header("Content-Type", ctype)
        self.send_header("Cache-Control", "no-store")
        self.end_headers()
        self.wfile.write(body)

    def do_GET(self):  # noqa: N802
        try:
            parts = [p for p in self.path.split("?")[0].split("/") if p]
            if not parts or parts[0] in ("s", "latest"):
                html = (Path(__file__).parent / "report.html").read_text()
                return self._send(200, html.encode(), "text/html; charset=utf-8")
            if parts[0] == "api" and len(parts) == 2:
                sid = SESSION if parts[1] == "latest" else parts[1]
                data = load(sid)
                ans = (data.get("report") or {}).get("answer") or ""
                data["numbers"] = numbers_check(ans, data["calls"]) if ans else []
                data["sections"] = sections(ans) if ans else []
                try:
                    data["jev"] = jev_patterns(data["calls"])
                except Exception:  # noqa: BLE001
                    data["jev"] = {}
                return self._send(200, json.dumps(data, default=str).encode(), "application/json")
            if parts[0] == "support" and len(parts) == 2:   # Jev section support (one SQL call, cached)
                sid = SESSION if parts[1] == "latest" else parts[1]
                data = load(sid)
                ans = (data.get("report") or {}).get("answer") or ""
                secs = sections(ans) if ans else []
                return self._send(200, json.dumps(jev_section_support(sid, secs, data["calls"]) if secs else []).encode(),
                                  "application/json")
            if parts[0] == "verify" and len(parts) == 3:
                sid = SESSION if parts[1] == "latest" else parts[1]
                return self._send(200, json.dumps(verify(sid, int(parts[2])), default=str).encode(), "application/json")
            if parts[0] == "jevq":                               # what Jev is asked (read from the code that asks it)
                import jev_guide
                return self._send(200, json.dumps(jev_guide.guide()).encode(), "application/json")
            if parts[0] == "sessions":
                items = sorted((p.stem for p in DIR.glob("*.jsonl")), reverse=True)[:50] if DIR.exists() else []
                return self._send(200, json.dumps(items).encode(), "application/json")
            self._send(404, b"not found", "text/plain")
        except Exception as e:  # noqa: BLE001
            self._send(500, json.dumps({"error": str(e)[:300]}).encode(), "application/json")


def serve() -> int:
    """Start the page server once per process on 127.0.0.1 (first free port from LOGS_REPORT_PORT, default 8765)."""
    global _server
    if _server is None:
        port = int(os.environ.get("LOGS_REPORT_PORT", "8765"))
        for p in range(port, port + 20):
            try:
                _server = ThreadingHTTPServer(("127.0.0.1", p), _Handler)
                break
            except OSError:
                continue
        if _server is None:
            raise RuntimeError("no free port for the session report")
        threading.Thread(target=_server.serve_forever, daemon=True).start()
    return _server.server_address[1]


def session_report(
    question: Annotated[Optional[str], Field(description="The user's question, verbatim.")] = None,
    answer: Annotated[Optional[str], Field(description="Your final answer as you gave it to the user (plain text or "
                                                       "markdown), so the page can check every number in it.")] = None,
) -> dict:
    """Show the user what happened in this session: a local page with the answer, every tool call, and one-click
    verification of every number.

    Use when: you have answered the user's question with these tools — call it once at the end with the question and
    your final answer, and give the user the link. Also when the user asks for the report / to see the session.
    Not for: answering questions (it runs no new queries).
    Returns: url (open in a browser; local only), session id, tool calls recorded, and how many numbers in the answer
    were found in a tool result.
    Caveats: the page is served on 127.0.0.1 by this server process and lives as long as the session; a session file
    stays in runs/sessions/.
    Example: session_report(question='<the question>', answer='<your final answer>')
    Next: tell the user the url.
    """
    port = serve()
    if question or answer:
        _write({"kind": "report", "ts": datetime.now().isoformat(timespec="milliseconds"), "question": question,
                "answer": answer})
    s = load(SESSION)
    nums = numbers_check(answer or "", s["calls"]) if answer else []
    return {"url": f"http://127.0.0.1:{port}/s/{SESSION}", "live_url": f"http://127.0.0.1:{port}/latest",
            "session": SESSION, "tool_calls": len(s["calls"]),
            "numbers_in_answer": len(nums), "numbers_found_in_results": sum(n["step"] is not None for n in nums),
            "tell_user": f"Open http://127.0.0.1:{port}/s/{SESSION} to see every step and verify each number."}
