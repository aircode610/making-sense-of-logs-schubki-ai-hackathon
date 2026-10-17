# 004: BGL patterns + episodes (in SQL, at load)

- **Status:** done (2026-10-17)
- **Owner:** Amirali · **Branch:** `feat/004-bgl-patterns-episodes` · **Date:** 2026-10-17
- **PLAN.md block / slice:** B2 · patterns + episodes for BGL (OpenStack masks = Konark, same mechanism)

## 1. Goal
Every BGL line gets a `pattern_id` (log template, variable parts masked), plus a `patterns` table and an `episodes`
table, so team-lead/manager answers count **recurring problems and episodes, not lines** (non-negotiable 4,
`ROLES.md` definitions). Moves role insight (30%) and search + analytics (25%).

## 2. Done when (decided before starting)
- 0 BGL rows without `pattern_id`; `sum(patterns.lines)` = 4,747,963; template count reported (probe: ~1,100,
  ≤ ~100 singletons). Spot check: the "kernel panic" pattern = 18 lines on 18 nodes (plan 003 live check).
- `episodes`: lines sum to 4,747,963; episode counts reported for gap 10 / 30 / 60 min; one gap **frozen** in
  `DECISIONS.md` with the reason (STATUS open decision).
- Patterns are coherent: on the tune part (`ts < 2005-12-05`) the share of alert lines whose pattern is ≥ 95 % one alert
  category is reported (labels used here as a check only, never as input).
- Full reload (schema + BGL + OpenStack) still < 1 min; `search_logs` / `get_context` checks from plan 003 still pass;
  `search_logs` gains a `pattern_id` filter and returns `pattern_id` per row.

## 3. Approach
- **Template = SQL masking** (probe, 1.6 s for 4.7M lines): in order, mask MAC-like `FF:F2:9F:…` → `<MAC>`, BGL
  locations inside text → `<LOC>`, `Thu Aug 4 …PDT 2005` → `<DATE>`, hex ≥ 6 → `<HEX>`, numbers → `<N>`, merge runs of
  masks, collapse spaces. Pattern key = (dataset, component, template). No Drain3 (Python) needed at this granularity.
- **Schema change** (`00_schema.sql`): `logs.pattern_id INTEGER` (+ in the inverted index). SereneDB can't `ALTER TABLE
  ADD COLUMN` on a search table (verified) → `DROP` + recreate, so every loader re-runs once; Konark's loader names its
  columns, so it keeps working (OpenStack `pattern_id` stays NULL until his masks). I tell Konark.
- **`10_bgl.sql`**: compute the template in the staging table; `pattern_id` = rank by (first ts, component, template),
  deterministic across reloads; insert `pattern_id` with each row.
- **New `load/30_patterns_episodes.sql`** (re-runnable, per dataset rows replaced), from `logs`:
  - `patterns(dataset, pattern_id, component, template, severity` (most frequent)`, lines, problem_lines` (severity in
    FATAL/FAILURE/SEVERE/ERROR)`, nodes, first_ts, last_ts, weeks_active, bursts, episodes, example_line_id)`.
  - `episodes(dataset, pattern_id, node, episode_no, start_ts, end_ts, lines)`: `LAG(ts)` per (pattern, node) — node
    NULL → component — new episode when gap > G. `bursts` = same split per pattern across all nodes (one storm on
    1,000 nodes = 1 burst, 1,000 node-episodes; both kept, the tools will say which they show).
- Plain (non-search) tables for `patterns` / `episodes`: small, aggregated, no full-text needed.

## 4. How we check it
SQL checks for every §2 number; plan 003 check script re-run; timings in `PERFORMANCE.md`. Held-out: gap/masks are
looked at on the whole corpus but nothing is fitted to labels; the label-purity check uses only `ts < 2005-12-05`.

## 5. Out of scope / risks
- Out: OpenStack masks (Konark), `top_patterns` / `priority_table` tools (B3), Jev pattern judgments, rollup tables.
- Risk: masks too coarse (merge different faults) or too fine. Mitigation: label-purity check + eyeball top 50; one
  tuning round, then freeze.
- Risk: window functions over 4.7M rows slow under emulation. Mitigation: measure; partition by (pattern, node) is sorted.
- Shared schema change while Konark builds plan 051: his tools don't depend on `pattern_id`; he re-runs the 3 loaders.

## 6. Steps
- [x] Branch; schema + `10_bgl.sql` masks + `pattern_id`; reload all; checks
- [x] `30_patterns_episodes.sql`; gap sensitivity; freeze gap (DECISIONS)
- [x] Label-purity check (tune part); eyeball top 50 patterns; one mask tuning round if needed
- [x] `search_logs` pattern_id filter + field; re-run plan 003 checks
- [x] PERFORMANCE, README load step, §7, STATUS, plans index; tell Konark; push branch

## 7. Results (filled after)
Done 2026-10-17.

| Check | Result |
|---|---|
| BGL rows with `pattern_id` | 4,747,963 / 4,747,963 · **1,126 patterns**, 63 singletons |
| Σ lines in `patterns` / `episodes` / `bursts` | 4,747,963 each |
| "kernel panic" | pattern 576: 18 lines, 18 nodes, **13 bursts**, 8 weeks active |
| Label purity (tune part, `ts < 2005-12-05`) | **100 %** of 334,863 alert lines in patterns that are ≥ 95 % one category; 4 of 1,058 patterns mix alert/normal (9 minority lines) |
| Problem severity vs alerts | 727 patterns have problem-severity lines, only 76 carry alerts → severity alone is a weak problem signal (Jev in B3) |
| Reload schema + BGL + OpenStack + 30_patterns | ≈ 31 s (BGL parse 23.2 s incl. masking, +7 s) |
| Plan 003 tool checks | all pass; `search_logs(pattern_id=576)` = 18 lines / 18 nodes; p95 12–36 ms |

Gap sweep (BGL):

| gap | node-episodes | problem node-ep. | bursts | problem bursts |
|---|---|---|---|---|
| 5 min | 2,985,873 | 622,736 | 51,630 | 16,319 |
| 10 min | 2,879,079 | 612,377 | 46,570 | 15,831 |
| **30 min** | **2,417,597** | **554,386** | **36,714** | **14,737** |
| 60 min | 2,183,302 | 523,493 | 30,646 | 13,471 |
| 240 min | 1,837,634 | 511,544 | 20,197 | 11,099 |

- **Decision H16:** gap 30 min (smooth curve, no elbow → keep the ROLES draft). **Bursts are the headline unit** for
  lead/manager (node-episodes ≈ lines/2 for fleet-wide patterns, no correction); at 30 min only 1 burst lasts > 1 day
  (36 h of parity errors), none > 7 days, median burst = 1 line. ROLES.md definitions updated.
- No mask-tuning round needed (purity 100 %). Known limitation: a log-format change (~Nov) adds "… over N seconds", so
  some faults appear as two patterns; `dcr` register variants are separate patterns (arguably correct).
- Added beyond plan: small `pattern_templates` table (loader writes the template text; `patterns` joins it), and a
  `bursts` table next to `episodes` (plan only had a burst count).
- Schema change: `00_schema.sql` now **resets** (DROP + CREATE; SereneDB can't ALTER a search table). Konark: re-run
  00 → 10 → 20 → 30. OpenStack `pattern_id` stays NULL until OpenStack masks (Konark, B2); `30_…sql` already handles
  every dataset that has pattern ids.
- Next (B3, Amirali): `top_patterns` + `priority_table` tools for lead/manager on `patterns` / `bursts`.
