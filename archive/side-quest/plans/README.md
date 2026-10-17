# Experiment plans

**Rule: no experiment work starts without an approved plan in this folder.**

Workflow for every experiment:
1. Copy `TEMPLATE.md` → `plans/NNN-short-name.md` (NNN = next number, e.g. `001-hadoop-minimal`).
2. Fill it in completely (Claude drafts, user reviews). Status: `draft`.
3. User approves → status `approved`. Create branch `exp/NNN-short-name` from `main`.
4. Execute **only** what the plan says. Any deviation → stop, update the plan, get re-approval.
5. Record results in the plan's Results section (status `done`), commit on the branch, user merges/pushes.

Guardrails every plan must respect: `docs/PRODUCT.md` (reliability, lean rule, generalization, bricks),
`docs/DECISIONS.md` (D1–D10), held-out rule D5 (Claude never sees held-out data).

| # | Plan | Status | Branch |
|---|---|---|---|
| 001 | [Hadoop minimal pipeline (warm-up)](001-hadoop-minimal.md) | **done** (held-out run once; D12) · [report](../reports/README.md) | `exp/001-hadoop-minimal` |
| 002 | [GAIA + Jev question design: ideas & lessons](002-ideas.md) | ideas (input for the plan below) | — |
| 002 | [GAIA, three roles + Jev question design](002-gaia-question-design.md) | **done** (held-out run once; D14) · [report + demo](../reports/README.md) | `exp/002-gaia-question-design` |
