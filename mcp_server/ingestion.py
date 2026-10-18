"""How well an auto-detected dataset was understood (plan 057 part 3): the format scripts/ingest.py chose, how much of the
file it matched, which field became which column, and samples of the lines it did not match."""
import json
import time
from typing import Annotated

from pydantic import Field

from core import MAX_ROWS, Dataset, check_dataset, envelope, query, render


def ingest_report(
    dataset: Dataset,
    unmatched_limit: Annotated[int, Field(ge=0, le=MAX_ROWS, description="Unmatched lines to show (default 5).")] = 5,
) -> dict:
    """How was this dataset's log format detected, and how much of the file did the parser understand?

    Use when: a dataset was loaded by auto-detection (its description says so) and you must say how reliable its
    timestamps, levels and components are, or a question touches lines that may not have been parsed.
    Not for: what a dataset contains (describe_corpus); hand-written loaders (no report: they are parsed by design).
    Returns: format (lnav name + title), sample coverage, lines loaded, lines the format did not match (count, share,
    samples with line_id), timestamp format, assumed year if the log has none, the field → column map, the runner-up
    formats with their coverage.
    Caveats: unmatched lines keep their text but inherit time, component and level from the previous line.
    Example: ingest_report(dataset)
    Next: search_logs / get_context(line_id) on an unmatched line; describe_corpus for the field meanings.
    """
    t0 = time.perf_counter()
    check_dataset(dataset)
    p = {"d": dataset}
    sql = ("SELECT r.format, r.format_title, r.file, r.sample_lines, r.sample_matched, "
           "round(r.sample_matched::DOUBLE / r.sample_lines, 4) AS sample_coverage, r.ts_format, r.year_assumed, "
           "r.field_map, r.candidates, r.regexes_skipped, "
           "(SELECT count(*) FROM logs l WHERE l.dataset = r.dataset) AS lines_loaded, "
           "(SELECT count(*) FROM ingest_unparsed u WHERE u.dataset = r.dataset) AS lines_unmatched "
           "FROM ingest_runs r WHERE r.dataset = %(d)s")
    rows = query(sql, p)
    sqls, hints = [render(sql, p)], []
    if not rows:
        hints.append("Hand-written loader (load/*.sql): no auto-detection report; its format is parsed by design.")
        return envelope("ingest_report", dict(dataset=dataset), sqls, dict(dataset=dataset),
                        scope=f"{dataset}; not auto-detected", rows=[], t0=t0, total_matches=0, truncated=False,
                        hints=hints)
    r = rows[0]
    r["field_map"], r["candidates"] = json.loads(r["field_map"]), json.loads(r["candidates"])
    r["unmatched_share"] = round(r["lines_unmatched"] / max(r["lines_loaded"], 1), 4)
    ex_sql = ("SELECT l.line_id, l.ts, l.body FROM ingest_unparsed u JOIN logs l ON l.dataset = u.dataset "
              f"AND l.line_id = u.line_id WHERE u.dataset = %(d)s ORDER BY l.line_id LIMIT {unmatched_limit}")
    examples = query(ex_sql, p) if unmatched_limit else []
    sqls.append(render(ex_sql, p))
    if r["year_assumed"]:
        hints.append(f"The log has no year: {r['year_assumed']} was assumed; say so when giving dates.")
    if r["lines_unmatched"]:
        hints.append(f"{r['lines_unmatched']} lines were not matched by the format (kept as continuation lines).")
    return envelope("ingest_report", dict(dataset=dataset, unmatched_limit=unmatched_limit), sqls, dict(dataset=dataset),
                    scope=f"{dataset}; auto-detected loader load/gen/{dataset}.sql", rows=rows, t0=t0,
                    total_matches=r["lines_unmatched"], truncated=r["lines_unmatched"] > len(examples),
                    unmatched_examples=examples, hints=hints)
