"""The 4 bricks as plain functions: Pattern -> Evidence -> Verdict -> Finding.

Each takes the example dict ({qid, job, question} plus earlier bricks) and a Ctx, and returns ONLY its own brick.
pipeline/chain.py wires them together and traces every step.
"""
import zlib
from dataclasses import dataclass, field
from pathlib import Path

from pipeline import config, prompts, queries
from pipeline.cache import cached
from pipeline.db import query
from pipeline import models


@dataclass
class Ctx:
    conn: object
    schema: str
    templates: dict              # pattern_id -> template text (from Drain3)
    cache_dir: Path
    variant: dict = field(default_factory=lambda: dict(config.VARIANT))
    pattern_jobs: dict = field(default_factory=dict)   # pattern_id -> number of jobs containing it
    total_jobs: int = 0
    typical_duration_s: float = 0.0                     # median job duration in the corpus (A4)

    def load_corpus_stats(self):
        rows = query(self.conn, queries.PATTERN_STATS, self.schema, service=config.SERVICE_NAME)
        self.pattern_jobs = {r["pattern_id"]: r["n_jobs"] for r in rows}
        self.total_jobs = query(self.conn, queries.TOTAL_JOBS, self.schema, service=config.SERVICE_NAME)[0]["n"]
        self.typical_duration_s = float(query(self.conn, queries.TYPICAL_DURATION, self.schema,
                                              service=config.SERVICE_NAME)[0]["median_s"])


# ---------------- Brick 1: Pattern ---------------------------------------------------------------
def pattern_brick(x: dict, ctx: Ctx) -> dict:
    """Patterns present in the job (SQL), with their Drain3 template text.
    WARN+ only for evidence "basic"/"full"; ALL severities for "rarity" (A4; the Evidence brick then selects)."""
    min_sev = 1 if ctx.variant["evidence"] == "rarity" else config.EVIDENCE_MIN_SEVERITY
    rows = query(ctx.conn, queries.JOB_PATTERNS, ctx.schema, service=config.SERVICE_NAME, job=x["job"],
                 min_sev=min_sev, chars=config.EXAMPLE_LINE_CHARS)
    for r in rows:
        r["template"] = ctx.templates.get(r["pattern_id"], "?")
        r["n_jobs_with_pattern"] = ctx.pattern_jobs.get(r["pattern_id"], 0)
    facts = query(ctx.conn, queries.JOB_FACTS, ctx.schema, service=config.SERVICE_NAME, job=x["job"])[0]
    return {"patterns": rows, "job_facts": facts, "total_jobs": ctx.total_jobs,
            "typical_duration_s": ctx.typical_duration_s,
            "sql": {"JOB_PATTERNS": queries.JOB_PATTERNS.format(s=ctx.schema),
                    "JOB_FACTS": queries.JOB_FACTS.format(s=ctx.schema)}}


# ---------------- Brick 2: Evidence --------------------------------------------------------------
def _timing_words(frac: float) -> str:
    if frac < 0.05:
        return "at the very start of the job"
    if frac < 0.33:
        return "early in the job"
    if frac < 0.66:
        return "midway through the job"
    return "late in the job"


def _rarity_words(n_jobs: int, total: int) -> str:
    if n_jobs <= 1:
        return f"seen only in this job (1 of {total} jobs)"
    if n_jobs / total <= 0.25:
        return f"rare: seen in {n_jobs} of {total} jobs"
    if n_jobs / total <= 0.6:
        return f"occasional: seen in {n_jobs} of {total} jobs"
    return f"common: seen in {n_jobs} of {total} jobs"


def _duration_words(span_s: float, typical_s: float) -> str:
    """A4: job duration relative to the corpus median job duration."""
    minutes, typical_min = round(span_s / 60), round(typical_s / 60)
    ratio = span_s / max(typical_s, 1e-9)
    if ratio >= 1.5:
        return f"about {minutes} minutes, about {ratio:.1f}x longer than a typical job ({typical_min} min)"
    if ratio <= 0.67:
        return f"about {minutes} minutes, shorter than a typical job ({typical_min} min)"
    return f"about {minutes} minutes, typical for a job ({typical_min} min)"


def evidence_brick(x: dict, ctx: Ctx) -> dict:
    """Select + rank the job's patterns, keep top K, describe them in words.
    basic/full: all WARN+ patterns, ranked severity desc, rarity asc, count desc.
    rarity (A4): rare patterns (any severity) + all WARN+, ranked rarity asc, severity desc, count desc."""
    p = x["pattern"]
    f = p["job_facts"]
    span = max((f["t1"] - f["t0"]).total_seconds(), 1e-9)
    if ctx.variant["evidence"] == "rarity":
        rare_max = config.RARE_MAX_JOB_FRACTION * p["total_jobs"]
        candidates = [r for r in p["patterns"] if r["n_jobs_with_pattern"] <= rare_max
                      or r["max_severity"] >= config.EVIDENCE_MIN_SEVERITY]
        ranked = sorted(candidates, key=lambda r: (r["n_jobs_with_pattern"], -r["max_severity"], -r["n"]))
    else:
        ranked = sorted(p["patterns"], key=lambda r: (-r["max_severity"], r["n_jobs_with_pattern"], -r["n"]))
    items = {}
    for i, r in enumerate(ranked[:config.TOP_K_EVIDENCE], start=1):
        item = {"log_pattern": r["template"], "severity": r["severity_text"],
                "occurrences": f"{r['n']} lines in {r['n_containers']} of {f['n_containers']} containers"}
        if ctx.variant["evidence"] in ("full", "rarity"):
            item["first_appearance"] = _timing_words((r["first_seen"] - f["t0"]).total_seconds() / span)
            item["rarity"] = _rarity_words(r["n_jobs_with_pattern"], p["total_jobs"])
            item["example_line"] = r["example_line"]
        items[f"E{i}"] = {**item, "_pattern_id": r["pattern_id"]}
    duration = (_duration_words(span, p["typical_duration_s"]) if ctx.variant["evidence"] == "rarity"
                else f"about {round(span / 60)} minutes")
    job = {"duration": duration, "containers": f["n_containers"],
           "lines": f"{f['n_lines']} lines: {f['n_fatal']} FATAL, {f['n_error']} ERROR, {f['n_warn']} WARN"}
    return {"job": job, "items": items, "n_candidates": len(ranked)}


def evidence_state(x: dict) -> dict:
    """The exact state sent to Jev and to the LLM baseline B1 (internal _fields stripped)."""
    items = {k: {kk: vv for kk, vv in v.items() if not kk.startswith("_")} for k, v in x["evidence"]["items"].items()}
    return {"question": x["question"], "job": x["evidence"]["job"], "evidence": items or "no WARN/ERROR/FATAL lines"}


# ---------------- Brick 3: Verdict ---------------------------------------------------------------
def verdict_brick(x: dict, ctx: Ctx) -> dict:
    """ONE Jev request: root cause (Choice over classes) + key evidence (Choice over evidence ids) [+ shuffles]."""
    state = evidence_state(x)
    questions = prompts.jev_questions(list(x["evidence"]["items"]), ctx.variant, seed=zlib.crc32(x["qid"].encode()))  # stable across runs
    request = {"model": config.JEV_MODEL, "state": state, "questions": questions, "repeat": x.get("repeat", 0)}
    out = cached(ctx.cache_dir, "jev", request, lambda: models.jev(state, questions))
    a = out["answers"]
    rc = a["root_cause"]
    shuffles = [a[k]["choice"] for k in a if k.startswith("root_cause_shuffle_")]
    agreement = (1 + sum(s == rc["choice"] for s in shuffles)) / (1 + len(shuffles))
    return {"class": rc["choice"], "probabilities": rc["probabilities"], "confidence": rc["confidence"],
            "shuffle_agreement": agreement, "key_evidence": a["key_evidence"]["choice"],
            "key_evidence_confidence": a["key_evidence"]["confidence"],
            "request": {"state": state, "questions": questions},
            "model": out["model"], "latency_ms": out["latency_ms"], "input_tokens": out["input_tokens"],
            "cost_usd": out["cost_usd"], "cached": out["cached"]}


# ---------------- Brick 4: Finding ---------------------------------------------------------------
def finding_brick(x: dict, ctx: Ctx) -> dict:
    """Answer card. Confidence = Jev's computed confidence x shuffle agreement (1.0 when no shuffles)."""
    v = x["verdict"]
    conf = v["confidence"] * v["shuffle_agreement"]
    cited = v["key_evidence"]
    item = x["evidence"]["items"].get(cited)
    return {"answer": v["class"], "confidence": round(conf, 3),
            "badge": "auto" if conf >= config.AUTO_THRESHOLD else "needs review",
            "cited_evidence": cited, "cited_pattern": item["log_pattern"] if item else None}
