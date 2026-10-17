"""Baselines B1-B4 (plans/001 §5). Each returns {"class", "probabilities", ...} so metrics treat all alike.

LLM confidence is SELF-REPORTED (that is the point of comparing calibration): we spread (1-c) evenly
over the other classes to get a probability vector.
"""
import json
import zlib

from langchain_core.runnables import RunnableLambda
from sklearn.feature_extraction.text import TfidfVectorizer
from sklearn.linear_model import LogisticRegression

from pipeline import bricks, config, models, prompts, queries
from pipeline.cache import cached
from pipeline.db import query


def _probs_from_self_report(cls: str, conf) -> dict:
    try:
        conf = min(max(float(conf), 0.0), 1.0)
    except (TypeError, ValueError):
        conf = 0.0
    if cls not in config.CLASSES:
        return {c: 1 / len(config.CLASSES) for c in config.CLASSES}
    rest = (1 - conf) / (len(config.CLASSES) - 1)
    return {c: (conf if c == cls else rest) for c in config.CLASSES}


def _llm_result(out: dict, system: str, prompt: str) -> dict:
    p = out["parsed"]
    cls = str(p.get("class", "")).strip().lower()
    cls = cls if cls in config.CLASSES else "invalid"
    return {"class": cls, "probabilities": _probs_from_self_report(cls, p.get("confidence")),
            "self_reported_confidence": p.get("confidence"), "key_evidence": p.get("key_evidence"),
            "raw_reply": out["text"], "latency_ms": out["latency_ms"], "cost_usd": out["cost_usd"],
            "input_tokens": out["input_tokens"], "cached": out["cached"],
            "request": {"system": system, "prompt": prompt},  # exact LLM input, for tracing
            "error": out.get("error")}


def _definitions() -> str:
    """The SAME structured class definitions Jev gets (definition + covers + does_not_cover)."""
    return json.dumps(prompts.CLASS_DEFINITIONS_STRUCTURED, indent=1)


def _b1_prompt(x: dict, ctx: bricks.Ctx, order: list[str]) -> str:
    return prompts.LLM_SAME_EVIDENCE.format(
        question=x["question"], classes=order,
        definitions_block=prompts.llm_definitions_block(ctx.variant["criteria"], order),
        state_json=json.dumps(bricks.evidence_state(x), indent=1))


def b1_llm_same_evidence(x: dict, ctx: bricks.Ctx) -> dict:
    """LLM mirror of the Jev Verdict for the SAME variant: identical evidence state, identical class options
    (plain names or structured definitions), and the same shuffled orders when the variant uses shuffles."""
    def ask(order):
        prompt = _b1_prompt(x, ctx, order)
        req = {"model": config.LLM_MODEL, "system": prompts.LLM_SYSTEM, "prompt": prompt, "repeat": x.get("repeat", 0)}
        return _llm_result(cached(ctx.cache_dir, "llm", req, lambda: models.llm(prompts.LLM_SYSTEM, prompt)),
                           prompts.LLM_SYSTEM, prompt)
    out = ask(config.CLASSES)
    seed = zlib.crc32(x["qid"].encode())
    shuffles = [ask(order) for order in prompts.shuffled_orders(seed, ctx.variant["shuffles"])]
    out["shuffle_agreement"] = (1 + sum(s["class"] == out["class"] for s in shuffles)) / (1 + len(shuffles))
    out["shuffle_answers"] = [s["class"] for s in shuffles]
    out["latency_ms"] += sum(s["latency_ms"] for s in shuffles)
    out["cost_usd"] += sum(s["cost_usd"] for s in shuffles)
    out["variant"] = dict(ctx.variant)
    return out


def b2_llm_raw_logs(x: dict, ctx: bricks.Ctx) -> dict:
    rows = query(ctx.conn, queries.JOB_RAW_LINES, ctx.schema, service=config.SERVICE_NAME, job=x["job"])
    n = config.RAW_LOG_HEAD_TAIL
    keep = [r for i, r in enumerate(rows) if i < n or i >= len(rows) - n or r["severity_number"] >= 13]
    text = "\n".join(f"{r['timestamp']} {r['severity_text']} {r['body']}" for r in keep)[:config.RAW_LOG_MAX_CHARS]
    prompt = prompts.LLM_RAW_LOGS.format(question=x["question"], raw_logs=text, classes=config.CLASSES,
                                         definitions=_definitions())
    req = {"model": config.LLM_MODEL, "system": prompts.LLM_SYSTEM, "prompt": prompt, "repeat": x.get("repeat", 0)}
    return _llm_result(cached(ctx.cache_dir, "llm", req, lambda: models.llm(prompts.LLM_SYSTEM, prompt)),
                       prompts.LLM_SYSTEM, prompt)


class PatternClassifier:
    """B3: TF-IDF over the job's pattern ids (bag of patterns, weighted by count) + logistic regression."""

    def __init__(self):
        self.vec = TfidfVectorizer(token_pattern=r"P\d+", lowercase=False, sublinear_tf=True)
        self.clf = LogisticRegression(max_iter=2000, class_weight="balanced")

    @staticmethod
    def doc(x: dict) -> str:
        return " ".join(" ".join([r["pattern_id"]] * r["n"]) for r in x["pattern"]["patterns"])

    def fit(self, examples: list[dict], labels: list[str]):
        self.clf.fit(self.vec.fit_transform([self.doc(x) for x in examples]), labels)
        return self

    def predict(self, x: dict) -> dict:
        p = self.clf.predict_proba(self.vec.transform([self.doc(x)]))[0]
        probs = {c: 0.0 for c in config.CLASSES} | dict(zip(self.clf.classes_, p))
        return {"class": max(probs, key=probs.get), "probabilities": probs, "latency_ms": 0, "cost_usd": 0.0}


# B4: hand-written keyword rules (deliberately NOT general - shows what a non-general approach gets).
RULES = [("disk full", ["no space", "disk full", "diskchecker"]),
         ("network disconnection", ["no route to host", "unreachable", "timed out", "timeout"]),
         ("machine down", ["connection refused", "lost", "killed", "not responding"])]


def b4_rules(x: dict, ctx: bricks.Ctx) -> dict:
    text = " ".join((r["template"] + " " + (r["example_line"] or "")).lower() for r in x["pattern"]["patterns"])
    cls = next((c for c, words in RULES if any(w in text for w in words)), None)
    if cls is None:  # no keyword hit: no errors -> normal, else the most common failure class in dev
        f = x["pattern"]["job_facts"]
        cls = "normal" if f["n_error"] + f["n_fatal"] == 0 else "machine down"
    return {"class": cls, "probabilities": {c: float(c == cls) for c in config.CLASSES}, "latency_ms": 0,
            "cost_usd": 0.0}


def runnable(fn, name: str, ctx: bricks.Ctx):
    return RunnableLambda(lambda x: fn(x, ctx)).with_config(run_name=name)
