-- requires: data/raw/apache/Apache.log
-- Load Apache httpd error log (Loghub, 56,481 lines, 2005-06-09 → 2006-02-28) via the generic loader (plan 011).
-- Line: [Thu Jun 09 06:07:04 2005] [notice] LDAP: Built with OpenLDAP LDAP SDK
--       [Sat Jan 21 04:34:39 2006] [error] [client 216.83.140.52] script not found or unable to stat: /var/www/cgi-bin/awstats
-- Lines without the [date] [level] prefix continue the previous message (they inherit its time and level, not its component).
-- component = the module prefix of the message when there is one ('mod_jk', 'jk2_init()', 'LDAP'), else 'httpd'.
\timing on
CREATE TEMP TABLE stage AS
WITH raw AS (
    SELECT row_number() OVER () AS line_id, line
    FROM read_csv('/data/raw/apache/Apache.log', columns = {'line': 'VARCHAR'}, header = false,
                  delim = E'\x01', quote = '', escape = '', auto_detect = false)
), p AS (
    SELECT line_id, line, regexp_extract(line,
        '^\[\w{3} (\w{3} +\d+ \d\d:\d\d:\d\d \d{4})\] \[(\w+)\] (.*)$', ['ts', 'severity', 'body']) AS r
    FROM raw
)
SELECT line_id,
       try_strptime(nullif(r.ts, ''), '%b %d %H:%M:%S %Y')                     AS ts,
       -- component from the line's own text; continuation lines too (plan 014: inheriting the previous line's module
       -- filed httpd's 'script not found' continuations under mod_jk / jk2_init()). Time and level still inherit.
       coalesce(nullif(regexp_extract(CASE WHEN r.ts = '' THEN line ELSE r.body END,
                '^(?:\[client [^\]]+\] )?(mod_\w+|jk2_\w+\(\)|[A-Z][A-Za-z]+\.\w+\(\)|LDAP|Digest|suEXEC)', 1), ''), 'httpd') AS component,
       nullif(r.severity, '')                                                  AS severity,
       NULL::VARCHAR AS node, NULL::VARCHAR AS location,
       NULL::INTEGER AS status, NULL::DOUBLE AS duration_ms,
       CASE WHEN r.ts = '' THEN line ELSE r.body END                           AS body,
       NULL::VARCHAR AS label,
       NULL::VARCHAR AS object_id,
       NULL::VARCHAR AS request_id
FROM p;
\set ds apache
\set pbase 300000
\set title 'Apache httpd error log (one web server)'
\set description 'Loghub Apache: error_log of one Apache httpd server, 2005-06-09 to 2006-02-28 (264 days). Levels notice / warn / error; client IPs inside messages are extracted as entities (ip:...). Multi-line messages inherit the previous line time and level.'
\ir lib/stage_to_logs.sql
