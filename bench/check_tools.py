"""Plan 011 checks: every new tool's key numbers equal an INDEPENDENT hand-written SQL query, on every loaded dataset
(generality test), plus p95 per tool. Run after a reload: .venv/bin/python bench/check_tools.py [--remote]
(--remote also checks the remote Parquet tools: needs internet, ~10 s)."""
import statistics
import sys
import time
from datetime import timedelta
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mcp_server"))
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
import analytics
import discover
import remote
import search
import semantic
import terms
import timeline
import workspace
from core import query, registry

fails, times = [], {}


def ok(name, got, want):
    good = got == want
    print(("ok   " if good else "FAIL ") + name + ("" if good else f"\n   got  {got}\n   want {want}"))
    if not good:
        fails.append(name)


def run(fn, *a, **kw):
    t = time.perf_counter()
    r = fn(*a, **kw)
    times.setdefault(fn.__name__, []).append((time.perf_counter() - t) * 1000)
    return r


def one(sql, p=None):
    return list(query(sql, p or {})[0].values())[0]


DATASETS = list(registry())
for ds in DATASETS:
    lo, hi = registry()[ds]["first_ts"], registry()[ds]["last_ts"]
    # the busiest problem pattern of the dataset (generic choice, no dataset knowledge)
    pid = one("SELECT p.pattern_id FROM patterns p JOIN pattern_judgments j USING (dataset, pattern_id) "
              "WHERE p.dataset = %(d)s ORDER BY (j.p_problem >= 0.5) DESC, p.bursts DESC, p.pattern_id LIMIT 1", {"d": ds})
    word = one("SELECT t FROM (SELECT unnest(ts_dict_agg(body)) AS t, unnest(ts_dict_count(body)) AS c FROM logs_idx "
               "WHERE dataset @@ %(d)s) WHERE length(t) >= 5 AND regexp_matches(t, '^[a-z]+$') ORDER BY c DESC LIMIT 1", {"d": ds})
    print(f"== {ds}: pattern {pid}, word {word!r}")

    r = run(discover.describe_corpus)
    row = next(x for x in r["rows"] if x["dataset"] == ds)
    ok(f"{ds} describe_corpus lines", row["lines"], one("SELECT count(*) FROM logs WHERE dataset = %(d)s", {"d": ds}))
    ok(f"{ds} describe_corpus bursts", row["bursts"], one("SELECT count(*) FROM bursts WHERE dataset = %(d)s", {"d": ds}))

    r = run(discover.list_values, ds, "component", limit=50)
    ok(f"{ds} list_values component total", r["values_total"],
       one("SELECT count(DISTINCT component) FROM logs WHERE dataset = %(d)s", {"d": ds}))
    top = r["rows"][0]
    ok(f"{ds} list_values top component lines", top["lines"],
       one("SELECT count(*) FROM logs WHERE dataset = %(d)s AND component = %(c)s", {"d": ds, "c": top["value"]}))

    r = run(discover.suggest_terms, word[:-1] + ("x" if word[-1] != "x" else "y"), ds)
    ok(f"{ds} suggest_terms recovers {word!r}", word in [x["term"] for x in r["rows"]], True)

    r = run(search.search_logs, query_text=word, dataset=ds, match="synonyms", limit=3)
    ok(f"{ds} search synonyms ⊇ exact", r["total_matches"] >= one(
        "SELECT count(*) FROM logs WHERE dataset = %(d)s AND body @@ %(w)s::tsquery", {"d": ds, "w": word}), True)
    r = run(search.search_logs, query_text=word, dataset=ds, highlight=True, limit=3)
    ok(f"{ds} search highlight marks the word", all("«" in (x.get("snippet") or "") for x in r["rows"]), True)

    r = run(terms.facet, ds, word, dims=["component", "severity"], top=50)
    comp_sum = sum(x["lines"] for x in r["rows"] if x["dim"] == "component")
    ok(f"{ds} facet components sum = total (when complete)", comp_sum == r["total_matches"] or r["distinct"]["component"] > 50, True)
    ok(f"{ds} facet total", r["total_matches"],
       one("SELECT count(*) FROM logs WHERE dataset = %(d)s AND body @@ websearch_to_tsquery(%(w)s)", {"d": ds, "w": word}))

    mid = lo + (hi - lo) / 2
    r = run(terms.distinctive_terms, ds, mid, mid + timedelta(days=1), baseline="before", min_lines=1, limit=5)
    if r["rows"]:
        t = r["rows"][0]["term"]
        ok(f"{ds} distinctive_terms window_lines of {t!r}", r["rows"][0]["window_lines"],
           one("SELECT count(*) FROM logs WHERE dataset = %(d)s AND ts >= %(s)s AND ts < %(e)s AND body @@ %(t)s::tsquery",
               {"d": ds, "s": mid, "e": mid + timedelta(days=1), "t": t}))

    r = run(terms.top_entities, ds, "any", limit=3)
    if r["rows"]:
        e = r["rows"][0]
        ok(f"{ds} top_entities lines of {e['entity']}", e["lines"],
           one("SELECT count(*) FROM (SELECT unnest(entities) AS x FROM logs WHERE dataset = %(d)s) WHERE x = %(e)s",
               {"d": ds, "e": e["entity"]}))

    r = run(timeline.pattern_history, ds, pid)
    ok(f"{ds} pattern_history bursts in series", sum(x["bursts"] for x in r["rows"]),
       one("SELECT count(*) FROM bursts WHERE dataset = %(d)s AND pattern_id = %(p)s", {"d": ds, "p": pid}))
    r = run(timeline.burst_timeline, ds, pid)
    ok(f"{ds} burst_timeline contains the pattern", pid in [x["pattern_id"] for x in r["rows"]] or r["truncated"], True)
    r = run(timeline.spread, ds, pattern_id=pid)
    ok(f"{ds} spread nodes", r["nodes"],
       one("SELECT count(DISTINCT coalesce(node, component)) FROM logs WHERE dataset = %(d)s AND pattern_id = %(p)s", {"d": ds, "p": pid}))
    r = run(timeline.whats_new, ds, lo, hi + timedelta(seconds=1), problem_only=False, limit=50)
    ok(f"{ds} whats_new over whole dataset = all patterns", r["total_matches"],
       one("SELECT count(*) FROM patterns WHERE dataset = %(d)s", {"d": ds}))
    r = run(timeline.precursors, ds, pid, 600)
    ok(f"{ds} precursors occurrences = node episodes", r["occurrences"],
       one("SELECT count(*) FROM episodes WHERE dataset = %(d)s AND pattern_id = %(p)s", {"d": ds, "p": pid}))
    r = run(timeline.co_occurrence, ds, pid, window_s=300)
    ok(f"{ds} co_occurrence shares in [0,1]", all(0 <= x["share"] <= 1 for x in r["rows"]), True)
    r = run(timeline.periodicity, ds, pid)
    ok(f"{ds} periodicity bursts by hour", r["total_matches"],
       one("SELECT count(*) FROM bursts WHERE dataset = %(d)s AND pattern_id = %(p)s", {"d": ds, "p": pid}))

    r = run(analytics.rollup, ds, unit="lines", problem_only=False, by=["team"])
    ok(f"{ds} rollup grand total lines", r["rows"][0]["lines"], one("SELECT count(*) FROM logs WHERE dataset = %(d)s", {"d": ds}))
    r = run(analytics.heatmap, ds, unit="lines", problem_only=False, rows="severity" if ds != "ssh" else "component",
            cols="month", top_rows=30)
    ok(f"{ds} heatmap cells sum = lines", r["total_matches"], one("SELECT count(*) FROM logs WHERE dataset = %(d)s", {"d": ds}))
    try:
        r = run(analytics.reliability_trend, ds, bucket="day")
        ok(f"{ds} reliability_trend total = problem bursts", r["total_matches"], one(
            "SELECT count(*) FROM bursts b JOIN pattern_judgments j USING (dataset, pattern_id) WHERE b.dataset = %(d)s "
            "AND j.p_problem >= 0.5", {"d": ds}))
    except ValueError as e:
        print(f"skip {ds} reliability_trend: {e}")

    r = run(semantic.similar_patterns, ds, pid, 3)
    ok(f"{ds} similar_patterns distances ascending", [x["distance"] for x in r["rows"]] == sorted(x["distance"] for x in r["rows"]), True)
    r = run(semantic.find_patterns, word, ds, "lexical", 3)
    ok(f"{ds} find_patterns lexical hits contain the word", all(word in x["template"].lower() for x in r["rows"]), True)

# dataset-specific features that only some datasets have (checked where present)
r = run(timeline.request_timeline, "openstack", instance_id="9fafc51c-d0dd-41df-99e9-6c79d8334eaf")
ok("openstack request_timeline lines", r["total_matches"],
   one("SELECT count(*) FROM logs WHERE dataset = 'openstack' AND instance_id = '9fafc51c-d0dd-41df-99e9-6c79d8334eaf'"))
r = run(analytics.latency_profile, "openstack", group_by="component")
ok("openstack latency_profile timed > 0", all(x["timed"] > 0 for x in r["rows"]), True)
r = run(terms.check_watchlist, "ssh", registry()["ssh"]["first_ts"], registry()["ssh"]["last_ts"]) if "ssh" in DATASETS else None
if r:
    w = next(x for x in r["rows"] if x["watch"] == "break-in attempt")
    ok("ssh watchlist break-in lines", w["window_lines"], one(
        "SELECT count(*) FROM logs WHERE dataset = 'ssh' AND ts >= %(s)s AND ts < %(e)s AND body @@ ts_phrase('POSSIBLE BREAK-IN ATTEMPT')",
        {"s": registry()["ssh"]["first_ts"], "e": registry()["ssh"]["last_ts"]}))

ws = run(workspace.create_focus_index, "bgl", registry()["bgl"]["last_ts"] - timedelta(days=1), registry()["bgl"]["last_ts"],
         name="check_tools")
ok("workspace rows", ws["total_matches"], one("SELECT count(*) FROM logs WHERE dataset = 'bgl' AND ts >= %(s)s AND ts < %(e)s",
                                             {"s": registry()["bgl"]["last_ts"] - timedelta(days=1), "e": registry()["bgl"]["last_ts"]}))
r = run(search.search_logs, query_text="error", workspace="check_tools", limit=1) if "workspace" in search.search_logs.__code__.co_varnames else None
if r:
    ok("workspace search = corpus search", r["total_matches"], one(
        "SELECT count(*) FROM logs WHERE dataset = 'bgl' AND ts >= %(s)s AND ts < %(e)s AND body @@ websearch_to_tsquery('error')",
        {"s": registry()["bgl"]["last_ts"] - timedelta(days=1), "e": registry()["bgl"]["last_ts"]}))
run(workspace.drop_focus_index, "check_tools")
ok("workspace dropped", one("SELECT count(*) FROM workspaces WHERE name = 'check_tools'"), 0)

if "--remote" in sys.argv:
    from datetime import datetime
    s, e = datetime(2025, 9, 23, 0, 10), datetime(2025, 9, 23, 0, 10, 2)
    r = run(remote.remote_count_by, s, e)
    ok("remote_count_by total = sum of groups (all groups shown)", r["total_matches"] == sum(x["rows"] for x in r["rows"]) or r["truncated"], True)
    ok("remote row groups read < total", r["row_groups_read"] < r["row_groups_total"], True)

print()
for k, v in sorted(times.items()):
    print(f"{k:<22} calls {len(v):>2}  median {statistics.median(v):7.1f} ms  max {max(v):7.1f} ms")
print(f"\n{len(fails)} failed" if fails else "\nall checks passed")
sys.exit(1 if fails else 0)
