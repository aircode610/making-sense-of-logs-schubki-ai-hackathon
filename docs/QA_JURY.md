# Jury Q&A tracker (pitch + questions, updated at every stage)

**Session:** Sat 17 Oct 2026, 16:00–21:04 CEST, Zoom
(https://us06web.zoom.us/j/86394339259?pwd=uRzLMr7jnbN1sdwxrMUBIvUR7hQajS.1). Our slot: **18:50–19:00 CEST** (join 18:45).
Join 5 min early, Zoom name `Team | Name`, wait to be admitted. **10 minutes.** Bring 2–3 specific questions.
Logs and EEG Q&As run in parallel.

Goal: make an impression **and** get advice. Plan for 10 min: 1 min pitch · 1 min show something real · 6 min questions ·
2 min buffer. One person talks, the other takes notes into the log below.

## Current stage → what to show
| Stage | What we can show | Update the pitch with |
|---|---|---|
| S0 setup (now) | data facts (BGL 855k FATAL vs 348k alert lines; OpenStack 3 anomalous VMs), architecture, ownership table | the thesis + the problems with the baseline |
| S1 data loaded, first queries | load time, `describe_corpus`, a full-text search + a full-corpus count by team | real numbers from SereneDB |
| S2 tools via MCP | Claude calling our tools, results with SQL + truncation flags | tool list, result limits |
| S3 agent + 3 roles | one question, three answer cards | role recipes, checker |
| S4 eval | baseline vs ours table | measured wins |

## Numbers we can show now (S2, 2026-10-17, plans 002–008 + 050–054)
- Load by SereneDB itself: BGL 4.7M + OpenStack 208k lines + templates + bursts in **≈ 31 s** (emulated amd64); counts
  equal awk. Group-bys 3–85 ms straight from the inverted index.
- MCP tools live in Claude Code: `search_logs`, `get_context` (p95 < 45 ms); kernel-panic investigation done via MCP.
- 1,126 BGL patterns; **727 have problem severities but only 76 carry real alerts** → severity alone is a poor problem
  signal (why we judge patterns with Jev). 4.7M lines = **36,714 bursts** (lines ≠ incidents, measured).
- Manager priority is computed in SQL (weights shown, independently reproduced). Honest finding: on severity alone the
  top 10 holds 1/10 real alert patterns (FATAL register dumps win) → the Jev step is measured, not decorative.
- **Jev in SQL, measured:** 1,126 patterns judged once in 20 s (≈ $0.02); priority top 10 with real alerts **1/10 → 5/10**,
  recurrence top 10 **0/10 → 5/10** (tune period). Jev alone ≈ severity; the decomposed `dump` question is what wins.
- **Agent (S3):** one LangGraph agent, three role recipes; every number in the answer card is verified against the SQL
  result it cites (engineer 25/25, lead 86/86, manager 47/47); the plain ReAct baseline with the same tools: 30/34
  (rounded / derived numbers). Jev picks the role when none is given. Each answer = one LangSmith trace.
- OpenStack: 208k lines → **106 patterns**. The labelled anomalous VMs use only normal templates; what gives them away is
  spawn time (37–51 s vs normal ≤ 28 s) → we flag numeric outliers per pattern, not just rare templates.
- **`value_outliers` (SQL median + MAD per pattern, rule fixed before looking at labels):** finds **4/4** labelled
  anomalous VMs, ranked as the 4 most extreme (2.6×, 2.1×, 1.6×, 1.5× normal), 2 mild extra flags; ~100 ms. The engineer
  agent answers "were any VMs abnormally slow?" with all of them, checker 55/55. All 100 lines of those VMs are INFO: no error or warning to search for.

## Pitch (60 s, current version — S0)
"Logs answer different questions for different people, but an LLM reading 50 retrieved lines can't tell you how often
something happens, and it can't be trusted with numbers. Our design: **SereneDB counts, Jev judges, the LLM explains, and
every sentence is checked against the query that produced it.** We mine log patterns at load time, have TypeSafe's Jev
judge each *pattern* once inside SereneDB (`ai_system_one`), so 'problem patterns by team over the whole corpus' is one
SQL query. Each role gets a different evidence recipe — engineer: search and surrounding events; team lead: recurring
patterns by team and trend; manager: a computed, auditable priority table. Every answer comes as facts with query
citations, hypotheses, unknowns and a next step, and we measure groundedness against a plain ReAct baseline."

## Questions for the jury (ranked; pick 2–3 for the slot)
1. **Incidents vs lines:** we report **bursts** (same pattern anywhere, split by a 30-min gap: 4.7M BGL lines → 36,714
   bursts) next to raw line counts and node spread. Is that a convincing unit for "recurring problems"?
2. **In-database AI:** is classifying *patterns* inside SereneDB with `ai_system_one` (Jev) — then aggregating those
   judgments in SQL — in the spirit of "the database calculates", or do you want all judgment in the agent?
3. **Demo surface:** for judging, do you prefer Claude connected to our MCP server, or our own UI that shows the answer
   card and evidence? (We plan both on the same tools — which should the 5-minute demo lead with?)
4. **Labels:** may we use BGL alert labels / OpenStack anomaly ids to *evaluate* our answers (not as agent input)?
5. **Worked investigation:** is there a BGL period or issue you'd find most convincing (e.g. a KERNDTLB storm), or is our choice part of the score?
6. **Clean checkout:** the full load from raw files takes ≈ 31 s, so judges load from scratch. Any constraint on the
   judges' machines we should know (Apple Silicon emulation, RAM)?

## Log (append after each conversation)
| When | Who | Asked | Answer / advice | Action |
|---|---|---|---|---|
| | | | | |
