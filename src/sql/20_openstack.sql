-- Load OpenStack (3 files) into logs + labels, and the ownership table. Expects empty tables: reload = ./load/reload.sh.
-- Run after 00_schema.sql: psql -h localhost -p 7890 -U postgres -d postgres -f load/20_openstack.sql
-- Line: <file>.log.<stamp> date time pid LEVEL module [req-id user tenant - - -] message
-- line_id = running line number over abnormal (1..18434), normal1, normal2 in that order.
\timing on

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
       nullif(regexp_extract(line, '\[instance: ([0-9a-f-]+)\]', 1), '')        AS object_id,   -- the VM
       CASE WHEN r.tenant NOT IN ('', '-') THEN r.tenant END                    AS tenant_id,   -- → entity 'tenant:…'
       CAST(nullif(regexp_extract(line, 'status: (\d+) len: \d+ time: [\d.]+', 1), '') AS INTEGER) AS status,
       -- duration (plan 012): HTTP request time, or a VM lifecycle step 'Took N seconds to spawn / build / …'
       coalesce(CAST(nullif(regexp_extract(line, 'status: \d+ len: \d+ time: ([\d.]+)', 1), '') AS DOUBLE),
                CAST(nullif(regexp_extract(line, 'Took ([\d.]+) seconds', 1), '') AS DOUBLE)) * 1000 AS duration_ms,
       nullif(r.body, '')                                                       AS body,
       -- Template (plan 053): mask variable parts, most specific first; keep the HTTP status code, merge mask runs.
       regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(
       regexp_replace(regexp_replace(
           coalesce(r.body, ''),
           '[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', '<UUID>', 'g'),
           '\d{1,3}(\.\d{1,3}){3}(,\d{1,3}(\.\d{1,3}){3})*', '<IP>', 'g'),        -- 10.11.27.243,10.11.10.1
           '(^|[^a-zA-Z])(0x)?[0-9a-fA-F]{6,}', '\1<HEX>', 'g'),                    -- not inside words (Traceback)
           '(status: \d+ len: )\d+ time: [\d.]+', '\1<N> time: <N>', 'g'),         -- mask len/time
           '(status: )(\d+)', '\1#\2', 'g'),                                       -- '#' shields the status code
           '(^|[^\d#])\d+(\.\d+)*', '\1<N>', 'g'),
           '(<N>|<HEX>)([:./\-x,]*(<N>|<HEX>))+', '<N>', 'g'),
           '\s+', ' ', 'g'),
           'status: #', 'status: ', 'g')                                    AS template
FROM p;

-- pattern_id = 100000 + rank of (first occurrence, component, template): stable across reloads, never a BGL id.
CREATE TEMP TABLE os_pat AS
SELECT component, template, (100000 + row_number() OVER (ORDER BY first_ts, component, template))::INTEGER AS pattern_id
FROM (SELECT component, template, min(ts) AS first_ts FROM os_stage GROUP BY 1, 2);

INSERT INTO logs (dataset, line_id, ts, component, severity, severity_number, request_id, object_id, status, duration_ms,
                  entities, body, pattern_id)
SELECT 'openstack', s.line_id, s.ts, s.component, s.severity, sm.severity_number, s.request_id, s.object_id, s.status,
       s.duration_ms, list_concat(extract_entities(s.body), CASE WHEN s.tenant_id IS NOT NULL THEN ['tenant:' || s.tenant_id] ELSE []::VARCHAR[] END),
       s.body, p.pattern_id
FROM os_stage s JOIN os_pat p ON p.component = s.component AND p.template = s.template
LEFT JOIN severity_map sm ON sm.word = upper(s.severity)
ORDER BY s.ts, s.line_id;

INSERT INTO pattern_templates SELECT 'openstack', pattern_id, component, template FROM os_pat;

-- Evaluation only: the injected-anomaly VM ids (never read by agent tools).
INSERT INTO labels
SELECT 'openstack', row_number() OVER (), line
FROM read_csv('/data/raw/openstack/anomaly_labels.txt', columns = {'line': 'VARCHAR'}, header = false,
              delim = E'\x01', quote = '', escape = '', auto_detect = false)
WHERE line ~ '^[0-9a-f]{8}-';
-- NOTE: label.line_id for openstack is the label row number, label text is the instance id.

INSERT INTO datasets VALUES ('openstack', 'OpenStack nova logs (cloud VM lifecycle and API)',
    'Loghub OpenStack: nova-api / nova-compute / nova-scheduler logs of a small cloud, 2017-05-16 to 2017-05-17, with request ids, tenant ids, VM instance ids, HTTP status and request latency inline. Some VMs had injected anomalies (labels for evaluation only).',
    NULL, NULL, 'nova request id (req-…): one API call and the work it triggers',
    'VM instance uuid: follows one VM across requests and services (spawn, build, delete)',
    'HTTP status of nova-api requests (status: N in the message)',
    'HTTP request time (time: N) and VM lifecycle step times (Took N seconds to spawn / build / delete)', 100000);

DROP TABLE os_stage;
DROP TABLE os_pat;
-- ownership: load/lib/ownership_dataset.sql (generic, per dataset).
