-- Ownership of ONE dataset (plan 057 chain by Konark, per dataset since plan 016; was 94_ownership + 96b). Run after the
-- dataset's Jev traits / component areas exist (lib/build_dataset.sql, or loader/jev.py after live judging).
-- First hit wins for the team:
--   1 curated exact row (data/ownership.csv)                 source 'curated'          confidence 1.0
--   2 curated dataset default ('*' row)                      source 'curated default'  confidence 0.95
--   3 Jev owner_hint among the dataset's curated teams       source 'jev owner_hint'   confidence = Jev p (>= 0.6)
--   4 area from a name rule (data/ownership_rules.csv) → team (data/area_teams.csv)   'rule: <source_ref>'  0.9
--   5 area from Jev (component_areas, p >= 0.6) → team                                'jev area'   confidence = Jev p
--   6 none → no row (tools show 'unowned')
-- Every row also gets an area (name rule first, else Jev area >= 0.6) and, for curated rows, a dispute flag when the
-- component's Jev owner hints (p >= 0.8) mostly name another curated team. psql variable: ds.
SET sdb_scan_split = 'never';
DELETE FROM ownership WHERE dataset = :'ds';
INSERT INTO ownership
WITH c AS (
    SELECT DISTINCT dataset, component,
           -- normalise a program name: drop "[pid]", "(pam_unix)", a trailing "-<n>" / ".service", lower case
           lower(regexp_replace(regexp_replace(component, '(\[\d+\]|\(.*\))$', ''), '(-\d+|\.service)$', '')) AS norm
    FROM logs WHERE dataset = :'ds' AND component IS NOT NULL
), rule AS (
    SELECT dataset, component, area, source_ref FROM (
        SELECT c.dataset, c.component, r.area, r.source_ref,
               row_number() OVER (PARTITION BY c.dataset, c.component ORDER BY r.priority, length(r.pattern) DESC) AS rk
        FROM c JOIN ownership_rules r
          ON (r.match_type = 'exact' AND c.norm = r.pattern)
          OR (r.match_type = 'prefix' AND starts_with(c.norm, r.pattern))
          OR (r.match_type = 'regex' AND regexp_matches(c.norm, r.pattern)))
    WHERE rk = 1
), area AS (
    SELECT c.dataset, c.component,
           CASE WHEN r.area IS NOT NULL THEN r.area WHEN j.confidence >= 0.6 THEN j.area END AS area,
           CASE WHEN r.area IS NOT NULL THEN 'rule: ' || r.source_ref WHEN j.confidence >= 0.6 THEN 'jev area' END AS area_source,
           CASE WHEN r.area IS NOT NULL THEN 0.9 WHEN j.confidence >= 0.6 THEN j.confidence END AS area_confidence
    FROM c LEFT JOIN rule r USING (dataset, component)
    LEFT JOIN (SELECT * FROM component_areas WHERE dataset = :'ds') j USING (dataset, component)
), hint AS (  -- per component: the curated team its Jev owner hints name most (by lines), and how strongly
    SELECT dataset, component, owner_hint, conf, share FROM (
        SELECT p.dataset, p.component, j.owner_hint,
               sum(p.lines * j.owner_confidence) / sum(p.lines) AS conf,
               sum(p.lines) / sum(sum(p.lines)) OVER (PARTITION BY p.dataset, p.component) AS share,
               row_number() OVER (PARTITION BY p.dataset, p.component ORDER BY sum(p.lines) DESC, j.owner_hint) AS rk
        FROM patterns p JOIN pattern_traits j USING (dataset, pattern_id)
        WHERE p.dataset = :'ds' AND j.owner_hint IS NOT NULL AND j.owner_confidence >= 0.6 AND p.component IS NOT NULL
        GROUP BY 1, 2, 3)
    WHERE rk = 1
), strong AS (  -- the same, counting only confident hints (p >= 0.8): basis of the dispute flag
    SELECT dataset, component, owner_hint, conf, share FROM (
        SELECT p.dataset, p.component, j.owner_hint,
               sum(p.lines * j.owner_confidence) / sum(p.lines) AS conf,
               sum(p.lines) / sum(sum(p.lines)) OVER (PARTITION BY p.dataset, p.component) AS share,
               row_number() OVER (PARTITION BY p.dataset, p.component ORDER BY sum(p.lines) DESC, j.owner_hint) AS rk
        FROM patterns p JOIN pattern_traits j USING (dataset, pattern_id)
        WHERE p.dataset = :'ds' AND j.owner_hint IS NOT NULL AND j.owner_confidence >= 0.8 AND p.component IS NOT NULL
        GROUP BY 1, 2, 3)
    WHERE rk = 1
), x AS (
    SELECT c.dataset, c.component, a.area, a.area_source, a.area_confidence,
           e.team AS exact_team, e.description AS exact_desc, d.team AS default_team, d.description AS default_desc,
           h.owner_hint, h.conf AS hint_conf, s.owner_hint AS strong_hint, s.conf AS strong_conf, s.share AS strong_share,
           t.team AS area_team, t.description AS area_desc
    FROM c
    LEFT JOIN area a USING (dataset, component)
    LEFT JOIN ownership_raw e ON e.dataset = c.dataset AND e.component = c.component
    LEFT JOIN ownership_raw d ON d.dataset = c.dataset AND d.component = '*'
    LEFT JOIN hint h ON h.dataset = c.dataset AND h.component = c.component
    LEFT JOIN strong s ON s.dataset = c.dataset AND s.component = c.component
    LEFT JOIN area_teams t ON t.area = a.area
)
SELECT dataset, component,
       CASE WHEN exact_team IS NOT NULL THEN exact_team WHEN default_team IS NOT NULL THEN default_team
            WHEN owner_hint IS NOT NULL THEN owner_hint ELSE area_team END AS team,
       CASE WHEN exact_team IS NOT NULL THEN exact_desc WHEN default_team IS NOT NULL THEN default_desc
            WHEN owner_hint IS NOT NULL THEN NULL ELSE area_desc END AS description,
       area, area_source, round(area_confidence, 3) AS area_confidence,
       CASE WHEN exact_team IS NOT NULL THEN 'curated' WHEN default_team IS NOT NULL THEN 'curated default'
            WHEN owner_hint IS NOT NULL THEN 'jev owner_hint' WHEN area_team IS NOT NULL THEN area_source END AS source,
       round(CASE WHEN exact_team IS NOT NULL THEN 1.0 WHEN default_team IS NOT NULL THEN 0.95
                  WHEN owner_hint IS NOT NULL THEN hint_conf WHEN area_team IS NOT NULL THEN area_confidence END, 3)
           AS confidence,
       -- dispute: curated owner, but confident Jev hints for most of the component's lines name another team
       CASE WHEN coalesce(exact_team, default_team) IS NOT NULL AND strong_hint IS NOT NULL AND strong_share >= 0.5
                 AND strong_hint <> coalesce(exact_team, default_team) THEN strong_hint END AS disputed_by,
       CASE WHEN coalesce(exact_team, default_team) IS NOT NULL AND strong_hint IS NOT NULL AND strong_share >= 0.5
                 AND strong_hint <> coalesce(exact_team, default_team) THEN round(strong_conf, 3) END AS dispute_confidence
FROM x
WHERE coalesce(exact_team, default_team, owner_hint, area_team) IS NOT NULL
ORDER BY 1, 2;
