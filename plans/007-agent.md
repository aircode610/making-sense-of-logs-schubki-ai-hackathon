# 007: The agent: LangGraph role recipes + evidence ledger + claim checker, baseline ReAct, LangSmith tracing

- **Status:** done (2026-10-17); approved up front by Amirali ("sophisticated LangGraph agent, good LangSmith tracing, don't ask")
- **Owner:** Amirali · **Branch:** `feat/007-agent` · **Date:** 2026-10-17
- **PLAN.md block / slice:** B2/B3 · baseline ReAct agent + our layer (ARCHITECTURE.md "Agent")

## 1. Goal
One agent answers all three roles over the 6 MCP tools (same tools Claude uses), with role-specific evidence recipes,
an answer card whose every number is checked against the query results, and full LangSmith traces; plus the brief's
reference design (plain ReAct agent) as the baseline for `EVAL.md`. Moves role insight (30%), recommendation (25%),
"shows its work" (minimal requirement), execution.

## 2. Done when
- `python -m agent.run --role engineer|lead|manager "question"` answers one question per role with an answer card
  (answer, facts with evidence ids, hypotheses, unknowns, next steps, scope, computed confidence) and an evidence
  appendix (SQL + key results); `--role` omitted → role routed by Jev (calibrated choice) with LLM fallback.
- Claim checker: every number in facts / answer / ranked items is found in a cited tool result, else flagged (one
  revision round, then marked unverified); manager answers checked for invented money / downtime / customer impact;
  role checklist (ROLES.md acceptance) enforced before composing (coverage loop).
- `--baseline` runs `create_agent` with the same tools and a role prompt (free-text answer).
- LangSmith: one trace per question, named, tagged (role, ours/baseline, model) with metadata (question, role source,
  evidence ids, check results, verified-number rate); trace URL printed. Runs saved to `runs/` (gitignored).
- One answer per role recorded in §7 (numbers verified rate, tools called, latency, trace links).

## 3. Approach
- **Graph** (`agent/graph.py`, LangGraph `StateGraph`): `route` → `gather` (LLM with role tool subset + recipe, parallel
  tool calls) ⇄ `tools` (runs calls concurrently, parses envelopes into the evidence ledger) → `coverage`
  (deterministic role checklist; missing evidence → nudge back, max 2) → `compose` (structured output `AnswerCard`
  from the ledger only) → `check` (deterministic) → `compose` once more on failures → END. Tool budget per run.
- **Files:** `agent/graph.py` (state, nodes, builders), `agent/prompts.py` (role recipes), `agent/card.py` (schema +
  render), `agent/checker.py` (number verification, forbidden claims, checklist, confidence), `agent/run.py` (CLI, MCP
  client, tracing). Model `init_chat_model(AGENT_MODEL)` (no custom temperature: not supported by current Claude models). MCP via pinned `langchain-mcp-adapters`.
- Confidence = computed (verified-number rate, checklist), never self-reported.

## 4. How we check it
One question per role (dev questions, tune period only), card + checker output inspected, trace opened in LangSmith.
Baseline run on the same questions. Eval harness = next plan. Held-out untouched.

## 5. Out of scope / risks
- Out: eval harness + metrics (E1–E8), UI, held-out runs, Jev claim checking (number check is deterministic here).
- Risk: checker false positives on numbers (dates, ranks). Mitigation: dates matched as strings, small ordinals ignored.
- Risk: LLM cost/latency → tool budget, compact ledger in the compose prompt.

## 6. Steps
- [x] plan + package skeleton; card schema; checker (unit-free, scripted examples)
- [x] graph + recipes; run CLI + tracing; baseline
- [x] one question per role (ours + baseline); fix; §7, README, STATUS; push branch

## 7. Results (filled after)
Done 2026-10-17 (dev questions, tune period only; runs in `runs/agent/`, traces in LangSmith EU project
`making-sense-of-logs`).

| Run | role (how) | tool calls | time | numbers verified | checker |
|---|---|---|---|---|---|
| R43-M0 kernel panics 2005-08-19 | engineer (given) | 4 | 50 s | 25/25 | passed |
| recurring problems Nov 2005 | lead (given) | 5 | 33 s | 86/86 | passed |
| priorities Nov 2005 | manager (given) | 3 | 20 s | 47/47 | passed |
| "is rts panic getting worse?" | lead (**Jev routed**) | 5 | 45 s | 47/47 | passed |
| priorities Nov 2005, **baseline** `create_agent` | manager | 6 | 29 s | **30/34** (rounded / derived: 10,400, 1,000, 5,100 ×2) | — |

- Roles differ by evidence, not length: engineer = search + context + whole-system count + history; lead = top
  patterns (bursts, growth) + weekly trend by team + counts by team; manager = priority table + team roll-up, top 3 in
  the computed order, unknowns say cost / downtime / impact are not in the logs.
- Jev routing (`ai_system_one` choice in SereneDB): 3/3 dev questions routed correctly with confidence 1.0.
- Fixes during build: Sonnet 5.5 rejects custom `temperature` → removed; structured output via forced tool calling is
  unsupported on Sonnet 5.5 → `method="json_schema"`; LangSmith `read_run` / `get_run_url` deprecated → URL from the
  run tree (`RunTree.get_url()`), no extra API call.
- Honest note: the baseline is strong when given our tools (same priority table); its weakness is unverifiable numbers
  (rounded, derived percentages) and uncited advice. Measured properly in the eval plan (E2 groundedness, E4 role
  distinctness, E5 forbidden claims) on a question set, not one question.
- Next: eval harness (ours vs baseline on a dev question set; the held-out set only through its own runner), then UI.
