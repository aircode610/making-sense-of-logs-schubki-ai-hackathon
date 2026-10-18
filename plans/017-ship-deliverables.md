# 017: Ship the deliverables (investigation, eval, dashboard, MCP prompts + resources, slides, cleanup)

- **Status:** done
- **Owner:** Amirali (approved in chat 2026-10-18: "do all") · **Branch:** `feat/017-ship` · **Date:** 2026-10-18

## 1. Goal
Close the brief's open deliverables (worked investigation, tool docs, slides, demo), report a final eval on the 50
golden questions, give judges a dashboard, extend the MCP beyond tools, and remove what the repo no longer needs.

## 2. Done when
Worked investigation with every number found in a result; final A/B our agent vs the reference ReAct agent on 50 keys;
a static dashboard + a static evidence page that open without a server; prompts + resources + completions served and
probed; slides ≤ 5 min with notes; lint + check_tools pass.

## 3. Approach
- `eval/ab.py`: arm `baseline` (the brief's reference agent), so `--arms product,baseline` runs the product vs reference.
- `mcp_server/resources.py`: 6 resources (datasets, glossary, field guide, ownership, session, session step) +
  completions; prompts `worked_investigation`, `whole_corpus_counts`.
- Session report: static snapshot mode (`scripts/export_report.py`); Verify fix (recorded datetimes are strings);
  `## heading` sections. `scripts/build_dashboard.py` + template → `docs/dashboard.html`; `scripts/tools_doc.py` → `docs/TOOLS.md`.
- Slides: `docs/slides/build.js` (pptxgenjs) → `.pptx`, speaker notes = demo script.
- Cleanup: archive/, tutorial/, vendored SereneDB / Jev doc dumps, internal working docs, superseded results.

## 7. Results
- Final A/B (`eval/results/ab-20261018-193248.md`): **16-12** (9 tie, 13 inconsistent); base corpus **13-2**; engineer
  10-2; manager 2-6 (the ranking-first manager recipe loses on small single-problem logs); wrong claims 53 vs 69;
  44 s vs 22 s per answer. The 3 OTel questions scored 0 for both (OTel slice not loaded).
- Worked investigation: 20 calls, 62/62 numbers found, 17/17 read steps verify identical, 1.8 s in SereneDB.
- MCP: 44 tools, 5 prompts, 3 resources + 3 templates, completions. lint passed (32.2k tokens); check_tools 39 x 10 pass.
- Verify bug fixed: steps with start / end failed to re-run (datetime args recorded as strings).
- Follow-up: manager recipe should follow the dominant problem when the ranking has one clear item.
