-- Load OpenSSH auth log (Loghub, 655,146 lines, host LabSZ, 28 days Dec → Jan) via the generic loader (plan 011).
-- Line: Dec 10 06:55:46 LabSZ sshd[24200]: Invalid user webmaster from 173.234.31.186
-- syslog has no year: Dec is taken as 2017 and Jan as 2018 (assumption, stated in the datasets row). No log level:
-- severity stays NULL (problem detection relies on the Jev pattern judgment). request_id = 'sshd-<pid>' groups one
-- connection's lines (pids are reused over 28 days, so treat it as a session id within hours).
\timing on
CREATE TEMP TABLE stage AS
WITH raw AS (
    SELECT row_number() OVER () AS line_id, line
    FROM read_csv('/data/raw/ssh/SSH.log', columns = {'line': 'VARCHAR'}, header = false,
                  delim = E'\x01', quote = '', escape = '', auto_detect = false)
), p AS (
    SELECT line_id, line, regexp_extract(line,
        '^(\w{3}) +(\d+) (\d\d:\d\d:\d\d) (\S+) ([\w\-]+)\[(\d+)\]: (.*)$',
        ['mon', 'day', 'time', 'host', 'proc', 'pid', 'body']) AS r
    FROM raw
)
SELECT line_id,
       try_strptime(r.mon || ' ' || r.day || ' ' || CASE r.mon WHEN 'Dec' THEN '2017' ELSE '2018' END || ' ' || r.time,
                    '%b %d %Y %H:%M:%S')                                       AS ts,
       nullif(r.proc, '')                                                      AS component,
       NULL::VARCHAR                                                           AS severity,
       nullif(r.host, '')                                                      AS node,
       nullif(r.host, '')                                                      AS location,
       NULL::INTEGER AS status, NULL::DOUBLE AS latency_ms,
       CASE WHEN r.mon = '' THEN line ELSE r.body END                          AS body,
       NULL::VARCHAR AS label,
       CASE WHEN r.pid <> '' THEN r.proc || '-' || r.pid END                   AS request_id
FROM p;
\set ds ssh
\set pbase 400000
\set title 'OpenSSH server auth log (host LabSZ)'
\set description 'Loghub OpenSSH: sshd auth log of one internet-facing server (LabSZ), 28 days from Dec 10 (year not logged: Dec = 2017, Jan = 2018 assumed). No log levels (severity is NULL). Failed passwords, invalid users, break-in attempts; attacker IPs are entities (ip:...); request_id = sshd-<pid> = one connection.'
\set location_hint 'host'
\set id_fields 'request_id (sshd-<pid> session)'
\ir lib/stage_to_logs.sql
