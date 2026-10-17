"""MCP server: log search + summary tools over SereneDB (stdio). Run: .venv/bin/python mcp_server/server.py"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent))

from mcp.server.fastmcp import FastMCP

import counts
import patterns
import search

mcp = FastMCP("logs", instructions=(
    "Tools over BGL (supercomputer RAS logs, 2005-06-03 → 2006-01-04) and OpenStack (nova) logs in SereneDB. "
    "Every result includes the SQL that ran, its filters and scope, total_matches and a truncated flag: cite them. "
    "Numbers come only from tool results; returned lines are samples, totals are exact. Lines are not incidents."))

READ_ONLY = {"readOnlyHint": True, "destructiveHint": False, "idempotentHint": True, "openWorldHint": False}

mcp.tool(annotations={"title": "Search logs", **READ_ONLY})(search.search_logs)
mcp.tool(annotations={"title": "Events around a line", **READ_ONLY})(search.get_context)
mcp.tool(annotations={"title": "Counts by group", **READ_ONLY})(counts.count_by)
mcp.tool(annotations={"title": "Counts over time", **READ_ONLY})(counts.trend)
mcp.tool(annotations={"title": "Recurring problems", **READ_ONLY})(patterns.top_patterns)
mcp.tool(annotations={"title": "Priority ranking", **READ_ONLY})(patterns.priority_table)

if __name__ == "__main__":
    mcp.run()
