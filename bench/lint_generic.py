"""Plan 012 lint: the MCP server and the agent stay dataset-agnostic, and every tool description follows the template.

1. No dataset knowledge in code: string literals of mcp_server/, agent/ and eval/ (harness code) must not contain a
   loaded dataset's name, component, example node / location / id (read from the database, so the list grows with
   every dataset). Comments are reported as warnings only.
2. Every tool description has the parts of the template: the question it answers (first line), Use when, Not for,
   Returns, Caveats, Example, Next.
3. Budget: all tool definitions together (name + description + input schema) ≤ 36k tokens (+20 % over the
   plan-011 server's 29,963), measured on the server as shipped (plan 016: the single-dataset mode, LOGS_DATASET unset
   or a name; the multi-dataset harness mode LOGS_DATASET='*' is reported, not enforced), counted with the
   Anthropic token counter when a key is set (else estimated as characters / 4).
Run: .venv/bin/python bench/lint_generic.py   (exit 1 on a violation)
"""
import asyncio
import io
import json
import os
import re
import sys
import tokenize
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "mcp_server"))
from dotenv import load_dotenv

load_dotenv(ROOT / ".env")
from core import loaded_datasets, query, single

PARTS = ["Use when:", "Not for:", "Returns:", "Caveats:", "Example:", "Next:"]
BUDGET = 36_000  # counted tokens = the plan's "+20 %" over the plan-011 server (29,963 counted)
# Ordinary English / operations words that some dataset happens to use as a component name; not dataset knowledge.
COMMON = {"email", "payment", "shipping", "checkout", "quote", "cart", "frontend", "recommendation", "kernel", "Digest",
          "accounting", "currency", "LDAP", "image", "network", "storage", "kafka", "ad",
          "Index", "Calendar"}  # Android tag names (plan 057) that are ordinary words in existing code


def forbidden() -> set[str]:
    words = set(loaded_datasets())   # every loaded dataset, whatever the server mode
    for v in loaded_datasets().values():
        # identifier-like component names only: plain lower-case words ('last', 'login', 'kernel') are ordinary English
        words |= {c for c in v.get("components") or [] if len(c) >= 4 and not re.fullmatch(r"[a-z]+", c)}
    for r in query("SELECT field, example FROM dataset_examples WHERE field IN ('node', 'location', 'request_id', 'object_id')", {}):
        ex = str(r["example"])
        words.add(ex)
        words.add(ex.split("/")[0])
    return {w for w in words if w and w not in COMMON and len(w) >= 3}


def scan(files: list[Path], bad: set[str]) -> tuple[list[str], list[str]]:
    errors, warnings = [], []
    pat = re.compile(r"(?<![\w-])(" + "|".join(re.escape(w) for w in sorted(bad, key=len, reverse=True)) + r")(?![\w-])")
    for f in files:
        src = f.read_text()
        for tok in tokenize.generate_tokens(io.StringIO(src).readline):
            if tok.type not in (tokenize.STRING, tokenize.COMMENT) and not tok.type == getattr(tokenize, "FSTRING_MIDDLE", -1):
                continue
            for m in pat.finditer(tok.string):
                msg = f"{f.relative_to(ROOT)}:{tok.start[0]}: {m.group(1)!r}"
                (warnings if tok.type == tokenize.COMMENT else errors).append(msg)
    return errors, warnings


async def tool_defs() -> list[dict]:
    import server
    return [{"name": t.name, "description": t.description or "", "input_schema": t.inputSchema}
            for t in await server.mcp.list_tools()]


def count_tokens(defs: list[dict]) -> tuple[int, str]:
    if os.getenv("ANTHROPIC_API_KEY"):
        try:
            import anthropic
            c = anthropic.Anthropic()
            with_tools = c.messages.count_tokens(model="claude-sonnet-5-5", tools=defs,
                                                 messages=[{"role": "user", "content": "x"}]).input_tokens
            bare = c.messages.count_tokens(model="claude-sonnet-5-5", messages=[{"role": "user", "content": "x"}]).input_tokens
            return with_tools - bare, "counted"
        except Exception as e:  # noqa: BLE001
            print(f"(token count API unavailable: {e}; estimating)")
    return sum(len(json.dumps(d)) for d in defs) // 4, "estimated"


def main() -> int:
    files = sorted((ROOT / "mcp_server").glob("*.py")) + sorted((ROOT / "agent").glob("*.py")) + \
        [ROOT / "eval" / f for f in ("judge.py", "metrics.py", "run_eval.py")]
    errors, warnings = scan(files, forbidden())
    defs = asyncio.run(tool_defs())
    for d in defs:
        missing = [p for p in PARTS if p not in d["description"]]
        if missing:
            errors.append(f"tool {d['name']}: description lacks {', '.join(missing)}")
        for k, p in d["input_schema"].get("properties", {}).items():
            if not p.get("description") and "$ref" not in p:
                errors.append(f"tool {d['name']}: parameter {k} has no description")
    tokens, how = count_tokens(defs)
    print(f"{len(defs)} tools, definitions {tokens:,} tokens ({how}; budget {BUDGET:,})")
    if tokens > BUDGET:
        (errors if single() else warnings).append(f"tool definitions {tokens:,} tokens > budget {BUDGET:,}"
                                                  + ("" if single() else " (multi-dataset harness mode: not enforced)"))
    for w in warnings:
        print("warn ", w)
    for e in errors:
        print("FAIL ", e)
    print(f"\n{len(errors)} violations" if errors else "\nlint passed")
    return 1 if errors else 0


if __name__ == "__main__":
    sys.exit(main())
