# Novelty: what everyone builds vs what we build

## The baseline every team will ship (we build it too, as the yardstick)
ReAct agent + MCP server with `search_logs`, `get_context`, `count_by`, `trend` (parameterized SQL) → LLM reads the
returned rows and writes the answer; roles = different system prompts.

Where it breaks (each is a measurable failure, see `EVAL.md`):
1. **Sample bias:** the LLM decides "what's important" from the 20–50 lines a search returned.
2. **Lines vs incidents:** 152k KERNDTLB lines look like 152k problems; one storm on one node dominates counts.
3. **Severity ≠ problem:** BGL has 855k FATAL lines but 348k labelled alert lines; ranking by severity misleads.
4. **Unverified numbers:** the LLM paraphrases, rounds or invents numbers; nobody checks prose against results.
5. **Roles = tone:** same evidence, different length — exactly what the brief says is not enough.
6. **No honest uncertainty:** no "the logs don't establish this", no computed confidence.
7. **Cost/latency:** every role question = a long multi-step LLM loop over raw rows.

## Our thesis (pitch line)
> **SereneDB counts, Jev judges, the LLM explains — and every sentence is checked against the query that produced it.**

## Our edges (each is a hypothesis we must measure against the baseline)
| # | Idea | Why it wins | How we show it |
|---|---|---|---|
| N1 | **Patterns as the unit** (templates mined at load, `pattern_id` on every row) + **episodes** (bursts split by time gap, per node/component) | Millions of lines → hundreds of patterns; recurrence = pattern over time; "N lines in K episodes on M nodes" instead of fake incident counts | lines vs episodes vs nodes in every count; lead answers per pattern |
| N2 | **Jev judgments stored in the DB** (`ai_system_one` on the patterns table, not on 4.7M lines): is-it-a-problem, failure area, severity Score, with calibrated probabilities | Meaning is judged once per pattern for cents; then "problem patterns by team" is plain SQL over the whole corpus — whole-corpus aggregation of *judgments*, not of keywords | agreement with BGL alert labels at pattern level (precision/recall, Brier) vs severity-only and vs LLM |
| N3 | **Computed priority for the manager**: score = f(frequency, trend, spread over nodes/teams, Jev severity), weights in code, shown with its inputs | Ranking is reproducible and auditable; the LLM only explains it; never invents impact | same ranking every run; each rank traceable to SQL inputs |
| N4 | **Evidence ledger + claim checker**: every tool call stores id, SQL, params, scope, row count, truncated flag, result; the answer cites evidence ids; code checks every number exists in a cited result; Jev Noul checks claim ⇐ evidence | "Shows its work" by construction; groundedness is a number on the answer card | % numbers verified, % sentences cited, unsupported claims caught (baseline vs ours) |
| N5 | **Role = evidence recipe, not prompt**: engineer = search → context window → first occurrence; lead = patterns × period × team × trend; manager = priority table + trend direction | Answers differ in evidence and actions by design (30% criterion) | overlap of tools/evidence between roles on the same question; per-role checklist |
| N6 | **Answer card with labelled sections**: FACTS (cited) · HYPOTHESES · UNKNOWN · NEXT STEP, + computed confidence badge | Directly matches the "facts vs hypotheses" requirement | checklist pass rate; judge readability |
| N7 | **One toolset, three faces**: the same MCP server serves Claude (judges), our LangGraph agent and our UI | Best-MCP award + no duplicated logic | judges connect Claude with README steps |
| N8 (optional) | Agent-managed index workspace with measured speedup; remote 50B-row OTel Parquet; RLS per role | Special awards / bonuses | timings with vs without index; rows scanned, latency |

## Guardrails from our experiments (`LESSONS.md`)
- Jev is fast, cheap, consistent and calibrated, **not** more accurate than an LLM on identical evidence; it over-flags
  routine errors. → Code decides the deterministic cases first; Jev gets narrow per-pattern questions; measure it.
- The evidence step (what SereneDB selects) is the biggest lever for every model.
- Any component stays only if it measurably helps (lean rule).
