"""Every SereneDB query the pipeline runs. `{s}` = schema (dev or other), filled by the caller.

Notes for calibration / debugging:
- Job scope = resource attribute `application.id` (JSON ->>, a column scan; fine at this size, revisit if slow).
- Pattern id per row = `log_attributes ->> 'pattern_id'` (D3).
- All numbers shown to Jev / the LLM come from these queries; words are derived from them in pipeline/bricks.py.
"""

# Brick 1 - Pattern: per-pattern stats across the whole corpus in this schema (rarity baseline).
PATTERN_STATS = """
SELECT log_attributes ->> 'pattern_id'                                   AS pattern_id,
       count(*)                                                          AS n_lines,
       count(DISTINCT resource_attributes ->> 'application.id')          AS n_jobs,
       max(severity_number)                                              AS max_severity
FROM {s}.otel_logs
WHERE service_name = %(service)s
GROUP BY 1
"""

TOTAL_JOBS = """
SELECT count(DISTINCT resource_attributes ->> 'application.id') AS n
FROM {s}.otel_logs WHERE service_name = %(service)s
"""

# Brick 2 - Evidence: job-level facts.
JOB_FACTS = """
SELECT min("timestamp")                                                   AS t0,
       max("timestamp")                                                   AS t1,
       count(DISTINCT resource_attributes ->> 'container.id')             AS n_containers,
       count(*)                                                           AS n_lines,
       count(*) FILTER (WHERE severity_number >= 21)                      AS n_fatal,
       count(*) FILTER (WHERE severity_number >= 17 AND severity_number < 21) AS n_error,
       count(*) FILTER (WHERE severity_number >= 13 AND severity_number < 17) AS n_warn
FROM {s}.otel_logs
WHERE service_name = %(service)s AND resource_attributes ->> 'application.id' = %(job)s
"""

# Brick 2 - Evidence: WARN+ patterns of the job with counts, spread and first appearance.
JOB_PATTERNS = """
SELECT log_attributes ->> 'pattern_id'                                   AS pattern_id,
       max(severity_number)                                              AS max_severity,
       any_value(severity_text ORDER BY severity_number DESC)            AS severity_text,
       count(*)                                                          AS n,
       count(DISTINCT resource_attributes ->> 'container.id')            AS n_containers,
       min("timestamp")                                                  AS first_seen,
       left(any_value(body ORDER BY "timestamp"), %(chars)s)             AS example_line
FROM {s}.otel_logs
WHERE service_name = %(service)s
  AND resource_attributes ->> 'application.id' = %(job)s
  AND severity_number >= %(min_sev)s
GROUP BY 1
"""

# Baseline B2: raw lines of a job (WARN+ plus head and tail).
JOB_RAW_LINES = """
SELECT "timestamp", severity_text, body, severity_number
FROM {s}.otel_logs
WHERE service_name = %(service)s AND resource_attributes ->> 'application.id' = %(job)s
ORDER BY "timestamp"
"""

# Brick 2 - Evidence (A4): typical job duration in the corpus (median, seconds). Label-free baseline for "longer than usual".
TYPICAL_DURATION = """
SELECT median(d) AS median_s FROM (
    SELECT epoch(max("timestamp")) - epoch(min("timestamp")) AS d
    FROM {s}.otel_logs WHERE service_name = %(service)s
    GROUP BY resource_attributes ->> 'application.id'
) t
"""
