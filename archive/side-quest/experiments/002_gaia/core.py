"""Experiment 002 core (plans/002-gaia-question-design.md): shared by the dev runner and the held-out evaluation.

Every function takes a `Run` (schema, data dir, cache) so the same code runs on dev and, once, on held-out.
Both models always get the identical state + questions (D11); `fairness_ok` checks that per pair.
"""
import gzip
import json
import math
import random
import statistics
import sys
import threading
import time
import zlib
from collections import Counter, defaultdict
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass, field
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from sklearn.feature_extraction.text import TfidfVectorizer  # noqa: E402
from sklearn.linear_model import LogisticRegression  # noqa: E402

from pipeline import config, db, gaia, gaia_bricks as B, gaia_prompts as P, gaia_queries as Q, metrics  # noqa: E402

LABELS = B.LABELS
WORKERS = 8
CATALOG = [  # plan §3.5: written by hand from GAIA's architecture, before running
    ("webservice1", "frontend", True, "web team"), ("webservice2", "frontend", True, "web team"),
    ("mobservice1", "backend", False, "mobile team"), ("mobservice2", "backend", False, "mobile team"),
    ("logservice1", "backend", False, "platform team"), ("logservice2", "backend", False, "platform team"),
    ("redisservice1", "data", False, "platform team"), ("redisservice2", "data", False, "platform team"),
    ("dbservice1", "data", False, "data team"), ("dbservice2", "data", False, "data team"),
]


@dataclass
class Run:
    schema: str
    data: Path                     # dataset/<side>/gaia
    container_data: str            # same folder as seen inside the SereneDB container (/dataset/...)
    cache: Path
    out: Path
    otlp_url: str
    run_id: str = ""
    windows: list = field(default_factory=list)
    templates: dict = field(default_factory=dict)
    _local: object = field(default_factory=threading.local)

    def conn(self):
        if not hasattr(self._local, "conn"):
            self._local.conn = db.connect()
        return self._local.conn

    def ctx(self) -> B.Ctx:
        return B.Ctx(conn=self.conn(), schema=self.schema, templates=self.templates, cache_dir=self.cache,
                     corpus_windows=self.corpus_windows, n_corpus_windows=len(self.windows))

    corpus_windows: dict = field(default_factory=dict)


def jl(path: Path) -> list[dict]:
    return [json.loads(l) for l in path.read_text().splitlines() if l.strip()]


# ------------------------------------------------------------------ ingest ----------------------------------------
def ingest(run: Run, templates_from: Path):
    """Rollup + error traces (read_csv inside SereneDB), windows table, catalog, raw rows over OTLP."""
    c = run.conn()
    s = run.schema
    t0 = time.time()
    c.execute(Q.LOAD_ROLLUP.format(s=s, path=f"{run.container_data}/rollup.csv.gz"))
    c.execute(Q.LOAD_ERROR_TRACES.format(s=s, path=f"{run.container_data}/error_traces.csv.gz"))
    c.execute(f"CREATE OR REPLACE TABLE {s}.gaia_catalog (service VARCHAR, tier VARCHAR, customer_facing BOOLEAN, owner VARCHAR)")
    for row in CATALOG:
        c.execute(f"INSERT INTO {s}.gaia_catalog VALUES (%s, %s, %s, %s)", row)
    c.execute(f"CREATE OR REPLACE TABLE {s}.gaia_windows (wid VARCHAR, t1 TIMESTAMP, t2 TIMESTAMP)")
    for w in jl(run.data / "windows.jsonl"):
        c.execute(f"INSERT INTO {s}.gaia_windows VALUES (%s, %s, %s)", (w["wid"], w["t1"], w["t2"]))
    svc = "('" + "','".join(Q.SERVICES) + "')"
    c.execute(f"DELETE FROM {s}.otel_logs WHERE service_name IN {svc}")
    batch, n = [], 0
    for line in gzip.open(run.data / "rows.jsonl.gz", "rt"):
        batch.append(json.loads(line))
        if len(batch) == 5000:
            _send(batch, run.otlp_url)
            n += len(batch)
            batch = []
    if batch:
        _send(batch, run.otlp_url)
        n += len(batch)
    c.execute(f"VACUUM (REFRESH_TABLE) {s}.otel_logs")
    got = c.execute(f"SELECT count(*) AS n FROM {s}.otel_logs WHERE service_name IN {svc}").fetchone()["n"]
    r = c.execute(f"SELECT count(*) AS n, min(minute) AS a, max(minute) AS b FROM {s}.gaia_rollup").fetchone()
    print(f"ingest: {got}/{n} raw rows, rollup {r['n']} rows ({r['a']}..{r['b']}), {time.time() - t0:.0f}s")


def _send(rows, url):
    import base64
    import urllib.request
    auth = "Basic " + base64.b64encode(":".join(config.OTLP_AUTH).encode()).decode()
    req = urllib.request.Request(url, data=json.dumps(gaia.otlp_payload(rows)).encode(), method="POST",
                                 headers={"Content-Type": "application/json", "Authorization": auth})
    with urllib.request.urlopen(req) as resp:
        assert resp.status == 200


# ------------------------------------------------------------------ tracing ---------------------------------------
TRACE_DDL = """CREATE TABLE IF NOT EXISTS {s}.traces (run_id VARCHAR, qid VARCHAR, step VARCHAR, started_at TIMESTAMP,
latency_ms DOUBLE, input_json VARCHAR, output_json VARCHAR, error VARCHAR)"""


def trace(run: Run, qid: str, step: str, inp, out, latency_ms=0.0, error=None):
    run.conn().execute(f"INSERT INTO {run.schema}.traces VALUES (%s, %s, %s, now(), %s, %s, %s, %s)",
                       (run.run_id, qid, step, latency_ms, json.dumps(inp, default=str), json.dumps(out, default=str),
                        error))


def pmap(fn, items):
    with ThreadPoolExecutor(WORKERS) as ex:
        return list(ex.map(fn, items))


def fairness_ok(jev_req: dict, llm_req: dict) -> bool:
    """Same state and same options per question: the LLM prompt must contain the exact state JSON and every option key."""
    prompt = llm_req["prompt"]
    if json.dumps(jev_req["state"], indent=1) not in prompt:
        return False
    return all(json.dumps(k) in prompt for q in jev_req["questions"].values() if q["type"] == "choice" for k in q["criteria"])


# ------------------------------------------------------------------ engineer --------------------------------------
def engineer(run: Run, questions: list[dict], evidence_variant: str, design: str, models=("jev", "llm"),
             repeat: int = 0, shuffle_seed: int | None = None) -> list[dict]:
    """One (evidence, question design) variant on both models. Returns one row per question with both findings."""
    wins = {w["wid"]: w for w in run.windows}

    def one(q):
        ctx = run.ctx()
        w = wins[q["wid"]]
        ev = B.evidence(w, ctx, evidence_variant)
        state = B.state_of(q, ev)
        qs = P.engineer_questions(design, list(ev["items"]), B.service_candidates(w, ctx) if "Q7" in design else {})
        if shuffle_seed is not None:
            qs = P.shuffled(qs, shuffle_seed + zlib.crc32(q["qid"].encode()))
        row = {"qid": q["qid"], "wid": q["wid"], "wording": q["wording"], "label": q["label"]["fault"],
               "root_label": q["label"]["root_service"], "slice": q["slice"], "overlap": q["overlap"],
               "variant": f"{evidence_variant}/{design}", "evidence_pattern_ids": [v["_pattern_id"] for v in ev["items"].values()],
               "n_candidates": ev["n_candidates"]}
        reqs = {}
        for m in models:
            r = B.ask(m, state, qs, ctx, repeat)
            f = B.engineer_finding(design, r["answers"])
            row[m] = {**f, "latency_ms": r["latency_ms"], "cost_usd": r["cost_usd"], "input_tokens": r["input_tokens"],
                      "error": r.get("error")}
            reqs[m] = r["request"]
            trace(run, q["qid"], f"{m}:{evidence_variant}/{design}" + (f":rep{repeat}" if repeat else ""),
                  r["request"], {"answers": r["answers"], "finding": f, "raw_reply": r.get("raw_reply")}, r["latency_ms"],
                  r.get("error"))
        if "jev" in reqs and "llm" in reqs:
            row["fair"] = fairness_ok(reqs["jev"], reqs["llm"])
        return row
    return pmap(one, questions)


# ------------------------------------------------------------------ baselines -------------------------------------
def b2_raw(run: Run, questions: list[dict]) -> list[dict]:
    """B2: LLM on raw logs (window WARN+ lines + first/last 50 lines, <= 120k chars), wording 0 only (amendment 2).
    Same fault options/definitions + root-service options (plain service names)."""
    wins = {w["wid"]: w for w in run.windows}

    def one(q):
        ctx = run.ctx()
        w = wins[q["wid"]]
        f = B.window_facts(w, ctx)
        ht = query_rows(run, Q.WINDOW_HEAD_TAIL, t1=w["t1"], t2=w["t2"], n=config.RAW_LOG_HEAD_TAIL)
        lines = [f"{r['timestamp']} {r['service']} {r['severity_text']} {r['body']}" for r in f["raw_warn"]]
        head = [f"{r['timestamp']} {r['service']} {r['severity_text']} {r['body']}" for r in ht]
        text = "\n".join(head[:config.RAW_LOG_HEAD_TAIL] + lines + head[config.RAW_LOG_HEAD_TAIL:])[:config.RAW_LOG_MAX_CHARS]
        state = {"question": q["question"], "raw_logs": text or "no lines"}
        qs = {"fault": P._fault_choice(P.OPTIONS, "`question` asks about a time window of a multi-service system. "
                                       "`raw_logs` holds the window's raw WARN/ERROR lines plus its first and last "
                                       "lines. Which option best describes what happened in this window?"),
              "root_service": P.root_service({s: s for s in Q.SERVICES})}
        r = B.ask("llm", state, qs, ctx)
        fnd = B.engineer_finding("Q7", r["answers"])
        trace(run, q["qid"], "B2_llm_raw_logs", {"prompt_chars": len(r["request"]["prompt"])},
              {"answers": r["answers"], "finding": fnd}, r["latency_ms"], r.get("error"))
        return {"qid": q["qid"], "wid": q["wid"], "label": q["label"]["fault"], "root_label": q["label"]["root_service"],
                "slice": q["slice"], "overlap": q["overlap"], "wording": q["wording"],
                "b2": {**fnd, "latency_ms": r["latency_ms"], "cost_usd": r["cost_usd"], "error": r.get("error")}}
    return pmap(one, [q for q in questions if q["wording"] == 0])


def query_rows(run: Run, sql: str, **params):
    return db.query(run.conn(), sql, run.schema, **params)


def window_doc(run: Run, wid: str) -> str:
    """B3 features: the window's (service|severity|pattern) tokens, repeated by log count (capped)."""
    w = next(x for x in run.windows if x["wid"] == wid)
    f = B.window_facts(w, run.ctx())
    return " ".join(" ".join([f"{r['service']}|{r['severity_text']}|{r['pattern_id']}"] * min(int(r["n_window"]), 50))
                    for r in f["patterns"])


def b3_classifier(run: Run, rows: list[dict], folds: dict) -> list[dict]:
    """TF-IDF + LR per fold (train on the other folds' windows)."""
    docs = {wid: window_doc(run, wid) for wid in {r["wid"] for r in rows}}
    lab = {r["wid"]: r["label"] for r in rows}
    out = {}
    for k in sorted(set(folds.values())):
        train = [w for w in docs if folds[w] != k]
        test = [w for w in docs if folds[w] == k]
        vec = TfidfVectorizer(token_pattern=r"\S+", lowercase=False, sublinear_tf=True)
        clf = LogisticRegression(max_iter=3000, class_weight="balanced")
        clf.fit(vec.fit_transform([docs[w] for w in train]), [lab[w] for w in train])
        for w, p in zip(test, clf.predict_proba(vec.transform([docs[w] for w in test]))):
            probs = {c: 0.0 for c in LABELS} | dict(zip(clf.classes_, p))
            out[w] = {"pred": max(probs, key=probs.get), "probs": probs, "confidence": B.choice_confidence(probs)}
    return [{**r, "b3": out[r["wid"]]} for r in rows]


RULES = [("file_missing", ["no such file", "not found", "missing", "does not exist"]),
         ("permission_denied", ["denied", "refuse", "permission", "forbidden", "unauthorized"])]


def b4_rules(run: Run, rows: list[dict]) -> list[dict]:
    """Keyword rules on the window's anomalous patterns (E1 candidates); root service = earliest error spike."""
    wins = {w["wid"]: w for w in run.windows}
    out = []
    for r in rows:
        ctx = run.ctx()
        f = B.window_facts(wins[r["wid"]], ctx)
        text = " ".join((ctx.templates.get(x["pattern_id"], "") + " " + f["examples"].get((x["service"], x["pattern_id"]), "")).lower()
                        for x in B._anomalous(f))
        pred = next((c for c, words in RULES if any(wd in text for wd in words)), "none")
        probs = {c: float(c == pred) for c in LABELS}
        spike = B.earliest_spike(f)
        out.append({**r, "b4": {"pred": pred, "probs": probs, "confidence": 1.0,
                                "root_service": spike if spike != "none" else "none"}})
    return out


# ------------------------------------------------------------------ CV + metrics ----------------------------------
def make_folds(windows: list[dict], k: int = 5, seed: int = 2026) -> dict:
    """Whole days -> k folds, balanced by number of fault windows then windows (greedy). wid -> fold."""
    day_f, day_n = Counter(), Counter()
    for w in windows:
        d = w["t1"][:10]
        day_n[d] += 1
        day_f[d] += w["slice"] == "fault"
    days = sorted(day_n, key=lambda d: (-day_f[d], -day_n[d], d))
    rng = random.Random(seed)
    load = [[0, 0, i] for i in range(k)]
    fold_of_day = {}
    for d in days:
        rng.shuffle(load)
        load.sort(key=lambda x: (x[0], x[1]))
        load[0][0] += day_f[d]
        load[0][1] += day_n[d]
        fold_of_day[d] = load[0][2]
    return {w["wid"]: fold_of_day[w["t1"][:10]] for w in windows}


def mrows(rows, key):
    """Rows for pipeline/metrics.py from one system's findings (primary metric excludes overlapping fault windows)."""
    return [{"label": r["label"], "class": r[key]["pred"], "probabilities": r[key]["probs"],
             "confidence": r[key]["confidence"], "latency_ms": r[key].get("latency_ms", 0),
             "cost_usd": r[key].get("cost_usd", 0.0), "wid": r["wid"], "slice": r["slice"], "wording": r.get("wording", 0),
             "abstain": r[key].get("abstain", False), "root_label": r.get("root_label"),
             "root_pred": r[key].get("root_service")} for r in rows if not r["overlap"] and key in r]


def day_bootstrap_ci(rows, fn, n=1000, seed=0):
    by_day = defaultdict(list)
    for r in rows:
        by_day[r["wid_day"]].append(r)
    days = list(by_day)
    rng = random.Random(seed)
    vals = sorted(fn([x for _ in days for x in by_day[rng.choice(days)]]) for _ in range(n))
    return vals[int(0.025 * n)], vals[int(0.975 * n)]


def score(rows: list[dict], folds: dict, wday: dict) -> dict:
    """All engineer metrics for one system's rows (from mrows)."""
    for r in rows:
        r["wid_day"] = wday[r["wid"]]
    f1 = lambda rs: metrics.macro_f1(rs, LABELS)  # noqa: E731
    per_fold = [f1([r for r in rows if folds[r["wid"]] == k]) for k in sorted(set(folds.values()))]
    lat = sorted(r["latency_ms"] for r in rows)
    fault = [r for r in rows if r["slice"] == "fault"]
    notrace = [r for r in rows if r["slice"] == "notrace"]
    loc = [r for r in fault if r["root_pred"] is not None]
    out = {"n": len(rows), "macro_f1": f1(rows), "macro_f1_ci95": day_bootstrap_ci(rows, f1),
           "fold_mean": statistics.mean(per_fold), "fold_sd": statistics.pstdev(per_fold),
           "accuracy": metrics.accuracy(rows), "brier": metrics.brier(rows, LABELS), "ece": metrics.ece(rows),
           "fault_recall": statistics.mean(r["class"] == r["label"] for r in fault) if fault else None,
           "no_fault_on_notrace": statistics.mean(r["class"] == "none" for r in notrace) if notrace else None,
           "false_none_on_fault": statistics.mean(r["class"] == "none" for r in fault) if fault else None,
           "abstain_rate": statistics.mean(r["abstain"] for r in rows),
           "root_top1": statistics.mean(r["root_pred"] == r["root_label"] for r in loc) if loc else None,
           "latency_p50_ms": lat[len(lat) // 2] if lat else 0, "latency_p95_ms": lat[int(len(lat) * 0.95) - 1] if lat else 0,
           "cost_per_1k_usd": 1000 * statistics.mean(r["cost_usd"] for r in rows) if rows else 0}
    return out


def tune_threshold_cv(rows, folds, target=0.9):
    """R3: per fold, pick the smallest threshold reaching `target` selective accuracy on the other folds, apply it to
    the fold. Returns pooled (selective accuracy, coverage) and per-fold thresholds."""
    kept, n, ths = [], 0, []
    for k in sorted(set(folds.values())):
        train = [r for r in rows if folds[r["wid"]] != k]
        test = [r for r in rows if folds[r["wid"]] == k]
        t = next((x / 100 for x in range(30, 100) if (lambda a: a[1] > 0 and a[0] >= target)(metrics.selective(train, x / 100))), None)
        ths.append(t)
        n += len(test)
        if t is not None:
            kept += [r for r in test if r["confidence"] >= t]
    acc = statistics.mean(r["class"] == r["label"] for r in kept) if kept else float("nan")
    return {"selective_acc": acc, "coverage": len(kept) / n if n else 0.0, "thresholds": ths}


def paraphrase_consistency(rows):
    by = defaultdict(set)
    for r in rows:
        by[r["wid"]].add(r["class"])
    return statistics.mean(len(v) == 1 for v in by.values())


def evidence_recall(run: Run, rows: list[dict], folds: dict) -> float:
    """H-4: share of fault windows whose evidence holds the fault's signature pattern, the pattern most enriched in the
    OTHER folds' fault windows of that type (vs normal windows). Learned per fold, never hand-written."""
    wins = {w["wid"]: w for w in run.windows}
    pats = {wid: {r["pattern_id"] for r in B.window_facts(wins[wid], run.ctx())["patterns"]} for wid in {r["wid"] for r in rows}}
    lab = {r["wid"]: (r["label"], r["slice"]) for r in rows}
    ev = {r["wid"]: set(r["evidence_pattern_ids"]) for r in rows if r["wording"] == 0}
    hits = []
    for k in sorted(set(folds.values())):
        train = [w for w in pats if folds[w] != k]
        normal = [w for w in train if lab[w][1] == "normal"]
        for ftype in ("file_missing", "permission_denied"):
            fw = [w for w in train if lab[w][0] == ftype]
            if not fw:
                continue
            cand = set().union(*(pats[w] for w in fw))
            sig = max(cand, key=lambda p: sum(p in pats[w] for w in fw) / len(fw) - sum(p in pats[w] for w in normal) / max(len(normal), 1))
            hits += [sig in ev[w] for w in ev if folds[w] == k and lab[w][0] == ftype]
    return statistics.mean(hits) if hits else float("nan")


# ------------------------------------------------------------------ lead ------------------------------------------
def lead_same(run: Run, pairs: list[dict], models=("jev", "llm")) -> list[dict]:
    """L0: Noul 'same underlying problem?' over two incident fingerprints (identical for both models)."""
    wins = {w["wid"]: w for w in run.windows}
    wording = jl_wordings(run)["lead_same"][0]

    def one(p):
        ctx = run.ctx()
        state = {"question": wording.format(ta=p["ta"], tb=p["tb"]),
                 "incident_a": B.fingerprint(wins[p["wa"]], ctx), "incident_b": B.fingerprint(wins[p["wb"]], ctx)}
        qs = {"same_problem": P.lead_same_problem()}
        row = {"pid": f"{p['wa']}~{p['wb']}", "wa": p["wa"], "wb": p["wb"], "label": p["same_problem"]}
        reqs = {}
        for m in models:
            r = B.ask(m, state, qs, ctx)
            py = float(r["answers"]["same_problem"]["noul"])
            row[m] = {"p_yes": py, "pred": py >= 0.5, "latency_ms": r["latency_ms"], "cost_usd": r["cost_usd"]}
            reqs[m] = r["request"]
            trace(run, row["pid"], f"{m}:L0", r["request"], r["answers"], r["latency_ms"], r.get("error"))
        if len(reqs) == 2:
            row["fair"] = fairness_ok(reqs["jev"], reqs["llm"])
        return row
    return pmap(one, pairs)


def lead_broad(run: Run, wids: list[str], evidence_variant: str, models=("jev", "llm")) -> dict:
    """L1 (= Q6): broad taxonomy Choice per window; two incidents are 'same' if same broad class (not 'no fault') and
    same top fingerprint service. Returns wid -> {model: (class, top_service)}."""
    wins = {w["wid"]: w for w in run.windows}

    def one(wid):
        ctx = run.ctx()
        w = wins[wid]
        ev = B.evidence(w, ctx, evidence_variant)
        state = B.state_of({"question": "What kind of problem, if any, happened in this window?"}, ev)
        qs = {"broad": P.broad_question()}
        fp = B.fingerprint(w, ctx)
        top = fp["pattern_1"]["service"] if isinstance(fp, dict) else None
        out = {}
        for m in models:
            r = B.ask(m, state, qs, ctx)
            out[m] = (r["answers"]["broad"]["choice"], top, r["latency_ms"], r["cost_usd"])
            trace(run, wid, f"{m}:L1", r["request"], r["answers"], r["latency_ms"], r.get("error"))
        return wid, out
    return dict(pmap(one, wids))


def lead_repeat(run: Run, items: list[dict], models=("jev", "llm")) -> list[dict]:
    """L2: Choice 'repeat of known problem K, or new?'; known problems described by the fingerprint of their latest
    earlier incident (>= 1 h before, <= 7 days)."""
    wins = sorted(run.windows, key=lambda w: w["t1"])
    by_wid = {w["wid"]: w for w in wins}
    faults = [w for w in wins if w["slice"] == "fault" and not w["overlap"]]
    wording = jl_wordings(run)["lead_repeat"][0]

    def latest(problem, before):
        c = [w for w in faults if (w["fault"], w["root_service"]) == tuple(problem) and w["t1"] <= before]
        return c[-1] if c else None

    def one(it):
        ctx = run.ctx()
        w = by_wid[it["wid"]]
        from datetime import datetime, timedelta
        before = (datetime.strptime(w["t1"], "%Y-%m-%d %H:%M") - timedelta(hours=1)).strftime("%Y-%m-%d %H:%M")
        known, kmap = {}, {}
        for i, prob in enumerate(it["known_problems"], 1):
            lw = latest(prob, before)
            if lw:
                known[f"K{i}"] = B.fingerprint(lw, ctx)
                kmap[f"K{i}"] = prob
        truth = next((k for k, v in kmap.items() if it["truth"] != "new" and list(v) == list(it["truth"])), "new")
        row = {"wid": it["wid"], "label": truth, "n_known": len(known)}
        if not known:
            return row
        state = {"question": wording.format(t=it["t"]), "incident": B.fingerprint(w, ctx), "known_problems": known}
        qs = {"repeat": P.lead_repeat(list(known))}
        reqs = {}
        for m in models:
            r = B.ask(m, state, qs, ctx)
            a = r["answers"]["repeat"]
            row[m] = {"pred": a.get("choice"), "probs": a.get("probabilities"), "latency_ms": r["latency_ms"],
                      "cost_usd": r["cost_usd"]}
            reqs[m] = r["request"]
            trace(run, it["wid"], f"{m}:L2", r["request"], r["answers"], r["latency_ms"], r.get("error"))
        if len(reqs) == 2:
            row["fair"] = fairness_ok(reqs["jev"], reqs["llm"])
        return row
    return pmap(one, items)


def jl_wordings(run: Run) -> dict:
    return json.loads((run.data / "wordings.json").read_text())


def pair_f1(rows, key) -> dict:
    tp = sum(r[key]["pred"] and r["label"] for r in rows)
    fp = sum(r[key]["pred"] and not r["label"] for r in rows)
    fn = sum((not r[key]["pred"]) and r["label"] for r in rows)
    prec = tp / (tp + fp) if tp + fp else 0.0
    rec = tp / (tp + fn) if tp + fn else 0.0
    f1 = 2 * prec * rec / (prec + rec) if prec + rec else 0.0
    br = statistics.mean((r[key].get("p_yes", float(r[key]["pred"])) - r["label"]) ** 2 for r in rows)
    return {"n": len(rows), "precision": prec, "recall": rec, "f1": f1, "brier_binary": br,
            "accuracy": statistics.mean(r[key]["pred"] == r["label"] for r in rows)}


# ------------------------------------------------------------------ manager ---------------------------------------
def problem_numbers(run: Run, wids: list[str]) -> dict:
    """SQL numbers for one problem over its incidents this week (sum over its windows)."""
    wins = {w["wid"]: w for w in run.windows}
    extra, minutes = 0.0, 0
    for wid in wids:
        f = B.window_facts(wins[wid], run.ctx())
        extra += float(f["failed"]["extra_failed"])
        offs = [s["first_spike_offset"] for s in f["services"] if s["first_spike_offset"] is not None]
        minutes += (15 - min(offs)) if offs else 0
    return {"incidents": len(wids), "extra_failed": round(extra), "affected_minutes": int(minutes)}


def impact_rule(nums: dict, customer_facing: bool) -> tuple:
    """Pre-registered manager proxy truth (plan §3.2): failed requests x customer-facing weight, ties by minutes."""
    return (nums["extra_failed"] * (2 if customer_facing else 1), nums["affected_minutes"])


def manager(run: Run, weeks: list[dict], models=("jev", "llm")) -> dict:
    """M0 pairwise 'fix first' (both option orders) and M1 impact Score per problem."""
    cf = {s: c for s, _, c, _ in CATALOG}
    wins = {w["wid"]: w for w in run.windows}
    probs_desc, truth_key = {}, {}
    for wk in weeks:
        for p in wk["problems"]:
            key = (wk["week_start"], p["fault"], p["service"])
            nums = problem_numbers(run, p["wids"])
            latest = max(p["wids"], key=lambda x: wins[x]["t1"])
            fp = B.fingerprint(wins[latest], run.ctx())
            top = {k: v for k, v in list(fp.items())[:3]} if isinstance(fp, dict) else fp
            svc = top["pattern_1"]["service"] if isinstance(top, dict) else p["service"]
            probs_desc[key] = {"what": top, "incidents_this_week": f"{nums['incidents']} incidents",
                               "affected_minutes": f"about {nums['affected_minutes']} minutes with an error spike",
                               "extra_failed_requests": f"about {nums['extra_failed']} more failed requests than usual",
                               "customer_facing": ("yes: customers use this service directly" if cf.get(svc)
                                                   else "no: internal service")}
            truth_key[key] = impact_rule(nums, cf.get(p["service"], False))
    pairs = []
    for wk in weeks:
        keys = [(wk["week_start"], p["fault"], p["service"]) for p in wk["problems"]]
        pairs += [(a, b) for i, a in enumerate(keys) for b in keys[i + 1:] if truth_key[a] != truth_key[b]]
    wording = jl_wordings(run)["manager"][0]

    def m0(pair):
        a, b = pair
        ctx = run.ctx()
        state = {"question": wording.format(a="problem A", b="problem B"), "problems": {"A": probs_desc[a], "B": probs_desc[b]}}
        truth = "A" if truth_key[a] > truth_key[b] else "B"
        row = {"pair": f"{a}|{b}", "label": truth}
        for m in models:
            ans = []
            for order in (["A", "B"], ["B", "A"]):
                r = B.ask(m, state, {"first": P.manager_first(order)}, ctx)
                ans.append(r["answers"]["first"].get("choice"))
                trace(run, row["pair"], f"{m}:M0:{''.join(order)}", r["request"], r["answers"], r["latency_ms"])
            row[m] = {"pred": ans[0], "order_agree": ans[0] == ans[1]}
        return row

    def m1(key):
        ctx = run.ctx()
        state = {"question": "How large is this problem's user impact this week?", "problem": probs_desc[key]}
        out = {}
        for m in models:
            r = B.ask(m, state, {"impact": P.manager_impact()}, ctx)
            out[m] = float(r["answers"]["impact"]["score"])
            trace(run, str(key), f"{m}:M1", r["request"], r["answers"], r["latency_ms"])
        return key, out
    m0_rows = pmap(m0, pairs)
    m1_scores = dict(pmap(m1, list(probs_desc)))
    m1_rows = [{"pair": f"{a}|{b}", "label": "A" if truth_key[a] > truth_key[b] else "B",
                **{m: {"pred": "A" if m1_scores[a][m] >= m1_scores[b][m] else "B"} for m in models}} for a, b in pairs]
    return {"m0": m0_rows, "m1": m1_rows, "problems": {str(k): v for k, v in probs_desc.items()},
            "rule": {str(k): v for k, v in truth_key.items()}}
