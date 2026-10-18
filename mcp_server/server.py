"""MCP server: log search + summary tools over SereneDB (stdio). Run: .venv/bin/python mcp_server/server.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.fastmcp import FastMCP

import analytics
import counts
import discover
import outliers
import patterns
import remote
import search
import semantic
import terms
import timeline
import workspace

from core import corpus_text

mcp = FastMCP("logs", log_level="WARNING", instructions=(
    "Tools over log datasets in SereneDB: " + corpus_text() + ". "
    "Every result includes the SQL that ran, its filters and scope, total_matches and a truncated flag: cite them. "
    "Numbers come only from tool results; returned lines are samples, totals are exact. Lines are not incidents."))

READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}

WRITES = {"readOnlyHint": False, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}
REMOTE = {**READ_ONLY, "openWorldHint": True}

# (function, title, annotations): every tool is a fixed, parameterized query; the LLM fills typed fields only.
SPEC = [
    (discover.describe_corpus, "What is loaded", READ_ONLY),
    (discover.list_values, "Valid filter values", READ_ONLY),
    (discover.suggest_terms, "Spelling suggestions", READ_ONLY),
    (discover.explain_search, "Why a search matches", READ_ONLY),
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
TOOLS = {fn.__name__: fn for fn, _, _ in SPEC}
for fn, title, ann in SPEC:
    mcp.tool(annotations={"title": title, **ann})(fn)

if __name__ == "__main__":
    mcp.run()
