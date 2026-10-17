-- Load OpenStack (3 files) into logs + labels, and the ownership table. Re-runnable (replaces OpenStack rows).
-- Run after 00_schema.sql: psql -h localhost -p 7890 -U postgres -d postgres -f load/20_openstack.sql
-- Line: <file>.log.<stamp> date time pid LEVEL module [req-id user tenant - - -] message
-- line_id = running line number over abnormal (1..18434), normal1, normal2 in that order.
\timing on

DELETE FROM logs   WHERE dataset = 'openstack';
DELETE FROM labels WHERE dataset = 'openstack';

CREATE TEMP TABLE os_stage AS
WITH raw AS (
    SELECT 0 AS off, row_number() OVER () AS n, line FROM read_csv('/data/raw/openstack/openstack_abnormal.log',
        columns = {'line': 'VARCHAR'}, header = false, delim = E'\x01', quote = '', escape = '', auto_detect = false)
    UNION ALL
    SELECT 18434, row_number() OVER (), line FROM read_csv('/data/raw/openstack/openstack_normal1.log',
        columns = {'line': 'VARCHAR'}, header = false, delim = E'\x01', quote = '', escape = '', auto_detect = false)
    UNION ALL
    SELECT 18434 + 52312, row_number() OVER (), line FROM read_csv('/data/raw/openstack/openstack_normal2.log',
        columns = {'line': 'VARCHAR'}, header = false, delim = E'\x01', quote = '', escape = '', auto_detect = false)
), p AS (
    SELECT off + n AS line_id, line,
        regexp_extract(line,
            '^(nova-[a-z]+)\S* (\d{4}-\d\d-\d\d \d\d:\d\d:\d\d\.\d+) \d+ ([A-Z]+) \S+(?: (?:\[(?:req-[0-9a-f-]+ (\S+) (\S+) [^\]]*|-)\] )?(.*))?$',
            ['component', 'ts', 'severity', 'user', 'tenant', 'body']) AS r
    FROM raw
)
SELECT line_id,
       r.component,
       strptime(r.ts, '%Y-%m-%d %H:%M:%S.%f')                                  AS ts,
       r.severity,
       nullif(regexp_extract(line, '\[(req-[0-9a-f-]+) ', 1), '')               AS request_id,
       nullif(regexp_extract(line, '\[instance: ([0-9a-f-]+)\]', 1), '')        AS instance_id,
       CASE WHEN r.tenant NOT IN ('', '-') THEN r.tenant END                    AS tenant_id,
       CAST(nullif(regexp_extract(line, 'status: (\d+) len: \d+ time: [\d.]+', 1), '') AS INTEGER) AS status,
       CAST(nullif(regexp_extract(line, 'status: \d+ len: \d+ time: ([\d.]+)', 1), '') AS DOUBLE) * 1000 AS latency_ms,
       nullif(r.body, '')                                                       AS body
FROM p;

INSERT INTO logs (dataset, line_id, ts, component, severity, request_id, instance_id, tenant_id, status, latency_ms, body)
SELECT 'openstack', line_id, ts, component, severity, request_id, instance_id, tenant_id, status, latency_ms, body
FROM os_stage ORDER BY ts, line_id;

-- Evaluation only: the injected-anomaly VM ids (never read by agent tools).
INSERT INTO labels
SELECT 'openstack', row_number() OVER (), line
FROM read_csv('/data/raw/openstack/anomaly_labels.txt', columns = {'line': 'VARCHAR'}, header = false,
              delim = E'\x01', quote = '', escape = '', auto_detect = false)
WHERE line ~ '^[0-9a-f]{8}-';
-- NOTE: label.line_id for openstack is the label row number, label text is the instance id.

DROP TABLE os_stage;

DROP TABLE IF EXISTS ownership;
CREATE TABLE ownership AS SELECT * FROM read_csv('/data/ownership.csv');
