-- Load Zookeeper (Loghub, 74,380 lines, one ensemble member, 2015-07-29 → 2015-08-27) via the generic loader (plan 011).
-- Line: 2015-07-29 17:41:41,536 - INFO  [main:QuorumPeerConfig@101] - Reading configuration from: /etc/zookeeper/conf/zoo.cfg
--        date time,ms - LEVEL [thread:Class@line] - message      → component = Java class, location = class/thread.
\timing on
CREATE TEMP TABLE stage AS
WITH raw AS (
    SELECT row_number() OVER () AS line_id, line
    FROM read_csv('/data/raw/zookeeper/Zookeeper.log', columns = {'line': 'VARCHAR'}, header = false,
                  delim = E'\x01', quote = '', escape = '', auto_detect = false)
), p AS (
    SELECT line_id, regexp_extract(line,
        '^(\d{4}-\d\d-\d\d \d\d:\d\d:\d\d),(\d{3}) - ([A-Z]+) +\[(.*):([A-Za-z0-9_$.]+)@\d+\] - (.*)$',
        ['ts', 'ms', 'severity', 'thread', 'class', 'body']) AS r, line
    FROM raw
)
SELECT line_id,
       try_strptime(nullif(r.ts, '') || '.' || r.ms, '%Y-%m-%d %H:%M:%S.%g')  AS ts,
       nullif(r.class, '')                                                     AS component,
       nullif(r.severity, '')                                                  AS severity,
       NULL::VARCHAR                                                           AS node,
       CASE WHEN r.class <> '' THEN r.class || '/' || regexp_replace(r.thread, '[/\s]', '_', 'g') END AS location,
       NULL::INTEGER AS status, NULL::DOUBLE AS latency_ms,
       CASE WHEN r.ts = '' THEN line ELSE r.body END                           AS body,
       NULL::VARCHAR AS label,
       NULL::VARCHAR AS request_id
FROM p;
\set ds zookeeper
\set pbase 200000
\set title 'Zookeeper coordination service logs (one ensemble member)'
\set description 'Loghub Zookeeper: Java log4j lines from a ZooKeeper ensemble member, 2015-07-29 to 2015-08-27. component = Java class, location = class/thread. Leader election, quorum connections, client sessions.'
\set location_hint 'class/thread'
\set id_fields ''
\ir lib/stage_to_logs.sql
