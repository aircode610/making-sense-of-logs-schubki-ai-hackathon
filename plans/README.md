# Plans

**Rule: no task starts without an approved plan in this folder.** Claude drafts, a human (Amirali or Konark) approves,
then work starts. Plans are short (one screen); speed comes from small tasks, not from skipping the plan.

Workflow for every task:
1. Copy `TEMPLATE.md` → `plans/NNN-short-name.md`. **Numbers by range, so parallel plans never collide:**
   Amirali **002–049**, Konark **050–099** (next free number in *your* range; a joint plan takes the drafter's range).
   Pull first; add your row to the index below.
2. Claude drafts it. Status `draft`.
3. Human approves → status `approved`. Branch `feat/NNN-short-name` from `main`.
4. Do **only** what the plan says. Deviation → stop, update the plan, get re-approval.
5. Fill in Results (numbers, what changed), status `done`, update `docs/STATUS.md` (+ `PERFORMANCE.md` / `DECISIONS.md` /
   `QA_JURY.md` if affected). Commit/merge when the user asks.

Every plan respects: `CLAUDE.md` non-negotiables, `docs/ROLES.md` (role spec), `docs/EVAL.md`, `docs/PERFORMANCE.md`,
`docs/HELDOUT.md` (Claude never sees held-out), `docs/DECISIONS.md`.

| # | Plan | Owner | Status | Branch |
|---|---|---|---|---|
| 000 | [Fresh-session setup checks](000-setup.md) | Amirali | done | `feat/000-setup` |
| 001 | [Held-out guard + split definition](001-heldout-guard.md) | Amirali | done | `feat/001-heldout-guard` |
| 002 | [BGL load (SQL-native)](002-bgl-load.md) | Amirali | done | `feat/002-bgl-load` |
| 003 | [Engineer tools: search_logs + get_context (MCP)](003-engineer-tools.md) | Amirali | done | `feat/003-engineer-tools` |
| 004 | [BGL patterns + episodes (SQL)](004-bgl-patterns-episodes.md) | Amirali | done | `feat/004-bgl-patterns-episodes` |
| 005 | [Lead + manager tools: top_patterns + priority_table](005-lead-manager-tools.md) | Amirali | done | `feat/005-lead-manager-tools` |
| 006 | [Jev pattern judgment (fault vs routine)](006-jev-pattern-judgment.md) | Amirali | done | `feat/006-jev-pattern-judgment` |
| 007 | [Agent: LangGraph recipes + checker, baseline, LangSmith](007-agent.md) | Amirali | done | `feat/007-agent` |
| 008 | [Agent split: ReAct gatherer + coverage middleware, composer](008-agent-split.md) | Amirali | done | `feat/008-agent-split` |
| 009 | [Eval harness: ours vs baseline, deterministic + LLM judge](009-eval.md) | Amirali | done | `feat/009-eval` |
| 010 | [Eval fit for iteration: version vs version, noise, judge fix](010-eval-iteration.md) | Amirali | done | `feat/010-eval-iteration` |
| 011 | [SereneDB full-capability tools, generalized](011-serenedb-features.md) | Amirali | done | `feat/011-serenedb-features` |
| 012 | [Stand-alone, dataset-agnostic MCP server + tool descriptions](012-mcp-descriptions.md) | Amirali | done | `feat/012-mcp-descriptions` |
| 013 | [Blind A/B: plan-010 tools vs plan-011 tools, investigator judge](013-blind-ab-tools.md) | Amirali | draft | `feat/013-blind-ab` |
| 050 | [OpenStack load + ownership](050-openstack-load.md) | Konark | done | `feat/050-openstack-load` |
| 051 | [count_by + trend MCP tools](051-count-trend-tools.md) | Konark | done | `feat/051-count-trend-tools` |
| 052 | [One-command reload](052-reload-publish.md) | Konark | done | `feat/051-count-trend-tools` |
| 053 | [OpenStack patterns (SQL masks)](053-openstack-patterns.md) | Konark | done | `feat/053-openstack-patterns` |
| 054 | [OpenStack Jev judgments + value_outliers](054-openstack-judgments-outliers.md) | Konark | done | `feat/054-openstack-judgments-outliers` |
| 055 | [B3 leftovers: engineer rate baseline, dev questions, review](055-engineer-baseline.md) | Konark | done | `feat/055-engineer-baseline` |
| 056 | [Clean-checkout test](056-clean-checkout.md) | Konark | draft | `feat/056-clean-checkout` |
