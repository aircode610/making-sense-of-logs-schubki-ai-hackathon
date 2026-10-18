-- Example values per dataset and field (plan 012), computed once at load time so tool descriptions can show REAL values
-- of every loaded dataset ("node: bgl e.g. R30-M0-N9-C:J16-U01; ssh e.g. LabSZ") without dataset knowledge in code
-- and without slow queries at server start. Long format: one row per (dataset, field); field 'entity:<kind>' per
-- extracted entity kind. example = the most frequent value (any value for ids); n_values = distinct values.
\timing on
SET sdb_scan_split = 'never';
DROP TABLE IF EXISTS dataset_examples CASCADE;
CREATE TABLE dataset_examples AS
WITH node AS (
    SELECT dataset, 'node' AS field, arg_max(v, c) AS example, count(*) AS n_values
    FROM (SELECT dataset, node AS v, count(*) AS c FROM logs WHERE node IS NOT NULL GROUP BY 1, 2) GROUP BY 1
), loc AS (
    SELECT dataset, 'location' AS field, arg_max(v, c) AS example, count(*) AS n_values
    FROM (SELECT dataset, location AS v, count(*) AS c FROM logs WHERE location IS NOT NULL GROUP BY 1, 2) GROUP BY 1
), req AS (
    SELECT dataset, 'request_id' AS field, any_value(request_id) AS example, count(DISTINCT request_id) AS n_values
    FROM logs WHERE request_id IS NOT NULL GROUP BY 1
), obj AS (
    SELECT dataset, 'object_id' AS field, any_value(object_id) AS example, count(DISTINCT object_id) AS n_values
    FROM logs WHERE object_id IS NOT NULL GROUP BY 1
), st AS (
    SELECT dataset, 'status' AS field, string_agg(v::VARCHAR, ', ' ORDER BY c DESC) AS example, count(*) AS n_values
    FROM (SELECT dataset, status AS v, count(*) AS c FROM logs WHERE status IS NOT NULL GROUP BY 1, 2) GROUP BY 1
), dur AS (
    SELECT dataset, 'duration_ms' AS field, round(median(duration_ms))::VARCHAR AS example, count(*) AS n_values
    FROM logs WHERE duration_ms IS NOT NULL GROUP BY 1
), ent AS (
    SELECT dataset, 'entity:' || kind AS field, arg_max(x, c) AS example, count(*) AS n_values
    FROM (SELECT dataset, x, split_part(x, ':', 1) AS kind, count(*) AS c
          FROM (SELECT dataset, unnest(entities) AS x FROM logs) GROUP BY 1, 2, 3) GROUP BY 1, 2
)
SELECT * FROM node UNION ALL SELECT * FROM loc UNION ALL SELECT * FROM req UNION ALL SELECT * FROM obj
UNION ALL SELECT * FROM st UNION ALL SELECT * FROM dur UNION ALL SELECT * FROM ent
ORDER BY 1, 2;
