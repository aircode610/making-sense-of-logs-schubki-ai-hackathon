# 013: Blind A/B of the toolsets: plan-010 tools vs plan-011 tools, judged by an investigator with full log access

- **Status:** draft
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
- [x] 25 more questions (writers per dataset) + their answer keys (50 keys, all golden facts agree; judgement calls settled + frozen, H27)
- [x] Neutral recipes + `role_tools` parameter; diff of rendered prompts = empty (prompt depends only on role + shared recipes; leak scan: no tool name in it; smoke: both arms stay in their toolsets). Also fixed `corpus()` (plan-012 column rename had silently reduced it to a one-line fallback)
- [ ] `sql` judge tool (read-only), investigate + compare agents, blinding + leak scan
- [ ] Smoke on 2 questions, read transcripts
- [ ] Full run, results file, STATUS / EVAL.md

## 7. Results (filled after)
