"""Plan 051 check: count_by / trend equal the awk/grep reference counts (plans 002, 050); trend sums = totals; timings.
Run (BGL + OpenStack loaded): .venv/bin/python bench/check_counts.py"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / "src/mcp_server"))
from dotenv import load_dotenv

load_dotenv(Path(__file__).resolve().parents[2] / ".env")
from counts import count_by, trend

times, fails = [], []


def groups(**kw):
    r = count_by(**kw)
    times.append(r["elapsed_ms"])
    return {row[kw["group_by"]]: row["lines"] for row in r["rows"]}, r


def check(name, got, want):
    ok = got == want
    print(("ok   " if ok else "FAIL ") + name + ("" if ok else f"\n   got  {got}\n   want {want}"))
    if not ok:
        fails.append(name)


g, r = groups(group_by="severity", dataset="bgl")
check("bgl severity", g, {"INFO": 3735823, "FATAL": 855501, "ERROR": 112355, "WARNING": 23357, "SEVERE": 19213, "FAILURE": 1714})
check("bgl total", r["total_lines"], 4747963)
g, _ = groups(group_by="component", dataset="bgl")
check("bgl component", g, {"KERNEL": 4324967, "APP": 228536, "DISCOVERY": 97172, "MMCS": 88930, "HARDWARE": 5148,
                           "MONITOR": 1681, "LINKCARD": 1170, "CMCS": 211, "BGLMASTER": 145, "SERV_NET": 3})
g, _ = groups(group_by="severity", dataset="bgl", start="2005-12-05")
check("bgl severity since 2005-12-05", g, {"INFO": 90615, "FATAL": 38420, "ERROR": 188, "WARNING": 459, "SEVERE": 188, "FAILURE": 4})
g, _ = groups(group_by="component", dataset="openstack")
check("openstack component", g, {"nova-compute": 104086, "nova-api": 102868, "nova-scheduler": 866})
g, _ = groups(group_by="severity", dataset="openstack")
check("openstack severity", g, {"INFO": 204506, "WARNING": 3118, "ERROR": 194, "CRITICAL": 2})
BASE = ("bgl", "openstack")  # reference counts exist for the base corpus; extra datasets are checked in check_tools.py


def base_only(g: dict) -> dict:
    """Teams of the base corpus only (extra datasets bring their own teams)."""
    merged = {}
    for ds in BASE:
        for k, v in groups(**{**g, "dataset": ds})[0].items():
            merged[k] = merged.get(k, 0) + v
    return dict(sorted(merged.items(), key=lambda kv: -kv[1]))


g = base_only({"group_by": "team"})
check("team (both datasets)", g, {"node-platform": 4331285, "hpc-workloads": 228536, "cluster-control": 188142,
                                  "cloud-compute": 104952, "cloud-api": 102868})
g, _ = groups(group_by="dataset", query_text="parity")
check("fts parity", g, {"bgl": 121498})
g, _ = groups(group_by="dataset", query_text='"cache parity error"')
check("fts phrase", g, {"bgl": 106220})
g = base_only({"group_by": "team", "severity": "ERROR"})
check("team where severity=ERROR", g, {"cluster-control": 112355, "cloud-compute": 192, "cloud-api": 2})
g, _ = groups(group_by="dataset", status=200)
check("status=200 present only in openstack", list(g), ["openstack"])
r = count_by(group_by="node", dataset="bgl", limit=5)
check("node groups_total / truncated", (r["groups_total"], r["truncated"]), (69241, True))

# trend: buckets sum to the totals of count_by with the same filters
for kw in [dict(dataset="bgl"), dict(dataset="openstack", bucket="hour"), dict(dataset="bgl", severity="FATAL", bucket="day"),
           dict(dataset="bgl", team="node-platform", bucket="week"), dict(dataset="openstack", query_text="error", bucket="hour")]:
    t = trend(**kw)
    times.append(t["elapsed_ms"])
    c = count_by(group_by="dataset", **{k: v for k, v in kw.items() if k != "bucket"})
    check(f"trend sum {kw} [{t['bucket']}]", (sum(x["lines"] for x in t["rows"]), t["truncated"]), (c["total_lines"], False))
t = trend(dataset="bgl", group_by="team", top_groups=3)
times.append(t["elapsed_ms"])
by = {}
for x in t["rows"]:
    by[x["team"]] = by.get(x["team"], 0) + x["lines"]
check("trend by team sums (top 3)", by, {"node-platform": 4331285, "hpc-workloads": 228536, "cluster-control": 188142})
t = trend(dataset="bgl", bucket="day", start="2005-11-01", end="2005-11-04", severity="FATAL")
check("trend zero-fill day buckets", [x["lines"] for x in t["rows"]], [92, 0, 5655])

# plan 004: every BGL row has a pattern; patterns / bursts / episodes account for every line
from core import query

check("bgl rows without pattern_id",
      query("SELECT count(*) AS n FROM logs WHERE dataset = 'bgl' AND pattern_id IS NULL", {})[0]["n"], 0)
check("bgl patterns", query("SELECT count(*) AS n FROM patterns WHERE dataset = 'bgl'", {})[0]["n"], 1126)
for tbl in ("patterns", "bursts", "episodes"):
    check(f"bgl lines in {tbl}", query(f"SELECT sum(lines) AS n FROM {tbl} WHERE dataset = 'bgl'", {})[0]["n"], 4747963)
check("kernel panic pattern (lines, nodes, bursts)",
      tuple(query("SELECT lines, nodes, bursts FROM patterns WHERE dataset = 'bgl' AND template = 'kernel panic'", {})[0].values()),
      (18, 18, 13))

# plan 053: same for OpenStack (ids from 100001; HTTP status kept in the template)
check("openstack rows without pattern_id",
      query("SELECT count(*) AS n FROM logs WHERE dataset = 'openstack' AND pattern_id IS NULL", {})[0]["n"], 0)
check("openstack patterns", query("SELECT count(*) AS n FROM patterns WHERE dataset = 'openstack'", {})[0]["n"], 106)
for tbl in ("patterns", "bursts", "episodes"):
    check(f"openstack lines in {tbl}",
          query(f"SELECT sum(lines) AS n FROM {tbl} WHERE dataset = 'openstack'", {})[0]["n"], 207820)
check("openstack problem-level lines (194 ERROR + 2 CRITICAL + 3118 WARNING + 2 HTTP 503; WARN counts since plan 011)",
      query("SELECT sum(problem_lines) AS n FROM patterns WHERE dataset = 'openstack'", {})[0]["n"], 194 + 2 + 3118 + 2)
check("openstack 503 on servers/detail is its own pattern",
      query("SELECT lines AS n FROM patterns WHERE dataset = 'openstack' AND strpos(template, 'servers/detail HTTP/<N>\" status: 503') > 0", {})[0]["n"], 2)

# plan 054: value_outliers = an independent recomputation in Python (raw lines, Python regex + statistics)
import re
from outliers import value_outliers

o = value_outliers(dataset="openstack", limit=50)
times.append(o["elapsed_ms"])
vals = {}
# independent of the loader's duration_ms: parse the raw message text again (HTTP time, or 'Took N seconds')
for r in query("SELECT l.pattern_id, l.object_id, l.body FROM logs l JOIN patterns p USING (dataset, pattern_id) "
               "WHERE l.dataset = 'openstack' AND (strpos(p.template, 'Took <N> seconds') > 0 "
               "OR strpos(p.template, ' time: <N>') > 0)", {}):
    m = re.search(r"status: \d+ len: \d+ time: ([\d.]+)", r["body"] or "") or re.search(r"Took ([\d.]+) seconds", r["body"] or "")
    v = float(m.group(1)) if m else None
    if v is not None:
        vals.setdefault(r["pattern_id"], []).append((v, r["object_id"]))
ref_lines, ref_inst = 0, set()
for pid, xs in vals.items():
    med = statistics.median(v for v, _ in xs)
    thr = max(med + 6 * statistics.median(abs(v - med) for v, _ in xs), med + 2)
    hits = [i for v, i in xs if v > thr]
    ref_lines += len(hits)
    ref_inst |= {i for i in hits if i}
check("value_outliers (flagged lines, VMs) vs Python", (o["total_matches"], o["flagged_objects"]), (ref_lines, len(ref_inst)))
check("value_outliers flagged VMs (objects field)", {x["object_id"] for x in o["objects"]}, ref_inst)

# plan 055: rate_vs_baseline = an independent recomputation in Python (raw timestamps, same-length windows back from
# the window start, clipped to the dataset's first line)
from datetime import datetime as D, timedelta as TD
from counts import rate_vs_baseline


def ref_baseline(sql, ws, we, days, first_ts):
    w = we - ws
    n_win = int((ws - max(ws - TD(days=days), first_ts)) / w)
    ts = [r["ts"] for r in query(sql, {"s": ws - n_win * w, "e": we})]
    now_n = sum(t >= ws for t in ts)
    per = [0] * n_win
    for t in ts:
        if t < ws:
            per[int((ws - t) / w)] += 1
    return now_n, n_win, sum(per), max(per, default=None), sum(n >= now_n > 0 for n in per)


def got_baseline(r):
    x = r["rows"][0]
    return (x["window_lines"], x["baseline_windows"], x.get("baseline_lines"), x.get("baseline_max_per_window"),
            x.get("baseline_windows_at_or_above"))


first = {d: query("SELECT min(ts) AS t FROM logs WHERE dataset = %(d)s", {"d": d})[0]["t"] for d in ("bgl", "openstack")}
KF = "SELECT ts FROM logs WHERE dataset = 'bgl' AND component = 'KERNEL' AND severity = 'FATAL' AND ts >= %(s)s AND ts < %(e)s"
for name, ws, we in (("1 h", D(2005, 11, 17, 5), D(2005, 11, 17, 6)), ("1 day", D(2005, 11, 17), D(2005, 11, 18)),
                     ("5 min", D(2005, 11, 17, 5, 30), D(2005, 11, 17, 5, 35))):
    rb = rate_vs_baseline(dataset="bgl", component="KERNEL", severity="FATAL", start=ws, end=we)
    times.append(rb["elapsed_ms"])
    check(f"rate_vs_baseline KERNEL FATAL {name} window vs Python", got_baseline(rb), ref_baseline(KF, ws, we, 7, first["bgl"]))
ws, we = D(2017, 5, 16, 6), D(2017, 5, 16, 7)
rb = rate_vs_baseline(dataset="openstack", status=503, start=ws, end=we)
check("rate_vs_baseline clipped at OpenStack start (vs Python, clipped flag)",
      (got_baseline(rb), rb["rows"][0]["baseline_clipped"], rb["new_in_baseline"]),
      (ref_baseline("SELECT ts FROM logs WHERE dataset = 'openstack' AND status = 503 AND ts >= %(s)s AND ts < %(e)s",
                    ws, we, 7, first["openstack"]), True, True))
check("rate_vs_baseline no data before the first BGL hour",
      rate_vs_baseline(dataset="bgl", severity="FATAL", start=D(2005, 6, 3, 15), end=D(2005, 6, 3, 16))["no_baseline_data"], True)
check("rate_vs_baseline new pattern (R43-M0 kernel panic)",
      rate_vs_baseline(dataset="bgl", location="R43/R43-M0", query_text="kernel panic",
                       start=D(2005, 8, 19, 13), end=D(2005, 8, 19, 15))["new_in_baseline"], True)

# plan 057: every logged level word has a severity_number (an unmapped word = add it to data/severity_map.csv)
check("level words without severity_number (add to data/severity_map.csv)",
      query("SELECT list(DISTINCT dataset || ':' || severity) AS w FROM logs "
            "WHERE severity IS NOT NULL AND severity_number IS NULL", {})[0]["w"] or [], [])
check("severity_number never set without a level word",
      query("SELECT count(*) AS n FROM logs WHERE severity IS NULL AND severity_number IS NOT NULL", {})[0]["n"], 0)

times.sort()
print(f"\n{len(times)} calls: median {statistics.median(times):.0f} ms, p95 {times[int(len(times) * .95) - 1]:.0f} ms, max {times[-1]:.0f} ms")
sys.exit(1 if fails else 0)
