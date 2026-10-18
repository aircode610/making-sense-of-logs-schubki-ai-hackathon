-- Load HDFS_v1 (Loghub, 11,175,629 lines, 1.58 GB, a Hadoop cluster's HDFS over ~39 hours, 2008-11-09/11) via the
-- generic loader (plan 011): the scale test of the pipeline. Optional: only when data/raw/hdfs/HDFS.log exists
-- (scripts/download_data.sh hdfs).
-- Line: 081109 203518 143 INFO dfs.DataNode$DataXceiver: Receiving block blk_-1608999687919862906 src: /10.250.19.102:54106 dest: /10.250.19.102:50010
--       yymmdd HHMMSS pid LEVEL component: message      → request_id = the block id (blk_…), the correlation id of HDFS.
-- Labels (evaluation only): preprocessed/anomaly_label.csv marks blocks Normal / Anomaly → labels(label = block id).
\timing on
CREATE TEMP TABLE stage AS
WITH raw AS (
    SELECT row_number() OVER () AS line_id, line
    FROM read_csv('/data/raw/hdfs/HDFS.log', columns = {'line': 'VARCHAR'}, header = false,
                  delim = E'\x01', quote = '', escape = '', auto_detect = false)
), p AS (
    SELECT line_id, line, regexp_extract(line, '^(\d{6} \d{6}) \d+ ([A-Z]+) ([\w.$]+): (.*)$',
                                         ['ts', 'severity', 'component', 'body']) AS r
    FROM raw
)
SELECT line_id,
       try_strptime(nullif(r.ts, ''), '%y%m%d %H%M%S')                        AS ts,
       nullif(r.component, '')                                                AS component,
       nullif(r.severity, '')                                                 AS severity,
       NULL::VARCHAR AS node, NULL::VARCHAR AS location,
       NULL::INTEGER AS status, NULL::DOUBLE AS latency_ms,
       CASE WHEN r.ts = '' THEN line ELSE r.body END                          AS body,
       NULL::VARCHAR AS label,
       nullif(regexp_extract(r.body, '(blk_-?\d+)', 1), '')                   AS request_id
FROM p;
\set ds hdfs
\set pbase 500000
\set title 'HDFS_v1 Hadoop file system logs (scale test, 11M lines)'
\set description 'Loghub HDFS_v1: HDFS NameNode / DataNode logs of a Hadoop cluster over about 39 hours from 2008-11-09. request_id = the HDFS block id (blk_...), which follows one block across replicas; client and datanode IPs inside messages are entities (ip:...). Block-level anomaly labels exist for evaluation only.'
\set location_hint ''
\set id_fields 'request_id (HDFS block id blk_...)'
\ir lib/stage_to_logs.sql
INSERT INTO labels
SELECT 'hdfs', row_number() OVER (), "BlockId"
FROM read_csv('/data/raw/hdfs/preprocessed/anomaly_label.csv', header = true, auto_detect = true)
WHERE "Label" = 'Anomaly';
