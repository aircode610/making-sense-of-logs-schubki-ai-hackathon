"""Pattern tools: recurring log patterns and a computed priority ranking, over patterns and bursts (plan 004 tables). Everything is computed in SQL:
counts, previous-period comparison, percentile ranks and the priority score (weights inlined in the query). No LLM.
"Problem" pattern (plan 006, DECISIONS H18): problem-severity lines AND p_problem >= 0.5, where
p_problem = p_fault × (1 − p_dump) from the stored Jev judgment of the pattern (pattern_judgments, judged once)."""
import time
from datetime import datetime, timedelta
from typing import Annotated, Literal, Optional

from pydantic import Field

from core import MAX_ROWS, envelope, query, render

PROBLEM = "('FATAL', 'FAILURE', 'SEVERE', 'ERROR', 'CRITICAL')"
P_PROBLEM_MIN = 0.5
ProblemFilter = Annotated[Literal["jev", "severity"], Field(
    description="How 'problem pattern' is decided: 'jev' (default) = has problem-severity lines AND the stored Jev "
                "judgment says it reports a real fault, not a diagnostic dump field (p_problem >= 0.5); "
                "'severity' = any FATAL/FAILURE/SEVERE/ERROR line (baseline; ranks routine register dumps high).")]
# Priority weights (fixed up front, returned with every result). Inputs are percentiles (cume_dist) over the candidates.
WEIGHTS = {"frequency": 0.30, "trend": 0.20, "spread": 0.25, "persistence": 0.15, "severity": 0.10}

Ds = Annotated[Literal["bgl", "openstack"], Field(description="Dataset (patterns are per dataset).")]
Start = Annotated[Optional[datetime], Field(description="Period start (inclusive). Default: 28 days before `end`.")]
End = Annotated[Optional[datetime], Field(description="Period end (exclusive). Default: the dataset's last timestamp.")]


def _period(dataset: str, start, end) -> tuple[datetime, datetime, datetime]:
    """(prev_start, start, end): default end = last ts of the dataset ("corpus now"), default length 28 days;
    the previous period has the same length and ends where this one starts."""
    if end is None:
        end = query("SELECT max(ts) AS t FROM logs WHERE dataset = %(d)s", {"d": dataset})[0]["t"] + timedelta(microseconds=1)
    if start is None:
        start = end - timedelta(days=28)
    if start >= end:
        raise ValueError("start must be before end.")
    return start - (end - start), start, end


def _base_sql(problem_only: bool, problem_filter: str = "jev", extra_where: str = "") -> str:
    """One row per pattern with lines in the period: lines, nodes, weeks, problem lines, top-node share,
    bursts started in the period and in the previous period, owner team, first seen in the corpus."""
    return f"""
WITH now AS (
    SELECT pattern_id, count(*) AS lines, count(DISTINCT node) AS nodes,
           count(DISTINCT date_trunc('week', ts)) AS weeks_active,
           count(*) FILTER (WHERE severity IN {PROBLEM}) AS problem_lines
    FROM logs WHERE dataset = %(d)s AND ts >= %(s)s AND ts < %(e)s AND pattern_id IS NOT NULL GROUP BY 1
), top_node AS (
    SELECT pattern_id, max(n) AS top_node_lines FROM (
        SELECT pattern_id, node, count(*) AS n FROM logs
        WHERE dataset = %(d)s AND ts >= %(s)s AND ts < %(e)s AND node IS NOT NULL GROUP BY 1, 2) GROUP BY 1
), b_now AS (
    SELECT pattern_id, count(*) AS bursts FROM bursts WHERE dataset = %(d)s AND start_ts >= %(s)s AND start_ts < %(e)s GROUP BY 1
), b_prev AS (
    SELECT pattern_id, count(*) AS bursts_prev FROM bursts WHERE dataset = %(d)s AND start_ts >= %(ps)s AND start_ts < %(s)s GROUP BY 1
), base AS (
    SELECT p.pattern_id, p.template, p.component, coalesce(o.team, 'unowned') AS team, p.severity,
           now.lines, now.problem_lines, now.nodes, now.weeks_active,
           coalesce(b_now.bursts, 0) AS bursts, coalesce(b_prev.bursts_prev, 0) AS bursts_prev,
           coalesce(b_now.bursts, 0) - coalesce(b_prev.bursts_prev, 0) AS change,
           round(top_node.top_node_lines::DOUBLE / now.lines, 3) AS top_node_share,
           p.first_ts AS first_seen, p.first_ts >= %(s)s AS new,
           round(j.p_fault, 3) AS p_fault, round(j.p_dump, 3) AS p_dump,
           round(j.p_fault * (1 - j.p_dump), 3) AS p_problem, j.kind
    FROM now JOIN patterns p ON p.dataset = %(d)s AND p.pattern_id = now.pattern_id
    LEFT JOIN pattern_judgments j ON j.dataset = %(d)s AND j.pattern_id = now.pattern_id
    LEFT JOIN ownership o ON o.dataset = %(d)s AND o.component = p.component
    LEFT JOIN top_node ON top_node.pattern_id = now.pattern_id
    LEFT JOIN b_now ON b_now.pattern_id = now.pattern_id LEFT JOIN b_prev ON b_prev.pattern_id = now.pattern_id
    WHERE TRUE {_problem_where(problem_filter) if problem_only else ""} {extra_where}
)"""


def _problem_where(problem_filter: str) -> str:
    w = "AND now.problem_lines > 0"
    return w if problem_filter == "severity" else w + f" AND j.p_fault * (1 - j.p_dump) >= {P_PROBLEM_MIN}"


def _params(dataset, ps, s, e, **kw) -> dict:
    return {"d": dataset, "ps": ps, "s": s, "e": e, **{k: v for k, v in kw.items() if v is not None}}


def top_patterns(
    dataset: Ds,
    start: Start = None,
    end: End = None,
    team: Annotated[Optional[str], Field(
        description="Owning team: node-platform, hpc-workloads, cluster-control, cloud-api, cloud-compute, unowned.")] = None,
    component: Annotated[Optional[str], Field(description="Exact component, e.g. KERNEL.")] = None,
    problem_only: Annotated[bool, Field(description="Only problem patterns (see problem_filter).")] = True,
    problem_filter: ProblemFilter = "jev",
    rank_by: Annotated[Literal["bursts", "nodes", "lines", "growth"], Field(
        description="'bursts' = how often it recurs (default), 'nodes' = how widespread, 'lines' = log volume "
                    "(inflated by storms), 'growth' = bursts now minus bursts in the previous period.")] = "bursts",
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description=f"Patterns to return (max {MAX_ROWS}).")] = 20,
) -> dict:
    """Recurring problems in a period: which log patterns recur, how often, where, whose, and whether they grow.

    One row per pattern (a log message template, numbers/ids masked): template, component, owner team, lines, bursts
    (= recurrences: same pattern anywhere, split by > 30 min quiet), nodes, weeks_active, bursts_prev (previous period
    of equal length) and change, new (first seen in the corpus inside the period), top_node_share (1.0 = one node only),
    p_fault / p_dump / p_problem / kind (stored Jev judgment of the pattern: calibrated probabilities, not counts).
    Period defaults to the last 28 days of the dataset; both periods are returned as absolute dates.
    Bursts count recurrences, not confirmed incidents; lines count log entries.
    """
    t0 = time.perf_counter()
    ps, s, e = _period(dataset, start, end)
    extra = (" AND coalesce(o.team, 'unowned') = %(team)s" if team else "") + (" AND p.component = %(comp)s" if component else "")
    order = {"bursts": "bursts DESC, nodes DESC", "nodes": "nodes DESC, bursts DESC", "lines": "lines DESC",
             "growth": "change DESC, bursts DESC"}[rank_by]
    sql = _base_sql(problem_only, problem_filter, extra) + f"""
SELECT *, count(*) OVER () AS candidates FROM base ORDER BY {order}, pattern_id LIMIT {limit}"""
    params = _params(dataset, ps, s, e, team=team, comp=component)
    rows = query(sql, params)
    n = rows[0]["candidates"] if rows else 0
    for r in rows:
        del r["candidates"]
    f = dict(dataset=dataset, start=s, end=e, team=team, component=component)
    return envelope("top_patterns", dict(problem_only=problem_only, problem_filter=problem_filter, rank_by=rank_by,
                                         limit=limit, **f), [render(sql, params)], f,
                    scope=f"{dataset}, period {s:%Y-%m-%d %H:%M} → {e:%Y-%m-%d %H:%M}, previous {ps:%Y-%m-%d %H:%M} → {s:%Y-%m-%d %H:%M}; "
                          f"bursts = recurrences (30-min gap), lines = log entries",
                    rows=rows, t0=t0, total_matches=n, truncated=n > len(rows),
                    period={"start": s.isoformat(sep=" "), "end": e.isoformat(sep=" ")},
                    previous_period={"start": ps.isoformat(sep=" "), "end": s.isoformat(sep=" ")})


def priority_table(
    dataset: Ds,
    start: Start = None,
    end: End = None,
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description="Ranked problems to return (max 50).")] = 10,
    problem_filter: ProblemFilter = "jev",
) -> dict:
    """Computed priority ranking of problem patterns for a period, plus a per-team roll-up.

    score (0-100) = 100 × Σ weight × percentile (share of candidates with a value ≤ this one) among all problem
    patterns of the period, for five MEASURED
    inputs: frequency = bursts, trend = bursts − bursts in the previous period, spread = distinct nodes,
    persistence = weeks active / weeks in the period, severity = p_problem (stored Jev judgment that the pattern
    reports a real fault; with problem_filter='severity': share of problem-severity lines). Weights and each
    item's per-input contribution are returned, so every score can be recomputed. Raw line counts are shown but not
    used for ranking. The ranking says what the logs measure; it does not know cost, downtime or customer impact.
    """
    t0 = time.perf_counter()
    ps, s, e = _period(dataset, start, end)
    # calendar weeks (Monday start, as date_trunc('week')) the period touches, so persistence ≤ 1
    monday = lambda t: (t - timedelta(days=t.weekday())).date()
    weeks = (monday(e - timedelta(microseconds=1)) - monday(s)).days // 7 + 1
    w = WEIGHTS
    sev = "p_problem" if problem_filter == "jev" else "round(problem_lines::DOUBLE / lines, 3)"
    sql = _base_sql(True, problem_filter) + f""",
inputs AS (
    SELECT *, round(weeks_active::DOUBLE / {weeks}, 3) AS persistence,
              round(problem_lines::DOUBLE / lines, 3) AS problem_share, {sev} AS severity_input
    FROM base
), ranked AS (
    SELECT *,
        cume_dist() OVER (ORDER BY bursts)        AS pr_frequency,
        cume_dist() OVER (ORDER BY change)        AS pr_trend,
        cume_dist() OVER (ORDER BY nodes)         AS pr_spread,
        cume_dist() OVER (ORDER BY persistence)   AS pr_persistence,
        cume_dist() OVER (ORDER BY severity_input) AS pr_severity
    FROM inputs
)
SELECT *, round(100 * ({w['frequency']} * pr_frequency + {w['trend']} * pr_trend + {w['spread']} * pr_spread
                       + {w['persistence']} * pr_persistence + {w['severity']} * pr_severity), 1) AS score
FROM ranked ORDER BY score DESC, bursts DESC, pattern_id"""
    params = _params(dataset, ps, s, e)
    allrows = query(sql, params)
    items = []
    for i, r in enumerate(allrows[:limit], 1):
        items.append({
            "rank": i, "pattern_id": r["pattern_id"], "template": r["template"], "component": r["component"],
            "team": r["team"], "score": r["score"], "new": r["new"],
            "inputs": {"bursts": r["bursts"], "bursts_prev": r["bursts_prev"], "change": r["change"], "nodes": r["nodes"],
                       "weeks_active": r["weeks_active"], "persistence": r["persistence"],
                       "problem_share": r["problem_share"], "p_problem": r["p_problem"], "severity_input": r["severity_input"],
                       "lines": r["lines"], "top_node_share": r["top_node_share"]},
            "judgment": {"p_fault": r["p_fault"], "p_dump": r["p_dump"], "kind": r["kind"]},
            "contributions": {k: round(100 * w[k] * r[f"pr_{k}"], 1) for k in w},
        })
    teams = {}
    for r in allrows:  # roll-up over ALL problem patterns of the period, not only the top items
        t = teams.setdefault(r["team"], {"team": r["team"], "problem_patterns": 0, "bursts": 0, "bursts_prev": 0,
                                         "lines": 0, "top_item": None})
        t["problem_patterns"] += 1
        t["bursts"] += r["bursts"]
        t["bursts_prev"] += r["bursts_prev"]
        t["lines"] += r["lines"]
        if t["top_item"] is None:  # allrows is sorted by score
            t["top_item"] = {"pattern_id": r["pattern_id"], "template": r["template"], "score": r["score"]}
    rollup = sorted(teams.values(), key=lambda t: -t["bursts"])
    for t in rollup:
        t["change"] = t["bursts"] - t["bursts_prev"]
    f = dict(dataset=dataset, start=s, end=e)
    env = envelope("priority_table", dict(limit=limit, problem_filter=problem_filter, **f), [render(sql, params)], f,
                   scope=f"{dataset}, period {s:%Y-%m-%d %H:%M} → {e:%Y-%m-%d %H:%M} ({weeks} weeks), previous "
                         f"{ps:%Y-%m-%d %H:%M} → {s:%Y-%m-%d %H:%M}; candidates = problem patterns ({problem_filter} filter)",
                   rows=[], t0=t0, total_matches=len(allrows), truncated=len(allrows) > len(items),
                   weights=w, formula="score = 100 × Σ weight × cume_dist(input) over all candidates (share of candidates with a value ≤ this one)",
                   period={"start": s.isoformat(sep=" "), "end": e.isoformat(sep=" ")},
                   previous_period={"start": ps.isoformat(sep=" "), "end": s.isoformat(sep=" ")})
    del env["rows"]
    env.update(items=items, team_rollup=rollup,
               unknown="Cost, downtime, customer impact and root cause are not in these logs.")
    return env
