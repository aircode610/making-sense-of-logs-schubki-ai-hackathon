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

## Numbers we can show now (S2, 2026-10-17, plans 002–009 + 050–055)
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
- **Eval (S4, 18 dev questions, LangSmith experiments, Opus judge):** ours vs baseline with the same tools: claims
  supported 0.89 vs 0.59 (re-judged with full evidence, plan 010: 0.92 vs 0.71; ours ×3 now 0.96), numbers grounded 0.99 vs 0.85, golden facts 0.79 vs 0.59, next-step specificity 4.3 vs 2.6,
  pairwise 10-4; cost: 34 s vs 13 s per answer. Honest gaps: tool overlap across roles higher for ours; checker misses
  scope / hypotheses sections (fix next).

- **Engineer baseline (`rate_vs_baseline`):** "is this rate unusual here?" vs same-length windows of the previous week,
  never pretending a baseline exists before the data starts ("baseline only 8 h"). Engineer eval 8 questions: ours vs
  baseline pairwise **8-0**, claims supported 0.88 vs 0.47. Honest: as a fault detector "unusual" only beats raw volume
  for alert onsets (17 % vs 14 % precision), so we present it as context for an engineer, not as anomaly detection.

## Script for 18:50 (10 min, Zoom; Amirali talks, Konark notes + timer)

**Goal of this slot:** learn *how they score*, above all: do they reward **efficiency and design** (DB does the work,
cheap typed judgments, measured grounding) or mainly **answer richness** (more LLM, more tokens, more tools)? Every
question carries context, so the questions are also the pitch. Each question says what we decide from the answer.

**Have open before joining (screen share only if asked):** `eval/results/20261017-174933.md` (ours vs baseline table) ·
one manager answer card in the terminal · one LangSmith trace.

### 0:00–1:00 · Opening (pitch in one breath)
"We're Amirali and Konark. Our thesis: **SereneDB counts, Jev judges, the LLM explains, and every number is checked
against the query that produced it.** SereneDB itself loads both datasets in about 30 seconds and mines 1,126 BGL
log patterns at load time, so the agent works on recurring patterns and bursts, not on 4.7 million lines. One LangGraph
agent serves all three roles with different evidence recipes over six MCP tools, and we already evaluate it against the
plain ReAct agent from the brief, with the same tools. We have four questions about how you judge."

### 1:00–3:00 · Q1 — Efficiency vs richness (THE question)
**Context:** "We could make answers richer by giving the agent more turns, more tools and more tokens. We did the
opposite: push the work into the database. Example: instead of an LLM reading log lines, Jev, a small typed model,
judges each of the 1,126 *patterns* once, inside SereneDB with `ai_system_one`: 20 seconds, about two cents. That moved
real alerts in the manager's top 10 from 1 to 5. Our agent costs 34 s per answer vs 13 s for the plain baseline, because
we add a composer and a deterministic number checker."
**Ask:** "**Does the jury score efficiency (latency, cost, tokens, using the database well), or mainly the quality of
the final answer? If we have one more day, should it go into a smarter, cheaper pipeline or into richer answers?**"
**We decide:** where Sunday's hours go (performance / cost section in README + slides vs more agent features).

### 3:00–4:30 · Q2 — Is Jev inside the rules?
**Context:** "The brief says to use only the tools and resources it lists. Jev is called through SereneDB's own built-in
function `ai_system_one`, judgments are stored in a table, and a clean checkout loads them from a committed file, so the
judges need no extra key for the data pipeline."
**Ask:** "**Is in-database AI judgment through `ai_system_one` within the rules and in the spirit of 'the database
calculates', or would you rather all judgment stayed in the agent?**"
**We decide:** keep Jev as the headline (if yes) or present it as an optional layer with the severity-only baseline as
default (if unsure).

### 4:30–6:00 · Q3 — How they judge correctness and "shows its work"
**Context:** "We count lines exactly, but present recurrences as **bursts**: the same pattern anywhere, split by 30 quiet
minutes. 4.7 million BGL lines are 36,714 bursts. Every number in an answer must appear in the tool result it cites; a
checker enforces that. On 18 dev questions the baseline with the same tools grounds 85% of its numbers and an Opus judge
finds 59% of its claims supported; ours 99% and 89%. We use the BGL alert labels and OpenStack anomaly ids only to
*evaluate*, never as agent input."
**Ask:** "**How will you check our numbers and claims: against your own queries, by reading the evidence we show, or
both? And is evaluating with the dataset labels acceptable, as long as the agent never sees them?**"
**We decide:** how prominent the evidence appendix / SQL is in the demo; whether the label-based results go on a slide.

### 6:00–7:30 · Q4 — Demo surface and reproducibility
**Context:** "The same MCP server serves Claude Code, our agent and our eval. A clean checkout loads everything in about
30 seconds; only the agent itself needs an Anthropic key."
**Ask:** "**For the 5 minutes, would you rather see Claude connected to our MCP server, or our own agent with a small UI
showing the answer card and its SQL evidence? And will the judges have their own Claude / API key when reproducing?**"
**We decide:** whether we build the Streamlit UI tomorrow or invest in MCP setup instructions.

### 7:30–9:00 · Q5 (only if time) — what a good recommendation looks like
**Ask:** "For the manager we rank problems with a computed, weighted score and never mention money or downtime. **What
would make a recommendation convincing to you: shorter and decisive, or showing the measured basis for every item?**"

### 9:00–10:00 · Close
"Thanks. One line to remember: **the database does the counting and the cheap judging, the LLM only explains, and every
number is checked.**" Konark reads back the 2–3 decisions from the notes.

### If they ask us (short answers ready)
- **Why Jev, not just the LLM?** Measured: Jev alone was no better than severity; splitting the question ("is this a
  fault?" + "is this one field of a register dump?") is what moved the top 10 from 1/10 to 5/10, for two cents, judged
  once and stored. An LLM per line would be 4.7M calls.
- **Why bursts and not incidents?** The logs cannot tell incidents; bursts are a measured, stated rule (30-min gap,
  frozen before evaluation), always shown next to lines and node spread.
- **Is your baseline weak on purpose?** No: it gets all six of our tools, including the priority table. It loses on
  grounding (rounded or derived numbers, causes stated as facts), not on access.
- **Weaknesses?** 2.6× slower than the baseline; a 4.7M-line load runs under emulation on Apple Silicon; dev questions
  were written by us, so a separate human-written set is held back for the final numbers.
- **OpenStack?** Konark: anomalous VMs log no special messages; they are slow (37–51 s vs ≤ 28 s spawn). A per-pattern
  outlier rule in SQL (median + MAD) finds all 4 labelled VMs as the 4 most extreme.

## Log (append after each conversation)
| When | Who | Asked | Answer / advice | Action |
|---|---|---|---|---|
| | | | | |
