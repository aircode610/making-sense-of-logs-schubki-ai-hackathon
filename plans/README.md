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
