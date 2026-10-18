# 015: Session report — see what happened inside Claude, and verify every number in one click

- **Status:** done (Amirali, 2026-10-18: "let's start with plan 015 now"; SereneDB look, clean, details on click)
- **Owner:** Amirali · **Branch:** `feat/015-session-report` (on top of `feat/014-one-dataset`) · **Date:** 2026-10-18
- **PLAN.md block / slice:** deliverable for judges (MCP first, visual second) · Best MCP Server award

## 1. Goal
Judges add our MCP to their own Claude and ask questions. At the end they get one link to a clean page that shows the
session end to end — the answer, which tools ran and why, what each returned (short), the SQL — and can re-run any
number's query to verify it (one-click verification). Looks like a SereneDB product.

## 2. Done when
- Every tool call of an MCP session is recorded (no client change): tool, args, SQL, totals, truncation, rows (short),
  server ms, timestamp → `runs/sessions/<session>.jsonl` (local, gitignored; no DB writes, works for read-only roles).
- New tool `session_report(question?, answer?)` returns `http://127.0.0.1:<port>/s/<session>`; the server instructions
  ask Claude to call it after answering. `/latest` always shows the current session live (refresh-free polling).
- Page: answer with numbers marked verified / not found in any result (existing checker rule), click a number → its
  step; timeline of steps (one line each: tool, what it found, ms; click → args, rows, SQL); summary strip (calls, DB
  time vs total, rows scanned). Light + dark, SereneDB tokens (Urbanist, #11121d / #f0f2f5 / #4a7aad, purple gradient).
- **Verify:** per step and "verify all": re-runs the step's stored SQL (only that, read-only role), compares the result
  with the recorded one, shows match / changed + new ms. Nothing else is executable from the page.
- Judge setup in README: `claude mcp add … LOGS_DATASET=…`, ask, open the link. check_tools + lint pass; token budget.

## 3. Approach
- `mcp_server/session.py`: recorder (wraps every registered tool once in server.py, after pinning), JSONL store,
  stdlib `http.server` on 127.0.0.1 in a daemon thread (started on the first `session_report` call or by env
  `LOGS_REPORT=1`), one HTML file `mcp_server/report.html` (vanilla JS, no build, fonts from Google Fonts: Urbanist).
- Verify endpoint `/verify/<session>/<step>`: reads that step's SQL from the session file; runs the main statement
  through `core.query` with `SET ROLE logs_manager` on its own connection; compares totals / first rows.
- Number check reuses `agent.checker` rules (numbers in the answer ⊂ values in the session's results).

## 4. How we check it
A real Claude Code session (headless `claude -p` with our MCP, pinned) → report link → page loads, steps = calls,
verify all = match; screenshot in light + dark; check_tools + lint; tamper test (edit a stored result → "changed").

## 5. Out of scope / risks
Out: on-demand indexing (016), live replay (017), Streamlit. Risks: Claude may not call `session_report` → `/latest`
+ README says "ask for the report"; port in use → next free port; LLM-written answer only exists if Claude passes it.

## 6. Steps
- [x] Recorder + store + `session_report` tool + instructions (+ a reminder in every tool result)
- [x] Report page (SereneDB tokens, light / dark, details on click) + verify endpoint
- [x] Real Claude Code sessions, screenshots (`docs/img/session-report-*.png`), README judge setup
- [x] STATUS / §7

## 7. Results (filled after)
- Real `claude -p` sessions (pinned bgl, D-L04 question): **Opus calls `session_report` by itself** and ends with the
  link; Sonnet (headless) answers without it → the live page (`/latest`, up from the first call) and "show me the
  session report" cover that. Answer numbers traced to tool results: 7 / 7.
- **Verify = re-call the tool with the recorded arguments** on its own read-only connection (`logs_manager`), compare
  totals + the key column of the rows. First version re-ran only the first SQL statement: it reported 'changed' for the
  hybrid `find_patterns` (fused result ≠ its lexical query) → fixed. Both steps match; a tampered session file is
  caught ('total matches 5 (was 7)'). Re-run times shown next to the recorded ones.
- check_tools 36 × 9 unpinned + pinned pass; lint passes; 41 tools, 34,440 / 36,000 definition tokens; the agent still
  parses envelopes (extra `session_report` key ignored).
- Deviation: sessions are JSONL files, not a DB table (works for read-only roles; no schema change before the merge).
