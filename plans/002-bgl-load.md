# 002: BGL load (SQL-native, in docker SereneDB)

- **Status:** done (2026-10-17)
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
- [x] Branch `feat/002-bgl-load`; commit pending docs (`HELDOUT_BRIEF.md`, STATUS) there
- [x] awk reference counts (total, labels, severity, component, slice, `parity`, malformed) → §7
- [x] `00_schema.sql` + `10_bgl.sql`; dry run on first 100k lines, then full load (timed)
- [x] Cross-check queries; FTS check; storage A/B if needed
- [x] Record PERFORMANCE.md, fill §7, STATUS, plans index; tell Konark the schema

## 7. Results (filled after)
Done 2026-10-17. Every check equals the reference count from the raw file (awk / Python regex):

| Check | Reference | SQL |
|---|---|---|
| BGL rows | 4,747,963 | 4,747,963 |
| alert labels (`labels`) | 348,460 | 348,460 |
| held-out slice `ts >= 2005-12-05` | 129,874 | 129,874 |
| min / max ts | 2005-06-03 / 2006-01-04 | 2005-06-03 15:42:50 / 2006-01-04 08:00:05 |
| severity INFO / FATAL / ERROR / WARNING / SEVERE / FAILURE | 3,735,823 / 855,501 / 112,355 / 23,357 / 19,213 / 1,714 | same |
| component KERNEL / APP / DISCOVERY / MMCS / HARDWARE / MONITOR / LINKCARD / CMCS / BGLMASTER / SERV_NET | 4,324,967 / 228,536 / 97,172 / 88,930 / 5,148 / 1,681 / 1,170 / 211 / 145 / 3 | same |
| slice by severity | 90,615 / 38,420 / 188 / 459 / 188 / 4 | same |
| distinct nodes / racks / midplanes | 69,241 / 64 / 128 | same |
| lines without a node (`NULL`, `UNKNOWN_LOCATION`, `-`) | 116,677 | 116,677 (4,747,963 − 4,631,286) |
| empty message | 34,470 | 34,470 |
| FTS `parity` / phrase `cache parity error` | 121,498 / 106,220 | same |
| team node-platform / hpc-workloads / cluster-control | 4,331,285 / 228,536 / 188,142 | same |

- **Load: 18.0 s** end to end (details + EXPLAIN in `PERFORMANCE.md`); 224 MB on disk. Search table kept: group-bys
  3–85 ms, so no plain-table A/B.
- **Deviation (better than planned):** no malformed lines. Field 6 (repeated location) sometimes holds junk with spaces,
  which shifts positional fields; anchoring the regex on the timestamp and `(RAS|NULL) COMPONENT SEVERITY` parses all
  4,747,963 lines. Positional awk counts in `CHALLENGE.md` (e.g. FATAL 855,195) were off by those ~320 lines; the
  regex counts above are the correct ones.
- **Fix:** `data/ownership.csv` had unquoted commas in two descriptions (invalid CSV); quoted them.
- Schema has OpenStack columns ready (`request_id, instance_id, tenant_id, status, latency_ms`, all indexed): Konark's
  loader inserts into the same `logs` table with `dataset = 'openstack'`.
- Dictionary breaks on non-letters, so hex ids (`0x00544eb8`) are not single tokens in `body`; node ids are exact-match
  columns. Revisit in plan 003 if search needs ids inside text.
- Next: plan 003, `search_logs` + `get_context` (MCP).
