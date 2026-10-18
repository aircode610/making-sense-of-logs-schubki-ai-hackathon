-- requires: data/raw/healthapp/HealthApp.log
-- Load HealthApp (Loghub, 253,395 lines, an Android health app, ~10 days from 2017-12-23) via the generic loader
-- (plan 012: unseen-dataset test). No log level (severity NULL), no host. component = app module (Step_LSC, HiH_…),
-- request_id = the process id. Line: 20171223-22:15:29:606|Step_LSC|30002312|onStandStepChanged 3579
-- The date is not zero-padded (201813-9:58:0:181 = 2018-1-3 09:58:00.181): yyyy + m/mm + d/dd, then h:m:s:ms.
\timing on
CREATE TEMP TABLE stage AS
WITH raw AS (
    SELECT row_number() OVER () AS line_id, line
    FROM read_csv('/data/raw/healthapp/HealthApp.log', columns = {'line': 'VARCHAR'}, header = false,
                  delim = E'\x01', quote = '', escape = '', auto_detect = false)
), p AS (
    SELECT line_id, line, regexp_extract(line, '^(\d{4})(\d{2,4})-(\d+):(\d+):(\d+):(\d+)\|([^|]*)\|([^|]*)\|(.*)$',
                                         ['y', 'md', 'h', 'mi', 's', 'ms', 'comp', 'pid', 'body']) AS r
    FROM raw
)
SELECT line_id,
       try_strptime(r.y || '-' ||
           CASE length(r.md) WHEN 4 THEN substr(r.md, 1, 2) || '-' || substr(r.md, 3, 2)
                             WHEN 2 THEN substr(r.md, 1, 1) || '-' || substr(r.md, 2, 1)
                             ELSE substr(r.md, 1, 1) || '-' || substr(r.md, 2, 2) END
           || ' ' || r.h || ':' || r.mi || ':' || r.s || '.' || lpad(r.ms, 3, '0'), '%Y-%m-%d %H:%M:%S.%g') AS ts,
       nullif(r.comp, '')                                                     AS component,
       NULL::VARCHAR AS severity, NULL::VARCHAR AS node, NULL::VARCHAR AS location,
       NULL::INTEGER AS status, NULL::DOUBLE AS duration_ms,
       CASE WHEN r.y = '' THEN line ELSE r.body END                           AS body,
       NULL::VARCHAR AS label,
       NULL::VARCHAR AS object_id,
       nullif(r.pid, '')                                                      AS request_id
FROM p;
\set ds healthapp
\set pbase 800000
\set title 'HealthApp Android app log (step counter and health data sync)'
\set description 'Loghub HealthApp: log of an Android health app, 2017-12-23 to 2018-01-03 (dates not zero-padded in the raw file). No log levels (severity is NULL), no host. Components are app modules: Step_* = step counting, HiH_* = HiHealth data store and sync.'
\set request_meaning 'app process id: all lines of one app process'
\ir lib/stage_to_logs.sql
