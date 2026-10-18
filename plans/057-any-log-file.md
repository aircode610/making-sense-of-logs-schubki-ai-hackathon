# 057: Any log file in (lower-risk version): inferred ownership, severity column, lnav format detection

- **Status:** parts 1–2 done (ownership, severity), part 3 to do · approved (Konark, 2026-10-18: lower-risk version)
- **Owner:** Konark · **Branch:** `feat/057-any-log-file` · **Date:** 2026-10-18
- **PLAN.md block / slice:** generality ("unseen logs"), on top of Amirali's plans 011–012

## 1. Goal
A new dataset still needs two hand-written things: a parse query (line format) and ownership rows. This plan
(1) infers ownership for any component on top of Amirali's curated table, each owner with source + confidence,
(2) adds one common severity number next to the raw level, (3) detects the line format from **all lnav format
definitions**, so a file in a known format loads with one command. Ideas with the most risk were cut (below).

## 2. Done when (decided before starting)
- **Ownership:** every (dataset, component) in `logs` has `team, area, source, confidence`; Amirali's curated rows
  and `*` defaults unchanged (existing checks pass); a **disputed** flag where curated owner and Jev `owner_hint`
  disagree (hint confidence ≥ 0.8); tools that show a team also show source + confidence; new tools `owner_of`,
  `ownership_gaps` equal independent SQL on every dataset.
- **Severity:** `logs.severity_number` (OTel 1–24) from `data/severity_map.csv`, NULL when the source has no level;
  problem rule, pattern checks and problem counts **unchanged**.
- **Formats:** `scripts/ingest.sh <file> <name>` tests every lnav format in SereneDB on a 2,000-line sample, uses the best
  one with ≥ 95 % coverage (else whole line = body, stated), writes `load/gen/<name>.sql`, loads it through
  `stage_to_logs.sql`, prints coverage and `count(*)` = `wc -l`; tools `ingest_report`, `unparsed_lines`.
- 2 unseen Loghub files (Proxifier, Android) load with no code or ownership rows written by us; `check_tools` passes
  on them; one agent run passes the checker. `./load/reload.sh` + all `bench/check_*.py` pass. **No eval runs.**

## 3. Approach
**1. Ownership** (`load/94_ownership.sql`, first hit wins; area → team via `data/area_teams.csv`, fictional):

| # | rule | source | confidence |
|---|---|---|---|
| 1 | curated exact row (Amirali, `data/ownership.csv`) | curated | 1.0 |
| 2 | dataset `*` default (Amirali) | curated default | 0.95 |
| 3 | Jev `owner_hint`, dataset has ≥ 2 curated teams (Amirali, `pattern_traits_*.csv`) | jev owner_hint | Jev p ≥ 0.6 |
| 4 | name rule after normalising (`[pid]`, `-\d+`, `.service`): OpenStack service types, Kubernetes components, ~50 common programs | `data/ownership_rules.csv` | 0.9 |
| 5 | syslog facility, when the format has one | RFC 5424 | 0.7 |
| 6 | Jev picks an area (component + 3 sample lines), once per component | `data/component_areas.csv` | Jev p ≥ 0.6 |
| 7 | none | unowned | — |

Disputed = curated (1–2) vs Jev `owner_hint` with p ≥ 0.8 naming another team.
**2. Severity:** `data/severity_map.csv` (lnav level words + RFC 5424 + OTel data model) → `severity_number`; added in
`stage_to_logs.sql` and the old loaders; nothing reads it for the problem rule.
**3. Formats:** vendored lnav `formats/*.json` (BSD-2, licence kept); `scripts/ingest.py` converts each regex to RE2
(named groups; formats that don't compile are listed), scores coverage on a sample table in SereneDB, maps lnav's own
field roles (timestamp, level, body, host, module/opid…) to the stage columns; unknown fields → body / entities.

**Cut to lower risk:** Fluent Bit / grok patterns, LLM-written parse query, Jev field mapping, changing the problem
rule to severity ≥ WARN, Jev-inferred severity, `severity_profile` tool.
**Sources:** lnav formats (github.com/tstack/lnav, BSD-2); OTel logs data model (SeverityNumber); RFC 5424 (levels,
facilities); OpenStack service-types authority (Apache-2.0); Kubernetes components docs; Loghub (test files, cite);
Amirali's `ownership.csv` + `pattern_traits_*.csv`; SereneDB regex functions + `ai_system_one` (Jev).

## 4. How we check it
Independent SQL for every tool number; curated owners unchanged; before / after problem counts identical; coverage +
`wc -l` per new file; existing checks on all datasets. Held-out untouched.

## 5. Out of scope / risks
Out: everything cut above, template GA/PA, eval runs. Risks left: some lnav regexes don't compile in RE2 (listed);
wrong format pick (visible in `ingest_report`, tie → more specific format); wrong inferred owner (source +
confidence, < 0.6 → unowned, curated wins); time (parts ship separately: 1 → 2 → 3); licences (kept + credited).
Touches Amirali's `94_ownership.sql` and team display in tools (tell him).

## 6. Steps
- [x] Part 1 ownership: rules + areas + chain + disputed + display; `owner_of`, `ownership_gaps`; checks
- [x] Part 2 severity column; checks unchanged
- [ ] Part 3 lnav detection + `ingest.sh` + `ingest_report`, `unparsed_lines`; 2 unseen files; one agent run
- [ ] §7, README, STATUS, DECISIONS, plans index; tell Amirali

## 7. Results (filled after)
**Part 1 (ownership), done 2026-10-18.** `load/96b_ownership_inferred.sql` rebuilds `ownership` after the Jev step:
curated rows (Amirali) first, then Jev owner_hint, name rules (`data/ownership_rules.csv`: 94 rows from OpenStack
service-types, Kubernetes components, common programs) → area → team (`data/area_teams.csv`), then Jev area
(`scripts/judge_areas.py` → `data/component_areas_<ds>.csv`, 167 components in ~5 s, 141 at p ≥ 0.6). New columns:
area, area_source, area_confidence, source, confidence, disputed_by, dispute_confidence. Tools `owner_of`,
`ownership_gaps`; `top_patterns` / `priority_table` rows carry owner_source / owner_confidence / owner_disputed_by;
composer rule: inferred owners are worded as inferred, disputes reported; lead + manager tool subsets extended.
- Curated owners unchanged on all 7 datasets (`check_tools`: 38 tools × 7 datasets pass, 362 checks; lint passes,
  34,723 / 36,000 definition tokens).
- **Disputes found:** BGL `APP` (curated hpc-workloads; confident Jev hints name node-platform, p 0.94, 228,536 lines;
  it is BGL's #1 recurring problem, the ciod I/O errors) and one ZooKeeper class (2 lines).
- **What-if without curated rows:** 141 of 161 components still get an owner (38 by rule, 103 by Jev area), 20 stay
  unowned; e.g. sshd → security-platform, mysqld → data-platform, named → network-ops, netfs → storage (Jev 0.93).
- **Benchmark vs the previous version** (`bench/tool_use.py`, Sonnet 5.5; previous = worktree of `57fea10` on the same
  database): Amirali's 29 questions on the 7 loaded datasets: facts 50/51 both, unseen Linux + HealthApp 10/10 both,
  first tool 1.00 → 0.97 (one valid alternative first tool), +7 % input tokens, latency per tool unchanged (± noise).
  **New ownership questions** (`bench/tool_use_ownership.yaml`, 4 q × 2 runs each): facts **0.43 / 0.57 → 1.00 / 1.00**,
  tool calls 10.4 → 2.0 per question, input tokens ~308k → 107k, 30 s → 9 s. The previous server could not find
  disputes or areas (it searched with count_by / top_patterns for 15–21 calls). O-1's expected fact was wrong at first
  (the whole-log top problem is 'rts panic', curated node-platform, not APP) and was fixed + re-scored before comparing.
- **Schema change documented** (all tools read `ownership`): README (pipeline, new log source, ownership table,
  tools), `docs/ARCHITECTURE.md`, `data/README.md`, `load/94_ownership.sql` header, DECISIONS H27.
**Part 2 (severity column), done 2026-10-18.** `logs.severity_number` (SMALLINT, in `logs_idx` and in focus-index
copies) = OpenTelemetry SeverityNumber from `data/severity_map.csv` (28 words: OTel, RFC 5424, Java util.logging, lnav
one-letter levels; BGL SEVERE 18, FAILURE 21; Apache NOTICE 10; OpenStack CRITICAL 22); filled by the three insert paths
(`10_bgl`, `20_openstack`, `lib/stage_to_logs.sql`); NULL for SSH / Linux / HealthApp (no level). Every logged word maps
(new check in `check_counts.py` flags unmapped words); problem rule unchanged (raw words, H22), so problem counts,
owners and all checks are identical. `search_logs` / `get_context` rows carry the number.
- **Benchmarks vs part 1** (same machine, same 7 datasets): full load (`reload.sh --skip-checks`, 3 runs each)
  30.8 s → 32.6 s (+6 %, inside part 1's spread 28.6–33.1 s); tool latency, sum of medians 618 → 623 ms (+0.8 %);
  `bench/tool_use.py` 29 q Sonnet: facts 50 → 49 /51 (the miss is wording: a correct answer wrote "two" instead of
  "2"), unseen 10/10 both, 1 tool error (model passed line_id 0, recovered), calls 3.6 → 3.9, input tokens 125k → 134k
  (run-to-run noise level). Verdict: same answers and speed; groundwork for part 3 (auto-detected formats' level words).
- First speed run looked like +70 %: the part-1 worktree had no raw files, so it loaded 2 datasets instead of 7;
  re-measured with the same data.
- Schema change documented: README (generic schema, new log source), `docs/ARCHITECTURE.md`, `data/README.md`,
  `load/00_schema.sql` comments, DECISIONS H28.
- Not built: syslog-facility step (no loaded format carries a facility; add when a loader parses `<PRI>`).
