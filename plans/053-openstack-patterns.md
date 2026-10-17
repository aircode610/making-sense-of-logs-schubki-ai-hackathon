# 053: OpenStack patterns (SQL masks → pattern_id)

- **Status:** done (2026-10-17)
- **Owner:** Konark · **Branch:** `feat/053-openstack-patterns` · **Date:** 2026-10-17
- **PLAN.md block / slice:** B2 · patterns for OpenStack (same mechanism as plan 004)

## 1. Goal
Every OpenStack row gets a `pattern_id`, so `patterns` / `bursts` / `episodes` (built by `95_patterns_episodes.sql`)
cover both datasets and lead/manager answers count recurring problems, not lines (non-negotiable 4). Moves role
insight (30 %) and search + analytics (25 %) on the second dataset.

## 2. Done when (decided before starting)
- 0 OpenStack rows without `pattern_id`; `sum(patterns.lines)` for openstack = 207,820; pattern count reported
  (probe: 104, 3 singletons). Same Σ check for `bursts` / `episodes`.
- HTTP status stays in the template (a 500 is a different pattern from a 200); ERROR/CRITICAL lines land in
  patterns whose `problem_lines` > 0 (check: Σ problem_lines = 196 ERROR + CRITICAL lines).
- Coherence (check only, labels never an input): share of lines on labelled anomalous instances per pattern;
  patterns that appear **only** on labelled instances listed.
- `./load/reload.sh` passes (29 + plan-004 checks + new openstack pattern checks); reload still < 1 min.

## 3. Approach
- `load/20_openstack.sql`: template in `os_stage`, masks in order: UUID → `<UUID>`, IP lists → `<IP>`,
  `status: NNN` kept, hex ≥ 6 → `<HEX>`, numbers → `<N>`, merge mask runs, collapse spaces (probe: 0.26 s).
  `pattern_id` = rank by (first ts, component, template) **offset by 100,000** so ids never collide with BGL
  (ids are unique per dataset anyway; offset just keeps them unambiguous in tool output).
  Insert `pattern_id` with each row; write `pattern_templates` rows. `95_…sql` needs no change.
- `bench/check_counts.py`: openstack pattern checks (no NULL, count, Σ lines in 3 tables).
- Episodes: OpenStack has no `node`, so node-episodes fall back to component (= ≈ bursts). Per-instance episodes
  are out of scope (noted as a follow-up).

## 4. How we check it
SQL checks for every §2 number in `check_counts.py`; eyeball all ~104 templates once; timings in `PERFORMANCE.md`.
Held-out untouched (masks are generic, not fitted to labels).

## 5. Out of scope / risks
- Out: per-instance / per-host episodes, `top_patterns` / `priority_table` (Amirali, B3), Jev judgments.
- Risk: URL query strings (`changes-since=…`) fragment into a few patterns. Accept if < 10 extra patterns.

## 6. Steps
- [x] Branch; masks + `pattern_id` in `20_openstack.sql`; reload; checks in `check_counts.py`
- [x] Coherence check vs labels; eyeball templates; one tuning round max
- [x] §7, PERFORMANCE, STATUS, plans index; tell Amirali

## 7. Results (filled after)
Done 2026-10-17.

| Check | Result |
|---|---|
| OpenStack rows with `pattern_id` | 207,820 / 207,820 · **106 patterns** (ids 100001–100106), 3 singletons |
| Σ lines in `patterns` / `bursts` / `episodes` | 207,820 each |
| Σ `problem_lines` | 196 = 192 ERROR + 2 ERROR + 2 CRITICAL ✓ |
| HTTP status kept | 503 on `GET /servers/detail` = own pattern 100103 (2 lines, 2017-05-16/17) next to 67,361 × 200 |
| `./load/reload.sh` | 32/32 checks, twice in a row, 27.7 s each; OpenStack stage + masks 1.3 s |
| `search_logs(pattern_id=100103)` (no dataset) | 2 lines, only OpenStack: the offset keeps ids unambiguous |

- **Coherence vs labels (check only):** the 4 labelled anomalous VMs (100 lines) appear **only in ordinary lifecycle
  patterns**; no pattern is specific to them. The anomaly is in the **values**: "Took N seconds to spawn / build"
  median 36.5 / 37.5 s (max 50.7 / 51.6) on labelled VMs vs 19.7 / 20.5 s (max 26.7 / 27.6) on the other 2,062.
  → OpenStack needs a per-pattern **numeric outlier** signal (durations, latency_ms), not template rarity. Follow-up
  plan (engineer slice): extract the number from duration templates, flag values beyond the pattern's normal range.
- Mask tuning (1 round): hex mask may not follow a letter (`Traceback` had become `Tr<HEX>k`).
- Known limitation: one image-cache fault (`InvalidDiskInfo`, 8×) produces **25 ERROR patterns**, one per traceback
  line, each with the same 8 bursts. Lead/manager tools must group co-occurring patterns (same bursts) or count the
  head line (`Error during ComputeManager._run_image_cache_manager_pass`) so one fault is not counted 25 times.
- Episodes fall back to component (OpenStack has no `node`); per-instance episodes are still a follow-up.
