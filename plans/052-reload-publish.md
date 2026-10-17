# 052: One-command reload (DROP + load + publish index + check)

- **Status:** done (2026-10-17) · requested directly by Konark
- **Owner:** Konark · **Branch:** `feat/051-count-trend-tools` (small follow-up) · **Date:** 2026-10-17

## 1. Goal
Reloads that always give exact counts; one command for a clean checkout (README, rubric "execution").

## 2. Done when
`./load/reload.sh` from any state → all `bench/check_counts.py` checks pass, twice in a row.

## 3. Approach
`00_schema.sql` drops + recreates `logs`/`labels`; loaders lose their `DELETE` lines; new `90_publish.sql`
(`VACUUM (REFRESH_TABLE)` + `COMPACT_TABLE`), because the inverted index is eventually consistent (docs `maintenance.md`).

## 7. Results
2 runs × 29/29 checks, ~21 s each (compaction 6 s). Wrong counts seen in plan 051 were unpublished index state, not DELETE.
