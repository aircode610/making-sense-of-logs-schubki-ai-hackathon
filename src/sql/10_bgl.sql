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
       nullif(r.body, '')                                             AS body,
       -- Template (plan 004): mask variable parts, most specific first, then merge runs of masks.
       regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(regexp_replace(
           r.body,
           '([0-9A-Fa-f]{2}:){3,}[0-9A-Fa-f]{1,2}', '<MAC>', 'g'),                    -- FF:F2:9F:16:BF:44
           'R\d\d-M[01](-N[0-9A-F])?(-[CIL])?(:J\d\d-U\d\d)?', '<LOC>', 'g'),            -- R02-M1-N0-C:J12-U11
           '(Mon|Tue|Wed|Thu|Fri|Sat|Sun) (Jan|Feb|Mar|Apr|May|Jun|Jul|Aug|Sep|Oct|Nov|Dec) +\d+ [\d:]+ [A-Z]{3} \d{4}',
           '<DATE>', 'g'),
           '(0x)?[0-9a-fA-F]{6,}', '<HEX>', 'g'),
           '\d+(\.\d+)*', '<N>', 'g'),
           '(<N>|<HEX>)([:./\-x,]*(<N>|<HEX>))+', '<N>', 'g'),
           '\s+', ' ', 'g')                                                AS template
FROM p;

-- pattern_id = rank of (first occurrence, component, template): stable across reloads.
CREATE TEMP TABLE bgl_pat AS
SELECT component, template, row_number() OVER (ORDER BY first_ts, component, template)::INTEGER AS pattern_id
FROM (SELECT component, coalesce(template, '') AS template, min(ts) AS first_ts FROM bgl_stage GROUP BY 1, 2);

-- Insert in time order so zonemaps prune time filters.
INSERT INTO logs (dataset, line_id, ts, component, severity, severity_number, node, location, entities, body, pattern_id)
SELECT 'bgl', s.line_id, s.ts, s.component, s.severity, sm.severity_number, s.node,
       s.rack || '/' || s.midplane || '/' || s.node, extract_entities(s.body), s.body, p.pattern_id
FROM bgl_stage s JOIN bgl_pat p ON p.component = s.component AND p.template = coalesce(s.template, '')
LEFT JOIN severity_map sm ON sm.word = upper(s.severity)
ORDER BY s.ts, s.line_id;

INSERT INTO labels SELECT 'bgl', line_id, label FROM bgl_stage WHERE label <> '-';

INSERT INTO pattern_templates SELECT 'bgl', pattern_id, component, template FROM bgl_pat;

INSERT INTO datasets VALUES ('bgl', 'Blue Gene/L supercomputer RAS logs (LLNL)',
    'Loghub BGL: reliability/availability/serviceability events of the Blue Gene/L supercomputer, 2005-06-03 to 2006-01-04 (214 days). Location = rack/midplane/node (R02-M1-N0-C:J12-U11: rack R02, midplane M1, node card N0, C = compute / I = I/O card). Components KERNEL, APP, MMCS, ... Alert labels exist for evaluation only.',
    'compute / I/O node: rack-midplane-nodecard-card-unit (C = compute card, I = I/O card)',
    'rack/midplane/node (first level = a whole rack, two levels = a midplane)',
    NULL, NULL, NULL, NULL, 0);

DROP TABLE bgl_stage;
DROP TABLE bgl_pat;
