"""Run the repo's psql scripts (load/*.sql) over psycopg, so loading needs no psql on the host (plan 016).

Supports exactly the psql features the loader files use: `\\set name value` (value: a word, a number or a quoted
'string' with '' escapes), `:name` / `:'name'` substitution (outside quoted strings and comments), `\\if :{?name}` /
`\\else` / `\\endif`, `\\ir file` (relative include), `\\timing` (ignored). Statements end at `;` outside quotes and
comments. Anything else starting with a backslash is an error, so a new psql feature fails loudly instead of silently.
"""
import re
import time
from pathlib import Path
from typing import Callable, Optional

import psycopg

_VAR = re.compile(r":'([A-Za-z_]\w*)'|:\{\?([A-Za-z_]\w*)\}|(?<![:\w]):([A-Za-z_]\w*)")


def _lit(v: str) -> str:
    return "'" + v.replace("'", "''") + "'"


def _value(raw: str) -> str:
    """psql \\set value: 'quoted string' (doubled quotes) or a bare word / number."""
    raw = raw.strip()
    if raw.startswith("'"):
        m = re.fullmatch(r"'((?:[^']|'')*)'", raw)
        if not m:
            raise ValueError(f"\\set: unterminated string {raw[:60]!r}")
        return m.group(1).replace("''", "'")
    return raw


def _substitute(stmt: str, var: dict) -> str:
    """psql variable interpolation outside string literals, quoted identifiers and comments; `::type` casts untouched."""
    out, i, n = [], 0, len(stmt)
    while i < n:
        c = stmt[i]
        if c == "'" or (c in "eE" and stmt[i + 1:i + 2] == "'"):        # string literal (E'' escapes handled below)
            j = i + (2 if c != "'" else 1)
            esc = c in "eE"
            while j < n:
                if esc and stmt[j] == "\\":
                    j += 2; continue
                if stmt[j] == "'":
                    if stmt[j + 1:j + 2] == "'":
                        j += 2; continue
                    break
                j += 1
            out.append(stmt[i:j + 1]); i = j + 1; continue
        if c == '"':
            j = stmt.index('"', i + 1); out.append(stmt[i:j + 1]); i = j + 1; continue
        if stmt.startswith("--", i):
            j = stmt.find("\n", i); j = n if j < 0 else j
            out.append(stmt[i:j]); i = j; continue
        if c == ":" and stmt[i + 1:i + 2] != ":" and (i == 0 or stmt[i - 1] != ":"):
            m = _VAR.match(stmt, i)
            if m:
                name = m.group(1) or m.group(3)
                if m.group(2):
                    raise ValueError(":{?name} is only supported in \\if")
                if name not in var:
                    raise ValueError(f"psql variable :{name} is not set")
                out.append(_lit(var[name]) if m.group(1) else var[name]); i = m.end(); continue
        out.append(c); i += 1
    return "".join(out)


def _split(text: str):
    """Yield ('meta', line) and ('sql', statement) in file order."""
    buf, i, n = [], 0, len(text)
    at_line_start, code = True, False  # code: the statement being built has SQL, not only comments / blanks
    while i < n:
        if at_line_start and text[i] == "\\" and not code:
            j = text.find("\n", i); j = n if j < 0 else j
            yield "meta", text[i:j].strip(); i = j + 1; continue
        c = text[i]
        at_line_start = False
        if not c.isspace() and not text.startswith("--", i):
            code = True
        if c == "'" or (c in "eE" and text[i + 1:i + 2] == "'" and (i == 0 or not (text[i - 1].isalnum() or text[i - 1] == "_"))):
            j = i + (2 if c != "'" else 1)
            esc = c in "eE"
            while j < n:
                if esc and text[j] == "\\":
                    j += 2; continue
                if text[j] == "'":
                    if text[j + 1:j + 2] == "'":
                        j += 2; continue
                    break
                j += 1
            buf.append(text[i:j + 1]); i = j + 1; continue
        if c == '"':
            j = text.index('"', i + 1); buf.append(text[i:j + 1]); i = j + 1; continue
        if text.startswith("--", i):
            j = text.find("\n", i); j = n if j < 0 else j
            buf.append(text[i:j]); i = j; continue
        if c == ";":
            stmt = "".join(buf).strip()
            if stmt:
                yield "sql", stmt
            buf, code = [], False; i += 1; continue
        if c == "\n":
            at_line_start = True
        buf.append(c); i += 1
    stmt = "".join(buf).strip()
    if stmt and any(not ln.strip().startswith("--") for ln in stmt.splitlines() if ln.strip()):
        yield "sql", stmt


def run_file(conn: psycopg.Connection, path: Path, var: Optional[dict] = None,
             log: Optional[Callable[[str], None]] = None) -> dict:
    """Execute one psql script; returns the variables at the end (includes see and change the same dict)."""
    var = var if var is not None else {}
    path = Path(path)
    stack = [True]  # \if nesting: whether the current branch runs
    t0 = time.perf_counter()
    for kind, item in _split(path.read_text()):
        active = all(stack)
        if kind == "meta":
            cmd, _, arg = item[1:].partition(" ")
            if cmd == "if":
                m = re.fullmatch(r":\{\?([A-Za-z_]\w*)\}", arg.strip())
                if not m:
                    raise ValueError(f"{path.name}: only `\\if :{{?name}}` is supported, got {item!r}")
                stack.append(m.group(1) in var)
            elif cmd == "else":
                stack[-1] = not stack[-1]
            elif cmd == "endif":
                stack.pop()
            elif not active:
                continue
            elif cmd == "set":
                name, _, raw = arg.strip().partition(" ")
                var[name] = _value(_substitute(raw, var)) if raw.strip() else ""
            elif cmd == "ir":
                run_file(conn, path.parent / arg.strip(), var, log)
            elif cmd == "timing":
                pass
            else:
                raise ValueError(f"{path.name}: unsupported psql command {item!r}")
            continue
        if active:
            sql = _substitute(item, var)
            try:
                conn.execute(sql)
            except psycopg.Error as e:
                raise RuntimeError(f"{path.name}: {str(e).splitlines()[0]}\n  in: {' '.join(sql.split())[:300]}") from e
    if log:
        log(f"{path.name} {time.perf_counter() - t0:.1f} s")
    return var
