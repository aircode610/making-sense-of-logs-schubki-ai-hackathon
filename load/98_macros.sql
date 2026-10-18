-- SQL API (plan 011): the main question shapes as table macros, so a person (or any SQL client / BI tool) runs the same
-- fixed queries the agent's tools run, filling only the parameters:  SELECT * FROM problem_patterns('bgl', DATE '2005-11-01', DATE '2005-11-29');
-- Recreated on every reload (they depend on the tables; 00_schema drops them with CASCADE).
\timing on
-- matching lines (exact count + sample through the inverted index)
CREATE OR REPLACE MACRO logs_count(ds, q, s, e) AS TABLE
    SELECT count(*) AS lines, count(DISTINCT node) AS nodes, min(ts) AS first_ts, max(ts) AS last_ts
    FROM logs WHERE dataset = ds AND ts >= s AND ts < e AND body @@ websearch_to_tsquery(q);
CREATE OR REPLACE MACRO logs_search(ds, q, s, e, k := 20) AS TABLE
    SELECT line_id, ts, component, severity, node, pattern_id, body
    FROM logs WHERE dataset = ds AND ts >= s AND ts < e AND body @@ websearch_to_tsquery(q) ORDER BY ts, line_id LIMIT k;
-- problem patterns of a period (stored Jev judgment) with recurrences, spread and owner
CREATE OR REPLACE MACRO problem_patterns(ds, s, e) AS TABLE
    SELECT p.pattern_id, p.template, p.component, coalesce(o.team, 'unowned') AS team,
           count(*) AS bursts, sum(b.lines) AS lines, max(b.nodes) AS max_nodes_per_burst, round(j.p_problem, 3) AS p_problem
    FROM bursts b JOIN patterns p ON p.dataset = b.dataset AND p.pattern_id = b.pattern_id
    JOIN pattern_judgments j ON j.dataset = b.dataset AND j.pattern_id = b.pattern_id
    LEFT JOIN ownership o ON o.dataset = p.dataset AND o.component = p.component
    WHERE b.dataset = ds AND b.start_ts >= s AND b.start_ts < e AND j.p_problem >= 0.5 AND p.problem_lines > 0
    GROUP BY ALL ORDER BY bursts DESC, lines DESC;
-- problem bursts per team, this period vs the previous period of equal length
CREATE OR REPLACE MACRO team_problem_bursts(ds, s, e) AS TABLE
    SELECT coalesce(o.team, 'unowned') AS team,
           count(*) FILTER (WHERE b.start_ts >= s) AS bursts,
           count(*) FILTER (WHERE b.start_ts < s) AS bursts_previous
    FROM bursts b JOIN patterns p ON p.dataset = b.dataset AND p.pattern_id = b.pattern_id
    JOIN pattern_judgments j ON j.dataset = b.dataset AND j.pattern_id = b.pattern_id
    LEFT JOIN ownership o ON o.dataset = p.dataset AND o.component = p.component
    WHERE b.dataset = ds AND b.start_ts >= s - (e - s) AND b.start_ts < e AND j.p_problem >= 0.5 AND p.problem_lines > 0
    GROUP BY 1 ORDER BY bursts DESC;
-- one pattern's bursts per week over the whole dataset
CREATE OR REPLACE MACRO pattern_weeks(ds, pid) AS TABLE
    SELECT date_trunc('week', start_ts) AS week, count(*) AS bursts, sum(lines) AS lines, max(nodes) AS max_nodes
    FROM bursts WHERE dataset = ds AND pattern_id = pid GROUP BY 1 ORDER BY 1;
-- typed values (ip:, path:, uuid:, url:) by mentions
CREATE OR REPLACE MACRO top_values(ds, prefix, k := 10) AS TABLE
    SELECT e AS value, count(*) AS lines, count(DISTINCT pattern_id) AS patterns
    FROM (SELECT unnest(entities) AS e, pattern_id FROM logs WHERE dataset = ds) WHERE e LIKE prefix || '%'
    GROUP BY 1 ORDER BY 2 DESC LIMIT k;
-- what preceded a pattern on the same node (nearest preceding episode, ASOF join)
CREATE OR REPLACE MACRO nearest_before(ds, pid, window_s := 600) AS TABLE
    WITH t AS (SELECT node, start_ts AS ts FROM episodes WHERE dataset = ds AND pattern_id = pid),
         o AS (SELECT node, start_ts AS ts, pattern_id FROM episodes WHERE dataset = ds AND pattern_id <> pid)
    SELECT o.pattern_id, any_value(p.template) AS template, count(*) AS times_nearest
    FROM t ASOF JOIN o ON o.node = t.node AND o.ts < t.ts
    JOIN patterns p ON p.dataset = ds AND p.pattern_id = o.pattern_id
    WHERE epoch(t.ts) - epoch(o.ts) <= window_s GROUP BY 1 ORDER BY 3 DESC LIMIT 10;
