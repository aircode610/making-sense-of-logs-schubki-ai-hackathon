# 018: Claude Code + our MCP vs plain Claude Code on the raw logs (50 answer keys)

- **Status:** done (Amirali: Sonnet 5.5 both arms, smoke first)
- **Owner:** Amirali · **Branch:** `feat/017-ship` (eval only, no product change) · **Date:** 2026-10-18
- **PLAN.md block / slice:** final eval for the judges

## 1. Goal
Show judges the difference that matters in practice: a user with Claude Code **with** our MCP server vs the same Claude
Code **without** anything (just the raw log files and its built-in Bash / Read / Grep). Same 50 questions, same frozen
answer keys, same blind Opus SQL judge and criteria as plan 013/017 (unchanged). Moves: search + analytics correctness,
recommendation grounding, execution / performance.

## 2. Done when
50 questions × 2 arms run and judged; report `eval/results/cc-<time>.md/.json/.runs.json` with: order-consistent wins
(all / role / dataset), claim accuracy, wrong claims, found_problem, rubric, E1, failed runs, and per arm wall s,
turns, tool calls, tokens, $ cost. 0 judge leaks; 0 bare-arm runs that touched the DB or the repo (else flagged invalid).
Summary in `docs/EVAL.md` + `docs/STATUS.md` + slide/dashboard numbers.

## 3. Approach
- New `eval/cc_ab.py` (one file). Imports unchanged from `eval/ab.py`: `blind`, `leaks`, `judge_pair` (judge prompt,
  `Verdict`, SQL tool, both orders, seed 13), `tally`, `KEYS`; `golden_hits` for E1. Nothing in `judge.py` / keys changes.
- Both arms = `claude -p <question> --bare --output-format stream-json --verbose --model sonnet --no-session-persistence
  --max-turns 60 --strict-mcp-config`, run in an empty temp dir outside the repo; same model (Sonnet 5.5, as plan 017), no prompt beyond the question.
  - **mcp:** `--tools ""` + `--mcp-config` our server pinned to the question's dataset (`LOGS_DATASET`, how a user runs
    it), `--allowedTools mcp__logs__*`.
  - **bare:** no MCP; `--tools Bash,Read,Grep,Glob` allowed; the temp dir holds `logs/` = **hard links** to that
    dataset's raw files only (no labels: `anomaly_labels.txt`, `anomaly_label.csv`, READMEs excluded; **BGL's inline
    label column cut** — the smoke run showed the bare arm reading `KERNPAN`/`APPSEV` off each line; OpenStack files
    renamed `nova-1..3.log`, Loghub's names say which one is abnormal). Question gets one
    neutral line appended: "The log files are in ./logs/." (it has no other way to know where they are).
  - otel: slice not loaded right now → load it once (`40_otel_demo.sql` + `build_dataset.sql`, other datasets
    untouched) and export the same rows to `otel.jsonl` for the bare arm.
- Arms per question run one after the other in random order (seeded); `--concurrency 3` questions.
- Blinding: strip the session_report link / "See every step…" line, then `blind()`; the leak scan stops judging as before.
- Integrity scan of bare transcripts: any Bash command touching `psql`, `7890`, the repo path, `answer_keys` → run flagged.
- Metrics from the stream-json `result` event (duration_ms, num_turns, total_cost_usd, usage) + tool calls by name.

## 4. How we check it
Smoke on 3 ids (bgl engineer, hdfs lead, manager) both arms, read transcripts by hand, then the full 50.
Held-out untouched.

## 5. Out of scope / risks
- Cost: Opus Claude Code ~100 runs + 200 judge calls; rough guess $150–300 (bare arm on BGL/HDFS greps can run long).
- Judge can partly tell arms apart by style (bare cites file lines, ours cites patterns); same caveat as plan 017.
- Bare arm hitting the 20 min timeout = failure, scored 0 (as in ab.py), reported separately.

## 6. Steps
- [x] otel slice load + export; hard-link dirs per dataset
- [x] `eval/cc_ab.py`; smoke 3 ids
- [x] full 50; report; docs / STATUS / slides numbers

## 7. Results (filled after)
Run `eval/results/cc-20261018-205503.md` (50 questions, Sonnet 5.5 both arms, judge = eval/ab.py unchanged, 0 leaks,
0 integrity flags: the bare arm never touched the DB or the repo).

| | Claude Code + our MCP | plain Claude Code (raw files, Bash/grep) |
|---|---|---|
| blind judge wins (order-consistent) | **30** | 15 (tie 1, inconsistent 4) |
| wins, base corpus (BGL + OpenStack) | **18** | 4 |
| wins by role: engineer / lead / manager | 8 / **13** / **9** | **9** / 2 / 4 |
| claim accuracy (judge + SQL) | **0.87** | 0.80 |
| wrong claims (50 answers) | **116** | 186 |
| found the real problem (0-2) | **1.51** | 1.22 |
| rubric (1-5) | **3.50** | 3.23 |
| E1 golden facts in the answer | **0.64** | 0.46 |
| seconds per answer, median / mean / max | **14.6 / 14.3 / 27** | 33.4 / 86.0 / 1500 (timeout) |
| seconds, large datasets (BGL 4.7M, HDFS 11M lines; 21 q) median / mean | **13.8 / 14.0** | 77.7 / 168.1 |
| failed runs | 0 | 1 (D-X17, HDFS, 25 min timeout) |
| tool errors | 2 | 14 |
| $ per answer (Claude Code's own count) | 0.049 | 0.038 |

Reading: our MCP wins where the logs are big or the question needs aggregation (BGL 15-1, leads 13-2, managers 9-4),
in a flat ~14 s whatever the size; plain Claude Code needs minutes on BGL / HDFS (one 25-min timeout) and gets more
wrong (counts lines as attempts / incidents, misses owners and fleet-wide context). Plain wins engineer questions on
the small extra datasets (9-8 engineer overall; ssh 3-1, linux 2-1, healthapp 2-1): grep over a few MB reads every
line, and the judge credited details our summaries dropped (e.g. D-X14 the two new Apache errors, D-X18 the first
quorum rejoin, D-E03 non-instance-tagged lines). Those are follow-ups for the tools, not judge errors. Cost per answer
is slightly higher with MCP (bigger tool results, $0.049 vs $0.038). The smoke run (3 q) predates the BGL label fix
and is not reported.
