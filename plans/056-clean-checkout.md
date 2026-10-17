# 056: Clean-checkout test (README setup from zero) + fix what breaks

- **Status:** draft
- **Owner:** Konark · **Branch:** `feat/056-clean-checkout` · **Date:** 2026-10-17
- **PLAN.md block / slice:** B5 · "clean-checkout test on K's machine" (STATUS setup gap, assigned to Konark)

## 1. Goal
A judge who clones the public repo and follows README.md gets a loaded database, passing checks, working MCP tools
and one agent answer, with no help from us. Moves the rubric's execution / reproducibility line and protects the demo
(non-negotiable: "setup from a clean checkout must work at all times on `main`").

## 2. Done when (decided before starting)
- Fresh `git clone` of `main` into an empty folder + a **fresh SereneDB volume**, following README.md literally
  (only adding keys to `.env`): `./load/reload.sh` → all checks pass (43); `mcp_server/server.py` lists 7 tools;
  one `agent.run` per role succeeds (checker passed).
- Every step that fails, is missing or is unclear is listed in §7 with its fix; fixes merged to README / scripts.
- Wall-clock time per step recorded (download, image pull, load, first answer) → README "expected times".

## 3. Approach
- Stop our running container (`docker compose down`, **volume kept**), clone into the scratchpad, run the README
  there (compose project = the clone's folder name → its own empty volume), then `down -v` the test volume and restart
  ours. Data: run `download_data.sh` for real (part of the test).
- Fix only what the test shows (README wording, missing prerequisite, script bug). Likely candidates to verify:
  `serenedb:latest` unpinned (pin the digest we tested), `psql` / `uv` install hints, Apple Silicon note, LangSmith
  EU endpoint in `.env.example`, MCP connection steps for non-Claude clients.
- No new features.

## 4. How we check it
The §2 run itself, then a second pass of the fixed README from a new clone (load + checks only).
Held-out untouched (`eval/heldout/` is gitignored, not part of the clone).

## 5. Out of scope / risks
- Out: UI, slides, worked investigation (next plan), held-out question writing (humans, without Claude).
- Risk: amd64 image under emulation is slow on a fresh volume → record the time, don't optimise here.
- Risk: our DB is down ~15 min during the test (Amirali uses his own machine, unaffected).

## 6. Steps
- [ ] Branch; `docker compose down` (keep volume); clone to scratchpad; follow README step by step, timing each
- [ ] Checks, MCP tool list, 3 agent runs; tear down test volume; restart ours + `./docker/secrets.sh`
- [ ] Fix README / scripts; second pass from a new clone (load + checks)
- [ ] §7, STATUS (tick the setup gap), plans index

## 7. Results (filled after)
