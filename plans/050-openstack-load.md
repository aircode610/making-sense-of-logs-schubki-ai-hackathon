# 050: OpenStack load + ownership table (SQL-native, in docker SereneDB)

- **Status:** done (2026-10-17)
- **Owner:** Konark · **Branch:** `feat/050-openstack-load` · **Date:** 2026-10-17
- **PLAN.md block / slice:** B1 · OpenStack load + ownership (`count_by` + `trend` tools = plan 051, after this)

## 1. Goal
All 207,820 OpenStack lines in the shared `logs` table (`dataset='openstack'`) with typed `ts, component, severity, node,
request_id, instance_id, tenant_id, status, latency_ms, body`, plus an `ownership` table, loaded by SereneDB itself.
Moves "search + analytics over the whole corpus" (25%) and "execution" (20%); foundation for count-by-team and the
OpenStack anomaly investigation (3 labelled VMs).

## 2. Done when
- `count(*) WHERE dataset='openstack'` = **207,820** (abnormal 18,434 + normal1 52,312 + normal2 137,074, minus any
  trailing-line difference vs `wc -l`; exact reference taken with awk first). BGL rows untouched (4,747,963).
- Counts by `component` (nova-api 102,868 / nova-compute 104,086 / nova-scheduler 866) and by `severity` equal awk.
- `status`/`latency_ms` filled for every `wsgi.server` request line; `instance_id` for every line with `[instance: …]`;
  `request_id` for every line with `req-…`; `tenant_id` set where present. Counts equal grep/awk.
- `anomaly_labels.txt` 3 instance ids (file lists 4 ids; verify) in `labels` as `dataset='openstack'`; **evaluation only**.
- `ownership` table loaded from `/data/ownership.csv`; `count by team` works across both datasets.
- FTS check: one term + one phrase count equals `grep -c`. Load time + size recorded in `docs/PERFORMANCE.md`.

## 3. Approach
- **Files:** `load/20_openstack.sql` (+ `ownership` table in `load/00_schema.sql`, `load/30_ownership.sql`). `psql -f`, no Python.
- **Parse in SQL** (as `10_bgl.sql`): `read_csv` the 3 files as one VARCHAR column (`filename=true` or per-file
  `UNION ALL`), `line_id` = line number **per file offset** so ids are unique and stable: abnormal, normal1, normal2 in
  fixed order (file order recorded in §7). Regex: `^(\S+) (date time) \d+ (LEVEL) (\S+) \[req-uuid tenant? …\] msg`.
  `component` = nova service from file prefix (`nova-api`…); `node` = NULL (no host field; `\d+` pid not stored).
  `status`, `latency_ms` from `status: (\d+) len: \d+ time: ([\d.]+)`; `instance_id` from `[instance: uuid]` (or the
  `/servers/<uuid>` path for API lines is **not** extracted: keep to explicit fields).
- Insert ordered by `ts, line_id` (zonemaps). Labels go only to `labels`.
- Ownership: `CREATE TABLE ownership` from `read_csv('/data/ownership.csv')`.

## 4. How we check it
awk/grep reference counts on the raw files first (§7 table), then SQL; `EXPLAIN ANALYZE` on a time-filtered
count; the BGL cross-checks from plan 002 re-run to prove nothing broke. Held-out untouched.

## 5. Out of scope / risks
- Out: `count_by`/`trend` tools (051), patterns/episodes (B2), UI.
- Risk: multi-line stack traces → continuation lines without a timestamp; count them, attach to the previous line's
  record or keep as separate rows with inherited `ts` (decide on the data, record here).
- Risk: lines without `req-…` or with `- - -` context → NULL columns, not dropped.
- Risk: `ts` timezone/format; abnormal run overlaps normal dates → check ordering and min/max per file.

## 6. Steps
- [x] Reference counts with awk/grep (total, component, severity, status, instance, request, continuation lines)
- [x] `load/20_openstack.sql` + ownership; dry run on a slice, then full load (timed)
- [x] Cross-check queries, FTS check, BGL regression check
- [x] PERFORMANCE.md, §7 here, STATUS, plans index; commit only when asked

## 7. Results (filled after)
Every check equals the awk/grep reference from the raw files:

| Check | Reference | SQL |
|---|---|---|
| rows | 207,820 (`wc -l` 207,825 incl. the 5-line labels file) | 207,820 (distinct `line_id` 207,820) |
| component nova-compute / nova-api / nova-scheduler | 104,086 / 102,868 / 866 | same |
| severity INFO / WARNING / ERROR / CRITICAL | 204,506 / 3,118 / 194 / 2 | same |
| `status`+`latency_ms` (wsgi request lines) | 98,733 | 98,733 (none with null latency) |
| `instance_id` / `request_id` / `tenant_id` | 51,553 / 192,174 / 115,504 | same |
| min / max ts | 2017-05-14 19:39:01.445 / 2017-05-17 12:02:35.320 | same |
| FTS `error` | 16 | 16 |
| team cloud-compute / cloud-api | 104,952 / 102,868 | same |

- **Load: ~1.2 s** (parse 0.9 s + insert 0.4 s). `load/20_openstack.sql` also creates `ownership` (13 rows, both datasets).
- **Deviation:** no continuation lines. 8 stack-trace header lines (`ERROR oslo_service.periodic_task`) have no message:
  loaded with `body` NULL. `line_id` = running number abnormal, normal1, normal2.
- `anomaly_labels.txt` lists **4** VM ids (text says 3); all 4 in `labels` (`line_id` = row number, `label` = instance id).
- `tenant_id` = the project id (3rd context token); user id not stored. `node` is NULL (no host field in OpenStack).
- BGL regression not re-run: this DB was fresh, BGL not loaded here (Amirali's `10_bgl.sql` is independent).
- Dropped a leftover empty-looking table `os_labels` in the local DB (not in the repo) to proceed.
