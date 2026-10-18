"""Ownership tools (plan 057): who owns a component and why, and where ownership is weak. The `ownership` table
combines the curated table with an inference chain (load/96b_ownership_inferred.sql); every row says its source
and confidence, so an answer can tell a curated owner from an inferred one."""
import time
from typing import Annotated, Optional

from pydantic import Field

from core import MAX_ROWS, Dataset, DatasetOpt, check_dataset, envelope, query, render

COLS = ("o.team, o.source, o.confidence, o.area, o.area_source, o.area_confidence, o.disputed_by, "
        "o.dispute_confidence, o.description")


def owner_of(
    dataset: Dataset,
    component: Annotated[str, Field(description="Exact component (case-sensitive); all values: list_values.")],
) -> dict:
    """Who owns this component, how do we know, and how sure is it?

    Use when: an answer names an owning team and you must say whether that owner is curated or inferred, or a team
    lead asks who should handle a component, or a component shows as 'unowned'.
    Not for: counts per team (count_by group_by='team'), all weak spots at once (ownership_gaps).
    Returns: one row: team, source ('curated' = hand-written table, 'curated default' = the dataset's default
    row, 'jev owner_hint' = Jev chose among the dataset's curated teams, 'rule: …' = public name list → area → team,
    'jev area' = Jev chose the functional area → team), confidence (1.0 curated, 0.95 default, else the rule's 0.9 or
    the Jev probability), area with its own source and confidence, disputed_by / dispute_confidence when confident
    Jev hints for most of the component's lines name another curated team, and the lines and patterns it logged.
    Caveats: teams outside the curated table come from data/area_teams.csv and are generic, not a real org chart;
    an inferred owner below 0.6 confidence is never stored (the component shows as unowned); a dispute is a flag
    to check the table, not a correction.
    Example: owner_of(dataset=<dataset>, component=<a value from list_values(field='component')>)
    Next: ownership_gaps() for every unowned / inferred / disputed component; top_patterns(team=…) for that
    team's recurring problems.
    """
    t0 = time.perf_counter()
    check_dataset(dataset)
    p = {"d": dataset, "c": component}
    sql = (f"SELECT l.component, {COLS}, count(*) AS lines, count(DISTINCT l.pattern_id) AS patterns "
           "FROM logs l LEFT JOIN ownership o ON o.dataset = l.dataset AND o.component = l.component "
           f"WHERE l.dataset = %(d)s AND l.component = %(c)s GROUP BY l.component, {COLS}")
    rows = query(sql, p)
    hints = []
    if not rows:
        hints.append(f"No lines with component {component!r} in {dataset}; valid values: list_values(field="
                     "'component').")
    elif rows[0]["team"] is None:
        rows[0]["team"] = "unowned"
        hints.append("No curated row, no name rule and no Jev area at p >= 0.6: say the owner is unknown.")
    elif rows[0]["source"] not in ("curated", "curated default"):
        hints.append(f"Inferred owner: say 'inferred ({rows[0]['source']}, confidence {rows[0]['confidence']})'.")
    if rows and rows[0].get("disputed_by"):
        hints.append(f"Disputed: Jev hints name {rows[0]['disputed_by']} (p {rows[0]['dispute_confidence']}); "
                     "report both, keep the curated owner.")
    return envelope("owner_of", dict(dataset=dataset, component=component), [render(sql, p)],
                    dict(dataset=dataset, component=component),
                    scope=f"{dataset}, component {component!r}; ownership = curated table + inference chain",
                    rows=rows, t0=t0, total_matches=len(rows), truncated=False, hints=hints)


def ownership_gaps(
    dataset: DatasetOpt = None,
    min_confidence: Annotated[float, Field(ge=0, le=1, description="Inferred owners below this confidence count as "
                                                                    "weak (default 0.8).")] = 0.8,
    limit: Annotated[int, Field(ge=1, le=MAX_ROWS, description=f"Rows to return, most lines first (max {MAX_ROWS}).")] = 20,
) -> dict:
    """Where is ownership missing, guessed or disputed, and how many log lines does that affect?

    Use when: before naming owners in a team-lead or manager answer, to know which owners are solid; or when asked
    which components nobody owns or whose owner table may be wrong.
    Not for: the owner of one component (owner_of), counts per team (count_by group_by='team').
    Returns: one row per weak component, most lines first: kind ('unowned' = no owner at all, 'inferred' = owner
    not from the curated table, 'weak' = inferred below min_confidence, 'disputed' = curated owner contradicted by
    confident Jev hints), team, source, confidence, disputed_by, lines, patterns; plus totals per kind with their
    share of the dataset's lines.
    Caveats: components with a curated owner and no dispute are not listed; lines are log entries, not incidents.
    Example: ownership_gaps(dataset=<dataset>, min_confidence=0.8)
    Next: owner_of(component) for the evidence of one row; top_patterns(team=…) to see what an uncertain
    team would own.
    """
    t0 = time.perf_counter()
    check_dataset(dataset)
    p = {"m": min_confidence}
    where = "WHERE l.component IS NOT NULL" + (" AND l.dataset = %(d)s" if dataset else "")
    if dataset:
        p["d"] = dataset
    base = (f"WITH c AS (SELECT l.dataset, l.component, count(*) AS lines, count(DISTINCT l.pattern_id) AS patterns "
            f"FROM logs l {where} GROUP BY 1, 2), "
            "g AS (SELECT c.*, o.team, o.source, o.confidence, o.disputed_by, o.dispute_confidence, "
            "CASE WHEN o.team IS NULL THEN 'unowned' WHEN o.disputed_by IS NOT NULL THEN 'disputed' "
            "WHEN o.source IN ('curated', 'curated default') THEN NULL "
            "WHEN o.confidence < %(m)s THEN 'weak' ELSE 'inferred' END AS kind, "
            "sum(c.lines) OVER (PARTITION BY c.dataset) AS dataset_lines "
            "FROM c LEFT JOIN ownership o ON o.dataset = c.dataset AND o.component = c.component) ")
    rows_sql = (base + "SELECT dataset, component, kind, coalesce(team, 'unowned') AS team, source, confidence, "
                "disputed_by, dispute_confidence, lines, patterns FROM g WHERE kind IS NOT NULL "
                f"ORDER BY lines DESC, dataset, component LIMIT {limit}")
    sum_sql = (base + "SELECT dataset, kind, count(*) AS components, sum(lines) AS lines, "
               "round(sum(lines)::DOUBLE / any_value(dataset_lines), 4) AS share_of_lines FROM g "
               "WHERE kind IS NOT NULL GROUP BY 1, 2 ORDER BY 1, 2")
    rows, totals = query(rows_sql, p), query(sum_sql, p)
    n = sum(t["components"] for t in totals)
    return envelope("ownership_gaps", dict(dataset=dataset, min_confidence=min_confidence, limit=limit),
                    [render(rows_sql, p), render(sum_sql, p)], dict(dataset=dataset),
                    scope=f"{dataset or 'all datasets'}; components without a solid curated owner; unit = log lines",
                    rows=rows, t0=t0, total_matches=n, truncated=n > len(rows), totals=totals,
                    hints=([] if n else ["Every component has a curated, undisputed owner."]))
