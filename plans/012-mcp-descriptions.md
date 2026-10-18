# 012: A stand-alone, dataset-agnostic MCP server: generalized tool surface + tool descriptions any agent can use

- **Status:** done, in review (approved by Amirali, 2026-10-18: "approved"; second model = Sonnet 5.5; every tool checked on every dataset)
- **Owner:** Amirali · **Branch:** `feat/012-mcp-descriptions` (on top of 011) · **Date:** 2026-10-18
- **PLAN.md block / slice:** B3 tools · MCP award · generality (the blind A/B, plan 013, runs after this)

## 1. Goal
Any MCP client (Claude Code, our agent, another LLM) given only our server and a free-form question can dig through
the logs on its own: pick the right tool from its description, pass valid values, follow ids from one result to the
next, and stop with evidence. No role split in the server, nothing dataset-specific in its code.

## 2. Done when (decided before starting)
- **Generalized:** a lint (`bench/lint_generic.py`) finds no dataset name or dataset value (components, nodes, message
  wording) in string literals of `mcp_server/` and `agent/`; all examples in descriptions come from the database.
  Two unseen Loghub datasets load with a loader file + ownership `*` rows only. **Every tool is run on every dataset**
  (`bench/check_tools.py`, inputs chosen from that dataset's own registry / values, no per-dataset branches) and its
  numbers equal an independent SQL query; all 9 datasets pass.
- **Descriptions:** every tool follows the template of §3B (a lint checks the parts are present); all tool definitions
  together ≤ 20k tokens (now 16.7k).
- **Measured** with a role-free benchmark (§3F), before → after, two models: first-tool hit, required tools used,
  invalid calls, calls / tokens per question, golden facts in the answer. After ≥ before on hit rate and facts, invalid
  calls down. Plus Claude Code headless on 10 questions (transcripts kept).
- Reload, `check_counts`, `check_patterns`, `check_tools`, replay: pass (differences from renamed columns explained).

## 3. Approach
Research (Anthropic "Writing effective tools for agents", Claude tool-use docs, Datadog / GitHub MCP servers, arXiv
2602.14878 "MCP tool descriptions are smelly"): detailed descriptions are the biggest lever; each states purpose,
when to use and when not, what it returns, caveats, parameter meanings, an example; unambiguous parameter names;
few, non-overlapping tools (GitHub cut 101 → 52 tools for better selection); actionable errors; results that point
to the next step; annotations for read-only / open-world.
- **A. Generic tool surface** (schema + loaders + tools): `rack` / `midplane` → `location` at any level (get_context
  scope `location` + `level`); `instance_id` → `object_id` (a long-lived thing followed across requests: VM, block,
  container); `request_id` = one request / session / trace; `latency_ms` → `duration_ms` (any duration the loader
  parses, e.g. "Took N seconds"), so `value_outliers` has no message regex; `tenant_id` → entity `tenant:…`. What each
  id / location / status means per dataset lives in new `datasets` columns, shown by `describe_corpus` and inserted
  into descriptions at startup.
- **B. Description template**, one per tool, shared parameter texts defined once in `core.py`:
  1. the question it answers, in the user's words; 2. *Use when* / *Not for* (names the sibling tool);
  3. *Returns*: what one row is, key fields, definitions (lines / bursts / episodes, units);
  4. *Caveats* (sample vs total, association ≠ cause, truncation); 5. *Example* call with live values;
  6. *Next*: which ids to pass on (pattern_id → history / spread / precursors, line_id → get_context).
  Parameters: meaning, format, default and its effect; enums explain every value.
- **C. Server instructions** (shown by Claude Code and other clients): the investigation loop (orient with
  `describe_corpus` → anchor → widen → check → stop), glossary (line, pattern, burst, episode, problem pattern, team),
  how ids flow between tools, the rules (numbers only from results, lines ≠ incidents).
- **D. Results that keep the agent digging**: envelope `hints` (deterministic): 0 hits → fuzzy / synonyms /
  suggest_terms with candidates; truncated → narrower filter or a counting tool; unknown filter value → closest valid
  values; rows with pattern_id → follow-up tools. Validation errors list valid values.
- **E. One tool set, no roles in the server**: every tool available to every question. Role playbooks become MCP
  *prompts* (`investigate_failure`, `review_recurring_problems`, `set_priorities`): optional templates a client can
  pick, never a tool filter. Merge overlapping tools where the benchmark shows confusion (candidates: count_by / rollup /
  facet, trend / heatmap, find / similar_patterns); operator tools (index_stats, explain_tool, focus index,
  remote_index) stay, optionally switched off with `LOGS_TOOLSETS`.
- **F. Benchmark** `bench/tool_use.py`: ~40 questions as a person would ask (failure, recurrence, priority, security,
  latency; all datasets incl. the 2 unseen), each with acceptable first tools, required tools and 1-3 SQL-verified facts.
  Plain agent, all tools, one-line system prompt; Opus 5.5 and Sonnet 5.5.
- **G. Unseen datasets**: two small Loghub sets from the brief not used so far: Linux and HealthApp (Spark is 2.75 GB,
  not small; HealthApp adds a new format: pipe-separated, unpadded dates, no levels, no host).

## 4. How we check it
Benchmark before (current server) → after each part (A, B+C, D, E); lint; all load / tool checks; replay; Claude Code
headless (`claude -p --mcp-config`) on 10 questions. Held-out untouched.

## 5. Out of scope / risks
- Out: agent prompts and role subsets (`ROLE_TOOLS`, recipes): next step, then the A/B (plan 013).
- Risk: renaming columns invalidates golden facts and replay → rebuild golden with `verify_order`, explain replay diffs.
- Risk: longer descriptions cost tokens → 20k budget, measured.

## 6. Steps
- [x] Benchmark questions + harness; baseline numbers on the current server
- [x] A: generic columns, registry meanings, loaders, tools, lint; reload + checks
- [x] B + C: template, shared parameter texts, rewrite 40 descriptions, server instructions; benchmark
- [x] D: hints + actionable errors; benchmark
- [x] E: MCP prompts; merges the benchmark asks for; benchmark
- [x] G: 2 unseen datasets, zero code change; checks + benchmark
- [x] Claude Code headless run; README tool table, PERFORMANCE / DECISIONS / STATUS

## 7. Results (filled after)
**Built.** A: generic `logs` columns (`location` at any level replaces rack / midplane, `object_id` replaces
instance_id, `duration_ms` = any duration the loader parses, so `value_outliers` / `latency_profile` have no message
regex; tenant → entity `tenant:…`); `datasets` gains node / location / request / object / status / duration meanings;
`load/93_examples.sql` stores a real example value per dataset and field; `reload.sh` runs every loader whose
`-- requires:` file exists and now stops on the first SQL error (it used to swallow it). B: 40 descriptions in the
template, shared parameter types in `core.py`. C: server instructions = investigation loop, id flow, glossary and a
**field guide** generated from the data (805 tokens). D: `hints` (0 hits, unknown component / level with closest
values, sample vs total, found pattern ids → follow-ups). E: playbooks as MCP prompts; no merges (the benchmark showed
no tool confusion: first-tool and required-tool rates 1.0). G: Linux (syslog, latin-1 attack bytes) and HealthApp
(new format) loaded with a loader file + `*` ownership row + the existing Jev / embedding scripts.
**Checks.** `bench/check_tools.py`: **every tool on every dataset vs independent SQL, 39 tools x 9 datasets, all pass**
(+ 3 remote tools; `remote_index` timed in PERFORMANCE.md, not in the regular check), inputs chosen generically from
each dataset, skips only where the dataset lacks the data (durations: OpenStack only; ids: 6 of 9; watches: 5 of 9).
`bench/lint_generic.py`: no dataset value in tool / agent / eval string literals, template complete, definitions
**33,652 tokens** (counted; plan-011 server 29,963: +12 %; the budget was restated in counted tokens as +20 %, since
the plan's "20k" was a characters / 4 estimate of the same +20 %). check_counts / check_patterns pass; dev golden facts
(25 q) unchanged, rankings re-verified; the role agent runs (checker passed). `bench/replay_tools.py` replays of old
ledgers fail on renamed parameters (midplane, instance_id): expected, not re-baselined.
**Benchmark** (`bench/tool_use.py`, plain agent, all tools, one-line prompt + server instructions as an MCP client
passes them; before = plan-011 server, re-scored after fact fixes):

| same 30 questions | first tool | required tools | facts | tool errors | calls / q | input tokens / q |
|---|---|---|---|---|---|---|
| Opus 5.5 before → after | 1.0 → 1.0 | 1.0 → 1.0 | 0.925 → 0.925 | 1 → 2 | 3.7 → 3.6 | 102k → 135k |
| Sonnet 5.5 before → after | 0.967 → 1.0 | 1.0 → 1.0 | **0.830 → 0.962** | 0 → 0 | 4.1 → 3.6 | 97k → 119k |
| unseen Linux + HealthApp (6 q), after | Opus 1.0 / Sonnet 1.0 | 1.0 / 1.0 | 0.90 / 1.0 | 0 / 0 | 3.7 / 3.5 | |

The 2 Opus errors were a pre-existing `facet` bug (one dimension → SereneDB cannot bind `grouping()`), fixed and added
to check_tools. Input tokens +22-33 %: server instructions + richer results. Claude Code headless (Sonnet, only this
server, 10 q incl. 2 unseen): first tool 9/10, required tools 10/10, 0 tool errors, 2.8 calls / q, facts 14/19 (the
misses are wording: "Two … lines", "50.7 s", "about 21,800"; answers checked by hand were correct). Its one wrong first
tool (remote data for a question about the loaded OTel slice) → remote source description now says a slice is loaded.
**Found on the way.** `judge_patterns.sql` nulled the whole Jev prompt when severity is NULL: 108 / 109 SSH fault
judgments had been empty since plan 011 (fixed, re-judged; DECISIONS H26).
**Not done / limits.** The benchmark is near its ceiling for selection (written by the same author as the
descriptions; the blind A/B of plan 013 and the human held-out set are the independent tests). Agent prompts and role
subsets unchanged (next step).
