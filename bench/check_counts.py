"""Plan 051 check: count_by / trend equal the awk/grep reference counts (plans 002, 050); trend sums = totals; timings.
Run (BGL + OpenStack loaded): .venv/bin/python bench/check_counts.py"""
import statistics
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent / "mcp_server"))
from dotenv import load_dotenv

load_dotenv(Path(__file__).parent.parent / ".env")
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
g, r = groups(group_by="team")
check("team (both datasets)", g, {"node-platform": 4331285, "hpc-workloads": 228536, "cluster-control": 188142,
                                  "cloud-compute": 104952, "cloud-api": 102868})
g, _ = groups(group_by="dataset", query_text="parity")
check("fts parity", g, {"bgl": 121498})
g, _ = groups(group_by="dataset", query_text='"cache parity error"')
check("fts phrase", g, {"bgl": 106220})
g, _ = groups(group_by="team", severity="ERROR")
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

times.sort()
print(f"\n{len(times)} calls: median {statistics.median(times):.0f} ms, p95 {times[int(len(times) * .95) - 1]:.0f} ms, max {times[-1]:.0f} ms")
sys.exit(1 if fails else 0)
