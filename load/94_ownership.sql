-- Ownership (plan 011, generic): data/ownership.csv maps (dataset, component) → team. A row with component '*' is the
-- dataset's default team for components without their own row (datasets with many components, e.g. Java classes).
-- `ownership` = one row per (dataset, component) that occurs in logs, exact match first, then the '*' default;
-- components with neither stay out (tools show them as 'unowned'). Run after the loaders.
-- Plan 057: load/96b_ownership_inferred.sql later REBUILDS `ownership` with the same (dataset, component, team,
-- description) for curated rows plus area / source / confidence / dispute columns and inferred rows.
\timing on
SET sdb_scan_split = 'never';  -- TsDict facet counts off by one with split segments (plan 011)
DROP TABLE IF EXISTS ownership_raw CASCADE;
CREATE TABLE ownership_raw AS SELECT * FROM read_csv('/data/ownership.csv', header = true, auto_detect = true);
DROP TABLE IF EXISTS ownership CASCADE;
CREATE TABLE ownership AS
SELECT c.dataset, c.component, coalesce(e.team, d.team) AS team, coalesce(e.description, d.description) AS description
FROM (SELECT DISTINCT dataset, component FROM logs WHERE component IS NOT NULL) c
LEFT JOIN ownership_raw e ON e.dataset = c.dataset AND e.component = c.component
LEFT JOIN ownership_raw d ON d.dataset = c.dataset AND d.component = '*'
WHERE coalesce(e.team, d.team) IS NOT NULL
ORDER BY 1, 2;

-- Saved searches (plan 011, tool check_watchlist): config rows per dataset, data/watchlist.csv.
DROP TABLE IF EXISTS watchlist CASCADE;
CREATE TABLE watchlist AS SELECT * FROM read_csv('/data/watchlist.csv', header = true, auto_detect = true);

-- Remote Parquet sources (plan 011, tools remote_*): queried in place over HTTPS, never loaded.
DROP TABLE IF EXISTS remote_sources CASCADE;
CREATE TABLE remote_sources AS SELECT * FROM read_csv('/data/remote_sources.csv', header = true, auto_detect = true);
