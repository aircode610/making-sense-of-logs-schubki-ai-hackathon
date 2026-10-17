# 000: Fresh-session setup checks

- **Status:** done (approved by Amirali, 2026-10-17)
- **Owner:** Amirali · **Branch:** `feat/000-setup` · **Date:** 2026-10-17
- **PLAN.md block / slice:** S0 · setup (`docs/STATUS.md` "First things in a fresh session")

## 1. Goal
Every tool the next plans depend on (docs MCPs, SereneDB + Jev in SQL, Python env, `.env` keys) is verified working,
so B1 (data load) starts without setup surprises. Moves the "setup from a clean checkout works" requirement (README).

## 2. Done when (decided before starting)
- `serenedb-docs`, `typesafe-docs`, `langchain-docs` each return a non-empty result for one search.
- `docker compose up -d` → container `serenedb` running; `docker/init.sql` applied; `./docker/secrets.sh` prints
  "typesafe secret registered".
- `SELECT 1` returns `1`; one `ai_system_one(...)` call returns a probability in [0, 1].
- `.venv` (Python 3.12) created, `requirements.txt` installs cleanly, all top-level packages import;
  `requirements.txt` pinned to the installed versions (`==`).
- `.env` contains every key **name** from `.env.example` (names compared only; values never printed). Empty optional
  values (`GOOGLE_API_KEY`) reported, not failed.
- All of the above recorded in §7.

## 3. Approach
- MCPs: one query each (`search_docs "read_csv"`, `search_type_safe "ai_system_one"`, `search_docs_by_lang_chain "init_chat_model"`).
- SereneDB: first `docker ps` for an existing `serenedb` container from `../jev-serenedb-side-quest`; if present,
  run `docker compose down` there (approved: just stop it). Then `docker compose up -d`, wait for port 7890,
  `psql ... -f docker/init.sql`, `./docker/secrets.sh`.
- Jev check (syntax from `tutorial/README.md`):
  `SELECT ai_system_one('kernel: data TLB error interrupt', 'Does this log line describe a hardware fault?');`
- Python: `uv venv --python 3.12 && uv pip install -r requirements.txt`; import smoke test; rewrite
  `requirements.txt` with `==` pins for the 11 top-level packages only (versions from `uv pip freeze`), keep comments.
- `.env` check: `comm` over `sed 's/=.*//'` of both files (names only), print missing names, nonempty yes/no per key.

## 4. How we check it
Command outputs above, pasted (trimmed) into §7. No data, no eval, held-out untouched.

## 5. Out of scope / risks
- **Out:** loading BGL/OpenStack/ownership (plan B1), held-out guard hook port (plan 001; must land before anyone creates `eval/heldout/`), Konark's clone test, organiser questions.
- Risk: amd64 image emulated on Apple Silicon → slow first start; just wait. `serenedb:latest` is unpinned (note the
  digest in §7). If `TYPESAFE_API_KEY` or `ANTHROPIC_API_KEY`/`LANGSMITH_API_KEY` are missing in `.env`, Amirali adds them;
  I never write or print key values.
- Docs MCP approval prompt is the user's (first `claude` start); if a server doesn't answer, I report it.

## 6. Steps
- [x] Query the 3 docs MCPs
- [x] Stop old `serenedb` container if running
- [x] `docker compose up -d`, `init.sql`, `secrets.sh`
- [x] `SELECT 1` + one `ai_system_one`
- [x] `uv venv` + install + import smoke test
- [x] Pin `requirements.txt`
- [x] `.env` key-name check
- [x] Fill §7, tick STATUS.md setup items, add plan row to `plans/README.md`

## 7. Results (filled after)
All checks pass (2026-10-17).
- **Docs MCPs:** `serenedb-docs` (`read_csv` → 2 hits), `typesafe-docs` (`ai_system_one` → 74 K chars), `langchain-docs`
  (`init_chat_model` → models#parameters) all answer.
- **Old container:** no container named `serenedb` existed (side-quest one already gone), port 7890 free; nothing stopped.
- **SereneDB:** `docker compose up -d` → accepting connections on 7890. Image digest
  `serenedb/serenedb@sha256:6d41ac6577e797289158786a2015ba8fbd6875feadb5c491518e166c011058c9`.
  `init.sql` applied; `secrets.sh` registered `typesafe` and `gemini`.
- **SQL:** `SELECT 1` → `1`. `ai_system_one('kernel: data TLB error interrupt', 'Does this log line describe a hardware fault?')` → `0.45` (0.49 s).
- **Python:** `.venv` 3.12, install clean, all 11 packages import (note: typesafe-sdk imports as `typesafe_sdk`).
  `requirements.txt` pinned (`==`) to the installed versions; reinstall check: "Checked 11 packages".
- **.env:** all 11 names from `.env.example` present. Values **empty**: `ANTHROPIC_API_KEY`, `LANGSMITH_API_KEY`
  → Amirali must fill them before the agent/LangSmith plans. All others set.
- **Recheck after keys added (same day):** all 11 values set. `AGENT_MODEL=anthropic:claude-sonnet-5-5` (Amirali) →
  `init_chat_model` call answered `ok` from `claude-sonnet-5-5`. LangSmith first gave **403** on the US endpoint: the account
  is EU → added `LANGSMITH_ENDPOINT=https://eu.api.smith.langchain.com` to `.env` and `.env.example`; then a traced run
  (`ChatAnthropic`) appeared in project `making-sense-of-logs`.
- Follow-ups: plan 001 (held-out guard).
