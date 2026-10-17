# 008: Split the agent into a ReAct gatherer (+ coverage middleware) and a composer; one role-neutral MCP server

- **Status:** done (2026-10-17); approved with one change: **keep per-role tool subsets** in the agent
- **Owner:** Amirali · **Branch:** `feat/008-agent-split` (stacked on `feat/007-agent`) · **Date:** 2026-10-17
- **PLAN.md block / slice:** B3 · agent refactor requested by Amirali

## 1. Goal
Use the prebuilt ReAct agent instead of our hand-rolled gather/tools loop, keep evidence gathering and answer writing
as two separate agents. The MCP server stays one server with all 6 tools and role-neutral descriptions (for Claude and
any client); inside our agent each role's gatherer keeps its tool subset (Amirali's call: structural role distinctness,
fewer choices per role). Cleaner graph and traces, and a clean ablation for the eval: baseline = the same
ReAct gatherer without recipe / coverage / composer.

## 2. Done when
- `agent/graph.py`: parent graph `route → gatherer → composer → END`, where
  - **gatherer** = `create_agent(model, the role's tool subset, system_prompt=role recipe, middleware=[coverage, tool-call limit])`
    (LangChain v1 `create_agent` = the successor of LangGraph's deprecated `create_react_agent`; runs on LangGraph);
  - **coverage** = custom `AgentMiddleware.after_model`: when the model stops calling tools but the role checklist is
    missing evidence, inject a nudge and `jump_to: "model"` (≤ 2 nudges); built-in `ToolCallLimitMiddleware` caps calls;
  - **composer** = its own small `StateGraph` subgraph `compose → check → (revise ≤ 1) → END` (structured
    `AnswerCard`, deterministic checker, computed confidence), reading only the evidence ledger.
  - The ledger is built from the gatherer's `ToolMessage`s (envelopes by `evidence_id`) when it hands over.
- `ROLE_TOOLS` subsets kept for the gatherer. MCP tool docstrings / module docs become role-neutral (what the tool
  does, not who uses it); README Tools table likewise. Still one MCP server (`logs`) with all tools, no change for Claude.
- Baseline = the same `create_agent` + all tools + plain role prompt (no recipe, no coverage, no composer).
- Same 4 dev questions as plan 007 re-run: all three roles + Jev routing work, checker numbers verified, latency and
  tool calls reported next to plan 007; LangSmith trace shows `route`, `gatherer` (model/tools steps + middleware),
  `composer` (`compose`, `check`) as nested runs.

## 3. Approach
- Middleware state: `GatherState(AgentState)` with `role`, `nudges`; coverage reads tools used from `ToolMessage.name`.
- Parent state keeps `question, role, route, messages, ledger, card, check, revisions`; gatherer and composer are added
  as subgraph nodes (traced as nested runs, named `gatherer` / `composer`).
- Prompts, `checker.py`, `card.py` unchanged; `run.py` reads `tools_used` / `nudges` from the new state.

## 4. How we check it
Re-run plan 007's dev questions (engineer, lead, manager, routed) + baseline; compare §7 tables; open one trace.

## 5. Out of scope / risks
- Out: eval harness, UI, new tools.
- Tools called per role are still reported (E4 role distinctness later).
- Risk: middleware jump semantics differ from our loop → verify nudge path with a forced-missing case.

## 6. Steps
- [x] gatherer (`create_agent` + coverage + limit middleware), composer subgraph, parent graph
- [x] role-neutral MCP tool docs; README; baseline = `create_agent` + all tools
- [x] re-run dev questions + baseline; §7, STATUS; push branch

## 7. Results (filled after)
Done 2026-10-17. Same dev questions as plan 007 (tune period), new graph:

| Question | role | tool calls | time | numbers verified | plan 007 |
|---|---|---|---|---|---|
| R43-M0 kernel panics | engineer | 5 | 45 s | 22/22 | 4 · 50 s · 25/25 |
| recurring problems Nov 2005 | lead | 5 | 29 s | 86/86 | 5 · 33 s · 86/86 |
| priorities Nov 2005 | manager | 4 | 22 s | 39/39 | 3 · 20 s · 47/47 |
| "rts panic getting worse?" | lead (Jev) | 5 | 28 s | 32/32 | 5 · 45 s · 47/47 |
| **forced coverage case:** "how many data TLB lines in Nov?" | engineer | 3 | 31 s | 30/30 | — |

- **Nudge path verified:** on the pure counting question the engineer gatherer stopped after `search_logs`;
  `CoverageMiddleware` nudged once (`nudges: 1`) and it fetched `get_context` before handover.
- Tools actually called per role (all split runs): engineer {search_logs, get_context, count_by}; lead {top_patterns,
  trend, count_by, search_logs ×1}; manager {priority_table, count_by, top_patterns}.
- Graph (xray): `route` → conditional → `gather_engineer|lead|manager` (each: model → ToolCallLimitMiddleware →
  CoverageMiddleware → model/tools/end) → `handover` → `composer` (compose ⇄ check). Traced as nested runs.
- `ToolCallLimitMiddleware.run_limit` resets on each nudge (a nudge is a user turn), so the whole-run budget (10) is
  enforced by the coverage middleware (no nudge beyond it); per-turn cap 8.
- MCP tool docs made role-neutral (`search.py`, `counts.py`, `patterns.py` module / tool docstrings, README table).
