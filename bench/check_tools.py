"""Every MCP tool on every loaded dataset (plans 011 + 012): the tool's key number equals an INDEPENDENT hand-written SQL
query, with inputs chosen generically from that dataset's own data (its busiest problem pattern, its most frequent
word, an example id from dataset_examples, …): no per-dataset branches, so a new dataset is tested with no change.
A tool that needs data the dataset does not have (durations, ids, watches) is reported as skipped with the reason.
Prints a tool × dataset matrix and p50 / max time per tool.
Run after a reload: .venv/bin/python bench/check_tools.py [--remote] [--no-ai]
(--remote: also the remote Parquet tools, needs internet; --no-ai: skip summarize_burst's live model call)."""
import statistics
import sys
import time
import traceback
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mcp_server"))
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
import analytics
import counts
import discover
import ingestion
import outliers
import ownership
import patterns
import remote
import search
import semantic
import terms
import timeline
import workspace
from core import query, registry, tsquery_sql

fails, times, matrix = [], {}, {}
PROBLEM_LEVEL = ("(l.severity IN ('FATAL', 'FAILURE', 'SEVERE', 'ERROR', 'CRITICAL', 'WARN', 'WARNING') "
                 "OR l.status >= 500 OR l.severity IS NULL)")


def mark(tool, ds, state):
    cur = matrix.setdefault(tool, {}).get(ds)
    if cur is None or (cur == "ok" and state != "ok" and not state.startswith("skip")):
        matrix[tool][ds] = state


def ok(tool, ds, name, got, want):
    good = got == want
    print(("ok   " if good else "FAIL ") + f"{ds} {tool}: {name}" + ("" if good else f"\n   got  {got}\n   want {want}"))
    if not good:
        fails.append(f"{ds} {tool}: {name}")
    mark(tool, ds, "ok" if good else "FAIL")


def skip(tool, ds, why):
    mark(tool, ds, "skip: " + why)


def run(fn, ds, *a, **kw):
    t = time.perf_counter()
    try:
        r = fn(*a, **kw)
    except Exception as e:  # noqa: BLE001  (a crash is a failure of that tool on that dataset)
        print(f"FAIL {ds} {fn.__name__}: raised {type(e).__name__}: {e}")
        traceback.print_exc(limit=1)
        fails.append(f"{ds} {fn.__name__}: raised")
        mark(fn.__name__, ds, "FAIL")
        return None
    times.setdefault(fn.__name__, []).append((time.perf_counter() - t) * 1000)
    return r


def one(sql, p=None):
    r = query(sql, p or {})
    return list(r[0].values())[0] if r else None


def example(ds, field):
    return one("SELECT example FROM dataset_examples WHERE dataset = %(d)s AND field = %(f)s", {"d": ds, "f": field})


DATASETS = list(registry())
for ds in DATASETS:
    reg = registry()[ds]
    lo, hi = reg["first_ts"], reg["last_ts"]
    end_all = hi + timedelta(seconds=1)
    P = {"d": ds}
    # generic inputs from the dataset's own data
    pid = one("SELECT p.pattern_id FROM patterns p JOIN pattern_judgments j USING (dataset, pattern_id) "
              "WHERE p.dataset = %(d)s ORDER BY (j.p_problem >= 0.5 AND p.problem_lines > 0) DESC, p.bursts DESC, "
              "p.pattern_id LIMIT 1", P)
    line = one("SELECT example_line_id FROM patterns WHERE dataset = %(d)s AND pattern_id = %(p)s", {"d": ds, "p": pid})
    word = one("SELECT t FROM (SELECT unnest(ts_dict_agg(body)) AS t, unnest(ts_dict_count(body)) AS c FROM logs_idx "
               "WHERE dataset @@ %(d)s) WHERE length(t) >= 5 AND regexp_matches(t, '^[a-z]+$') ORDER BY c DESC LIMIT 1", P)
    comp = (reg.get("components") or [None])[0]
    lines_total = one("SELECT count(*) FROM logs WHERE dataset = %(d)s", P)
    day = (hi - timedelta(days=1), end_all)
    print(f"\n== {ds}: pattern {pid}, line {line}, word {word!r}, component {comp!r}")

    # ---- discovery
    r = run(discover.describe_corpus, ds)
    if r:
        ok("describe_corpus", ds, "lines", next(x for x in r["rows"] if x["dataset"] == ds)["lines"], lines_total)
    r = run(discover.list_values, ds, ds, "component", limit=50)
    if r:
        ok("list_values", ds, "components", r["values_total"],
           one("SELECT count(DISTINCT component) FROM logs WHERE dataset = %(d)s", P))
    r = run(discover.suggest_terms, ds, word[:-1] + ("x" if word[-1] != "x" else "y"), ds)
    if r:
        ok("suggest_terms", ds, f"recovers {word!r}", word in [x["term"] for x in r["rows"]], True)
    exact = one("SELECT count(*) FROM logs WHERE dataset = %(d)s AND body @@ %(w)s::tsquery", {"d": ds, "w": word})
    r = run(discover.explain_search, ds, word, ds)
    if r:
        ok("explain_search", ds, "total", r["total_matches"], exact)

    r = run(ingestion.ingest_report, ds, ds, unmatched_limit=3)  # plan 057: auto-detected datasets only
    if r:
        auto = one("SELECT count(*) FROM ingest_runs WHERE dataset = %(d)s", P)
        ok("ingest_report", ds, "report only for auto-detected datasets", len(r["rows"]), auto)
        if auto:
            ok("ingest_report", ds, "lines loaded", r["rows"][0]["lines_loaded"], lines_total)

    # ---- search
    r = run(search.search_logs, ds, query_text=word, dataset=ds, limit=3)
    if r:
        ok("search_logs", ds, "total", r["total_matches"], exact)
    r = run(search.search_logs, ds, query_text=word, dataset=ds, match="synonyms", limit=3)
    if r:
        ok("search_logs", ds, "synonyms ⊇ exact", r["total_matches"] >= exact, True)
    r = run(search.search_logs, ds, query_text=word, dataset=ds, highlight=True, limit=3)
    if r:
        ok("search_logs", ds, "highlight marks the word", all("«" in (x.get("snippet") or "") for x in r["rows"]), True)
    if comp:
        r = run(search.search_logs, ds, dataset=ds, component=comp, start=day[0], end=day[1], limit=1)
        if r:
            ok("search_logs", ds, "filters only", r["total_matches"], one(
                "SELECT count(*) FROM logs WHERE dataset = %(d)s AND component = %(c)s AND ts >= %(s)s AND ts < %(e)s",
                {"d": ds, "c": comp, "s": day[0], "e": day[1]}))
    r = run(search.search_logs, ds, query_text=word + "zzqx", dataset=ds, limit=1)
    if r:
        ok("search_logs", ds, "0 hits gives hints", bool(r["total_matches"] == 0 and r.get("hints")), True)

    a = query("SELECT ts, node, component FROM logs WHERE dataset = %(d)s AND line_id = %(l)s", {"d": ds, "l": line})[0]
    sc, col = ("node", "node") if a["node"] else ("component", "component")
    r = run(search.get_context, ds, ds, line, before_s=300, after_s=300, scope=sc, limit=5)
    if r:
        ok("get_context", ds, f"lines around the anchor (scope {sc})", r["before_total"] + r["after_total"], one(
            f"SELECT count(*) - 1 FROM logs WHERE dataset = %(d)s AND {col} = %(v)s AND ts >= %(s)s AND ts < %(e)s",
            {"d": ds, "v": a[col], "s": a["ts"] - timedelta(seconds=300),
             "e": a["ts"] + timedelta(seconds=300, microseconds=1)}))

    # ---- terms
    r = run(terms.facet, ds, ds, word, dims=["component", "severity"], top=20)
    if r:
        ok("facet", ds, "total", r["total_matches"], one(
            "SELECT count(*) FROM logs WHERE dataset = %(d)s AND body @@ websearch_to_tsquery(%(w)s)", {"d": ds, "w": word}))
    r = run(terms.facet, ds, ds, dims=["component"], start=day[0], end=day[1], top=50)  # one dimension, filters only
    if r:
        ok("facet", ds, "one dimension sums to total", sum(x["lines"] for x in r["rows"]) == r["total_matches"]
           or r["distinct"]["component"] > 50, True)
    # a window with data: the day around the busiest burst of the pattern
    mid = one("SELECT start_ts FROM bursts WHERE dataset = %(d)s AND pattern_id = %(p)s ORDER BY lines DESC LIMIT 1",
              {"d": ds, "p": pid}) - timedelta(hours=12)
    r = run(terms.distinctive_terms, ds, ds, mid, mid + timedelta(days=1), baseline="before", min_lines=1, limit=5)
    if r and r["rows"]:
        t = r["rows"][0]["term"]
        ok("distinctive_terms", ds, f"window lines of {t!r}", r["rows"][0]["window_lines"], one(
            "SELECT count(*) FROM logs WHERE dataset = %(d)s AND ts >= %(s)s AND ts < %(e)s AND body @@ %(t)s::tsquery",
            {"d": ds, "s": mid, "e": mid + timedelta(days=1), "t": t}))
    elif r:
        skip("distinctive_terms", ds, "quiet window")
    if reg["entity_kinds"]:
        r = run(terms.top_entities, ds, ds, "any", limit=3)
        if r and r["rows"]:
            e = r["rows"][0]
            ok("top_entities", ds, f"lines of {e['entity']}", e["lines"], one(
                "SELECT count(*) FROM (SELECT unnest(entities) AS x FROM logs WHERE dataset = %(d)s) WHERE x = %(e)s",
                {"d": ds, "e": e["entity"]}))
    else:
        skip("top_entities", ds, "no entities extracted")
    if query("SELECT 1 FROM watchlist WHERE dataset = %(d)s LIMIT 1", P):
        r = run(terms.check_watchlist, ds, ds, lo, end_all)
        if r:
            w = r["rows"][0]
            expr, qp = tsquery_sql(w["query"], w["match"] or "web")
            ok("check_watchlist", ds, f"watch {w['watch']!r} lines", w["window_lines"], one(
                f"SELECT count(*) FROM logs WHERE dataset = %(d)s AND body @@ {expr}", {"d": ds, **qp}))
    else:
        skip("check_watchlist", ds, "no watches configured")

    # ---- counts
    r = run(counts.count_by, ds, "component", dataset=ds, limit=50)
    if r:
        ok("count_by", ds, "total lines", r["total_lines"], lines_total)
    r = run(counts.trend, ds, dataset=ds)
    if r:
        ok("trend", ds, "total lines", r["total_lines"], lines_total)
        if not r["truncated"]:
            ok("trend", ds, "buckets sum = lines", sum(x["lines"] for x in r["rows"]), lines_total)
    r = run(counts.rate_vs_baseline, ds, day[0], day[1], dataset=ds, query_text=word)
    if r:
        ok("rate_vs_baseline", ds, "window lines", r["rows"][0]["window_lines"], one(
            "SELECT count(*) FROM logs WHERE dataset = %(d)s AND ts >= %(s)s AND ts < %(e)s "
            "AND body @@ websearch_to_tsquery(%(w)s)", {"d": ds, "s": day[0], "e": day[1], "w": word}))
    timed = one("SELECT count(*) FROM logs WHERE dataset = %(d)s AND duration_ms IS NOT NULL", P)
    if timed:
        r = run(outliers.value_outliers, ds, ds, limit=5)
        if r:
            ok("value_outliers", ds, "baseline n = timed lines", sum(b["n"] for b in r["baselines"]), timed)
        r = run(analytics.latency_profile, ds, ds)
        if r:
            ok("latency_profile", ds, "histogram = timed lines", r["total_matches"], timed)
    else:
        skip("value_outliers", ds, "no durations")
        skip("latency_profile", ds, "no durations")

    # ---- patterns and priorities (whole span)
    n_prob = one(f"SELECT count(DISTINCT l.pattern_id) FROM logs l JOIN pattern_judgments j USING (dataset, pattern_id) "
                 f"WHERE l.dataset = %(d)s AND j.p_problem >= 0.5 AND {PROBLEM_LEVEL}", P)
    r = run(patterns.top_patterns, ds, ds, lo, end_all, limit=5)
    if r:
        ok("top_patterns", ds, "problem patterns", r["total_matches"], n_prob)
    r = run(patterns.priority_table, ds, ds, lo, end_all, limit=5)
    if r:
        ok("priority_table", ds, "problem patterns", r["total_matches"], n_prob)
        ok("priority_table", ds, "scores descending", [i["score"] for i in r["items"]],
           sorted((i["score"] for i in r["items"]), reverse=True))
        if r["team_rollup"]:
            team = r["team_rollup"][0]["team"]
            tr = run(analytics.team_risk, ds, ds, team, lo, end_all)
            if tr:
                ok("team_risk", ds, f"{team} problem patterns", tr["total_matches"], one(
                    f"SELECT count(DISTINCT l.pattern_id) FROM logs l JOIN pattern_judgments j USING (dataset, pattern_id) "
                    f"LEFT JOIN ownership o ON o.dataset = l.dataset AND o.component = l.component "
                    f"WHERE l.dataset = %(d)s AND j.p_problem >= 0.5 AND {PROBLEM_LEVEL} "
                    f"AND coalesce(o.team, 'unowned') = %(t)s", {"d": ds, "t": team}))
        else:
            skip("team_risk", ds, "no problem patterns")

    # ---- ownership (plan 057): curated owners unchanged, gaps = components without a curated row (+ disputes)
    if comp:
        r = run(ownership.owner_of, ds, ds, comp)
        if r:
            ok("owner_of", ds, f"{comp!r} lines", r["rows"][0]["lines"],
               one("SELECT count(*) FROM logs WHERE dataset = %(d)s AND component = %(c)s", {"d": ds, "c": comp}))
            cur = one("SELECT coalesce(max(team) FILTER (WHERE component = %(c)s), max(team) FILTER (WHERE component = '*')) "
                      "FROM ownership_raw WHERE dataset = %(d)s", {"d": ds, "c": comp})
            if cur:
                ok("owner_of", ds, "curated owner unchanged", (r["rows"][0]["team"], r["rows"][0]["source"] in
                                                              ("curated", "curated default")), (cur, True))
    r = run(ownership.ownership_gaps, ds, ds, limit=50)
    if r:
        no_curated = one("SELECT count(DISTINCT l.component) FROM logs l WHERE l.dataset = %(d)s AND l.component IS NOT NULL "
                         "AND NOT EXISTS (SELECT 1 FROM ownership_raw o WHERE o.dataset = l.dataset "
                         "AND o.component IN (l.component, '*'))", P)
        ok("ownership_gaps", ds, "components without a curated owner",
           sum(t["components"] for t in r["totals"] if t["kind"] != "disputed"), no_curated)

    # ---- timeline
    r = run(timeline.pattern_history, ds, ds, pid)
    if r:
        ok("pattern_history", ds, "bursts in series", sum(x["bursts_started"] for x in r["rows"]),
           one("SELECT count(*) FROM bursts WHERE dataset = %(d)s AND pattern_id = %(p)s", {"d": ds, "p": pid}))
        ok("pattern_history", ds, "lines in series (own timestamps)", sum(x["lines"] for x in r["rows"]),
           one("SELECT count(*) FROM logs WHERE dataset = %(d)s AND pattern_id = %(p)s", {"d": ds, "p": pid}))
    r = run(timeline.burst_timeline, ds, ds, pid)
    if r:
        ok("burst_timeline", ds, "contains the pattern", pid in [x["pattern_id"] for x in r["rows"]] or r["truncated"], True)
    r = run(timeline.spread, ds, ds, pattern_id=pid)
    if r:
        ok("spread", ds, "nodes", r["nodes"], one("SELECT count(DISTINCT coalesce(node, component)) FROM logs "
                                                  "WHERE dataset = %(d)s AND pattern_id = %(p)s", {"d": ds, "p": pid}))
    r = run(timeline.whats_new, ds, ds, lo, end_all, problem_only=False, limit=50)
    if r:
        ok("whats_new", ds, "whole span = all patterns", r["total_matches"],
           one("SELECT count(*) FROM patterns WHERE dataset = %(d)s", P))
    r = run(timeline.precursors, ds, ds, pid, 600)
    if r:
        ok("precursors", ds, "occurrences = node episodes", r["occurrences"],
           one("SELECT count(*) FROM episodes WHERE dataset = %(d)s AND pattern_id = %(p)s", {"d": ds, "p": pid}))
    r = run(timeline.co_occurrence, ds, ds, pid, window_s=300)
    if r:
        ok("co_occurrence", ds, "shares in [0,1]", all(0 <= x["share"] <= 1 for x in r["rows"]), True)
    r = run(timeline.periodicity, ds, ds, pid)
    if r:
        ok("periodicity", ds, "bursts by hour", r["total_matches"],
           one("SELECT count(*) FROM bursts WHERE dataset = %(d)s AND pattern_id = %(p)s", {"d": ds, "p": pid}))
    ids = [(f, example(ds, f)) for f in ("request_id", "object_id")]
    for field, ex in ids:
        if ex:
            r = run(timeline.request_timeline, ds, ds, **{field: ex})
            if r:
                sm = r["summary"]
                ok("request_timeline", ds, f"{field} session lines", sm["lines"], one(
                    f"SELECT count(*) FROM logs WHERE dataset = %(d)s AND {field} = %(x)s AND ts >= %(s)s AND ts <= %(e)s",
                    {"d": ds, "x": ex, "s": sm["first_ts"], "e": sm["last_ts"]}))
    if not any(ex for _, ex in ids):
        skip("request_timeline", ds, "no request / object ids")

    # ---- analytics
    r = run(analytics.rollup, ds, ds, unit="lines", problem_only=False, by=["team"])
    if r:
        ok("rollup", ds, "grand total lines", r["rows"][0]["lines"], lines_total)
    r = run(analytics.heatmap, ds, ds, unit="lines", problem_only=False, rows="severity", cols="month", top_rows=30)
    if r:
        ok("heatmap", ds, "cells sum = lines", r["total_matches"], lines_total)
    try:
        r = analytics.reliability_trend(ds, bucket="day")
        ok("reliability_trend", ds, "total = problem bursts", r["total_matches"], one(
            "SELECT count(*) FROM bursts b JOIN pattern_judgments j USING (dataset, pattern_id) JOIN patterns p "
            "USING (dataset, pattern_id) WHERE b.dataset = %(d)s AND j.p_problem >= 0.5 AND p.problem_lines > 0", P))
    except ValueError as e:
        skip("reliability_trend", ds, str(e))

    # ---- semantic
    r = run(semantic.similar_patterns, ds, ds, pid, 3)
    if r:
        ok("similar_patterns", ds, "distances ascending", [x["distance"] for x in r["rows"]],
           sorted(x["distance"] for x in r["rows"]))
    r = run(semantic.find_patterns, ds, word, ds, "lexical", 3)
    if r:
        ok("find_patterns", ds, "lexical hits contain the word", all(word in x["template"].lower() for x in r["rows"]), True)
    if "--no-ai" in sys.argv:
        skip("summarize_burst", ds, "--no-ai")
    else:
        r = run(semantic.summarize_burst, ds, ds, pid, window_s=60)
        if r:
            ok("summarize_burst", ds, "model summary present and labelled", bool(r["model_summary"]) and "warning" in r, True)

    # ---- workspace (one small window per dataset)
    name = f"check_{ds}"
    win = day
    for hours in (24, 1, 0.1):  # the last day, or a shorter window when the day exceeds the focus-index cap
        win = (hi - timedelta(hours=hours), end_all)
        n_day = one("SELECT count(*) FROM logs WHERE dataset = %(d)s AND ts >= %(s)s AND ts < %(e)s",
                    {"d": ds, "s": win[0], "e": win[1]})
        if n_day <= workspace.MAX_ROWS_WS:
            break
    ws = run(workspace.create_focus_index, ds, ds, win[0], win[1], name=name)
    if ws:
        ok("create_focus_index", ds, "rows copied", ws["total_matches"], n_day)
        r = run(search.search_logs, ds, query_text=word, workspace=name, limit=1)
        if r:
            ok("search_logs", ds, "workspace = corpus", r["total_matches"], one(
                "SELECT count(*) FROM logs WHERE dataset = %(d)s AND ts >= %(s)s AND ts < %(e)s "
                "AND body @@ websearch_to_tsquery(%(w)s)", {"d": ds, "s": win[0], "e": win[1], "w": word}))
        r = run(workspace.index_stats, ds)
        if r:
            ok("index_stats", ds, "workspace listed", name in [w["name"] for w in r["workspaces"]], True)
        run(workspace.drop_focus_index, ds, name)
        ok("drop_focus_index", ds, "removed", one("SELECT count(*) FROM workspaces WHERE name = %(n)s", {"n": name}), 0)
    r = run(workspace.explain_tool, ds, "search_logs", {"dataset": ds, "query_text": word})
    if r:
        ok("explain_tool", ds, "index serves the search", r["flags"]["inverted_index_scan"], True)

if "--remote" in sys.argv:
    from datetime import datetime
    s, e = datetime(2025, 9, 23, 0, 10), datetime(2025, 9, 23, 0, 10, 2)
    r = run(remote.remote_describe, "remote")
    if r:
        ok("remote_describe", "remote", "rows > 0", r["total_matches"] > 0, True)
    r = run(remote.remote_count_by, "remote", s, e)
    if r:
        ok("remote_count_by", "remote", "row groups pruned", r["row_groups_read"] < r["row_groups_total"], True)
    r = run(remote.remote_search, "remote", "error", s, e, limit=2)
    if r:
        ok("remote_search", "remote", "scan path", r["path"], "scan")

cols = DATASETS + (["remote"] if "--remote" in sys.argv else [])
print("\n" + "tool".ljust(20) + "".join(d[:9].rjust(10) for d in cols))
for tool in sorted(matrix):
    cells = []
    for d in cols:
        v = matrix[tool].get(d, "-")
        cells.append(("ok" if v == "ok" else "FAIL" if v.startswith("FAIL") else "skip" if v.startswith("skip") else "-").rjust(10))
    print(tool.ljust(20) + "".join(cells))
skips = sorted({f"{t} on {d}: {v[6:]}" for t, m in matrix.items() for d, v in m.items() if v.startswith("skip")})
if skips:
    print("\nskipped (the dataset lacks the data):\n  " + "\n  ".join(skips))
print()
for k, v in sorted(times.items()):
    print(f"{k:<22} calls {len(v):>3}  median {statistics.median(v):7.1f} ms  max {max(v):7.1f} ms")
print(f"\n{len(matrix)} tools x {len(DATASETS)} datasets; {len(fails)} failed" if fails else
      f"\n{len(matrix)} tools x {len(DATASETS)} datasets: all checks passed")
sys.exit(1 if fails else 0)
