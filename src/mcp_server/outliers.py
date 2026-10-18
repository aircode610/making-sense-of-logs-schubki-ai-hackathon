"""Value outliers: operations far slower than their own pattern's normal (plan 054; generic since plan 012).

A pattern's lines share one template, so their durations are comparable. The duration is the generic `duration_ms`
column, filled by each dataset's loader from whatever its format logs (request times, "took N seconds" steps, ...): no
message parsing here. Baseline = the pattern over the whole dataset; flagged = lines in the period above
max(median + k * MAD, median + min_excess_s). Robust stats (median, MAD), so the outliers themselves barely move the
baseline. The rule is fixed in code, never LLM-judged.
"""
import time
from datetime import datetime
from typing import Annotated, Optional

from pydantic import Field

from core import MAX_ROWS, Dataset, ObjectId, check_dataset, durations_in, envelope, query, registry, render

# Value in seconds (generic column, see the module docstring).
VALUE = "duration_ms / 1000.0"
# Patterns that carry a duration.
CANDIDATES = "SELECT DISTINCT pattern_id FROM logs WHERE dataset = %(d)s AND duration_ms IS NOT NULL"


def value_outliers(
    dataset: Dataset,
    pattern_id: Annotated[Optional[int], Field(description="Only this pattern (from top_patterns / search_logs).")] = None,
    object_id: ObjectId = None,
    start: Annotated[Optional[datetime], Field(description="Flag lines from this time (baseline stays the whole dataset).")] = None,
    end: Annotated[Optional[datetime], Field(description="Flag lines before this time (exclusive).")] = None,
    k: Annotated[float, Field(ge=1, le=20, description="Threshold = median + k × MAD (robust spread).")] = 6.0,
    min_excess_s: Annotated[float, Field(ge=0, description="A flagged value is also at least this many seconds above the median.")] = 2.0,
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description=f"Flagged lines to return, most extreme first (max {MAX_ROWS}).")] = 20,
) -> dict:
    """Which operations took far longer than normal for their own kind? Slow steps that log no error.

    Use when: "slow", "took long", "latency", "performance", "which requests / VMs / objects were abnormal" and the
    logs carry durations (datasets with durations: {durations}). The problem is an unusual number inside a
    normal message, not an error line.
    Not for: latency percentiles and error rates per group (latency_profile), error messages (search_logs).
    Returns: baselines per pattern (n, median, p95, MAD, threshold, flagged), flagged objects (max ratio, lines,
    first time) and flagged lines (value_s, ratio = value / median, ids); total_matches = flagged lines.
    Caveats: a flag says "unusually slow for this step", not why. Datasets without durations return nothing.
    Example: value_outliers(dataset=<dataset with durations>, start='<period start>')
    Next: request_timeline(object_id=… or request_id=…) for a flagged one; get_context(line_id) around the slow line.
    """
    t0 = time.perf_counter()
    check_dataset(dataset)
    params = {"d": dataset, "k": k, "x": min_excess_s}
    where = ""
    for col, v in (("pattern_id", pattern_id), ("object_id", object_id)):
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
    SELECT l.line_id, l.ts, l.pattern_id, l.object_id, l.request_id, l.{VALUE} AS value_s, l.body
    FROM logs l WHERE l.dataset = %(d)s AND l.pattern_id IN (SELECT pattern_id FROM t){where}
)"""
    flagged = "FROM f JOIN t USING (pattern_id) WHERE f.value_s > t.threshold"
    rows_sql = (f"{with_sql} SELECT f.line_id, f.ts, f.pattern_id, f.object_id, f.request_id, round(f.value_s, 3) AS value_s, "
                f"round(t.med, 3) AS median_s, round(f.value_s / t.med, 2) AS ratio, f.body {flagged} "
                f"ORDER BY ratio DESC, f.ts LIMIT {limit}")
    base_sql = (f"{with_sql} SELECT t.pattern_id, p.template, t.n, round(t.med, 3) AS median_s, round(t.p95, 3) AS p95_s, "
                f"round(t.mad, 3) AS mad_s, round(t.threshold, 3) AS threshold_s, "
                f"count(*) FILTER (WHERE f.value_s > t.threshold) AS flagged "
                f"FROM t JOIN patterns p ON p.dataset = %(d)s AND p.pattern_id = t.pattern_id "
                f"LEFT JOIN f ON f.pattern_id = t.pattern_id "
                f"GROUP BY ALL ORDER BY flagged DESC, t.n DESC")
    sum_sql = (f"{with_sql} SELECT count(*) AS total_matches, count(DISTINCT f.object_id) AS flagged_objects {flagged}")
    # One row per flagged object (all of them up to MAX_ROWS): the list survives even when the line rows are cut.
    inst_sql = (f"{with_sql} SELECT f.object_id, max(round(f.value_s / t.med, 2)) AS max_ratio, count(*) AS flagged_lines, "
                f"min(f.ts) AS first_ts {flagged} AND f.object_id IS NOT NULL GROUP BY 1 ORDER BY 2 DESC LIMIT {MAX_ROWS}")
    rows, baselines, s = query(rows_sql, params), query(base_sql, params), query(sum_sql, params)[0]
    instances = query(inst_sql, params)
    f = dict(dataset=dataset, pattern_id=pattern_id, object_id=object_id, start=start, end=end)
    return envelope("value_outliers", dict(k=k, min_excess_s=min_excess_s, limit=limit, **f),
                    [render(rows_sql, params), render(base_sql, params), render(sum_sql, params), render(inst_sql, params)], f,
                    scope=f"{dataset}, flagged {start or 'corpus start'} → {end or 'corpus end'}; baseline = each "
                          f"pattern over the whole dataset; threshold = max(median + {k:g}×MAD, median + {min_excess_s:g} s); "
                          f"unit = log lines (one slow operation = one line); duration = "
                          + (registry()[dataset].get("duration_meaning") or "not logged in this dataset"),
                    rows=rows, t0=t0, total_matches=s["total_matches"], flagged_objects=s["flagged_objects"],
                    truncated=s["total_matches"] > len(rows), baselines=baselines, objects=instances)


value_outliers.__doc__ = value_outliers.__doc__.replace("{durations}", durations_in())
