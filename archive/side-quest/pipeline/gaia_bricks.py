"""GAIA bricks (plan 002 §4): Pattern+Evidence from SereneDB (E0-E3), one request per question set for Jev and the
identical form for the LLM, Finding = label + computed confidence + citation.

All numbers come from pipeline/gaia_queries.py; this file only turns them into words and ranks evidence.
"""
import json
import threading
from dataclasses import dataclass, field
from pathlib import Path

from pipeline import config, gaia_prompts as P, gaia_queries as Q, models
from pipeline.cache import cached
from pipeline.db import query

TOP_K = 12                 # [KNOB] evidence items
MIN_RATIO = 2.0            # [KNOB] E1: "more frequent than usual" cutoff (window count vs usual per 15 min)
MIN_LINES = 3              # [KNOB] E1: ignore tiny counts unless the pattern is new in 24 h
RAW_CAP = 60               # [KNOB] E3: raw WARN/ERROR lines (dedup by service+pattern)
EXAMPLE_CHARS = 240
FINGERPRINT_K = 5          # lead/manager: top evidence items describing an incident
SEV_RANK = {"ERROR": 3, "CRITICAL": 4, "FATAL": 4, "WARNING": 2, "WARN": 2, "INFO": 1}


@dataclass
class Ctx:
    conn: object
    schema: str
    templates: dict
    cache_dir: Path
    corpus_windows: dict = field(default_factory=dict)   # E0 only: pattern -> number of corpus windows with it
    n_corpus_windows: int = 0


_facts, _lock = {}, threading.Lock()


def _num(rows: list[dict]) -> list[dict]:
    """SQL sums arrive as Decimal; make every numeric value a float."""
    from decimal import Decimal
    return [{k: float(v) if isinstance(v, Decimal) else v for k, v in r.items()} for r in rows]


def window_facts(w: dict, ctx: Ctx) -> dict:
    """All SQL for one window (cached per window; the same for every wording/variant/model)."""
    key = (ctx.schema, w["t1"], w["t2"])
    with _lock:
        if key in _facts:
            return _facts[key]
    p = {"t1": w["t1"], "t2": w["t2"]}
    blocks = float(query(ctx.conn, Q.HISTORY_BLOCKS, ctx.schema, **p)[0]["blocks"])
    pats = _num(query(ctx.conn, Q.WINDOW_PATTERNS, ctx.schema, blocks=blocks, **p))
    svcs = _num(query(ctx.conn, Q.WINDOW_SERVICES, ctx.schema, blocks=blocks, **p))
    ex = {(r["service"], r["pattern_id"]): r["example_line"]
          for r in query(ctx.conn, Q.WINDOW_EXAMPLES, ctx.schema, chars=EXAMPLE_CHARS, **p)}
    raw = query(ctx.conn, Q.WINDOW_RAW, ctx.schema, min_sev=13, **p)
    fr = _num(query(ctx.conn, Q.WINDOW_FAILED_REQUESTS, ctx.schema, blocks=blocks, **p))[0]
    out = {"blocks": blocks, "patterns": pats, "services": svcs, "examples": ex, "raw_warn": raw, "failed": fr,
           "sql": {"WINDOW_PATTERNS": Q.WINDOW_PATTERNS, "WINDOW_SERVICES": Q.WINDOW_SERVICES}}
    with _lock:
        _facts[key] = out
    return out


# ------------------------------------------------------------------ numbers -> words -------------------------------
def change_words(ratio: float, new: bool) -> str:
    if new:
        return "new: not seen in the previous 24 hours"
    if ratio >= 10:
        return "more than 10x its usual rate"
    if ratio >= 2:
        return f"about {round(ratio)}x its usual rate"
    if ratio >= 1.5:
        return "somewhat more than usual"
    if ratio > 0.67:
        return "about its usual rate"
    return "less than usual"


def when_words(offset) -> str:
    if offset is None:
        return "none"
    if offset < 3:
        return "from the start of the window"
    if offset < 10:
        return "in the middle of the window"
    return "near the end of the window"


def _window_summary(f: dict, with_usual: bool = True) -> dict:
    n = sum(s["n_window"] for s in f["services"])
    e = sum(s["err_window"] for s in f["services"])
    if not with_usual:
        return {"services_logging": len(f["services"]), "log_lines": f"{n:.0f}", "error_lines": f"{e:.0f}"}
    un = sum(s["usual_n"] for s in f["services"])
    ue = sum(s["usual_err"] for s in f["services"])
    return {"services_logging": len(f["services"]), "log_lines": f"{n:.0f} (usually about {un:.0f} per 15 min)",
            "error_lines": f"{e:.0f} (usually about {ue:.0f} per 15 min)"}


def _item(r: dict, f: dict, ctx: Ctx) -> dict:
    return {"service": r["service"], "log_pattern": ctx.templates.get(r["pattern_id"], "?"),
            "severity": r["severity_text"],
            "lines": f"{r['n_window']:.0f} in this window (usually about {r['usual_per_15min']:.0f} per 15 min)",
            "change": change_words(r["ratio"], r["new_in_24h"]),
            "first_seen": when_words(r["first_minute_offset"]),
            "example_line": f["examples"].get((r["service"], r["pattern_id"]), ""),
            "_pattern_id": r["pattern_id"]}


def _anomalous(f: dict) -> list[dict]:
    cands = [r for r in f["patterns"] if r["new_in_24h"] or (r["ratio"] >= MIN_RATIO and r["n_window"] >= MIN_LINES)]
    return sorted(cands, key=lambda r: (not r["new_in_24h"], -SEV_RANK.get(r["severity_text"], 1), -r["ratio"],
                                        -r["n_window"]))


def services_table(f: dict) -> dict:
    out = {}
    for s in sorted(f["services"], key=lambda s: s["service"]):
        r = (s["err_window"] + 1) / (s["usual_err"] + 1)
        out[s["service"]] = {"log_lines": f"{s['n_window']:.0f} (usually about {s['usual_n']:.0f})",
                             "error_lines": f"{s['err_window']:.0f}, {change_words(r, s['usual_err'] == 0 and s['err_window'] > 0)}",
                             "error_spike": when_words(s["first_spike_offset"])}
    return out


def earliest_spike(f: dict) -> str:
    sp = [s for s in f["services"] if s["first_spike_offset"] is not None]
    return min(sp, key=lambda s: (s["first_spike_offset"], -s["err_window"]))["service"] if sp else "none"


def evidence(w: dict, ctx: Ctx, variant: str) -> dict:
    """E0 | E1 | E1w (E1 without raw counts) | E2 | E3 -> {state parts, items (with _ids), n_candidates}."""
    f = window_facts(w, ctx)
    if variant == "E0":     # 001's A4: corpus-relative rarity, no 24 h baseline
        n = ctx.n_corpus_windows
        cands = [r for r in f["patterns"] if ctx.corpus_windows.get(r["pattern_id"], 0) <= 0.25 * n
                 or SEV_RANK.get(r["severity_text"], 1) >= 2]
        ranked = sorted(cands, key=lambda r: (ctx.corpus_windows.get(r["pattern_id"], 0),
                                              -SEV_RANK.get(r["severity_text"], 1), -r["n_window"]))
        items = {}
        for i, r in enumerate(ranked[:TOP_K], 1):
            k = ctx.corpus_windows.get(r["pattern_id"], 0)
            rarity = ("seen only in this window" if k <= 1 else f"rare: seen in {k} of {n} windows" if k <= 0.25 * n
                      else f"common: seen in {k} of {n} windows")
            items[f"E{i}"] = {"service": r["service"], "log_pattern": ctx.templates.get(r["pattern_id"], "?"),
                              "severity": r["severity_text"], "lines": f"{r['n_window']:.0f} in this window",
                              "rarity": rarity, "first_seen": when_words(r["first_minute_offset"]),
                              "example_line": f["examples"].get((r["service"], r["pattern_id"]), ""),
                              "_pattern_id": r["pattern_id"]}
        return {"window": _window_summary(f, with_usual=False), "items": items, "n_candidates": len(ranked)}
    ranked = _anomalous(f)
    items = {f"E{i}": _item(r, f, ctx) for i, r in enumerate(ranked[:TOP_K], 1)}
    out = {"window": _window_summary(f), "items": items, "n_candidates": len(ranked)}
    if variant == "E1w":   # amendment 4: same selection as E1, but no raw counts, only the computed comparison in words
        for it in items.values():
            it.pop("lines", None)
        n = sum(s["n_window"] for s in f["services"])
        e = sum(s["err_window"] for s in f["services"])
        un = sum(s["usual_n"] for s in f["services"])
        ue = sum(s["usual_err"] for s in f["services"])
        out["window"] = {"services_logging": "all ten" if len(f["services"]) == 10 else f"{len(f['services'])} of ten",
                         "log_volume": change_words((n + 1) / (un + 1), False),
                         "error_lines": change_words((e + 1) / (ue + 1), ue == 0 and e > 0)}
    if variant in ("E2", "E3"):
        out["services"] = services_table(f)
        out["earliest_error_spike"] = earliest_spike(f)
    if variant == "E3":
        seen, lines = set(), []
        for r in f["raw_warn"]:
            k = (r["service"], r["pattern_id"])
            if k not in seen:
                seen.add(k)
                lines.append(f"{r['service']} {r['severity_text']} {r['body'][:200]}")
            if len(lines) >= RAW_CAP:
                break
        out["raw_error_lines"] = lines or "none"
    return out


def state_of(x: dict, ev: dict) -> dict:
    """The exact state both models see (internal _fields stripped)."""
    items = {k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")} for k, v in ev["items"].items()}
    st = {"question": x["question"], "window": ev["window"],
          "evidence": items or "no log pattern is new or clearly more frequent than in the previous 24 hours"}
    for k in ("services", "earliest_error_spike", "raw_error_lines"):
        if k in ev:
            st[k] = ev[k]
    return st


def service_candidates(w: dict, ctx: Ctx) -> dict:
    """Q7 options: every service that logged in the window, described by its SQL numbers."""
    tbl = services_table(window_facts(w, ctx))
    return {s: f"{s}: log lines {v['log_lines']}; error lines {v['error_lines']}; error spike: {v['error_spike']}"
            for s, v in tbl.items()}


def fingerprint(w: dict, ctx: Ctx) -> dict | str:
    """Lead/manager: an incident described by its top anomalous patterns (no times, no labels)."""
    f = window_facts(w, ctx)
    top = _anomalous(f)[:FINGERPRINT_K]
    if not top:
        return "no log pattern is new or clearly more frequent than in the previous 24 hours"
    return {f"pattern_{i}": {k: v for k, v in _item(r, f, ctx).items() if k in
                             ("service", "log_pattern", "severity", "change", "example_line")}
            for i, r in enumerate(top, 1)}


# ------------------------------------------------------------------ asking both models -----------------------------
def _spread(options: list[str], answer, conf) -> dict:
    try:
        c = min(max(float(conf), 0.0), 1.0)
    except (TypeError, ValueError):
        c = 0.0
    if answer not in options:
        return {o: 1 / len(options) for o in options}
    rest = (1 - c) / (len(options) - 1) if len(options) > 1 else 0
    return {o: (c if o == answer else rest) for o in options}


def _yes(v) -> bool | None:
    if isinstance(v, bool):
        return v
    s = str(v).strip().lower()
    return True if s in ("true", "yes", "1") else False if s in ("false", "no", "0") else None


def normalize_llm(questions: dict, parsed: dict) -> dict:
    """LLM JSON -> the same answer shape as Jev (self-reported confidence spread into a distribution)."""
    out = {}
    for qid, q in questions.items():
        a = parsed.get(qid) if isinstance(parsed, dict) else None
        a = a if isinstance(a, dict) else {}
        ans, conf = a.get("answer"), a.get("confidence")
        if q["type"] == "noul":
            y = _yes(ans)
            try:
                c = min(max(float(conf), 0.0), 1.0)
            except (TypeError, ValueError):
                c = 0.5
            out[qid] = {"noul": 0.5 if y is None else (c if y else 1 - c)}
        elif q["type"] == "score":
            levels = [str(i) for i in range(len(q["criteria"]))]
            probs = _spread(levels, str(ans), conf)
            out[qid] = {"score": sum(int(k) * p for k, p in probs.items()), "probabilities": probs}
        else:
            opts = list(q["criteria"])
            probs = _spread(opts, ans, conf)
            out[qid] = {"choice": ans if ans in opts else "invalid", "probabilities": probs}
    return out


def ask(model: str, state: dict, questions: dict, ctx: Ctx, repeat: int = 0) -> dict:
    """One request: Jev system_one, or the LLM with the identical form. Returns {answers, latency_ms, cost_usd, request}."""
    if model == "jev":
        req = {"model": config.JEV_MODEL, "state": state, "questions": questions, "repeat": repeat}
        out = cached(ctx.cache_dir, "jev", req, lambda: models.jev(state, questions))
        return {"answers": out["answers"], "latency_ms": out["latency_ms"], "cost_usd": out["cost_usd"],
                "input_tokens": out["input_tokens"], "request": {"state": state, "questions": questions}}
    prompt = P.llm_form(state, questions)
    req = {"model": config.LLM_MODEL, "system": P.LLM_SYSTEM, "prompt": prompt, "repeat": repeat}
    out = cached(ctx.cache_dir, "llm", req, lambda: models.llm(P.LLM_SYSTEM, prompt))
    return {"answers": normalize_llm(questions, out.get("parsed", {})), "latency_ms": out["latency_ms"],
            "cost_usd": out["cost_usd"], "input_tokens": out["input_tokens"], "error": out.get("error"),
            "raw_reply": out.get("text", ""), "request": {"system": P.LLM_SYSTEM, "prompt": prompt}}


def choice_confidence(probs: dict) -> float:
    """Jev's documented Choice confidence, applied identically to both models' final distributions."""
    n = len(probs)
    return (max(probs.values()) - 1 / n) / (1 - 1 / n) if n > 1 else 1.0


# ------------------------------------------------------------------ engineer finding -------------------------------
LABELS = ["file_missing", "permission_denied", "none"]


def engineer_finding(design: str, ans: dict) -> dict:
    """Answers -> {pred, probs over LABELS, confidence, abstain, key_evidence, root_service}."""
    if design.startswith("Q2"):
        pf = float(ans["is_fault"]["noul"])
        ft = ans["fault_type"]["probabilities"]
        probs = {"none": 1 - pf} | {P.LABEL_OF[o]: pf * ft.get(o, 0) for o in P.OPTIONS[:2]}
        abstain = False
    else:
        op = ans["fault"]["probabilities"]
        probs = {l: 0.0 for l in LABELS}
        for o, p in op.items():
            probs[P.LABEL_OF[o]] += p
        abstain = ans["fault"].get("choice") == P.CANT_TELL
    pred = max(probs, key=probs.get)
    conf = 0.0 if abstain else choice_confidence(probs)
    out = {"pred": pred, "probs": probs, "confidence": round(conf, 4), "abstain": abstain,
           "key_evidence": ans.get("key_evidence", {}).get("choice")}
    if "root_service" in ans:
        out["root_service"] = ans["root_service"].get("choice")
        out["root_service_probs"] = ans["root_service"].get("probabilities")
    return out
