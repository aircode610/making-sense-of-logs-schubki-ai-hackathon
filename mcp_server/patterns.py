"""Pattern tools: recurring log patterns and a computed priority ranking, over patterns and bursts (plan 004 tables). Everything is computed in SQL:
counts, previous-period comparison, percentile ranks and the priority score (weights inlined in the query). No LLM.
"Problem" pattern (plan 006, DECISIONS H18): problem-severity lines AND p_problem >= 0.5, where
p_problem = max(p_fault × (1 − p_dump), p_threat) from the stored Jev judgments of the pattern (pattern_judgments,
judged once; p_threat = security event, plan 011)."""
import time
from datetime import datetime, timedelta
from typing import Annotated, Literal, Optional

from pydantic import Field

from core import (MAX_ROWS, Component, Dataset, Team, check_dataset, envelope, is_problem, judged, judged_note,
                  node_note, query, render)

PROBLEM = "('FATAL', 'FAILURE', 'SEVERE', 'ERROR', 'CRITICAL')"
# A problem-LEVEL line (candidate; the stored Jev judgment then decides): error-or-worse, WARN (some formats log real
# faults at WARN, plan 011), a 5xx status (a failed request logged at INFO, plan 054), or a format without levels.
PROBLEM_LINE = f"(severity IN {PROBLEM} OR severity IN ('WARN', 'WARNING') OR status >= 500 OR severity IS NULL)"
# The same without "no level": the problem rule of a dataset without Jev judgments (plan 016; see core.is_problem).
ERROR_LINE = f"(severity IN {PROBLEM} OR severity IN ('WARN', 'WARNING') OR status >= 500)"
P_PROBLEM_MIN = 0.5
ProblemFilter = Annotated[Literal["jev", "severity"], Field(
    description="How 'problem pattern' is decided: 'jev' (default) = has problem-level lines (error-or-worse, WARN, "
                "5xx status, or no level in the format) AND the stored Jev judgment says it reports a real fault (not a "
                "routine diagnostic dump) or a security event (p_problem >= 0.5); 'severity' = level / status only "
                "(the naive rule, kept for comparison).")]
# Priority weights (fixed up front, returned with every result). Inputs are percentiles (cume_dist) over the candidates.
WEIGHTS = {"frequency": 0.30, "trend": 0.20, "spread": 0.25, "persistence": 0.15, "severity": 0.10}

Ds = Dataset
Start = Annotated[Optional[datetime], Field(description="Period start (inclusive), 'YYYY-MM-DD'. Default: 28 days before `end`.")]
End = Annotated[Optional[datetime], Field(description="Period end (exclusive). Default: just after the dataset's last line "
                                                      "('now' of that dataset).")]


def _period(dataset: str, start, end) -> tuple[datetime, datetime, datetime]:
    """(prev_start, start, end): default end = last ts of the dataset ("corpus now"), default length 28 days;
    the previous period has the same length and ends where this one starts."""
    check_dataset(dataset)
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
           count(*) FILTER (WHERE {PROBLEM_LINE}) AS problem_lines,
           count(*) FILTER (WHERE {ERROR_LINE}) AS error_lines
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
    SELECT p.pattern_id, p.template, p.component, coalesce(o.team, 'unowned') AS team, o.source AS owner_source,
           o.confidence AS owner_confidence, o.disputed_by AS owner_disputed_by, p.severity,
           now.lines, now.problem_lines, now.error_lines, now.nodes, now.weeks_active,
           coalesce(b_now.bursts, 0) AS bursts, coalesce(b_prev.bursts_prev, 0) AS bursts_prev,
           coalesce(b_now.bursts, 0) - coalesce(b_prev.bursts_prev, 0) AS change,
           round(top_node.top_node_lines::DOUBLE / now.lines, 3) AS top_node_share,
           p.first_ts AS first_seen, p.first_ts >= %(s)s AS new,
           round(j.p_fault, 3) AS p_fault, round(j.p_dump, 3) AS p_dump,
           round(j.p_problem, 3) AS p_problem, round(j.p_threat, 3) AS p_threat, j.kind
    FROM now JOIN patterns p ON p.dataset = %(d)s AND p.pattern_id = now.pattern_id
    LEFT JOIN pattern_judgments j ON j.dataset = %(d)s AND j.pattern_id = now.pattern_id
    LEFT JOIN ownership o ON o.dataset = %(d)s AND o.component = p.component
    LEFT JOIN top_node ON top_node.pattern_id = now.pattern_id
    LEFT JOIN b_now ON b_now.pattern_id = now.pattern_id LEFT JOIN b_prev ON b_prev.pattern_id = now.pattern_id
    WHERE TRUE {_problem_where(problem_filter) if problem_only else ""} {extra_where}
)"""


def _problem_where(problem_filter: str) -> str:
    if problem_filter == "severity":
        return "AND now.problem_lines > 0"
    return "AND " + is_problem("j", "now.problem_lines", "now.error_lines", "%(d)s")  # unjudged: level rule (plan 016)


def _excluded(dataset, ps, s, e, extra: str = "", params_extra: Optional[dict] = None, n: int = 3) -> tuple[list, str]:
    """Plan 014: the most-recurring patterns the Jev filter left out although they have problem-level lines, with
    their judgment, so a frequent pattern judged 'not a fault' is visible (the judge, not the agent, decided it)."""
    sql = _base_sql(False, "jev", extra + f" AND now.problem_lines > 0 AND coalesce(j.p_problem, 0) < {P_PROBLEM_MIN}") + f"""
SELECT pattern_id, template, component, team, bursts, lines, nodes, p_problem, kind FROM base
ORDER BY bursts DESC, pattern_id LIMIT {n}"""
    params = _params(dataset, ps, s, e, **(params_extra or {}))
    return query(sql, params), render(sql, params)


def _params(dataset, ps, s, e, **kw) -> dict:
    return {"d": dataset, "ps": ps, "s": s, "e": e, **{k: v for k, v in kw.items() if v is not None}}


def top_patterns(
    dataset: Ds,
    start: Start = None,
    end: End = None,
    team: Team = None,
    component: Component = None,
    problem_only: Annotated[bool, Field(description="Only problem patterns (see problem_filter); False = every kind "
                                                    "of message.")] = True,
    problem_filter: ProblemFilter = "jev",
    rank_by: Annotated[Literal["bursts", "nodes", "lines", "growth"], Field(
        description="'bursts' = how often it recurs (default), 'nodes' = how widespread, 'lines' = log volume "
                    "(inflated by storms), 'growth' = bursts now minus bursts in the previous period.")] = "bursts",
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description=f"Patterns to return (max {MAX_ROWS}).")] = 20,
) -> dict:
    """Which problems recur most in a period, how often, where, whose, and are they growing?

    Use when: "which problems keep coming back", "top errors this month", "what got worse", "what does team X
    struggle with": one row per kind of problem (a log pattern), ranked.
    Not for: a computed priority order with weights (priority_table), one known error's lines (search_logs), patterns
    first seen in the period only (whats_new), finding a pattern by meaning (find_patterns).
    Returns: per pattern: template, component, owner team (with owner_source / owner_confidence: curated or inferred,
    see owner_of), lines, bursts (recurrences split by > 30 min quiet),
    nodes, weeks_active, bursts_prev (previous period of equal length), change, new (first seen in the period),
    top_node_share (1.0 = one node only), p_problem / kind (stored Jev judgment). Both periods as absolute dates.
    excluded_by_filter = the top recurring patterns with error-level lines that the Jev filter judged not a fault.
    Caveats: bursts count recurrences, not confirmed incidents; lines count log entries. Default period = the
    dataset's last 28 days.
    Example: top_patterns(dataset=<dataset>, start='<month start>', end='<next month start>', rank_by='growth')
    Next: pattern_history / spread / precursors(pattern_id) for one row; search_logs(pattern_id=…) for its lines.
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
    sqls = [render(sql, params)]
    excluded = None
    if problem_only and problem_filter == "jev" and judged(dataset):
        excluded, xsql = _excluded(dataset, ps, s, e, extra, dict(team=team, comp=component))
        sqls.append(xsql)
    return envelope("top_patterns", dict(problem_only=problem_only, problem_filter=problem_filter, rank_by=rank_by,
                                         limit=limit, **f), sqls, f,
                    excluded_by_filter=excluded,
                    scope=f"{dataset}, period {s:%Y-%m-%d %H:%M} → {e:%Y-%m-%d %H:%M}, previous {ps:%Y-%m-%d %H:%M} → {s:%Y-%m-%d %H:%M}; "
                          f"bursts = recurrences (30-min gap), lines = log entries" + node_note(dataset),
                    rows=rows, t0=t0, total_matches=n, truncated=n > len(rows),
                    hints=judged_note(dataset) if problem_only and problem_filter == "jev" else [],
                    period={"start": s.isoformat(sep=" "), "end": e.isoformat(sep=" ")},
                    previous_period={"start": ps.isoformat(sep=" "), "end": s.isoformat(sep=" ")})


def priority_table(
    dataset: Ds,
    start: Start = None,
    end: End = None,
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description="Ranked problems to return (max 50).")] = 10,
    problem_filter: ProblemFilter = "jev",
) -> dict:
    """What deserves attention first? A computed priority ranking of problems for a period, with a team roll-up.

    Use when: "what should we fix / prioritise first", "top 3 risks", "if we can fix only one thing": the ranking
    is computed, so explain it instead of re-ranking yourself.
    Not for: a plain list of recurring problems ranked by one measure (top_patterns), one team in depth (team_risk),
    whether things improve over time (reliability_trend).
    Returns: items (rank, score 0-100, template, component, team, measured inputs: bursts, change, nodes,
    persistence, p_problem, and each input's contribution), the weights and formula, and team_rollup over ALL
    problem patterns of the period.
    Caveats: the logs measure frequency, spread, trend and persistence; cost, downtime and customer impact are not in
    the logs (stated in `unknown`). Default period = the dataset's last 28 days.
    Example: priority_table(dataset=<dataset>, start='<period start>', end='<period end>')
    Next: team_risk(team) for the top team; pattern_history / spread for the top item.
    """
    t0 = time.perf_counter()
    ps, s, e = _period(dataset, start, end)
    # calendar weeks (Monday start, as date_trunc('week')) the period touches, so persistence ≤ 1
    monday = lambda t: (t - timedelta(days=t.weekday())).date()
    weeks = (monday(e - timedelta(microseconds=1)) - monday(s)).days // 7 + 1
    w = WEIGHTS
    # severity input: Jev p_problem; level share for the 'severity' filter or an unjudged dataset (plan 016)
    sev = "p_problem" if problem_filter == "jev" and judged(dataset) else "round(problem_lines::DOUBLE / lines, 3)"
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
            "team": r["team"], "owner_source": r["owner_source"], "owner_confidence": r["owner_confidence"],
            "owner_disputed_by": r["owner_disputed_by"], "score": r["score"], "new": r["new"],
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
                         f"{ps:%Y-%m-%d %H:%M} → {s:%Y-%m-%d %H:%M}; candidates = problem patterns ({problem_filter} filter)"
                         + node_note(dataset),
                   rows=[], t0=t0, total_matches=len(allrows), truncated=len(allrows) > len(items),
                   weights=w, formula="score = 100 × Σ weight × cume_dist(input) over all candidates (share of candidates with a value ≤ this one)",
                   period={"start": s.isoformat(sep=" "), "end": e.isoformat(sep=" ")},
                   previous_period={"start": ps.isoformat(sep=" "), "end": s.isoformat(sep=" ")})
    del env["rows"]
    if problem_filter == "jev" and judged(dataset):
        excluded, xsql = _excluded(dataset, ps, s, e)
        env["sql"].append(xsql)
        env["excluded_by_filter"] = excluded
    elif problem_filter == "jev":
        env["hints"] = judged_note(dataset)
    env.update(items=items, team_rollup=rollup,
               unknown="Cost, downtime, customer impact and root cause are not in these logs.")
    return env
