# Held-out evaluation (plan, to write together; only the script is new code)

**Why:** we will tune prompts, recipes, thresholds and priority weights on what we see. A held-out set that Claude
never sees shows the judges our answers generalize and aren't tuned to the demo questions.

## What is held out
1. **Held-out questions + golden answers** (`eval/heldout/questions.yaml`): about 10 per role, written by Konark/Amirali
   from `ROLES.md` patterns but with new nodes, periods, error texts and instances. Golden answers come from
   hand-checked SQL. Claude writes none of them and never reads them.
2. **A held-out time slice for label agreement** (E6 in `EVAL.md`): e.g. the last ~30 days of BGL. Jev thresholds and
   priority weights are tuned on the earlier part only; label agreement is reported on the slice.
   The agent still sees the whole corpus (the brief requires whole-corpus answers); only the *tuning* excludes the slice.

## The script (the only code that touches held-out data)
`eval/run_heldout.py`, run as plain `python3 eval/run_heldout.py <args>`:
- runs our agent **and** the baseline agent on the held-out questions;
- scores E1–E5 and E7 against golden answers, and E6 on the held-out slice;
- prints **aggregates only** (per role and metric, ours vs baseline), never questions, answers or rows;
- writes full traces only to `eval/heldout/out/` (Claude can't read it) and to LangSmith under a separate project.

## Rules
- Claude never reads, searches or writes `eval/heldout/**`. Enforced by porting the side-quest guard hook
  (`.claude/hooks/guard_eval_data.sh` + deny rules in `.claude/settings.json`), with the sanctioned script renamed.
- Run held-out sparingly: once mid-hackathon (sanity) and once on the final build. Report the result as measured,
  even if the baseline wins.
- Labels (BGL alert category, OpenStack anomaly ids) live in a separate `labels` table that no agent tool can read.
  If we build the RLS bonus, the agent's role is denied access to it.

## Steps
1. Amirali + Claude write `eval/run_heldout.py` against a dummy dev questions file (same format).
2. Port the guard; test it blocks reads.
3. Konark/Amirali write the held-out questions and golden SQL answers without Claude.
4. Run (sanity), then final.
