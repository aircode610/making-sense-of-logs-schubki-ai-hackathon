"""MCP server: log search + summary tools over SereneDB (stdio). Run: .venv/bin/python mcp_server/server.py"""
import functools
import inspect
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.fastmcp import FastMCP

import analytics
import counts
import discover
import ingestion
import outliers
import ownership
import patterns
import remote
import search
import semantic
import session
import setup
import terms
import timeline
import workspace

from core import active, field_guide, need_dataset, single

INSTRUCTIONS = """Log investigation tools over SereneDB (full-text, inverted indexes, SQL analytics, AI functions).

{setup}Field guide: the loaded datasets (each has its own time span: "now" = its last line) and what to pass for each filter:
{guide}

How to investigate (dig until the evidence answers the question, then stop):
1. Orient: describe_corpus says what each dataset is, its period, and what node / location / request_id / object_id /
   status / duration mean there. list_values gives exact filter values; never guess a component or node name.
2. Anchor: find the evidence the question is about. A known message → search_logs; a problem described in other
   words → find_patterns; "which problems / what first" over a period → top_patterns / priority_table; one id →
   request_timeline; "what changed" → whats_new / distinctive_terms; who / which IPs → top_entities.
3. Widen and explain: get_context / burst_timeline (around one occurrence), spread (one node or fleet-wide),
   pattern_history (new or recurring), rate_vs_baseline (unusual?), precursors / co_occurrence (what comes before /
   with it, with a control), trend / heatmap / reliability_trend (over time), count_by / facet / rollup (by group).
4. Check before answering: every number you state should come from a tool result (total_matches and counts are exact;
   returned rows are samples). 0 hits → match='fuzzy' / 'synonyms' or suggest_terms before saying "absent".

Ids flow between tools: rows carry line_id (→ get_context), pattern_id (→ pattern_history, spread, precursors,
co_occurrence, periodicity, burst_timeline, search_logs(pattern_id=…)), request_id / object_id (→ request_timeline),
entities like ip:… (→ search_logs(entity=…)).

Terms: line = one log entry; pattern = a kind of message (template with numbers / ids masked); burst = one recurrence
of a pattern (lines split by > 30 min quiet); episode = a burst on one node; problem pattern = has error-level lines
and a stored Jev judgment says it is a real fault or a security event; team = owner of a component (ownership table).
Lines are not incidents: use bursts for "how often" and nodes for "how widely". Association in time is not cause.
The logs hold no cost, downtime or customer impact.
Every result states its SQL, filters, scope, total_matches and whether it was truncated: cite them.
Finish every answer the same way: after writing your answer, call session_report(question, answer) with the user's
question and your final answer, then end your reply with the link it returns ("See every step and verify each number:
<url>"). The page shows the session's tool calls and re-runs their queries to verify each number."""

SETUP = """Setup and datasets (plan 016): the tools work on ONE dataset at a time, the active one; there is no
dataset parameter. setup_status shows the database, the loaded datasets and the active one. Nothing loaded →
load_logs(source='base') (the base corpus) or load_logs(source='<path to the user's log file>'); a finished load
becomes the active dataset. use_dataset(name) switches (whole-corpus counts: one call per dataset, reported together).

"""
if single():  # the shipped mode (plan 016): one active dataset, switchable at run time
    INSTRUCTIONS = INSTRUCTIONS.replace("{setup}", SETUP).replace(
        "Field guide: the loaded datasets (each has its own time span: \"now\" = its last line) and what to pass for each filter:",
        "Field guide of the active dataset at start (its time span: \"now\" = its last line; use_dataset / load_logs "
        "return the guide of a new one) and what to pass for each filter:").replace(
        "describe_corpus says what each dataset is", "describe_corpus says what the active dataset is")
else:
    INSTRUCTIONS = INSTRUCTIONS.replace("{setup}", "")
mcp = FastMCP("logs", log_level="WARNING",
              instructions=INSTRUCTIONS.format(guide=field_guide() or "(nothing loaded yet: see setup_status)"))

READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}

WRITES = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
REMOTE = {**READ_ONLY, "openWorldHint": True}

# (function, title, annotations): every tool is a fixed, parameterized query; the LLM fills typed fields only.
SPEC = [
    (setup.setup_status, "Setup and loaded datasets", READ_ONLY),
    (setup.load_logs, "Load logs (base corpus or a file)", WRITES),
    (setup.use_dataset, "Switch the active dataset", {**WRITES, "readOnlyHint": False}),
    (setup.remove_dataset, "Remove a dataset", {**WRITES, "destructiveHint": True, "idempotentHint": False}),
    (discover.describe_corpus, "What is loaded", READ_ONLY),
    (discover.list_values, "Valid filter values", READ_ONLY),
    (discover.suggest_terms, "Spelling suggestions", READ_ONLY),
    (discover.explain_search, "Why a search matches", READ_ONLY),
    (ingestion.ingest_report, "How a log format was detected", READ_ONLY),
    (search.search_logs, "Search logs", READ_ONLY),
    (search.get_context, "Events around a line", READ_ONLY),
    (terms.facet, "Breakdown of matches", READ_ONLY),
    (terms.distinctive_terms, "What is different in a window", READ_ONLY),
    (terms.top_entities, "Top IPs / paths / ids", READ_ONLY),
    (terms.check_watchlist, "Saved searches fired", READ_ONLY),
    (counts.count_by, "Counts by group", READ_ONLY),
    (counts.trend, "Counts over time", READ_ONLY),
    (counts.rate_vs_baseline, "Rate vs usual", READ_ONLY),
    (outliers.value_outliers, "Slow operations", READ_ONLY),
    (patterns.top_patterns, "Recurring problems", READ_ONLY),
    (patterns.priority_table, "Priority ranking", READ_ONLY),
    (ownership.owner_of, "Who owns a component", READ_ONLY),
    (ownership.ownership_gaps, "Unowned or uncertain owners", READ_ONLY),
    (timeline.pattern_history, "New or recurring", READ_ONLY),
    (timeline.burst_timeline, "Which error came first", READ_ONLY),
    (timeline.spread, "One node or fleet-wide", READ_ONLY),
    (timeline.whats_new, "New problems in a period", READ_ONLY),
    (timeline.precursors, "What comes before", READ_ONLY),
    (timeline.co_occurrence, "What occurs together", READ_ONLY),
    (timeline.periodicity, "Does it recur on a schedule", READ_ONLY),
    (timeline.request_timeline, "One request end to end", READ_ONLY),
    (analytics.rollup, "Totals with subtotals", READ_ONLY),
    (analytics.heatmap, "Team × week matrix", READ_ONLY),
    (analytics.reliability_trend, "Is reliability improving", READ_ONLY),
    (analytics.latency_profile, "Latency and error rate", READ_ONLY),
    (analytics.team_risk, "One team's risk", READ_ONLY),
    (semantic.similar_patterns, "Patterns that mean the same", READ_ONLY),
    (semantic.find_patterns, "Find patterns by meaning", READ_ONLY),
    (semantic.summarize_burst, "Model summary of a burst", READ_ONLY),
    (workspace.create_focus_index, "Create a focus index", WRITES),
    (workspace.drop_focus_index, "Drop a focus index", {**WRITES, "destructiveHint": True}),
    (workspace.index_stats, "Index statistics", READ_ONLY),
    (workspace.explain_tool, "Query plan of a tool", READ_ONLY),
    (remote.remote_describe, "Remote data: what is there", REMOTE),
    (remote.remote_count_by, "Remote data: counts", REMOTE),
    (remote.remote_search, "Remote data: search", REMOTE),
    (remote.remote_index, "Remote data: build an index", {**REMOTE, "readOnlyHint": False}),
]
SINGLE_SKIP = {"remote_describe", "remote_count_by", "remote_search", "remote_index"}  # other data than the user's
SETUP_TOOLS = {"setup_status", "load_logs", "use_dataset", "remove_dataset"}


def pin(fn):
    """Single-dataset server (plan 014 / 016): the same tool without its `dataset` parameter, called with the ACTIVE
    dataset at call time (it changes with load_logs / use_dataset)."""
    sig = inspect.signature(fn, eval_str=True)
    if "dataset" not in sig.parameters:
        return fn

    @functools.wraps(fn)
    def wrapper(*args, **kwargs):
        kwargs["dataset"] = need_dataset()
        return fn(*args, **kwargs)
    wrapper.__signature__ = sig.replace(parameters=[p for n, p in sig.parameters.items() if n != "dataset"])
    del wrapper.__wrapped__                     # FastMCP must read __signature__, not the original
    wrapper.__doc__ = (fn.__doc__ or "").replace("dataset=<dataset>, ", "").replace("(dataset=<dataset>)", "()")
    return wrapper


if single():
    SPEC = [(pin(fn), t, a) for fn, t, a in SPEC if fn.__name__ not in SINGLE_SKIP]
else:  # multi-dataset server (LOGS_DATASET='*'): loading / switching are CLI work there
    SPEC = [(fn, t, a) for fn, t, a in SPEC if fn.__name__ not in SETUP_TOOLS - {"setup_status"}]
# Plan 015: every tool call is recorded for the session report; session_report itself is not recorded.
SPEC = [(session.record(fn), t, a) for fn, t, a in SPEC] + [(session.session_report, "Show the session report", READ_ONLY)]
TOOLS = {fn.__name__: fn for fn, _, _ in SPEC}
for fn, title, ann in SPEC:
    mcp.tool(annotations={"title": title, **ann})(fn)


def _drop_titles(node):
    """pydantic adds a 'title' to every parameter ('Query Text', …): it repeats the name and costs ~2k tokens over all
    tools in every request. Removed from the published schemas (validation is unaffected)."""
    if isinstance(node, dict):
        node.pop("title", None)
        for k, v in node.items():
            if k != "properties":
                _drop_titles(v)
        for v in node.get("properties", {}).values():
            _drop_titles(v)
    elif isinstance(node, list):
        for v in node:
            _drop_titles(v)


for t in mcp._tool_manager.list_tools():
    _drop_titles(t.parameters)

# Optional playbooks (MCP prompts, plan 012): a client may start from one, but every tool stays available to every
# question; the server itself has no roles.
@mcp.prompt(title="Investigate a failure (engineer)")
def investigate_failure(question: str) -> str:
    """Engineer playbook: what failed, where, what happened just before and after, local or widespread, new or
    recurring, a labelled hypothesis and a concrete next check."""
    return (f"Investigate this failure with the logs tools: {question}\n\n"
            "1. Anchor: search_logs for the error (order='time'; filters for dataset, time, node / location / component); "
            "note total_matches, first_ts, last_ts, a line_id and the pattern_id. Unknown wording: find_patterns or "
            "suggest_terms. One id in the question: request_timeline.\n"
            "2. Around it: get_context(line_id) on the same node (then a coarser location or the same request / object); "
            "burst_timeline(pattern_id, at=…) for which error came first.\n"
            "3. Reach and history: spread(pattern_id) (one node or fleet-wide), pattern_history(pattern_id, as_of=…) "
            "(new or recurring), rate_vs_baseline for the window vs the previous days.\n"
            "4. Hypothesis material: precursors(pattern_id), distinctive_terms(window), top_entities, facet.\n"
            "Answer: facts with numbers from the results, ONE labelled hypothesis with what would confirm it, unknowns, "
            "and a concrete next check.")


@mcp.prompt(title="Review recurring problems (team lead)")
def review_recurring_problems(question: str) -> str:
    """Team-lead playbook: which problems recur over a period, how often, whose, trending how, what to look at first."""
    return (f"Review recurring problems with the logs tools: {question}\n\n"
            "1. top_patterns for the period (bursts = recurrences; rank_by='growth' for 'getting worse'; team= for one "
            "team); find_patterns when the problem is described in words.\n"
            "2. rollup (team → component subtotals) and trend / heatmap for the time profile.\n"
            "3. whats_new (first seen in the period), check_watchlist (known problems that came back).\n"
            "4. When asked: co_occurrence, periodicity, similar_patterns.\n"
            "Answer: the absolute period, the top 2-5 problems with owner team and measured basis (bursts, nodes, weeks, "
            "change), the one to investigate first and why, in numbers.")


@mcp.prompt(title="Set priorities (manager)")
def set_priorities(question: str) -> str:
    """Manager playbook: what deserves attention first, measured, with owners and actions; no invented impact."""
    return (f"Decide priorities with the logs tools: {question}\n\n"
            "1. priority_table for the period: the ranking is computed (weights returned): explain it, do not re-rank.\n"
            "2. reliability_trend for 'improving or worse'; team_risk for one team; rollup for team subtotals.\n"
            "3. Optionally whats_new / check_watchlist for what is new or came back.\n"
            "Answer: top 3 in the computed order with owner team, measured basis and an action to decide or fund; "
            "state that cost, downtime and customer impact are not in the logs.")


if __name__ == "__main__":
    mcp.run()
