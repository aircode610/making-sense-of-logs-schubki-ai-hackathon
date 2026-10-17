"""Split a dataset into dev / held-out (D4/D5). SANCTIONED SCRIPT: prints aggregates only.

Usage: .venv/bin/python scripts/make_split.py --dataset hadoop   (plan 001)
       .venv/bin/python scripts/make_split.py --dataset gaia     (plan 002, see gaia_split below)

Hadoop (plan 001):
- Unit = job. Groups = (cluster run, application type); whole groups go to one side (no leakage).
- Moves job dirs:  dataset/hadoop/application_*  ->  dataset/dev/hadoop/jobs/  or  dataset/heldout/hadoop/jobs/
- Moves the original label file to dataset/heldout/hadoop/ (it lists held-out labels too).
- Writes questions.jsonl per side: {qid, job, wording, question, label}.
- Prints: sizes, class counts, novelty counts (held-out templates unseen by a dev-fitted Drain3). Nothing else.
"""
import argparse
import csv
import gzip
import json
import random
import re
import shutil
import sys
from collections import Counter, defaultdict
from datetime import date, datetime, timedelta
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline import hadoop, patterns  # noqa: E402

SRC = ROOT / "dataset" / "hadoop"
DEV = ROOT / "dataset" / "dev" / "hadoop"
HELD = ROOT / "dataset" / "heldout" / "hadoop"

HELDOUT_GROUPS = {("1445076437777", "PageRank"), ("1445144423722", "PageRank"), ("1445182159119", "PageRank")}
LABEL_MAP = {"Normal": "normal", "Machine down": "machine down",
             "Network disconnection": "network disconnection", "Disk full": "disk full"}
DEV_WORDINGS = ["Why did Hadoop job {job} fail?",
                "What went wrong with job {job}?",
                "Did job {job} complete normally? If not, what was the cause?"]
HELDOUT_ONLY_WORDING = "Job {job} looks unhealthy — what's the root cause?"


def read_labels(path: Path) -> dict[str, tuple[str, str]]:
    labels, app, cls = {}, None, None
    for line in path.read_text().splitlines():
        if line.startswith("### "):
            app = line[4:].strip()
        elif line.rstrip().endswith(":"):
            cls = LABEL_MAP[line.strip()[:-1]]
        elif line.startswith("+ "):
            labels[line[2:].strip()] = (app, cls)
    return labels


def write_questions(path: Path, jobs: list[str], labels: dict, wordings: list[str]) -> int:
    n = 0
    with path.open("w") as f:
        for job in sorted(jobs):
            for w, text in enumerate(wordings):
                f.write(json.dumps({"qid": f"{job}#w{w}", "job": job, "wording": w,
                                    "question": text.format(job=job), "label": labels[job][1]}) + "\n")
                n += 1
    return n


def hadoop_split():
    if DEV.exists() or HELD.exists():
        sys.exit("split already exists; refusing to redo it")

    labels = read_labels(SRC / "abnormal_label.txt")
    dev_jobs, held_jobs = [], []
    for job, (app, _) in labels.items():
        run = job.split("_")[1]
        (held_jobs if (run, app) in HELDOUT_GROUPS else dev_jobs).append(job)

    # novelty: fit Drain3 on dev, then count templates that held-out creates (aggregates only)
    miner = patterns.new_miner()
    for job in dev_jobs:
        patterns.assign(miner, hadoop.parse_job(SRC / job))
    dev_ids = {f"P{c.cluster_id}" for c in miner.drain.clusters}
    n_dev_templates = len(dev_ids)
    held_records = [r for job in held_jobs for r in hadoop.parse_job(SRC / job)]
    patterns.assign(miner, held_records)
    new_ids = {f"P{c.cluster_id}" for c in miner.drain.clusters} - dev_ids
    held_warn = [r for r in held_records if r["severity"] >= 13]
    novel_warn = sum(r["pattern_id"] in new_ids for r in held_warn)

    # move data
    for jobs, dest in ((dev_jobs, DEV), (held_jobs, HELD)):
        (dest / "jobs").mkdir(parents=True)
        for job in jobs:
            shutil.move(str(SRC / job), str(dest / "jobs" / job))
    shutil.move(str(SRC / "abnormal_label.txt"), str(HELD / "abnormal_label.txt"))
    n_dev_q = write_questions(DEV / "questions.jsonl", dev_jobs, labels, DEV_WORDINGS)
    n_held_q = write_questions(HELD / "questions.jsonl", held_jobs, labels, DEV_WORDINGS + [HELDOUT_ONLY_WORDING])

    # aggregates only
    print(f"dev:      {len(dev_jobs)} jobs, {n_dev_q} questions, classes {dict(Counter(labels[j][1] for j in dev_jobs))}")
    print(f"held-out: {len(held_jobs)} jobs, {n_held_q} questions, classes {dict(Counter(labels[j][1] for j in held_jobs))}")
    print(f"novelty/pattern: dev-fitted Drain3 has {n_dev_templates} templates; held-out adds {len(new_ids)} new templates; "
          f"{novel_warn}/{len(held_warn)} held-out WARN+ lines use a new template")
    dev_combos = {labels[j] for j in dev_jobs}
    new_combos = sorted({labels[j] for j in held_jobs} - dev_combos)
    print(f"novelty/evidence+verdict: (app, class) combos only in held-out: {new_combos}")
    print("novelty/finding: 1 question wording exists only in held-out")


# ---------------------------------------------------------------- GAIA (plan 002) ----------------------------------
# Sides by DAY (no window, pair or week crosses sides). Aug 1-24 = dev (incl. forced Aug 1-10); Aug 25-31 + all of July
# (webservice1 logs only) = held-out: "train on the past weeks, test on the next week + an unseen month".
# One chronological pass: Drain3 learns on dev days only; held-out rows are matched against the dev miner, unmatched
# ones go to a separate held-out miner (ids "H…") -> novelty counts, no template leakage into dev.
GAIA_DEV = ROOT / "dataset" / "dev" / "gaia"
GAIA_HELD = ROOT / "dataset" / "heldout" / "gaia"
AUG_HELD_FROM = date(2021, 8, 25)
SEED = 2026
WIN = timedelta(minutes=15)
MARGIN = timedelta(minutes=30)
JITTER_MAX_MIN = 5
PER_DAY = {"aug": {"normal": 5, "notrace": 3}, "jul": {"normal": 2, "notrace": 2}}
LEAD_PAIRS = {"dev": 150, "held": 60}          # positives per side; negatives = same number (half fault/fault, half fault/none)
WORDINGS = {
    "engineer": ["What went wrong in the system between {t1} and {t2}?",
                 "Was there an incident between {t1} and {t2}? If so, what caused it and where?",
                 "Users reported errors around {t}. What happened?"],
    "lead_same": ["Is the incident at {ta} the same problem as the one at {tb}?"],
    "lead_repeat": ["Has the incident at {t} happened before this week?"],
    "lead_period": ["What problems kept coming back in {period}?"],
    "manager": ["Which of these problems should we fix first: {a} or {b}?",
                "What should the team prioritise this week?"],
}
HELD_ONLY = {"engineer": "Something looked off between {t1} and {t2}: what's the root cause?",
             "lead_repeat": "Is {t} a repeat offender or something new?",
             "manager": "If we can fix only one thing this week, which one?"}
FMT = "%Y-%m-%d %H:%M"


def _side(d: date) -> str:
    return "held" if d.month == 7 or d >= AUG_HELD_FROM else "dev"


def _week(d: date) -> date:
    """Weeks counted from each period's start (Aug 1 dev, Aug 25 held-out, Jul 1), so no week crosses sides."""
    start = date(2021, 7, 1) if d.month == 7 else (AUG_HELD_FROM if d >= AUG_HELD_FROM else date(2021, 8, 1))
    return start + timedelta(days=7 * ((d - start).days // 7))


def _overlaps(intervals, a, b):
    return [i for i in intervals if i["start"] < b and i["end"] > a]


def _gaia_windows(inj, rng):
    """Engineer windows from injection records only (no logs read)."""
    faults = [i for i in inj if i["kind"] in ("file_missing", "permission_denied")]
    memory = [i for i in inj if i["kind"] == "memory"]
    wins, dropped_jul = [], 0
    for f in faults:
        if f["start"].month == 7 and f["kind"] == "file_missing" and f["service"] != "webservice1":
            dropped_jul += 1          # July has webservice1 logs only; a file fault elsewhere has no log path to it
            continue
        t1 = f["start"].replace(second=0, microsecond=0) - timedelta(minutes=rng.randint(0, JITTER_MAX_MIN))
        t2 = t1 + WIN
        others = [o for o in _overlaps(faults, t1, t2) if o is not f]
        wins.append({"slice": "fault", "fault": f["kind"], "root_service": f["service"], "t1": t1, "t2": t2,
                     "overlap": bool(others), "other_faults": [[o["kind"], o["service"]] for o in others]})
    days = sorted({d.date() for d in (i["start"] for i in inj)})
    for d in days:
        quota = PER_DAY["jul" if d.month == 7 else "aug"]
        mem_today = [m for m in memory if m["start"].date() == d]
        rng.shuffle(mem_today)
        n = 0
        for m in mem_today:
            if n >= quota["notrace"]:
                break
            t1 = m["start"].replace(second=0, microsecond=0) - timedelta(minutes=rng.randint(0, JITTER_MAX_MIN))
            if _overlaps(faults, t1 - MARGIN, t1 + WIN + MARGIN) or t1.date() != d:
                continue
            wins.append({"slice": "notrace", "fault": "none", "root_service": None, "memory_service": m["service"],
                         "t1": t1, "t2": t1 + WIN, "overlap": False, "other_faults": []})
            n += 1
        n = 0
        for h in rng.sample(range(24), 24):
            if n >= quota["normal"]:
                break
            for _ in range(20):
                t1 = datetime(d.year, d.month, d.day, h, rng.randint(0, 44))
                if not _overlaps(faults, t1 - MARGIN, t1 + WIN + MARGIN) and not _overlaps(memory, t1, t1 + WIN):
                    wins.append({"slice": "normal", "fault": "none", "root_service": None, "t1": t1, "t2": t1 + WIN,
                                 "overlap": False, "other_faults": []})
                    n += 1
                    break
    return wins, dropped_jul


def _mid(w):
    return (w["t1"] + WIN / 2).strftime(FMT)


def _gaia_lead(wins, side, rng):
    """Lead items within one side. Problem = (fault type, root-cause service)."""
    faults = [w for w in wins if w["slice"] == "fault" and not w["overlap"]]
    nones = [w for w in wins if w["slice"] != "fault"]
    prob = lambda w: (w["fault"], w["root_service"])
    pos = [(a, b) for i, a in enumerate(faults) for b in faults[i + 1:] if prob(a) == prob(b) and a["t1"].date() != b["t1"].date()]
    neg_ff = [(a, b) for i, a in enumerate(faults) for b in faults[i + 1:] if prob(a) != prob(b)]
    neg_fn = [(a, b) for a in faults for b in nones]
    k = min(LEAD_PAIRS[side], len(pos))
    pairs = [(a, b, True) for a, b in rng.sample(pos, k)]
    pairs += [(a, b, False) for a, b in rng.sample(neg_ff, min(k // 2, len(neg_ff)))]
    pairs += [(a, b, False) for a, b in rng.sample(neg_fn, min(k - k // 2, len(neg_fn)))]
    rng.shuffle(pairs)
    same = []
    for a, b, y in pairs:
        if rng.random() < 0.5:
            a, b = b, a
        same.append({"wa": a["wid"], "wb": b["wid"], "same_problem": y, "ta": _mid(a), "tb": _mid(b)})
    repeat, last_seen = [], {}       # known = problems seen in the previous 7 days (>= 1 h before this window)
    for w in sorted(faults, key=lambda w: w["t1"]):
        known = sorted(p for p, t in last_seen.items()
                       if w["t1"] - timedelta(days=7) <= t <= w["t1"] - timedelta(hours=1))
        repeat.append({"wid": w["wid"], "t": _mid(w), "known_problems": [list(p) for p in known],
                       "truth": list(prob(w)) if prob(w) in known else "new"})
        last_seen[prob(w)] = w["t1"]
    weeks = defaultdict(list)
    for w in faults:
        weeks[_week(w["t1"].date())].append(w)
    manager = []
    for start, ws in sorted(weeks.items()):
        probs = defaultdict(list)
        for w in ws:
            probs[prob(w)].append(w["wid"])
        if len(probs) >= 2:
            manager.append({"week_start": str(start), "problems": [{"fault": p[0], "service": p[1], "wids": v}
                                                                   for p, v in sorted(probs.items())]})
    return same, repeat, manager


def _write_side(dest, side, wins, inj, rng):
    dest.mkdir(parents=True)
    wordings = {k: v + ([HELD_ONLY[k]] if side == "held" and k in HELD_ONLY else []) for k, v in WORDINGS.items()}
    (dest / "wordings.json").write_text(json.dumps(wordings, indent=1))
    with (dest / "windows.jsonl").open("w") as f:
        for w in wins:
            f.write(json.dumps({**w, "t1": w["t1"].strftime(FMT), "t2": w["t2"].strftime(FMT)}) + "\n")
    n_q = 0
    with (dest / "questions.jsonl").open("w") as f:
        for w in wins:
            for i, text in enumerate(wordings["engineer"]):
                q = text.format(t1=w["t1"].strftime(FMT), t2=w["t2"].strftime(FMT), t=_mid(w))
                f.write(json.dumps({"qid": f"{w['wid']}#w{i}", "wid": w["wid"], "wording": i, "question": q,
                                    "t1": w["t1"].strftime(FMT), "t2": w["t2"].strftime(FMT),
                                    "label": {"fault": w["fault"], "root_service": w["root_service"]},
                                    "slice": w["slice"], "overlap": w["overlap"]}) + "\n")
                n_q += 1
    same, repeat, manager = _gaia_lead(wins, side, rng)
    for name, rows in (("lead_same.jsonl", same), ("lead_repeat.jsonl", repeat), ("manager_weeks.jsonl", manager)):
        with (dest / name).open("w") as f:
            for r in rows:
                f.write(json.dumps(r) + "\n")
    with (dest / "injections.csv").open("w", newline="") as f:
        wr = csv.writer(f)
        wr.writerow(["service", "kind", "start", "end"])
        for i in inj:
            wr.writerow([i["service"], i["kind"], i["start"].isoformat(), i["end"].isoformat()])
    return n_q, same, repeat, manager


class _Out:
    """Per-side streaming outputs: raw rows of window minutes (all levels) + WARN+ rows within ±30 min,
    minute rollup (service, severity, pattern) and distinct ERROR trace ids per (minute, service)."""

    def __init__(self, dest, wins):
        self.rows = gzip.open(dest / "rows.jsonl.gz", "wt")
        self.rollup = gzip.open(dest / "rollup.csv.gz", "wt")
        self.errtr = gzip.open(dest / "error_traces.csv.gz", "wt")
        self.rollup.write("minute,service,severity_text,pattern_id,n\n")
        self.errtr.write("minute,service,n_error_traces\n")
        self.full, self.warn = set(), set()
        for w in wins:
            m = w["t1"]
            while m < w["t2"]:
                self.full.add(m)
                m += timedelta(minutes=1)
            m = w["t1"] - MARGIN
            while m < w["t2"] + MARGIN:
                self.warn.add(m)
                m += timedelta(minutes=1)
        self.cnt, self.tr, self.day, self.n_rows = Counter(), defaultdict(set), None, 0

    def add(self, r, pid):
        m = r["ts"].replace(second=0, microsecond=0)
        if self.day is not None and m.date() != self.day:
            self.flush()
        self.day = m.date()
        self.cnt[(m, r["service"], r["severity_text"], pid)] += 1
        if r["severity_number"] >= 17 and r["trace_id"]:
            self.tr[(m, r["service"])].add(r["trace_id"])
        if m in self.full or (r["severity_number"] >= 13 and m in self.warn):
            self.rows.write(json.dumps({**r, "ts": r["ts"].isoformat(timespec="milliseconds"), "pattern_id": pid}) + "\n")
            self.n_rows += 1

    def flush(self):
        for (m, s, sev, pid), n in sorted(self.cnt.items()):
            self.rollup.write(f"{m:%Y-%m-%d %H:%M},{s},{sev},{pid},{n}\n")
        for (m, s), ids in sorted(self.tr.items()):
            self.errtr.write(f"{m:%Y-%m-%d %H:%M},{s},{len(ids)}\n")
        self.cnt, self.tr = Counter(), defaultdict(set)

    def close(self):
        self.flush()
        for f in (self.rows, self.rollup, self.errtr):
            f.close()


def _mask(rx, s):
    for r, n in rx:
        s = r.sub(n, s)
    return s


def gaia_split():
    from pipeline import gaia
    if GAIA_DEV.exists() or GAIA_HELD.exists():
        sys.exit("split already exists; refusing to redo it")
    rng = random.Random(SEED)
    inj = gaia.load_injections()
    wins, dropped_jul = _gaia_windows(inj, rng)
    n_all = len(wins)            # drop windows whose ±30 min context crosses a side boundary (rows would split)
    wins = [w for w in wins if _side((w["t1"] - MARGIN).date()) == _side((w["t2"] + MARGIN).date())
            and (w["t1"] - MARGIN).month == (w["t2"] + MARGIN).month]
    n_boundary = n_all - len(wins)
    order = list(range(len(wins)))
    rng.shuffle(order)
    for k, i in enumerate(order):
        wins[i]["wid"] = f"w{k:04d}"
    wins.sort(key=lambda w: w["t1"])
    by_side = {s: [w for w in wins if _side(w["t1"].date()) == s] for s in ("dev", "held")}
    inj_side = {s: [i for i in inj if _side(i["start"].date()) == s] for s in ("dev", "held")}
    parts = {"dev": by_side["dev"], "held Aug week": [w for w in by_side["held"] if w["t1"].month == 8]}
    for s, ws in parts.items():     # stratification check (aggregates): both fault types in dev and in the Aug week
        kinds = {w["fault"] for w in ws if w["slice"] == "fault"}
        if kinds != {"file_missing", "permission_denied"}:
            sys.exit(f"abort: {s} lacks a fault type (has {sorted(kinds)}); revisit the split in the plan")

    summary = {}
    for s, dest in (("dev", GAIA_DEV), ("held", GAIA_HELD)):
        summary[s] = _write_side(dest, s, by_side[s], inj_side[s], rng)

    # ---- one chronological pass over the logs: Aug (all services), then July (webservice1) ----
    rx = [(re.compile(p), f"<{n}>") for p, n in patterns.MASKS]
    dev_miner, held_miner = patterns.new_miner(), patterns.new_miner()
    memo = {"dev": {}, "held": {}}
    outs = {"dev": _Out(GAIA_DEV, by_side["dev"]), "held": _Out(GAIA_HELD, by_side["held"])}
    stats = Counter()
    for name in ("2021-08", "webservice1_2021-07"):
        for row in gaia.stream_rows(name):
            r = gaia.parse_record(row["service"], row["message"])
            if r is None:
                stats["malformed"] += 1
                continue
            side = _side(r["ts"].date())
            first = r["body"].split("\n", 1)[0]
            key = _mask(rx, first)
            pid = memo[side].get(key)
            if pid is None:
                if side == "dev":
                    pid = f"P{dev_miner.add_log_message(first)['cluster_id']}"
                else:
                    c = dev_miner.match(first)
                    pid = f"P{c.cluster_id}" if c else f"H{held_miner.add_log_message(first)['cluster_id']}"
                if len(memo[side]) > 3_000_000:
                    memo[side].clear()
                memo[side][key] = pid
            outs[side].add(r, pid)
            stats[f"{side}_rows"] += 1
            if side == "held" and r["severity_number"] >= 13:
                stats["held_warn"] += 1
                stats["held_warn_new"] += pid.startswith("H")
    for o in outs.values():
        o.close()
    patterns.save(dev_miner, GAIA_DEV / "drain3_dev.json")
    patterns.dump_templates(dev_miner, GAIA_DEV / "templates.json")
    patterns.save(held_miner, GAIA_HELD / "drain3_held_new.json")

    # ---- aggregates only ----
    for s in ("dev", "held"):
        n_q, same, repeat, manager = summary[s]
        ws = by_side[s]
        days = sorted({w["t1"].date() for w in ws})
        print(f"[{s}] days {len(days)} ({days[0]}..{days[-1]}), windows {len(ws)}, engineer questions {n_q}, "
              f"log rows streamed {stats[f'{s}_rows']}, rows kept {outs[s].n_rows}")
        print(f"  windows by slice: {dict(Counter(w['slice'] for w in ws))}; overlapping fault windows: "
              f"{sum(w['overlap'] for w in ws)}")
        print(f"  fault windows by (fault, service): "
              f"{dict(sorted(Counter((w['fault'], w['root_service']) for w in ws if w['slice'] == 'fault').items()))}")
        print(f"  lead same-problem pairs {len(same)} (positive {sum(p['same_problem'] for p in same)}); "
              f"repeat items {len(repeat)} (new {sum(r['truth'] == 'new' for r in repeat)}); manager weeks {len(manager)} "
              f"(problems/week {[len(m['problems']) for m in manager]})")
    print(f"July file faults dropped (no webservice1 path): {dropped_jul}; windows dropped at side boundaries: "
          f"{n_boundary}; malformed rows: {stats['malformed']}")
    print(f"novelty/pattern: dev Drain3 templates {len(dev_miner.drain.clusters)}; held-out-only templates "
          f"{len(held_miner.drain.clusters)}; {stats['held_warn_new']}/{stats['held_warn']} held-out WARN+ rows use one")
    print("novelty/time+telemetry: held-out = Aug 25-31 (future week) + July (unseen month, webservice1 logs only)")
    print("novelty/question: 1 held-out-only wording each for engineer, lead (repeat) and manager")


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--dataset", required=True, choices=["hadoop", "gaia"])
    args = ap.parse_args()
    hadoop_split() if args.dataset == "hadoop" else gaia_split()


if __name__ == "__main__":
    main()
