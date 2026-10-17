# 002: BGL load (SQL-native, in docker SereneDB)

- **Status:** approved (Amirali, 2026-10-17)
- **Owner:** Amirali · **Branch:** `feat/002-bgl-load` · **Date:** 2026-10-17
- **PLAN.md block / slice:** B1 · BGL load (tools `search_logs` + `get_context` = plan 003)

## 1. Goal
All 4,747,963 BGL lines in SereneDB as typed, time-sorted, full-text-indexed rows, loaded by SereneDB itself, with
exact counts that match awk. Moves rubric "search + analytics over the whole corpus" (25%) and "execution" (20%:
load time, clean checkout); foundation for every role.

## 2. Done when (decided before starting)
- `SELECT count(*) FROM logs WHERE dataset='bgl'` = **4,747,963**; `labels` has **348,460** BGL alert rows
  (334,863 + 13,597, plan 001); rows with `ts >= '2005-12-05'` = **129,874**.
- Counts by `severity` and by `component` equal the awk counts (table in §7); min/max `ts` = 2005-06-03 / 2006-01-04.
- Full-text: `body @@ 'parity'` (and one phrase query) count equals `grep -c` on the raw file for the same term.
- Malformed lines (~320 with a shifted layout) are loaded, not dropped, and counted (`component = 'UNKNOWN'` or similar).
- One `count by team` works (join with `/data/ownership.csv` via `read_csv`; the `ownership` table itself is Konark's).
- Load time + table/index size recorded in `docs/PERFORMANCE.md`; one command reloads from scratch.

## 3. Approach
- **Files:** `load/00_schema.sql` (shared contract with Konark: `logs`, `labels`), `load/10_bgl.sql`. Run with
  `psql -f`. No Python.
- **Shared `logs` schema** (ARCHITECTURE.md, minus `pattern_id` which comes in B2): `dataset, line_id BIGINT,
  ts TIMESTAMP, component, severity, node, rack, midplane, request_id, instance_id, status, latency_ms, body`.
  BGL fills `node` (location field), `rack` (`R02`), `midplane` (`R02-M1`); OpenStack columns stay NULL.
  `line_id` = line number in the raw file (stable id for `get_context` and evidence).
- **Parse in SQL:** `read_csv('/data/raw/BGL.log', columns={'line':'VARCHAR'}, header=false, delim=<char not in file>,
  quote='', auto_detect=false)` + `row_number()` → split fields; `ts` from field 5 (`%Y-%m-%d-%H.%M.%S.%f`);
  body = text after field 9. Label (field 1, `-` → no row) goes **only** to `labels(dataset, line_id, label)`, never
  into `logs` (no agent tool reads `labels`).
- **Storage + index** (as `otel_logs`, verified in docs): `CREATE TABLE … WITH (storage='search',
  optimize_top_k='bm25(1.2, 0.75)')`, insert **ordered by ts** (zonemap pruning), one inverted index:
  `ts, body <dict with frequency+position+norm>, dataset, component, severity, node, rack, midplane` (filters and
  text in one index pass). Dictionary: `split_text(case:='lower', break:='alpha')` like the OTel one; check that
  hex/ids such as `0x00544eb8` and `R02-M1` stay searchable, else adjust once.
- **Measure, not assume:** time `count(*) GROUP BY component` and a time-filtered count on the search table. If
  aggregations are slow (> 1 s), try a plain columnar table + the same inverted index and keep the faster (§7).

## 4. How we check it
awk/grep counts on `data/raw/BGL.log` vs SQL (§2 list) = E1 seeds. `EXPLAIN ANALYZE` on the timed queries.
Held-out untouched (the slice is just a `ts` filter; no tuning here).

## 5. Out of scope / risks
- Out: OpenStack load + `ownership` table (Konark), patterns/episodes (B2), MCP tools (plan 003), rollups.
- Risk: emulated amd64 image → slow load. Mitigation: one pass, no per-row functions beyond string split; measure.
- Risk: `read_csv` mangling lines (quotes, odd bytes). Mitigation: `quote=''`, explicit column, count check.
- Risk: Konark's OpenStack columns need more fields: schema is a contract, adding a nullable column is cheap. Pull first.

## 6. Steps
- [ ] Branch `feat/002-bgl-load`; commit pending docs (`HELDOUT_BRIEF.md`, STATUS) there
- [ ] awk reference counts (total, labels, severity, component, slice, `parity`, malformed) → §7
- [ ] `00_schema.sql` + `10_bgl.sql`; dry run on first 100k lines, then full load (timed)
- [ ] Cross-check queries; FTS check; storage A/B if needed
- [ ] Record PERFORMANCE.md, fill §7, STATUS, plans index; tell Konark the schema

## 7. Results (filled after)
