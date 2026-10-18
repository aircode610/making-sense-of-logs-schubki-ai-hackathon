# 013: Blind A/B of the toolsets: plan-010 tools vs plan-011 tools, judged by an investigator with full log access

- **Status:** done
- **Owner:** Amirali · **Branch:** `feat/013-blind-ab` (after plan 012: generalized MCP + descriptions) · **Date:** 2026-10-18
- **PLAN.md block / slice:** eval · proves the plan-011 tools earn their place

## 1. Goal
One fair number for "do the 32 new SereneDB tools make the answers better?": the same agent, run twice per question,
where the only difference is the MCP toolset, compared by a blind judge that investigated the logs itself.

## 2. Done when (decided before starting)
- Arms differ only in tools: same graph, model, composer, checker, budgets and identical prompt text (diff of the two
  rendered system prompts = empty; logged in the results).
- Judge investigates every question with read-only SQL over the full logs **before** it sees any answer, then compares
  the two answers blind (labels X/Y randomized, both orders, tool names / evidence ids masked; a leak scan finds no tool
  name in what the judge sees). Only order-consistent wins count.
- Results file: wins / losses / ties / inconsistent overall, per role and per dataset; per arm: judge-verified claim
  accuracy, "found the real problem" score, rubric means, golden facts (E1), tool calls, time, tokens.

## 3. Approach
- **Arms** (`eval/ab.py`, one script): `old` = per-role subsets of the 8 original tools (plan-010 `ROLE_TOOLS`:
  engineer 6, lead 4, manager 4); `new` = current `ROLE_TOOLS` (14 / 13 / 10). Both use the current code of each tool
  (same database, same fixes, every dataset reachable). `build_graph(tools, role_tools=…)` gets the subset as a parameter.
- **One prompt for both:** a tool-neutral version of the recipes (evidence each role needs, in order; no tool names),
  so tool choice comes only from the tools' own descriptions. Used by both arms in this eval; becomes the product
  prompt only if it is not worse than the current one (separate check, not this plan).
- **Coverage nudge:** only the role checklist items both arms can satisfy (search_logs + get_context; top_patterns +
  trend/count_by; priority_table), unchanged.
- **Deviation (2026-10-18):** the judge's `sql` tool runs as DB role `logs_manager` (database-enforced read-only, 60 s cancel, 200 rows), which cannot read `labels`; the label evidence is already in the frozen answer keys, so the compare step grades against the key + SQL and the separate per-run investigation step is dropped (replaced by the keys).
- **Judge = an agent** (Opus, `JUDGE_MODEL`), tool `sql` (one SELECT/WITH statement, read-only role, 200-row cap,
  60 s timeout) over every table incl. raw `logs` (full text search `body @@ …`), `labels` (ground truth where the
  dataset has it), `ownership`, `patterns`, `bursts`, `episodes`.
  1. *Investigate* (blind, ≤ 25 queries): answers the question itself; writes reference findings (facts with the SQL
     that proved them, what a good answer for this role must contain, traps).
  2. *Compare* (fresh agent per order, ≤ 15 queries): findings + answer X + answer Y; verifies each answer's key
     claims with SQL; per answer: claims correct / wrong / unverifiable, found_problem 0-2, rubric 1-5 (role fit,
     next step, evidence, separation, clarity), then winner X / Y / tie with reasons. Run with X/Y swapped.
- **Blinding:** both answers rendered by the same card renderer; tool names and titles of all 40 tools → `[tool]`,
  `ev-…` ids dropped, check / Jev-support footer dropped; random X/Y per question (seed stored); mapping kept outside
  the judge's context.
- **Answer keys (truth, built first; approved by Amirali 2026-10-18):** one fresh, context-free agent per question
  investigates with read-only SQL over raw `logs` + `labels` + `ownership`, anchored on the question's golden facts
  (not our MCP tools, not past agent answers / bench results). Output `eval/answer_keys/<id>.yaml`: findings each with
  its SQL + result, what a good answer for the role must conclude, traps, what the logs don't establish, golden-fact
  discrepancies. Human spot-check, then frozen; the compare step grades against the key (replaces per-run investigation).
- **25 more dev questions (requested by Amirali 2026-10-18):** every dataset ≥ 3 questions (linux 4, healthapp 4,
  ssh/hdfs/zookeeper/apache 3, otel/openstack 2, bgl 1) and new cases (false premise, one connection / trace timeline,
  rate vs baseline, periodicity, new pattern, latency, spread over components). Stage 1: one writer agent per dataset
  drafts question + golden SQL → `eval/new_questions/<dataset>.yaml`; I merge into `dev_questions.yaml` and run
  `build_golden.py`. Stage 2: fresh context-free agents build their answer keys (same prompt as the first 25).
- **Questions:** the 25 dev questions (20 BGL / OpenStack + 5 new datasets); arms run interleaved per question.

## 4. How we check it
Smoke on 2 questions first (inspect what the judge sees, leak scan, judge transcript). Then the full run. Spot-read 3
judge investigations against our golden facts. Held-out untouched.

## 5. Out of scope / risks
- Out: changing tools or the product prompt; held-out.
- Risk: the neutral prompt hurts both arms (fine for the comparison; reported). Risk: the judge's SQL can reach our
  derived tables (patterns, bursts) the new arm also uses: the investigation prompt starts from raw lines; reported.
- Cost: ~25 × (2 agent runs + 1 investigation + 2 comparisons) ≈ 1-2 h wall clock with 4 in parallel.

## 6. Steps
- [x] Answer keys: 25 parallel context-free agents → `eval/answer_keys/`, human spot-check, freeze
- [x] 25 more questions (writers per dataset) + their answer keys (50 keys, all golden facts agree; judgement calls settled + frozen, H30)
- [x] Neutral recipes + `role_tools` parameter; diff of rendered prompts = empty (prompt depends only on role + shared recipes; leak scan: no tool name in it; smoke: both arms stay in their toolsets). Also fixed `corpus()` (plan-012 column rename had silently reduced it to a one-line fallback)
- [x] `sql` judge tool (logs_manager, read-only), compare agents against the frozen keys, blinding + leak scan (`eval/ab.py`)
- [x] Smoke on 2 questions (D-X25, D-M07): prompts identical, no leaks, judge verifies with SQL and caught a false claim; first verdicts flipped with order (position bias on near-ties) → judge told order is random and to call tie unless one is clearly better; re-judged: 2 consistent ties
- [x] Performance split added (Amirali): wall = llm + tool (client) + other, plus tool db (server elapsed_ms) and per-tool calls / ms; arms of a question run sequentially
- [x] Full run, results file, STATUS / EVAL.md

## 7. Results (filled after)
Full run `eval/results/ab-20261018-144958.md` (git 23c2e78, agent Sonnet 5.5, judge Opus 5.5, seed 13, 50 questions,
prompts identical across arms, 0 leaks, 0 failed runs).

- **Wins (order-consistent): new 19 · old 11 · tie 13 · inconsistent 7.** Engineer 11-4 (4 tie), lead 4-4, manager 4-3.
  By dataset the new tools win most on the unseen / non-BGL sets (healthapp 3-0, ssh 3-1, openstack 3-1, apache 2-1),
  are even on BGL (5-5) and lose on HDFS (0-2).
- **Quality per arm (new vs old):** claim accuracy 0.944 vs 0.930 (wrong claims 53 vs 64), found the real problem
  1.58 vs 1.40 (of 2), rubric 3.83 vs 3.69, golden facts (E1) 0.823 vs 0.806.
- **Performance (mean per run; llm + tool + other = wall):** new 44.4 s = 40.3 LLM + 3.7 tool + 0.5 other; old 41.0 s
  = 37.4 + 3.1 + 0.4. **The LLM is 91 % of wall time in both arms.** SereneDB time (tools' server elapsed_ms) is
  0.38 s vs 0.26 s per run (58.6 vs 45.0 ms per call, < 1 % of wall); the rest of the tool time (~0.5 s per call) is
  MCP transport / client overhead. Same tool, same code → same speed in both arms (search_logs median 10.7 vs 10.4 ms,
  priority_table 40.6 vs 38.5 ms). The new arm is 8 % slower because it makes more calls (6.5 vs 5.8 tool, 5.2 vs
  4.9 LLM) and reads 34 % more input tokens (131k vs 98k: more tool results); its slowest tool is find_patterns
  (semantic search, median 551 ms, embedding call).
- **Reading:** the plan-011 tools make answers modestly better (more wins, fewer wrong claims, more often reach the
  real problem), mostly for engineers and on datasets outside BGL; they do not make answers faster. Database speed is
  not the bottleneck: per-run latency is decided by LLM turns, so SereneDB's indexing shows up as ~10-60 ms queries,
  not as wall-time savings. Levers if latency matters: fewer LLM turns, cheaper MCP transport, smaller tool results.
- **Caveats:** one run (noise floor from plan 010: rubric ±0.06, so the rubric gap is ~2×noise); 7 inconsistent
  verdicts; the shared tool-neutral prompt is not the product prompt; dev questions only (held-out untouched).
