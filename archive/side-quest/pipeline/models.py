"""Thin wrappers around the two model APIs. Both return plain dicts with latency, tokens and cost."""
import json
import re
import time

from langchain_google_genai import ChatGoogleGenerativeAI
from typesafe_sdk import TypeSafeClient

from pipeline import config

_jev = None
_llm = None


def jev(state: dict, questions: dict) -> dict:
    """One Jev request (all questions in parallel). Returns answers + usage."""
    global _jev
    _jev = _jev or TypeSafeClient(model=config.JEV_MODEL, timeout=60.0)
    t0 = time.perf_counter()
    res = _jev.system_one(state=state, questions=questions)
    ms = (time.perf_counter() - t0) * 1000
    tokens = res.usage.input_tokens
    return {"answers": res.model_dump()["answers"], "model": res.model, "latency_ms": round(ms),
            "input_tokens": tokens, "cost_usd": tokens * config.JEV_PRICE_PER_INPUT_TOKEN}


def llm(system: str, prompt: str) -> dict:
    """One Gemini call (thinking off). Parses the first JSON object in the reply."""
    global _llm
    _llm = _llm or ChatGoogleGenerativeAI(model=config.LLM_MODEL, temperature=0,
                                          thinking_budget=config.LLM_THINKING_BUDGET,
                                          timeout=60, max_retries=2)  # without a timeout, stuck calls hang forever
    t0 = time.perf_counter()
    try:
        msg = _llm.invoke([("system", system), ("human", prompt)])
    except Exception as e:  # one failed call = one recorded error, not a crashed run (and never cached)
        return {"parsed": {}, "text": "", "error": repr(e)[:500], "latency_ms": round((time.perf_counter() - t0) * 1000),
                "input_tokens": 0, "output_tokens": 0, "cost_usd": 0.0, "model": config.LLM_MODEL}
    ms = (time.perf_counter() - t0) * 1000
    text = msg.text if isinstance(msg.text, str) else msg.text()
    m = re.search(r"\{.*\}", text, re.S)
    try:
        parsed = json.loads(m.group(0)) if m else {}
    except json.JSONDecodeError:
        parsed = {}
    u = msg.usage_metadata or {}
    cost = u.get("input_tokens", 0) * config.LLM_PRICE_PER_INPUT_TOKEN + \
        u.get("output_tokens", 0) * config.LLM_PRICE_PER_OUTPUT_TOKEN
    return {"parsed": parsed, "text": text, "latency_ms": round(ms), "input_tokens": u.get("input_tokens", 0),
            "output_tokens": u.get("output_tokens", 0), "cost_usd": cost, "model": config.LLM_MODEL}
