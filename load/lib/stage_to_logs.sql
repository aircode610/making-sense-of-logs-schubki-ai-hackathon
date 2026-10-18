-- Generic second half of a dataset loader (plan 011). A loader parses its raw format into a TEMP table `stage` and
-- then `\ir lib/stage_to_logs.sql`; everything after parsing is shared, so a new dataset = one parse query.
--
-- stage columns (NULL where the format has nothing):
--   line_id BIGINT, ts TIMESTAMP, component VARCHAR, severity VARCHAR, node VARCHAR, location VARCHAR,
--   status INTEGER, duration_ms DOUBLE, body VARCHAR, label VARCHAR, request_id VARCHAR (one request / session /
--   trace), object_id VARCHAR (a long-lived thing followed across requests)
-- psql variables: ds, pbase (pattern_id base, unique per dataset), title, description, and what each filled column
--   means here (plan 012; leave unset when the column stays NULL): node_meaning, location_meaning, request_meaning,
--   object_meaning, status_meaning, duration_meaning;
--   variety (Drain-lite: a template word position with >= this many distinct values becomes <*>; default 10)
--
-- Steps: continuation lines (no timestamp of their own) inherit the previous line's ts / component / severity;
-- severity upper-cased; generic masks (mask_template) → a Drain-lite pass masks word positions whose values vary a lot
-- across otherwise-identical templates (user names, host names, file names) → pattern ids → logs, labels,
-- pattern_templates, datasets.
\if :{?variety}
\else
\set variety 10
\endif
\if :{?node_meaning}
\else
\set node_meaning ''
\endif
\if :{?location_meaning}
\else
\set location_meaning ''
\endif
\if :{?request_meaning}
\else
\set request_meaning ''
\endif
\if :{?object_meaning}
\else
\set object_meaning ''
\endif
\if :{?status_meaning}
\else
\set status_meaning ''
\endif
\if :{?duration_meaning}
\else
\set duration_meaning ''
\endif

CREATE TEMP TABLE s2 AS
SELECT line_id,
       coalesce(ts, last_value(ts IGNORE NULLS) OVER w)                AS ts,
       coalesce(component, last_value(component IGNORE NULLS) OVER w)  AS component,
       upper(coalesce(severity, last_value(severity IGNORE NULLS) OVER w)) AS severity,
       node, location, status, duration_ms, nullif(body, '') AS body, label, request_id, object_id,
       mask_template(body)                                             AS template0
FROM stage
WINDOW w AS (ORDER BY line_id ROWS BETWEEN UNBOUNDED PRECEDING AND CURRENT ROW);
DROP TABLE stage;  -- free the raw copy early (large datasets)

-- Drain-lite: for every template and word position, the "key" is the template with that word replaced by <*>.
-- If one key covers >= :variety distinct real words at that position, the position is a variable → mask it.
CREATE TEMP TABLE tw AS
SELECT component, template0, string_split(template0, ' ') AS w FROM (SELECT DISTINCT component, template0 FROM s2);

CREATE TEMP TABLE tpos AS
SELECT component, template0, p, w[p] AS word,
       array_to_string(list_transform(range(1, len(w) + 1), i -> CASE WHEN i = p THEN '<*>' ELSE w[i] END), ' ') AS k
FROM tw, LATERAL (SELECT unnest(range(1, len(w) + 1)) AS p);

CREATE TEMP TABLE tvar AS
SELECT component, k FROM tpos WHERE word NOT LIKE '<%>'
GROUP BY 1, 2 HAVING count(DISTINCT word) >= :variety;

CREATE TEMP TABLE tmap AS
SELECT t.component, t.template0,
       array_to_string(list_transform(range(1, len(t.w) + 1),
           i -> CASE WHEN list_contains(coalesce(m.ps, []), i) THEN '<*>' ELSE t.w[i] END), ' ') AS template
FROM tw t
LEFT JOIN (SELECT p.component, p.template0, list(p.p) AS ps
           FROM tpos p JOIN tvar v ON v.component IS NOT DISTINCT FROM p.component AND v.k = p.k
           GROUP BY 1, 2) m
  ON m.component IS NOT DISTINCT FROM t.component AND m.template0 = t.template0;

-- pattern_id = pbase + rank of (first occurrence, component, template): stable across reloads.
CREATE TEMP TABLE spat AS
SELECT component, template, (:pbase + row_number() OVER (ORDER BY first_ts, component, template))::INTEGER AS pattern_id
FROM (SELECT s.component, m.template, min(s.ts) AS first_ts
      FROM s2 s JOIN tmap m ON m.component IS NOT DISTINCT FROM s.component AND m.template0 = s.template0
      GROUP BY 1, 2);

-- Insert in time order so zonemaps prune time filters.
INSERT INTO logs (dataset, line_id, ts, component, severity, node, location, request_id, object_id, status, duration_ms,
                  entities, body, pattern_id)
SELECT :'ds', s.line_id, s.ts, s.component, s.severity, s.node, s.location, s.request_id, s.object_id, s.status, s.duration_ms,
       extract_entities(s.body), s.body, p.pattern_id
FROM s2 s
JOIN tmap m ON m.component IS NOT DISTINCT FROM s.component AND m.template0 = s.template0
JOIN spat p ON p.component IS NOT DISTINCT FROM m.component AND p.template = m.template
WHERE s.ts IS NOT NULL
ORDER BY s.ts, s.line_id;

INSERT INTO labels SELECT :'ds', line_id, label FROM s2 WHERE label IS NOT NULL AND label <> '-';

INSERT INTO pattern_templates SELECT :'ds', pattern_id, component, template FROM spat;

INSERT INTO datasets VALUES (:'ds', :'title', :'description', nullif(:'node_meaning', ''), nullif(:'location_meaning', ''),
    nullif(:'request_meaning', ''), nullif(:'object_meaning', ''), nullif(:'status_meaning', ''),
    nullif(:'duration_meaning', ''), :pbase);

DROP TABLE s2; DROP TABLE tw; DROP TABLE tpos; DROP TABLE tvar; DROP TABLE tmap; DROP TABLE spat;
