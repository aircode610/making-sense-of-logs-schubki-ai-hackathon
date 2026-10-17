"""Print a SereneDB doc page with its <SqlLogicTest id="..."/> examples inlined.

Usage: python3 scripts/serenedoc.py sql/indexes/inverted/full-text-search
       (path relative to docs/serenedb/docs, without .md)
"""
import pathlib
import re
import sys

ROOT = pathlib.Path(__file__).resolve().parent.parent / "docs" / "serenedb"


def example(test_id: str) -> str:
    path, _, name = test_id.rpartition("/")
    for suffix in (".test", ".test_slow"):
        f = ROOT / "doc-examples" / (path + suffix)
        if f.exists():
            break
    else:
        return f"[example {test_id} not found]"
    lines = f.read_text().splitlines()
    raw, body, inside, in_body = [], [], False, False
    for line in lines:
        if line.startswith("# DOCS_TEST:"):
            if inside:
                break
            inside = line.split(":", 1)[1].strip() == name
            continue
        if not inside:
            continue
        if line.startswith("#|"):
            raw.append(line[3:])
        elif line.startswith("# DOCS_TEST_BODY"):
            in_body = True
        elif in_body and line.strip() not in ("statement ok", "query", "query I", "query T") \
                and not line.startswith(("statement error", "#", "control ", "require ")):
            body.append(line)
    out = raw or body  # the sqllogictest body: SQL, then '----' and the expected result
    text = "\n".join(out).strip().replace("\n----\n", "\n-- result:\n")
    return "```sql\n" + text + "\n```" if text else f"[example {test_id}: empty]"


page = (ROOT / "docs" / (sys.argv[1] + ".md")).read_text()
page = re.sub(r'<SqlLogicTest id="([^"]+)"[^>]*/>', lambda m: example(m.group(1)), page)
print(page)
