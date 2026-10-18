-- Derived tables + config tables (plan 016): created ONCE per database, empty; every dataset fills its own rows with
-- load/lib/build_dataset.sql (DELETE … WHERE dataset = :ds, then INSERT), so adding or replacing one dataset never
-- rebuilds the others. A full reload (load/reload.sh, or `python -m loader reload`) = 00_schema + this file + every
-- loader + build_dataset.sql per dataset. Before plan 016 the steps 93–97 rebuilt these tables for all datasets at once.
SET sdb_scan_split = 'never';  -- TsDict facet counts off by one with split segments (plan 011)

-- ---------------------------------------------------------------- config (committed CSVs in data/, mounted at /data)
-- Ownership (plan 011, generic): data/ownership.csv maps (dataset, component) → team; component '*' = the dataset's
-- default team. Inference chain on top: load/lib/build_dataset.sql (plan 057).
DROP TABLE IF EXISTS ownership_raw CASCADE;
CREATE TABLE ownership_raw AS SELECT * FROM read_csv('/data/config/ownership.csv', header = true, auto_detect = true);
DROP TABLE IF EXISTS ownership_rules CASCADE;
CREATE TABLE ownership_rules AS SELECT * FROM read_csv('/data/config/ownership_rules.csv', header = true, auto_detect = true);
DROP TABLE IF EXISTS area_teams CASCADE;
CREATE TABLE area_teams AS SELECT * FROM read_csv('/data/config/area_teams.csv', header = true, auto_detect = true);
-- Saved searches (plan 011, tool check_watchlist): config rows per dataset, data/watchlist.csv.
DROP TABLE IF EXISTS watchlist CASCADE;
CREATE TABLE watchlist AS SELECT * FROM read_csv('/data/config/watchlist.csv', header = true, auto_detect = true);
-- Remote Parquet sources (plan 011, tools remote_*): queried in place over HTTPS, never loaded.
DROP TABLE IF EXISTS remote_sources CASCADE;
CREATE TABLE remote_sources AS SELECT * FROM read_csv('/data/config/remote_sources.csv', header = true, auto_detect = true);

-- ---------------------------------------------------------------- derived, one row set per dataset
-- Example values per dataset and field (plan 012): one row per (dataset, field); 'entity:<kind>' per entity kind.
DROP TABLE IF EXISTS dataset_examples CASCADE;
CREATE TABLE dataset_examples (dataset VARCHAR, field VARCHAR, example VARCHAR, n_values BIGINT);
-- Ownership (plan 057 columns): curated rows + inference chain; one row per (dataset, component) that has an owner.
DROP TABLE IF EXISTS ownership CASCADE;
CREATE TABLE ownership (dataset VARCHAR, component VARCHAR, team VARCHAR, description VARCHAR, area VARCHAR,
    area_source VARCHAR, area_confidence DOUBLE, source VARCHAR, confidence DOUBLE, disputed_by VARCHAR,
    dispute_confidence DOUBLE);
-- Patterns / node episodes / bursts (plan 004): episode = same pattern on the same node (no node → same component) split
-- by > 30 min quiet; burst = same pattern anywhere in the dataset split by > 30 min quiet (DECISIONS H16).
DROP TABLE IF EXISTS episodes CASCADE;
CREATE TABLE episodes (dataset VARCHAR, pattern_id INTEGER, node VARCHAR, episode_no INTEGER, start_ts TIMESTAMP,
    end_ts TIMESTAMP, lines BIGINT, first_line_id BIGINT);
DROP TABLE IF EXISTS bursts CASCADE;
CREATE TABLE bursts (dataset VARCHAR, pattern_id INTEGER, burst_no INTEGER, start_ts TIMESTAMP, end_ts TIMESTAMP,
    lines BIGINT, nodes BIGINT, first_line_id BIGINT);
DROP TABLE IF EXISTS patterns CASCADE;
CREATE TABLE patterns (dataset VARCHAR, pattern_id INTEGER, component VARCHAR, template VARCHAR, severity VARCHAR,
    lines BIGINT, problem_lines BIGINT, error_lines BIGINT, nodes BIGINT, bursts BIGINT, node_episodes BIGINT, weeks_active BIGINT,
    first_ts TIMESTAMP, last_ts TIMESTAMP, example_line_id BIGINT);
-- Jev judgments (plan 006) + traits (plan 011) + component areas (plan 057): from the committed CSVs for the datasets we
-- ship, or computed live inside SereneDB when a dataset is added with a key (loader/jev.py). p_problem (DECISIONS H18)
-- = max(p_fault × (1 − p_dump), p_threat). A dataset without rows here is "not judged" (datasets.judged = false) and
-- the tools fall back to the level rule for it (plan 016).
DROP TABLE IF EXISTS pattern_traits CASCADE;
CREATE TABLE pattern_traits (dataset VARCHAR, pattern_id INTEGER, p_threat DOUBLE, cause VARCHAR, cause_confidence DOUBLE,
    actionable DOUBLE, role VARCHAR, owner_hint VARCHAR, owner_confidence DOUBLE);
DROP TABLE IF EXISTS pattern_judgments CASCADE;
CREATE TABLE pattern_judgments (dataset VARCHAR, pattern_id INTEGER, p_fault DOUBLE, p_dump DOUBLE, p_corrected DOUBLE,
    kind VARCHAR, kind_confidence DOUBLE, p_threat DOUBLE, p_problem DOUBLE);
DROP TABLE IF EXISTS component_areas CASCADE;
CREATE TABLE component_areas (dataset VARCHAR, component VARCHAR, area VARCHAR, confidence DOUBLE);
-- Pattern index (plan 011): one row per pattern with its template text AND its embedding in ONE inverted index
-- (full-text + IVF vector), for similar_patterns / find_patterns. Patterns without a stored vector keep emb NULL.
DROP TABLE IF EXISTS pattern_index CASCADE;
CREATE TABLE pattern_index (
    dataset    VARCHAR NOT NULL,
    pattern_id INTEGER NOT NULL,
    component  VARCHAR,
    template   VARCHAR,
    emb        FLOAT[768]
) WITH (storage = 'search');
CREATE INDEX pattern_index_idx ON pattern_index USING inverted (
    dataset, pattern_id, component, template log_body_dict, emb ivf (metric = 'cosine'));
-- Stored model summaries of the top problem bursts (scripts/summarize_bursts.py, ai_summarize_agg): context, not evidence.
DROP TABLE IF EXISTS burst_summaries CASCADE;
CREATE TABLE burst_summaries (dataset VARCHAR, pattern_id INTEGER, burst_no INTEGER, summary VARCHAR, model VARCHAR,
    created VARCHAR);
