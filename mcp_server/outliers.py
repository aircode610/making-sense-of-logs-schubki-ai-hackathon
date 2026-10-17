"""Value outliers: operations far slower than their own pattern's normal (plan 054).

A pattern's lines share one template, so their durations are comparable: "Took N seconds to spawn" or the HTTP request
time (latency_ms). Baseline = the pattern over the whole dataset; flagged = lines in the period above
max(median + k * MAD, median + min_excess_s). Robust stats (median, MAD), so the outliers themselves barely move the
baseline. The rule is fixed in code, never LLM-judged.
"""
import time
from datetime import datetime
from typing import Annotated, Literal, Optional

from pydantic import Field

from core import MAX_ROWS, envelope, query, render

# Value in seconds: HTTP request time, or the number in a "Took <N> seconds ..." message.
VALUE = ("coalesce(latency_ms / 1000.0, "
         "CAST(nullif(regexp_extract(body, 'Took ([\\d.]+) seconds', 1), '') AS DOUBLE))")
# Patterns that carry such a value (template text from load time).
CANDIDATES = ("SELECT pattern_id FROM patterns WHERE dataset = %(d)s "
              "AND (strpos(template, 'Took <N> seconds') > 0 OR strpos(template, ' time: <N>') > 0)")


def value_outliers(
    dataset: Annotated[Literal["bgl", "openstack"], Field(
        description="Dataset. Durations exist in OpenStack (spawn / build / destroy times, HTTP request times).")],
    pattern_id: Annotated[Optional[int], Field(description="Only this pattern (from top_patterns / search_logs).")] = None,
    instance_id: Annotated[Optional[str], Field(description="Only lines of this OpenStack VM.")] = None,
    start: Annotated[Optional[datetime], Field(description="Flag lines from this time (baseline stays the whole dataset).")] = None,
    end: Annotated[Optional[datetime], Field(description="Flag lines before this time (exclusive).")] = None,
    k: Annotated[float, Field(ge=1, le=20, description="Threshold = median + k × MAD (robust spread).")] = 6.0,
    min_excess_s: Annotated[float, Field(ge=0, description="A flagged value is also at least this many seconds above the median.")] = 2.0,
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description=f"Flagged lines to return, most extreme first (max {MAX_ROWS}).")] = 20,
) -> dict:
    """Operations that took far longer than normal FOR THEIR OWN PATTERN, e.g. VM spawns at 50 s when that step
    normally takes 20 s, or API requests at 2 s when they normally take 0.25 s.

    Use it for "slow / took long / latency / performance / which VMs were abnormal" questions: problems that log no
    error, only an unusual number inside a normal message. Returns `baselines` (per pattern: n, median, p95, MAD,
    threshold, flagged count, template), `instances` (every flagged VM: max ratio, flagged lines, first time) and the
    flagged lines (value_s, ratio = value / median, ids). total_matches = all flagged lines; `flagged_instances` =
    distinct VMs among them. A flag says "unusually slow", not why.
    """
    t0 = time.perf_counter()
    params = {"d": dataset, "k": k, "x": min_excess_s}
    where = ""
    for col, v in (("pattern_id", pattern_id), ("instance_id", instance_id)):
        if v is not None:
            where += f" AND l.{col} = %({col})s"
            params[col] = v
    if start is not None:
        where += " AND l.ts >= %(start)s"
        params["start"] = start
    if end is not None:
        where += " AND l.ts < %(end)s"
        params["end"] = end
    base_pat = " AND pattern_id = %(pattern_id)s" if pattern_id is not None else ""
    # Baseline per pattern over the whole dataset; MAD = median absolute deviation (robust: outliers barely move it).
    with_sql = f"""WITH b AS (
    SELECT pattern_id, count(*) AS n, median(v) AS med, mad(v) AS mad, quantile_cont(v, 0.95) AS p95
    FROM (SELECT pattern_id, {VALUE} AS v FROM logs
          WHERE dataset = %(d)s AND pattern_id IN ({CANDIDATES}){base_pat}) WHERE v IS NOT NULL GROUP BY 1
), t AS (SELECT *, greatest(med + %(k)s * mad, med + %(x)s) AS threshold FROM b
), f AS (
    SELECT l.line_id, l.ts, l.pattern_id, l.instance_id, l.request_id, {VALUE.replace('latency_ms', 'l.latency_ms').replace('(body', '(l.body')} AS value_s, l.body
    FROM logs l WHERE l.dataset = %(d)s AND l.pattern_id IN (SELECT pattern_id FROM t){where}
)"""
    flagged = "FROM f JOIN t USING (pattern_id) WHERE f.value_s > t.threshold"
    rows_sql = (f"{with_sql} SELECT f.line_id, f.ts, f.pattern_id, f.instance_id, f.request_id, round(f.value_s, 3) AS value_s, "
                f"round(t.med, 3) AS median_s, round(f.value_s / t.med, 2) AS ratio, f.body {flagged} "
                f"ORDER BY ratio DESC, f.ts LIMIT {limit}")
    base_sql = (f"{with_sql} SELECT t.pattern_id, p.template, t.n, round(t.med, 3) AS median_s, round(t.p95, 3) AS p95_s, "
                f"round(t.mad, 3) AS mad_s, round(t.threshold, 3) AS threshold_s, "
                f"count(*) FILTER (WHERE f.value_s > t.threshold) AS flagged "
                f"FROM t JOIN patterns p ON p.dataset = %(d)s AND p.pattern_id = t.pattern_id "
                f"LEFT JOIN f ON f.pattern_id = t.pattern_id "
                f"GROUP BY ALL ORDER BY flagged DESC, t.n DESC")
    sum_sql = (f"{with_sql} SELECT count(*) AS total_matches, count(DISTINCT f.instance_id) AS flagged_instances {flagged}")
    # One row per flagged VM (all of them up to MAX_ROWS): the VM list survives even when the line rows are cut.
    inst_sql = (f"{with_sql} SELECT f.instance_id, max(round(f.value_s / t.med, 2)) AS max_ratio, count(*) AS flagged_lines, "
                f"min(f.ts) AS first_ts {flagged} AND f.instance_id IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT {MAX_ROWS}")
    rows, baselines, s = query(rows_sql, params), query(base_sql, params), query(sum_sql, params)[0]
    instances = query(inst_sql, params)
    f = dict(dataset=dataset, pattern_id=pattern_id, instance_id=instance_id, start=start, end=end)
    return envelope("value_outliers", dict(k=k, min_excess_s=min_excess_s, limit=limit, **f),
                    [render(rows_sql, params), render(base_sql, params), render(sum_sql, params), render(inst_sql, params)], f,
                    scope=f"{dataset}, flagged {start or 'corpus start'} → {end or 'corpus end'}; baseline = each "
                          f"pattern over the whole dataset; threshold = max(median + {k:g}×MAD, median + {min_excess_s:g} s); "
                          f"unit = log lines (one slow operation = one line)",
                    rows=rows, t0=t0, total_matches=s["total_matches"], flagged_instances=s["flagged_instances"],
                    truncated=s["total_matches"] > len(rows), baselines=baselines, instances=instances)
