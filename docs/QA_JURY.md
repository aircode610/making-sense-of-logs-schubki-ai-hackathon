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

## Pitch (60 s, current version — S0)
"Logs answer different questions for different people, but an LLM reading 50 retrieved lines can't tell you how often
something happens, and it can't be trusted with numbers. Our design: **SereneDB counts, Jev judges, the LLM explains, and
every sentence is checked against the query that produced it.** We mine log patterns at load time, have TypeSafe's Jev
judge each *pattern* once inside SereneDB (`ai_system_one`), so 'problem patterns by team over the whole corpus' is one
SQL query. Each role gets a different evidence recipe — engineer: search and surrounding events; team lead: recurring
patterns by team and trend; manager: a computed, auditable priority table. Every answer comes as facts with query
citations, hypotheses, unknowns and a next step, and we measure groundedness against a plain ReAct baseline."

## Questions for the jury (ranked; pick 2–3 for the slot)
1. **Incidents vs lines:** for BGL, would you accept "episodes" (bursts of the same pattern per node, split by time gap)
   as the unit for "recurring problems", reported next to raw line counts? Or do you expect line counts only?
2. **In-database AI:** is classifying *patterns* inside SereneDB with `ai_system_one` (Jev) — then aggregating those
   judgments in SQL — in the spirit of "the database calculates", or do you want all judgment in the agent?
3. **Demo surface:** for judging, do you prefer Claude connected to our MCP server, or our own UI that shows the answer
   card and evidence? (We plan both on the same tools — which should the 5-minute demo lead with?)
4. **Labels:** may we use BGL alert labels / OpenStack anomaly ids to *evaluate* our answers (not as agent input)?
5. **Worked investigation:** is there a BGL period or issue you'd find most convincing (e.g. a KERNDTLB storm), or is our choice part of the score?
6. **Clean checkout:** loading 4.7M lines under Docker emulation takes minutes — is a pre-load step acceptable, or should
   the judges' run load everything from scratch?

## Log (append after each conversation)
| When | Who | Asked | Answer / advice | Action |
|---|---|---|---|---|
| | | | | |
