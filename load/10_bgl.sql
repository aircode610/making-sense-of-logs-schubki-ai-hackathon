-- Load BGL into logs + labels, parsed by SereneDB from the raw file. Expects empty tables: reload = ./load/reload.sh.
-- Run after 00_schema.sql: psql -h localhost -p 7890 -U postgres -d postgres -f load/10_bgl.sql
-- Line format: label epoch date location ts location-repeat (RAS|NULL) component severity message
-- The repeated location is sometimes junk with spaces, so the parse anchors on ts and "(RAS|NULL) COMP SEV".
\timing on

CREATE TEMP TABLE bgl_stage AS
WITH raw AS (
    SELECT row_number() OVER () AS line_id, line
    FROM read_csv('/data/raw/BGL.log', columns = {'line': 'VARCHAR'}, header = false,
                  delim = E'\x01', quote = '', escape = '', auto_detect = false)
), p AS (
    SELECT line_id, regexp_extract(line,
        '^(\S+) \d+ \S+ (\S+) (\d{4}-\d\d-\d\d-\d\d\.\d\d\.\d\d\.\d{6})(?: .*?)? (?:RAS|NULL) ([A-Z_]+) (INFO|WARNING|ERROR|SEVERE|FATAL|FAILURE)(?: (.*))?$',
        ['label', 'loc', 'ts', 'component', 'severity', 'body']) AS r
    FROM raw
)
SELECT line_id,
       r.label,
       strptime(r.ts, '%Y-%m-%d-%H.%M.%S.%f')                        AS ts,
       r.component,
       r.severity,
       CASE WHEN r.loc LIKE 'R__-M_%' THEN r.loc END                  AS node,  -- NULL / UNKNOWN_LOCATION / '-' → NULL
       CASE WHEN r.loc LIKE 'R__-M_%' THEN substr(r.loc, 1, 3) END    AS rack,
       CASE WHEN r.loc LIKE 'R__-M_%' THEN substr(r.loc, 1, 6) END    AS midplane,
       nullif(r.body, '')                                             AS body
FROM p;

-- Insert in time order so zonemaps prune time filters.
INSERT INTO logs (dataset, line_id, ts, component, severity, node, rack, midplane, body)
SELECT 'bgl', line_id, ts, component, severity, node, rack, midplane, body
FROM bgl_stage ORDER BY ts, line_id;

INSERT INTO labels SELECT 'bgl', line_id, label FROM bgl_stage WHERE label <> '-';

DROP TABLE bgl_stage;
