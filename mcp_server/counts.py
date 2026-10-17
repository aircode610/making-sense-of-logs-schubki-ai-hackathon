"""Count tools: exact full-corpus counts by group, and counts over time. Counts are log LINES, never incidents."""
import time
from datetime import datetime, timedelta
from typing import Annotated, Literal, Optional

from pydantic import Field

from core import MAX_ROWS, envelope, filters_sql, query, render

TREND_ROWS = 500  # a time series is long by nature; still capped and flagged
GROUPS = {"dataset": "logs.dataset", "team": "coalesce(o.team, 'unowned')", "component": "logs.component",
          "severity": "logs.severity", "node": "logs.node"}
# Ownership (dataset, component → team) joined only when a team grouping / filter needs it; aliased so columns don't clash.
JOIN = "LEFT JOIN (SELECT dataset AS od, component AS oc, team FROM ownership) o ON o.od = logs.dataset AND o.oc = logs.component"

Dataset = Annotated[Optional[Literal["bgl", "openstack"]], Field(description="Restrict to one dataset; omit for both.")]
GroupBy = Literal["dataset", "team", "component", "severity", "node"]


def _where(f: dict, query_text, status, team) -> tuple[str, dict, bool]:
    """Common filters → (WHERE clause on `logs`, params, needs ownership join)."""
    where, params = filters_sql({k: v for k, v in f.items() if k != "team"})
    where = where.replace(" AND ", " AND logs.")  # qualify columns (the join also has dataset / component)
    if query_text:
        where += " AND logs.body @@ websearch_to_tsquery(%(q)s)"
        params["q"] = query_text
    if status is not None:
        where += " AND logs.status = %(status)s"
        params["status"] = status
    if team is not None:
        where += " AND coalesce(o.team, 'unowned') = %(team)s"
        params["team"] = team
    return "WHERE TRUE" + where, params, team is not None


def count_by(
    group_by: Annotated[GroupBy, Field(description="Group the counts by dataset, owning team, component, severity or node.")],
    dataset: Dataset = None,
    start: Annotated[Optional[datetime], Field(description="Inclusive start time, e.g. '2005-11-02 00:00'.")] = None,
    end: Annotated[Optional[datetime], Field(description="Exclusive end time.")] = None,
    team: Annotated[Optional[str], Field(
        description="Owning team (data/ownership.csv): node-platform, hpc-workloads, cluster-control, cloud-api, "
                    "cloud-compute; 'unowned' for unmapped components.")] = None,
    component: Annotated[Optional[str], Field(description="Exact component, e.g. KERNEL, nova-api.")] = None,
    severity: Annotated[Optional[str], Field(description="Exact severity, e.g. FATAL, ERROR.")] = None,
    node: Annotated[Optional[str], Field(description="Exact node / host.")] = None,
    status: Annotated[Optional[int], Field(description="OpenStack HTTP status, e.g. 500.")] = None,
    query_text: Annotated[Optional[str], Field(
        description='Full-text filter on the message (web-search syntax: words, "phrase", a OR b, -word). '
                    'Letters only: numbers / hex / ids are not searchable.')] = None,
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description=f"Groups to return, largest first (max {MAX_ROWS}).")] = 20,
) -> dict:
    """Exact number of log LINES per group (dataset / team / component / severity / node) over the whole corpus.

    Use it for "how much / which team / which component" questions. Counts cover every line matching the filters,
    not a sample; `total_lines` is the sum over all groups and `groups_total` how many groups exist, so truncated=true
    means only the largest groups are listed. Lines are not incidents: one fault can log thousands of lines.
    """
    t0 = time.perf_counter()
    f = dict(dataset=dataset, start=start, end=end, component=component, severity=severity, node=node, team=team)
    where, params, join = _where(f, query_text, status, team)
    expr = GROUPS[group_by]
    join = join or group_by == "team"
    frm = f"FROM logs {JOIN if join else ''} {where}"
    rows_sql = f"SELECT {expr} AS {group_by}, count(*) AS lines {frm} GROUP BY 1 ORDER BY 2 DESC, 1 LIMIT {limit}"
    sum_sql = f"SELECT count(*) AS total_lines, count(DISTINCT {expr}) AS groups_total {frm}"
    rows, s = query(rows_sql, params), query(sum_sql, params)[0]
    return envelope("count_by", dict(group_by=group_by, query_text=query_text, status=status, limit=limit, **f),
                    [render(rows_sql, params), render(sum_sql, params)], {**f, "status": status},
                    scope=f"{dataset or 'all datasets'}, {start or 'corpus start'} → {end or 'corpus end'}; unit = log lines",
                    rows=rows, t0=t0, total_lines=s["total_lines"], groups_total=s["groups_total"],
                    truncated=s["groups_total"] > len(rows))


def trend(
    bucket: Annotated[Optional[Literal["hour", "day", "week"]], Field(
        description="Time bucket. Omit to choose by the data's span (> 60 days: week, > 3 days: day, else hour); "
                    "weeks start on Monday. The bucket used is returned.")] = None,
    group_by: Annotated[Optional[GroupBy], Field(description="Optional: one series per dataset / team / component / severity / node.")] = None,
    dataset: Dataset = None,
    start: Annotated[Optional[datetime], Field(description="Inclusive start time.")] = None,
    end: Annotated[Optional[datetime], Field(description="Exclusive end time.")] = None,
    team: Annotated[Optional[str], Field(description="Owning team, or 'unowned'.")] = None,
    component: Annotated[Optional[str], Field(description="Exact component, e.g. KERNEL, nova-api.")] = None,
    severity: Annotated[Optional[str], Field(description="Exact severity, e.g. FATAL, ERROR.")] = None,
    node: Annotated[Optional[str], Field(description="Exact node / host.")] = None,
    status: Annotated[Optional[int], Field(description="OpenStack HTTP status, e.g. 500.")] = None,
    query_text: Annotated[Optional[str], Field(description='Full-text filter on the message (web-search syntax).')] = None,
    top_groups: Annotated[int, Field(ge=1, le=20, description="With group_by: keep the N largest groups.")] = 5,
) -> dict:
    """Number of log LINES per time bucket (optionally one series per group), with empty buckets shown as 0.

    Use it for "is it rising / when did it start / week over week" questions. Rows are {bucket_start, [group], lines};
    `bucket_start` is the start of the bucket (a partial first / last bucket is possible: see first_ts / last_ts).
    The sum over all rows equals `total_lines` of count_by with the same filters. Lines are not incidents. Direction
    (rising / falling) is not computed here: compare the numbers.
    """
    t0 = time.perf_counter()
    f = dict(dataset=dataset, start=start, end=end, component=component, severity=severity, node=node, team=team)
    where, params, join = _where(f, query_text, status, team)
    join = join or group_by == "team"
    frm = f"FROM logs {JOIN if join else ''} {where}"
    span_sql = f"SELECT count(*) AS total_lines, min(logs.ts) AS first_ts, max(logs.ts) AS last_ts {frm}"
    span = query(span_sql, params)[0]
    sqls = [render(span_sql, params)]
    scope = f"{dataset or 'all datasets'}, {start or 'corpus start'} → {end or 'corpus end'}; unit = log lines"
    if not span["total_lines"]:
        return envelope("trend", dict(bucket=bucket, group_by=group_by, query_text=query_text, status=status, **f),
                        sqls, {**f, "status": status}, scope, [], t0, bucket=bucket, total_lines=0, truncated=False)
    days = (span["last_ts"] - span["first_ts"]).days
    b = bucket or ("week" if days > 60 else "day" if days > 3 else "hour")
    step = {"hour": "1 hour", "day": "1 day", "week": "7 days"}[b]
    # bounds come from the DB, not the caller: inlined as literals (bound params in generate_series upset the wire protocol)
    lo, hi = (f"TIMESTAMP '{t:%Y-%m-%d %H:%M:%S.%f}'" for t in (span["first_ts"], span["last_ts"]))
    if group_by:
        expr = GROUPS[group_by]
        top_sql = f"SELECT {expr} AS g {frm} GROUP BY 1 ORDER BY count(*) DESC, 1 LIMIT {top_groups}"
        groups = [r["g"] for r in query(top_sql, params)]
        sqls.append(render(top_sql, params))
        glist = ", ".join("('" + str(g).replace("'", "''") + "')" for g in groups)
        rows_sql = (f"SELECT s.b AS bucket_start, g.g AS {group_by}, count(c.ts) AS lines "
                    f"FROM generate_series(date_trunc('{b}', {lo}), {hi}, interval '{step}') s(b) "
                    f"CROSS JOIN (VALUES {glist}) g(g) "
                    f"LEFT JOIN (SELECT logs.ts, {expr} AS g {frm}) c ON date_trunc('{b}', c.ts) = s.b AND c.g = g.g "
                    f"GROUP BY 1, 2 ORDER BY 2, 1 LIMIT {TREND_ROWS + 1}")
    else:
        rows_sql = (f"SELECT s.b AS bucket_start, count(c.ts) AS lines "
                    f"FROM generate_series(date_trunc('{b}', {lo}), {hi}, interval '{step}') s(b) "
                    f"LEFT JOIN (SELECT logs.ts {frm}) c ON date_trunc('{b}', c.ts) = s.b GROUP BY 1 ORDER BY 1 LIMIT {TREND_ROWS + 1}")
    rows = query(rows_sql, params)
    sqls.append(render(rows_sql, params))
    truncated = len(rows) > TREND_ROWS
    rows = rows[:TREND_ROWS]
    return envelope("trend", dict(bucket=b, group_by=group_by, query_text=query_text, status=status, top_groups=top_groups, **f),
                    sqls, {**f, "status": status}, scope, rows, t0, bucket=b, total_lines=span["total_lines"],
                    first_ts=span["first_ts"].isoformat(sep=" "), last_ts=span["last_ts"].isoformat(sep=" "),
                    groups=groups if group_by else None, truncated=truncated,
                    **({"note": f"only the {top_groups} largest groups are shown; their lines are a subset of total_lines"}
                       if group_by else {}))
