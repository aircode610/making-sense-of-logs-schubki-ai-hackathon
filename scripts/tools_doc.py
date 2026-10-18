"""Write docs/TOOLS.md from the running server's own MCP listing (plan 017): every tool's description, inputs
(type, default, allowed values) and outputs, plus the prompts and resources. The doc cannot drift from the code.
  uv run python scripts/tools_doc.py
"""
import asyncio
from pathlib import Path

from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client

ROOT = Path(__file__).resolve().parent.parent


def ptype(s: dict) -> str:
    if "anyOf" in s:
        return " | ".join(ptype(x) for x in s["anyOf"] if x.get("type") != "null") + " (optional)"
    if "enum" in s:
        return " / ".join(f"`{v}`" for v in s["enum"])
    if s.get("type") == "array":
        return f"list of {ptype(s.get('items', {}))}"
    return s.get("format") or s.get("type", "any")


async def main() -> None:
    p = StdioServerParameters(command=str(ROOT / ".venv/bin/python"), args=[str(ROOT / "mcp_server/server.py")])
    async with stdio_client(p) as (r, w), ClientSession(r, w) as s:
        await s.initialize()
        tools = (await s.list_tools()).tools
        prompts = (await s.list_prompts()).prompts
        res = (await s.list_resources()).resources
        tmpl = (await s.list_resource_templates()).resourceTemplates
    L = ["# Tools, prompts and resources of the `logs` MCP server", "",
         "Generated from the server's own MCP listing by `scripts/tools_doc.py` (what Claude sees, verbatim). "
         f"{len(tools)} tools, {len(prompts)} prompts, {len(res)} resources + {len(tmpl)} resource templates, argument "
         "completions for dataset / component / team / severity.", "",
         "Every tool result is an envelope: `tool`, `params`, `sql` (exact queries, values inlined), `filters`, `scope`, "
         "`total_matches` (exact, over all matches), `truncated`, `elapsed_ms`, `evidence_id`, `rows` (≤ 50, messages cut "
         "at 300 chars), `hints` (next step).", "", "## Index", "",
         "| Tool | Title | Read-only |", "|---|---|---|"]
    L += [f"| [`{t.name}`](#{t.name}) | {t.annotations.title if t.annotations else ''} | "
          f"{'yes' if t.annotations and t.annotations.readOnlyHint else 'no'} |" for t in tools]
    L += ["", "## Prompts (slash commands in Claude Code: `/mcp__logs__<name>`)", ""]
    for pr in prompts:
        args = ", ".join(f"`{a.name}`" + ("" if a.required else " (optional)") for a in pr.arguments or [])
        L.append(f"- **`{pr.name}`**({args}): {pr.description}")
    L += ["", "## Resources (`@logs:<uri>` in Claude Code)", ""]
    L += [f"- `{x.uri}`: {x.description}" for x in res] + [f"- `{x.uriTemplate}`: {x.description}" for x in tmpl]
    L += ["", "## Tools", ""]
    for t in tools:
        L += [f"### `{t.name}`", "", t.description.strip(), ""]
        props = t.inputSchema.get("properties", {})
        req = set(t.inputSchema.get("required", []))
        if props:
            L += ["| Input | Type | Default | Description |", "|---|---|---|---|"]
            for n, sch in props.items():
                d = "required" if n in req else f"`{sch.get('default')}`"
                L.append(f"| `{n}` | {ptype(sch)} | {d} | {(sch.get('description') or '').replace('|', '/')} |")
            L.append("")
    (ROOT / "docs/TOOLS.md").write_text("\n".join(L) + "\n")
    print(f"docs/TOOLS.md: {len(tools)} tools, {len(prompts)} prompts, {len(res) + len(tmpl)} resources")

asyncio.run(main())
