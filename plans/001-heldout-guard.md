# 001: Held-out guard + split definition

- **Status:** done (approved by Amirali, 2026-10-17)
- **Owner:** Amirali · **Branch:** `feat/001-heldout-guard` · **Date:** 2026-10-17
- **PLAN.md block / slice:** S0 · eval integrity (`docs/HELDOUT.md` steps 2–3)

## 1. Goal
Make it mechanically impossible (not just a rule) for Claude to see held-out data, and fix the split **before** any
data load or tuning, so E1–E7 held-out numbers are credible to the judges (`docs/EVAL.md`, `docs/HELDOUT.md`).

## 2. Done when (decided before starting)
- `.claude/hooks/guard_eval_data.sh` + `.claude/settings.json` in this repo; a scripted test of ≥ 10 hook inputs gives
  the expected allow/deny for every case (table in §7).
- Live check after you approve the hook (`/hooks` or restart): my `Read eval/heldout/questions.yaml` is **denied by the hook**
  (not "file not found").
- `eval/heldout/` is gitignored. BGL slice cutoff written in `docs/HELDOUT.md` + `docs/DECISIONS.md`.

## 3. Approach
- **Port the side-quest hook** (`../jev-serenedb-side-quest/.claude/hooks/guard_eval_data.sh`), changes only:
  protected dir `dataset/heldout` → `eval/heldout`; sanctioned scripts → just `eval/run_heldout.py`;
  Read is denied on paths under `eval/heldout/` (so `docs/HELDOUT.md` stays readable); drop the side-quest
  `serened.conf`/compose exemption. Bash/Grep/Glob/Write rules unchanged (any mention of the word → deny, except
  `python3 eval/run_heldout.py <simple args>`; code files may name it only in that script; `.md/.txt` exempt).
  Settings: same hook block + `deny: Read(eval/heldout/**), Edit(eval/heldout/**)`.
- **Gitignore `eval/heldout/`**: closes the `git diff/show/status` leak and makes the Grep tool (ripgrep) skip it.
  You and Konark share the files privately; commit them after the final run for transparency (your call).
- **Split** (held-out = 2 parts, `HELDOUT.md`):
  1. BGL time slice = last 30 days. I compute only the max date in `data/raw/BGL.log` (prints one date), cutoff =
     max − 30 d, rounded to 00:00. Tuning (Jev thresholds, priority weights) uses `ts < cutoff`; the agent still sees all.
  2. Held-out questions + golden SQL: **you/Konark** write them in `eval/heldout/questions.yaml`, not me. Text can be
     written now; golden answers need the loaded DB (after B1).
- Test: a scratchpad script builds hook inputs with `W="held""out"` (so my own command doesn't trip the hook) and
  checks each decision.

## 4. How we check it
Hook test table (§7) + live denial. No held-out file is created or read by me.

## 5. Out of scope / risks
- Out: `eval/run_heldout.py` (written later against a dummy dev file), questions, data load.
- Residual hole: a Bash glob like `cat eval/*/…` doesn't contain the word. Mitigation: gitignore + I never run
  recursive/glob reads over `eval/`; you can spot it in transcripts. Cheap extra (if you want): also deny Bash commands
  touching `eval/` outside `python3 eval/…`.
- The held-out LangSmith project (`…-heldout`) is off-limits to me too; noted in `HELDOUT.md`.

## 6. Steps
- [x] Port hook + settings, `chmod +x`; gitignore `eval/heldout/`
- [x] Scripted hook test (≥ 10 cases)
- [x] You approve the hook in Claude Code → live denial check
- [x] Compute BGL cutoff; record in `HELDOUT.md` + `DECISIONS.md`
- [x] Fill §7, STATUS, plans index

## 7. Results (filled after)
Done 2026-10-17 (status: done).
- **Hook test (scripted, 16/16 ok):** deny — Read questions file, Grep path in folder, Glob folder, Bash `cat` of it,
  sanctioned script + pipe, sanctioned + `;` chain, Write into folder, code file naming it. Allow — Read `docs/HELDOUT.md`,
  Read/Write `eval/run_heldout.py`, normal Read/Grep/Bash, Edit of a doc naming it.
- **Live:** `Read eval/heldout/questions.yaml` → refused by the settings deny rule; `cat` of it in Bash → refused by the hook.
  Both layers active.
- **Incident:** settings were hot-loaded before `chmod +x`, so the fail-closed hook blocked every tool until Amirali ran
  `chmod +x` by hand. Lesson: make the hook executable *before* writing `settings.json`.
- **BGL cutoff (H13):** dates 2005-06-03 … 2006-01-04 → slice `ts >= 2005-12-05 00:00`. Slice 129,874 lines /
  13,597 alert lines; tune part 4,618,089 / 334,863 (sum = 4,747,963 ✓). Slice holds ~3.9 % of alert lines: thin for
  rare categories — check per-category counts after the load (B1) and widen if E6 is too sparse.
- `eval/heldout/` gitignored. `docs/HELDOUT.md`, `docs/DECISIONS.md` (H13, H14) updated.
- **Next (humans only):** Amirali/Konark write `eval/heldout/questions.yaml` (~10 per role); golden SQL after B1.
