"""Every SereneDB query for GAIA (plan 002). `{s}` = schema. Params: %(t1)s / %(t2)s window bounds (TIMESTAMP).

Tables: {s}.otel_logs (raw rows of question windows, via OTLP), {s}.gaia_rollup (minute, service, severity_text,
pattern_id, n) for the whole period, {s}.gaia_error_traces (minute, service, n_error_traces), {s}.gaia_catalog.
History = the 24 h before the window (H-5: fixed window, not corpus-relative); usual = per 15 min over the history
minutes that exist (the first hours of a period have less history).
"""

SERVICES = ["dbservice1", "dbservice2", "logservice1", "logservice2", "mobservice1", "mobservice2",
            "redisservice1", "redisservice2", "webservice1", "webservice2"]

LOAD_ROLLUP = """
CREATE OR REPLACE TABLE {s}.gaia_rollup AS
SELECT CAST(minute AS TIMESTAMP) AS minute, service, severity_text, pattern_id, sum(n) AS n
FROM read_csv('{path}', header = true,
              columns = {{'minute': 'VARCHAR', 'service': 'VARCHAR', 'severity_text': 'VARCHAR',
                         'pattern_id': 'VARCHAR', 'n': 'BIGINT'}})
GROUP BY ALL
"""

LOAD_ERROR_TRACES = """
CREATE OR REPLACE TABLE {s}.gaia_error_traces AS
SELECT CAST(minute AS TIMESTAMP) AS minute, service, sum(n_error_traces) AS n_error_traces
FROM read_csv('{path}', header = true,
              columns = {{'minute': 'VARCHAR', 'service': 'VARCHAR', 'n_error_traces': 'BIGINT'}})
GROUP BY ALL
"""

# Number of 15-min blocks of history that exist before the window (<= 96).
HISTORY_BLOCKS = """
SELECT greatest(1, ceil(count(DISTINCT minute) / 15.0)) AS blocks
FROM {s}.gaia_rollup
WHERE minute >= CAST(%(t1)s AS TIMESTAMP) - INTERVAL 24 HOUR AND minute < CAST(%(t1)s AS TIMESTAMP)
"""

# E1: every (service, severity, pattern) in the window vs the same service's last 24 h.
WINDOW_PATTERNS = """
WITH w AS (
    SELECT service, severity_text, pattern_id, sum(n) AS n_window, min(minute) AS first_minute
    FROM {s}.gaia_rollup
    WHERE minute >= CAST(%(t1)s AS TIMESTAMP) AND minute < CAST(%(t2)s AS TIMESTAMP)
    GROUP BY ALL),
h AS (
    SELECT service, severity_text, pattern_id, sum(n) AS n_hist
    FROM {s}.gaia_rollup
    WHERE minute >= CAST(%(t1)s AS TIMESTAMP) - INTERVAL 24 HOUR AND minute < CAST(%(t1)s AS TIMESTAMP)
    GROUP BY ALL)
SELECT w.service, w.severity_text, w.pattern_id, w.n_window,
       coalesce(h.n_hist, 0) / %(blocks)s                                AS usual_per_15min,
       (w.n_window + 1.0) / (coalesce(h.n_hist, 0) / %(blocks)s + 1.0)   AS ratio,
       coalesce(h.n_hist, 0) = 0                                         AS new_in_24h,
       floor(epoch(w.first_minute) - epoch(CAST(%(t1)s AS TIMESTAMP))) / 60 AS first_minute_offset
FROM w LEFT JOIN h USING (service, severity_text, pattern_id)
"""

# E2: per-service volume and ERROR volume vs usual, and the first minute the service's ERROR rate spiked
# (> 3x its usual per-minute ERROR count + 3).
WINDOW_SERVICES = """
WITH wm AS (
    SELECT service, minute, sum(n) AS n, coalesce(sum(n) FILTER (WHERE severity_text = 'ERROR'), 0) AS e
    FROM {s}.gaia_rollup
    WHERE minute >= CAST(%(t1)s AS TIMESTAMP) AND minute < CAST(%(t2)s AS TIMESTAMP)
    GROUP BY ALL),
h AS (
    SELECT service, sum(n) AS n_hist, coalesce(sum(n) FILTER (WHERE severity_text = 'ERROR'), 0) AS e_hist
    FROM {s}.gaia_rollup
    WHERE minute >= CAST(%(t1)s AS TIMESTAMP) - INTERVAL 24 HOUR AND minute < CAST(%(t1)s AS TIMESTAMP)
    GROUP BY ALL)
SELECT wm.service,
       sum(wm.n)                                          AS n_window,
       sum(wm.e)                                          AS err_window,
       coalesce(any_value(h.n_hist), 0) / %(blocks)s      AS usual_n,
       coalesce(any_value(h.e_hist), 0) / %(blocks)s      AS usual_err,
       min(floor((epoch(wm.minute) - epoch(CAST(%(t1)s AS TIMESTAMP))) / 60))
           FILTER (WHERE wm.e > 3 * coalesce(h.e_hist, 0) / (%(blocks)s * 15.0) + 3) AS first_spike_offset
FROM wm LEFT JOIN h USING (service)
GROUP BY wm.service
"""

# Example line + first time of each (service, pattern) in the window (raw rows).
WINDOW_EXAMPLES = """
SELECT service_name AS service, log_attributes ->> 'pattern_id' AS pattern_id,
       left(any_value(body ORDER BY "timestamp"), %(chars)s) AS example_line
FROM {s}.otel_logs
WHERE "timestamp" >= CAST(%(t1)s AS TIMESTAMP) AND "timestamp" < CAST(%(t2)s AS TIMESTAMP)
  AND service_name IN ('dbservice1','dbservice2','logservice1','logservice2','mobservice1','mobservice2',
                       'redisservice1','redisservice2','webservice1','webservice2')
GROUP BY 1, 2
"""

# E3 + B2: raw lines of the window (time order).
WINDOW_RAW = """
SELECT "timestamp", service_name AS service, severity_text, severity_number, log_attributes ->> 'pattern_id' AS pattern_id,
       body
FROM {s}.otel_logs
WHERE "timestamp" >= CAST(%(t1)s AS TIMESTAMP) AND "timestamp" < CAST(%(t2)s AS TIMESTAMP)
  AND service_name IN ('dbservice1','dbservice2','logservice1','logservice2','mobservice1','mobservice2',
                       'redisservice1','redisservice2','webservice1','webservice2')
  AND severity_number >= %(min_sev)s
ORDER BY "timestamp"
"""

WINDOW_HEAD_TAIL = """
(SELECT "timestamp", service_name AS service, severity_text, body FROM {s}.otel_logs
 WHERE "timestamp" >= CAST(%(t1)s AS TIMESTAMP) AND "timestamp" < CAST(%(t2)s AS TIMESTAMP)
   AND service_name LIKE '%%service%%' ORDER BY "timestamp" LIMIT %(n)s)
UNION ALL
(SELECT "timestamp", service_name AS service, severity_text, body FROM {s}.otel_logs
 WHERE "timestamp" >= CAST(%(t1)s AS TIMESTAMP) AND "timestamp" < CAST(%(t2)s AS TIMESTAMP)
   AND service_name LIKE '%%service%%' ORDER BY "timestamp" DESC LIMIT %(n)s)
"""

# E0 (001's A4 as reference): corpus-relative rarity = in how many of the corpus windows a pattern appears.
CORPUS_PATTERN_WINDOWS = """
SELECT r.pattern_id, count(DISTINCT w.wid) AS n_windows
FROM {s}.gaia_rollup r JOIN {s}.gaia_windows w ON r.minute >= w.t1 AND r.minute < w.t2
GROUP BY 1
"""

# Manager: extra failed requests (distinct request ids with an ERROR) in a window vs the usual 15 min, system-wide.
WINDOW_FAILED_REQUESTS = """
WITH w AS (SELECT sum(n_error_traces) AS n FROM {s}.gaia_error_traces
           WHERE minute >= CAST(%(t1)s AS TIMESTAMP) AND minute < CAST(%(t2)s AS TIMESTAMP)),
h AS (SELECT sum(n_error_traces) AS n FROM {s}.gaia_error_traces
      WHERE minute >= CAST(%(t1)s AS TIMESTAMP) - INTERVAL 24 HOUR AND minute < CAST(%(t1)s AS TIMESTAMP))
SELECT coalesce(w.n, 0) AS failed_in_window, coalesce(h.n, 0) / %(blocks)s AS usual_failed,
       greatest(0, coalesce(w.n, 0) - coalesce(h.n, 0) / %(blocks)s) AS extra_failed
FROM w, h
"""
