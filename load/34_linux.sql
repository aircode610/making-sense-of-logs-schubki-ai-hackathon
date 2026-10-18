-- requires: data/raw/linux/Linux.log
-- Load Linux syslog (Loghub, 25,567 lines, one host "combo", Jun → Feb, ~264 days) via the generic loader (plan 012:
-- unseen-dataset test, nothing tuned for it). syslog has no year: Jun-Dec = 2005, Jan-Feb = 2006 (assumption, stated in
-- the datasets row). No log level (severity NULL). Read as latin-1: some lines carry raw non-UTF-8 attack bytes. component = program, request_id = '<program>-<pid>' when logged.
-- Line: Jun 14 15:16:01 combo sshd(pam_unix)[19939]: authentication failure; logname= uid=0 euid=0 tty=NODEVssh ...
\timing on
CREATE TEMP TABLE stage AS
WITH raw AS (
    SELECT row_number() OVER () AS line_id, line
    FROM read_csv('/data/raw/linux/Linux.log', columns = {'line': 'VARCHAR'}, header = false,
                  delim = E'\x01', quote = '', escape = '', auto_detect = false,
                  encoding = 'latin-1')  -- not all UTF-8: attack payloads with raw bytes (rpc.statd format-string attempts)
), p AS (
    SELECT line_id, line, regexp_extract(line,
        '^(\w{3}) +(\d+) (\d\d:\d\d:\d\d) (\S+) ([^\s:\[(]+)(?:\(([^)]*)\))?(?:\[(\d+)\])?:? ?(.*)$',
        ['mon', 'day', 'time', 'host', 'proc', 'sub', 'pid', 'body']) AS r
    FROM raw
)
SELECT line_id,
       try_strptime(r.mon || ' ' || r.day || ' ' || CASE WHEN r.mon IN ('Jan', 'Feb') THEN '2006' ELSE '2005' END
                    || ' ' || r.time, '%b %d %Y %H:%M:%S')                    AS ts,
       nullif(r.proc, '') || coalesce('(' || nullif(r.sub, '') || ')', '')    AS component,
       NULL::VARCHAR                                                          AS severity,
       nullif(r.host, '')                                                     AS node,
       nullif(r.host, '')                                                     AS location,
       NULL::INTEGER AS status, NULL::DOUBLE AS duration_ms,
       CASE WHEN r.mon = '' THEN line ELSE r.body END                         AS body,
       NULL::VARCHAR AS label,
       NULL::VARCHAR AS object_id,
       CASE WHEN r.pid <> '' THEN r.proc || '-' || r.pid END                  AS request_id
FROM p;
\set ds linux
\set pbase 700000
\set title 'Linux syslog of one server (host combo)'
\set description 'Loghub Linux: /var/log/messages of one Linux server (combo), Jun 9 to Feb 28 (year not logged: Jun-Dec = 2005, Jan-Feb = 2006 assumed). No log levels (severity is NULL). Kernel, sshd / ftpd / su authentication, udev, cron, named.'
\set node_meaning 'host name (one host: combo)'
\set location_meaning 'host'
\set request_meaning '<program>-<pid>: one process (pids are reused over months; request_timeline splits sessions at quiet gaps)'
\ir lib/stage_to_logs.sql
