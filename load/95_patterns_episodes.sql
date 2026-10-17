-- Patterns, node episodes and bursts for every dataset whose rows have pattern_id (plan 004). Re-runnable.
-- Run after the loaders AND 90_publish.sql (reads logs; the index must be published): part of ./load/reload.sh
-- Episode gap = 30 min (DECISIONS H16):
--   node episode = same pattern on the same node (no node → same component), split when the gap > 30 min;
--   burst        = same pattern anywhere in the dataset, split when the gap > 30 min (one storm on 1,000 nodes = 1 burst).
-- Bursts are the headline "how often" unit for team lead / manager; nodes give the spread.
\timing on

DROP TABLE IF EXISTS episodes;
CREATE TABLE episodes AS
WITH x AS (
    SELECT dataset, pattern_id, coalesce(node, component) AS node, ts, line_id,
           CASE WHEN ts - lag(ts) OVER w <= INTERVAL 30 MINUTE THEN 0 ELSE 1 END AS new_ep
    FROM logs WHERE pattern_id IS NOT NULL
    WINDOW w AS (PARTITION BY dataset, pattern_id, coalesce(node, component) ORDER BY ts, line_id)
), y AS (
    SELECT *, sum(new_ep) OVER (PARTITION BY dataset, pattern_id, node ORDER BY ts, line_id) AS episode_no FROM x
)
SELECT dataset, pattern_id, node, episode_no::INTEGER AS episode_no,
       min(ts) AS start_ts, max(ts) AS end_ts, count(*) AS lines, min(line_id) AS first_line_id
FROM y GROUP BY 1, 2, 3, 4
ORDER BY start_ts;

DROP TABLE IF EXISTS bursts;
CREATE TABLE bursts AS
WITH x AS (
    SELECT dataset, pattern_id, node, ts, line_id,
           CASE WHEN ts - lag(ts) OVER w <= INTERVAL 30 MINUTE THEN 0 ELSE 1 END AS new_b
    FROM logs WHERE pattern_id IS NOT NULL
    WINDOW w AS (PARTITION BY dataset, pattern_id ORDER BY ts, line_id)
), y AS (
    SELECT *, sum(new_b) OVER (PARTITION BY dataset, pattern_id ORDER BY ts, line_id) AS burst_no FROM x
)
SELECT dataset, pattern_id, burst_no::INTEGER AS burst_no, min(ts) AS start_ts, max(ts) AS end_ts,
       count(*) AS lines, count(DISTINCT node) AS nodes, min(line_id) AS first_line_id
FROM y GROUP BY 1, 2, 3
ORDER BY start_ts;

DROP TABLE IF EXISTS patterns;
CREATE TABLE patterns AS
WITH l AS (
    SELECT dataset, pattern_id, mode(severity) AS severity, count(*) AS lines,
           count(*) FILTER (WHERE severity IN ('FATAL', 'FAILURE', 'SEVERE', 'ERROR', 'CRITICAL')) AS problem_lines,
           count(DISTINCT node) AS nodes, min(ts) AS first_ts, max(ts) AS last_ts,
           count(DISTINCT date_trunc('week', ts)) AS weeks_active, min(line_id) AS example_line_id
    FROM logs WHERE pattern_id IS NOT NULL GROUP BY 1, 2
), e AS (SELECT dataset, pattern_id, count(*) AS node_episodes FROM episodes GROUP BY 1, 2),
   b AS (SELECT dataset, pattern_id, count(*) AS bursts FROM bursts GROUP BY 1, 2)
SELECT l.dataset, l.pattern_id, t.component, t.template, l.severity, l.lines, l.problem_lines, l.nodes,
       b.bursts, e.node_episodes, l.weeks_active, l.first_ts, l.last_ts, l.example_line_id
FROM l JOIN pattern_templates t USING (dataset, pattern_id) JOIN e USING (dataset, pattern_id)
       JOIN b USING (dataset, pattern_id)
ORDER BY l.dataset, l.pattern_id;
