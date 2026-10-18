-- Everything derived from ONE dataset's log lines (plan 016), re-runnable: each step deletes the dataset's rows and
-- inserts them again, so adding / replacing a dataset never touches the others. Same SQL as the former global steps
-- 93_examples, 95_patterns_episodes, 96_pattern_judgments, 96b_ownership_inferred, 97_pattern_vectors, restricted to
-- :ds. Run after the dataset's loader and `VACUUM (REFRESH_TABLE) logs` (these steps read the published index).
-- psql variable: ds. Tables: load/01_derived.sql.
SET sdb_scan_split = 'never';  -- TsDict facet counts off by one with split segments (plan 011)

-- ---------------------------------------------------------------- example values (plan 012; was 93_examples.sql)
DELETE FROM dataset_examples WHERE dataset = :'ds';
INSERT INTO dataset_examples
WITH d AS (SELECT * FROM logs WHERE dataset = :'ds'),
node AS (
    SELECT dataset, 'node' AS field, arg_max(v, c) AS example, count(*) AS n_values
    FROM (SELECT dataset, node AS v, count(*) AS c FROM d WHERE node IS NOT NULL GROUP BY 1, 2) GROUP BY 1
), loc AS (
    SELECT dataset, 'location' AS field, arg_max(v, c) AS example, count(*) AS n_values
    FROM (SELECT dataset, location AS v, count(*) AS c FROM d WHERE location IS NOT NULL GROUP BY 1, 2) GROUP BY 1
), req AS (
    SELECT dataset, 'request_id' AS field, any_value(request_id) AS example, count(DISTINCT request_id) AS n_values
    FROM d WHERE request_id IS NOT NULL GROUP BY 1
), obj AS (
    SELECT dataset, 'object_id' AS field, any_value(object_id) AS example, count(DISTINCT object_id) AS n_values
    FROM d WHERE object_id IS NOT NULL GROUP BY 1
), st AS (
    SELECT dataset, 'status' AS field, string_agg(v::VARCHAR, ', ' ORDER BY c DESC) AS example, count(*) AS n_values
    FROM (SELECT dataset, status AS v, count(*) AS c FROM d WHERE status IS NOT NULL GROUP BY 1, 2) GROUP BY 1
), dur AS (
    SELECT dataset, 'duration_ms' AS field, round(median(duration_ms))::VARCHAR AS example, count(*) AS n_values
    FROM d WHERE duration_ms IS NOT NULL GROUP BY 1
), ent AS (
    SELECT dataset, 'entity:' || kind AS field, arg_max(x, c) AS example, count(*) AS n_values
    FROM (SELECT dataset, x, split_part(x, ':', 1) AS kind, count(*) AS c
          FROM (SELECT dataset, unnest(entities) AS x FROM d) GROUP BY 1, 2, 3) GROUP BY 1, 2
)
SELECT * FROM node UNION ALL SELECT * FROM loc UNION ALL SELECT * FROM req UNION ALL SELECT * FROM obj
UNION ALL SELECT * FROM st UNION ALL SELECT * FROM dur UNION ALL SELECT * FROM ent
ORDER BY 1, 2;

-- ---------------------------------------------------------------- episodes, bursts, patterns (plan 004; was 95)
DELETE FROM episodes WHERE dataset = :'ds';
INSERT INTO episodes
WITH x AS (
    SELECT dataset, pattern_id, coalesce(node, component) AS node, ts, line_id,
           CASE WHEN ts - lag(ts) OVER w <= INTERVAL 30 MINUTE THEN 0 ELSE 1 END AS new_ep
    FROM logs WHERE dataset = :'ds' AND pattern_id IS NOT NULL
    WINDOW w AS (PARTITION BY pattern_id, coalesce(node, component) ORDER BY ts, line_id)
), y AS (
    SELECT *, sum(new_ep) OVER (PARTITION BY pattern_id, node ORDER BY ts, line_id) AS episode_no FROM x
)
SELECT dataset, pattern_id, node, episode_no::INTEGER AS episode_no,
       min(ts) AS start_ts, max(ts) AS end_ts, count(*) AS lines, min(line_id) AS first_line_id
FROM y GROUP BY 1, 2, 3, 4
ORDER BY start_ts;

DELETE FROM bursts WHERE dataset = :'ds';
INSERT INTO bursts
WITH x AS (
    SELECT dataset, pattern_id, node, ts, line_id,
           CASE WHEN ts - lag(ts) OVER w <= INTERVAL 30 MINUTE THEN 0 ELSE 1 END AS new_b
    FROM logs WHERE dataset = :'ds' AND pattern_id IS NOT NULL
    WINDOW w AS (PARTITION BY pattern_id ORDER BY ts, line_id)
), y AS (
    SELECT *, sum(new_b) OVER (PARTITION BY pattern_id ORDER BY ts, line_id) AS burst_no FROM x
)
SELECT dataset, pattern_id, burst_no::INTEGER AS burst_no, min(ts) AS start_ts, max(ts) AS end_ts,
       count(*) AS lines, count(DISTINCT node) AS nodes, min(line_id) AS first_line_id
FROM y GROUP BY 1, 2, 3
ORDER BY start_ts;

DELETE FROM patterns WHERE dataset = :'ds';
INSERT INTO patterns
WITH l AS (
    SELECT dataset, pattern_id, mode(severity) AS severity, count(*) AS lines,
           count(*) FILTER (WHERE severity IN ('FATAL', 'FAILURE', 'SEVERE', 'ERROR', 'CRITICAL', 'WARN', 'WARNING')
                            OR status >= 500                   -- HTTP 5xx: nova logs them at INFO (plan 054)
                            OR severity IS NULL) AS problem_lines,  -- WARN + no level: Jev decides (plan 011)
           count(*) FILTER (WHERE severity IN ('FATAL', 'FAILURE', 'SEVERE', 'ERROR', 'CRITICAL', 'WARN', 'WARNING')
                            OR status >= 500) AS error_lines,  -- explicit level only: the rule without Jev (plan 016)
           count(DISTINCT node) AS nodes, min(ts) AS first_ts, max(ts) AS last_ts,
           count(DISTINCT date_trunc('week', ts)) AS weeks_active, min(line_id) AS example_line_id
    FROM logs WHERE dataset = :'ds' AND pattern_id IS NOT NULL GROUP BY 1, 2
), e AS (SELECT pattern_id, count(*) AS node_episodes FROM episodes WHERE dataset = :'ds' GROUP BY 1),
   b AS (SELECT pattern_id, count(*) AS bursts FROM bursts WHERE dataset = :'ds' GROUP BY 1),
   t AS (SELECT * FROM pattern_templates WHERE dataset = :'ds')
SELECT l.dataset, l.pattern_id, t.component, t.template, l.severity, l.lines, l.problem_lines, l.error_lines, l.nodes,
       b.bursts, e.node_episodes, l.weeks_active, l.first_ts, l.last_ts, l.example_line_id
FROM l JOIN t USING (pattern_id) JOIN e USING (pattern_id) JOIN b USING (pattern_id)
ORDER BY l.pattern_id;

-- ---------------------------------------------------------------- stored Jev outputs (plan 006 / 011 / 057; was 96)
-- data/jev/ holds the committed outputs. :jev_ok = FALSE (LOGS_FRESH=1 / loader --fresh) ignores them, so loader/jev.py
-- judges the dataset live inside SereneDB, as for a user's own file.
\if :{?jev_ok}
\else
\set jev_ok TRUE
\endif
-- Committed CSVs of the datasets we ship, joined on (dataset, component, template) so they survive pattern-id
-- renumbering. A dataset added by a user has no CSV: loader/jev.py judges it live (with a key) and calls
-- lib/ownership_dataset.sql again, or it stays unjudged (tools fall back to the level rule).
DELETE FROM pattern_traits WHERE dataset = :'ds';
INSERT INTO pattern_traits
SELECT t.dataset, t.pattern_id, x.p_threat, x.cause, x.cause_confidence, x.actionable, x.role, nullif(x.owner_hint, ''),
       x.owner_confidence
FROM read_csv('/data/jev/pattern_traits_*.csv', header = true, quote = '"', escape = '"', auto_detect = false,
              columns = {'dataset': 'VARCHAR', 'component': 'VARCHAR', 'template': 'VARCHAR', 'pattern_id': 'INTEGER',
                         'p_threat': 'DOUBLE', 'cause': 'VARCHAR', 'cause_confidence': 'DOUBLE', 'actionable': 'DOUBLE',
                         'role': 'VARCHAR', 'owner_hint': 'VARCHAR', 'owner_confidence': 'DOUBLE'}) x
JOIN pattern_templates t ON t.dataset = x.dataset AND t.component IS NOT DISTINCT FROM x.component
                        AND t.template = coalesce(x.template, '')
WHERE x.dataset = :'ds' AND :jev_ok;

DELETE FROM pattern_judgments WHERE dataset = :'ds';
INSERT INTO pattern_judgments
SELECT t.dataset, t.pattern_id, j.p_fault, j.p_dump, j.p_corrected, j.kind, j.kind_confidence, tr.p_threat,
       greatest(j.p_fault * (1 - j.p_dump), coalesce(tr.p_threat, 0)) AS p_problem
FROM read_csv('/data/jev/pattern_judgments_*.csv', header = true, quote = '"', escape = '"', auto_detect = false,
              columns = {'dataset': 'VARCHAR', 'component': 'VARCHAR', 'template': 'VARCHAR', 'pattern_id': 'INTEGER',
                         'p_fault': 'DOUBLE', 'p_dump': 'DOUBLE', 'p_corrected': 'DOUBLE', 'kind': 'VARCHAR',
                         'kind_confidence': 'DOUBLE'}) j
JOIN pattern_templates t ON t.dataset = j.dataset AND t.component IS NOT DISTINCT FROM j.component
                        AND t.template = coalesce(j.template, '')
LEFT JOIN pattern_traits tr ON tr.dataset = t.dataset AND tr.pattern_id = t.pattern_id
WHERE j.dataset = :'ds' AND :jev_ok;

DELETE FROM component_areas WHERE dataset = :'ds';
INSERT INTO component_areas
SELECT * FROM read_csv('/data/jev/component_areas_*.csv', header = true, auto_detect = false,
                       columns = {'dataset': 'VARCHAR', 'component': 'VARCHAR', 'area': 'VARCHAR', 'confidence': 'DOUBLE'})
WHERE dataset = :'ds' AND :jev_ok;

DELETE FROM burst_summaries WHERE dataset = :'ds';
INSERT INTO burst_summaries
SELECT * FROM read_csv('/data/jev/burst_summaries.csv', header = true, quote = '"', escape = '"', auto_detect = false,
    columns = {'dataset': 'VARCHAR', 'pattern_id': 'INTEGER', 'burst_no': 'INTEGER', 'summary': 'VARCHAR',
               'model': 'VARCHAR', 'created': 'VARCHAR'})
WHERE dataset = :'ds' AND :jev_ok;

-- ---------------------------------------------------------------- pattern index (plan 011; was 97)
-- Vectors: data/pattern_vectors*.parquet (scripts/embed_patterns.py), joined on (dataset, component, template).
DELETE FROM pattern_index WHERE dataset = :'ds';
INSERT INTO pattern_index
SELECT p.dataset, p.pattern_id, p.component, p.template, v.emb::FLOAT[768]
FROM (SELECT * FROM patterns WHERE dataset = :'ds') p
LEFT JOIN (SELECT * FROM read_parquet('/data/jev/pattern_vectors*.parquet') WHERE dataset = :'ds' AND :jev_ok) v
  ON v.component IS NOT DISTINCT FROM p.component AND v.template = p.template;
VACUUM (REFRESH_TABLE) pattern_index;

\ir ownership_dataset.sql
