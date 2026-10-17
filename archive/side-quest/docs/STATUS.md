# Status / handoff (read this first in a new session)

_Last updated: 2026-10-12, session 2 (experiment 002 CLOSED after one held-out run; demo deck published)._

## Where we are
- **Phase:** experiments. **001 DONE** (merged). **002 DONE / CLOSED (D14)** on branch `exp/002-gaia-question-design`
  (user merges into `main`): GAIA, three roles in one pipeline, Jev questions per role, mirrored for the LLM.
- **002 in one line:** held-out (run once) Jev 0.85 vs LLM 0.90 macro-F1 (dev 0.80 vs 0.97), raw-logs LLM 0.38, classifier
  0.67; root service 0.64 both (July has only webservice1 logs); lead 0.85 / 0.87; manager 100% both; Jev 7.6× faster,
  19.6× cheaper, same answer across wordings 100%. CV-frozen evidence generalized this time. Plan §11, PIPELINE §11.6–11.7.
- **002 report:** https://claude.ai/artifact/FtbbRo9ZYvRXaXVX3vWagt (`reports/002-gaia.html`, full decision history).
  **Demo deck for teams new to Jev:** https://claude.ai/artifact/LPRakghFXmQFkFWtKdfyw3 (`reports/002-jev-demo.html`, built by
  `experiments/002_gaia/build_demo.py` from recorded dev calls + aggregates).
- **How 002 is implemented:** `experiments/002_gaia/README.md`.
- **001 in one line:** dev tie (Jev 0.51 vs LLM 0.49 macro-F1, Jev better calibrated, 8× faster, 17× cheaper);
  held-out (run once) Jev 0.32 vs LLM 0.42 vs raw-logs LLM 0.54 vs classifier 0.66 → dev-tuned evidence did not
  generalize (D12). H4 ("auto" answers ≥90% accurate) failed for both models.
- **Report:** https://claude.ai/artifact/8XPVMCUAX2aPirdtSeiUgE (source `reports/001-hadoop.html`; keep it updated per rule 7,
  and start a new report per experiment, e.g. `reports/002-….html`, registered in `reports/README.md`).
- **Reusable pieces:** `pipeline/` (4 bricks, tracing, baselines, metrics), `apps/trace_viewer.py` (Jev vs LLM side by
  side), `experiments/001_hadoop/` (runner, H4 analysis), split/eval scripts as templates for 002.

## Open items carried over from 001 (see also plans/002-ideas.md)
| Item | Status / what's needed |
|---|---|
| **H4: no "auto" threshold reaches 90% accuracy** | **Analysed (amendment 3), negative:** no signal works for either model; cause = failure labels with no trace in the logs (5 dev jobs). Keep current confidence; re-test on GAIA. PIPELINE §11.4 |
| **Held-out evaluation: DONE (once), negative for Jev** | Jev 0.32 vs LLM 0.42 vs raw-logs LLM 0.54 vs classifier 0.66 macro-F1; dev conclusions didn't generalize; see PIPELINE §11.5. Second listener (port 4319, separate schema) is configured; guard allows only `docker/serened.conf` + `docker-compose.yml` to name the schema (user-approved). Experiment 001 is CLOSED: do not re-run held-out. Old note: | User first adds the 2nd OTLP listener to `docker/serened.conf` and restarts SereneDB (exact steps in the session where amendment 3 was done, repeated in plans/001 §"Held-out: user steps"). `scripts/eval_heldout.py` not written. Needs a 2nd OTLP listener `http://0.0.0.0:4319?api=otel&schema=heldout` in `docker/serened.conf` (**user must add it**: the guard blocks Claude). Must ingest dev + held-out into schema `heldout`, run the frozen config for Jev AND the LLM + B2–B4 (B3 trained on all dev), print aggregates only. Run once. |
| Knob sensitivity | Untested: Drain3 `sim_th`/`depth`, `TOP_K_EVIDENCE`, `RARE_MAX_JOB_FRACTION` (0.25), timing/rarity word buckets |
| Key-evidence quality | No ground truth for "which line proves it"; citation accuracy unmeasured |
| Jev via SereneDB SQL | Pipeline uses the TypeSafe SDK; the in-database `ai_system_one` path is untested for parity |
| Explanation layer | LLM prose for the answer card + citation check: out of scope for 001 |
| Small n | Dev 105 questions (35 jobs); CIs are wide. GAIA (exp 002) and BGL give the real verdict |

## ➡️ Next: plan 003 (BGL)
- 002 frozen config = evidence **E1** (per-service 24 h baseline) + engineer questions **Q7**; do not re-run 002 held-out.
- Post-hoc (amendment 4, dev only): words-only evidence changed no Jev answer → counts are not the problem. 73% of
  questions need no model (no unusual pattern → no fault); the remaining gap is Jev calling routine items faults.
  Proposed 003 design: code decides "no items → no fault" and the citation; Jev answers one per-item question
  ("real fault or routine behaviour?") before the type Choice. Plan §11.3.
- Carry over from 002: (1) Jev's false alarms on routine errors at ~2× their usual rate; Q1 "cannot tell" was its best lever
  (+0.06, below the bar) → re-test on BGL; (2) lead/manager judgments are saturated on GAIA → need a corpus with more
  distinct problems; (3) root service needs the root service's own logs (July case).
- Data: 002 dev is ingested in schema `public` (`gaia_rollup`, `gaia_error_traces`, `gaia_windows`, `gaia_catalog`, raw rows in
  `otel_logs`). Re-run a dev wave: `.venv/bin/python experiments/002_gaia/run_dev.py waveN` (calls cached in `runs/002/cache`).
- Spend 002: dev Jev $0.32 + LLM $18.32; held-out about $6–7 more by estimate (≈ $5 of it the raw-logs baseline).

## Next experiments (proposed, not planned yet)
- **003 BGL** for calibration at scale and more alert categories.
- Later: explanation layer (LLM answer card with citation check), traces/metrics add-on, `ai_system_one` parity.

## Environment reminders
- `docker compose up -d`, then `./docker/secrets.sh` after every restart (secrets aren't persisted).
- SQL `psql -h localhost -p 7890 -U postgres -d postgres`; OTLP `:4318` with `otel:otel`.
- Keys in `~/.zshrc`: TYPESAFE_API_KEY, GOOGLE_API_KEY (OpenAI key is invalid). Load in bash with
  `eval "$(grep -E '^export (TYPESAFE_API_KEY|GOOGLE_API_KEY)=' ~/.zshrc)"` (sourcing .zshrc from bash kills the shell).
- Python: `.venv` (3.14), deps pinned in `requirements.txt`.
- Another project's SereneDB container (`schubki-t04-serenedb-1`) was stopped to free port 7890.
