"""MCP resources + argument completions (plan 017): what a client can read or @-mention without calling a tool.

Tools return at most 50 rows; resources give the full context behind them:
  logs://datasets                  the loaded datasets (lines, span, judged) and the active one
  logs://field-guide/{dataset}     what each filter means in one dataset, with real example values
  logs://ownership/{dataset}       the ownership table of one dataset (team, source, confidence, dispute)
  logs://glossary                  line / pattern / burst / episode / problem pattern, and the rules the tools follow
  logs://session/latest            this session's tool calls so far (SQL, totals, truncation), = the session report data
  logs://session/{session}/step/{n} one recorded step in full (its SQL and the rows the client saw)
Completions: dataset names, components, teams and severities of the active dataset, for prompt arguments and
resource-template parameters.
"""
import json

import core
import session

GLOSSARY = """line = one log entry. pattern = a kind of message (template with numbers / ids masked).
burst = one recurrence of a pattern (its lines split by > 30 min quiet): the unit for "how often".
episode = a burst on one node. nodes = how widely. problem pattern = has problem-level lines (error-or-worse, WARN,
HTTP 5xx, or no level in the format) and a stored Jev judgment says it reports a real fault or a security event.
team = owner of a component (ownership table; source + confidence per row).
Rules every tool follows: the database counts (totals are exact over all matches, rows are samples, <= 50);
every result carries its SQL, filters, scope, total_matches, truncated and an evidence_id; lines are not incidents;
association in time is not cause; the logs hold no cost, downtime or customer impact."""


def _j(x) -> str:
    return json.dumps(x, indent=1, default=str)


def register(mcp) -> None:
    @mcp.resource("logs://datasets", name="datasets", title="Loaded datasets", mime_type="application/json",
                  description="The loaded datasets (lines, time span, Jev-judged or not) and which one is active.")
    def datasets() -> str:
        reg = core.loaded_datasets()
        return _j({"active": core.active(), "datasets": [
            {"dataset": d, "title": v.get("title"), "lines": v.get("lines"), "first_ts": v.get("first_ts"),
             "last_ts": v.get("last_ts"), "teams": v.get("teams")} for d, v in reg.items()]})

    @mcp.resource("logs://glossary", name="glossary", title="Glossary and rules", mime_type="text/plain",
                  description="What line, pattern, burst, episode and problem pattern mean, and the rules every tool follows.")
    def glossary() -> str:
        return GLOSSARY

    @mcp.resource("logs://field-guide/{dataset}", name="field-guide", title="Field guide of a dataset",
                  mime_type="text/plain",
                  description="What node / location / request_id / object_id / status / duration / entities mean in one "
                              "dataset, its span, levels, components and teams, with real example values.")
    def field_guide(dataset: str) -> str:
        saved = core._active
        try:
            core.set_active(dataset) if core.single() else None
            return core.field_guide() or f"unknown dataset {dataset!r}; loaded: {', '.join(core.loaded_datasets())}"
        finally:
            core.set_active(saved) if core.single() else None

    @mcp.resource("logs://ownership/{dataset}", name="ownership", title="Ownership table of a dataset",
                  mime_type="application/json",
                  description="Component → owning team for one dataset, with source (curated / rule / Jev), confidence "
                              "and disputes (plan 057).")
    def ownership(dataset: str) -> str:
        rows = core.query("SELECT component, team, description, source, confidence, disputed_by FROM ownership "
                          "WHERE dataset = %(d)s ORDER BY team, component", {"d": dataset})
        return _j({"dataset": dataset, "sql": f"SELECT … FROM ownership WHERE dataset = '{dataset}'", "rows": rows})

    @mcp.resource("logs://session/latest", name="session", title="This session's evidence",
                  mime_type="application/json",
                  description="Every tool call of this session so far: tool, arguments, dataset, SQL, total_matches, "
                              "truncated, server ms. The full trail behind an answer.")
    def session_latest() -> str:
        s = session.load(session.SESSION)
        return _j({"session": s["session"], "report_url": f"http://127.0.0.1:{session.serve()}/s/{session.SESSION}",
                   "steps": [{"step": i + 1, "tool": c["tool"], "args": c["args"], "dataset": c.get("dataset"),
                              "total_matches": (c.get("result") or {}).get("total_matches"),
                              "truncated": (c.get("result") or {}).get("truncated"),
                              "sql": (c.get("result") or {}).get("sql"), "error": c.get("error")}
                             for i, c in enumerate(s["calls"])]})

    @mcp.resource("logs://session/{sid}/step/{n}", name="session-step", title="One recorded step in full",
                  mime_type="application/json",
                  description="One step of a session in full: arguments, SQL, totals and the rows the client saw.")
    def session_step(sid: str, n: str) -> str:
        calls = session.load(session.SESSION if sid == "latest" else sid)["calls"]
        i = int(n) - 1
        return _j(calls[i] if 0 <= i < len(calls) else {"error": f"step {n} not in session ({len(calls)} steps)"})

    # Concrete copies of the per-dataset templates for the base corpus, so they show up in Claude Code's @ picker
    # (clients list static resources; templates need the URI typed by hand).
    def bound(fn, ds):
        def read() -> str:
            return fn(ds)
        return read

    for ds in ("bgl", "openstack"):
        mcp.resource(f"logs://ownership/{ds}", name=f"ownership-{ds}", title=f"Ownership table: {ds}", mime_type="application/json",
                     description=f"Component → owning team in {ds}, with source, confidence and disputes.")(bound(ownership, ds))
        mcp.resource(f"logs://field-guide/{ds}", name=f"field-guide-{ds}", title=f"Field guide: {ds}", mime_type="text/plain",
                     description=f"What each field means in {ds}, with real example values.")(bound(field_guide, ds))

    from mcp.types import Completion

    @mcp.completion()
    async def complete(ref, argument, context):
        name, typed = argument.name, (argument.value or "").lower()
        reg = core.loaded_datasets()
        a = reg.get(core.active() or "", {})
        pool = {"dataset": list(reg), "component": a.get("components") or [], "team": a.get("teams") or [],
                "severity": a.get("severitys") or [], "sid": ["latest"]}.get(name)
        if pool is None:
            return None
        vals = [str(v) for v in pool if str(v).lower().startswith(typed)][:50]
        return Completion(values=vals, total=len(vals), hasMore=False)
