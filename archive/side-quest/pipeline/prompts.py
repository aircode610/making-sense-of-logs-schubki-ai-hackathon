"""Every Jev question and every LLM prompt used by the pipeline and baselines.

This is the main calibration surface. Rules we follow (docs/jev/NOTES.md):
- one narrow judgment per question; full meaning in `instructions` (question ids are not sent to Jev)
- point at state parts with backticked paths (`evidence`, `question`)
- numbers/time are computed in SQL and passed as words; Jev never does arithmetic
- class definitions are GENERIC infrastructure knowledge, never dataset-specific log strings
"""
import random

from pipeline import config

# ---------------------------------------------------------------------------------------------
# Root-cause classes. "plain" = just the label names (ablation A0). "structured" = definitions.
# ---------------------------------------------------------------------------------------------
CLASS_DEFINITIONS_STRUCTURED = {
    "normal": {
        "definition": "The job ran without an infrastructure fault.",
        "covers": "Routine warnings, retries that succeed quickly, informational noise.",
        "does_not_cover": "Any host, network or disk failure that disrupted the job.",
    },
    "machine down": {
        "definition": "A worker machine stopped or crashed while the job was running.",
        "covers": "A host abruptly disappearing: its tasks/containers are lost, it stops answering, "
                  "work is rescheduled elsewhere, connections to that host are refused.",
        "does_not_cover": "A host that is still running but unreachable over the network.",
    },
    "network disconnection": {
        "definition": "A machine stayed up but lost network connectivity to the rest of the cluster.",
        "covers": "Timeouts, unreachable host or no route to host, dropped connections, repeated retries "
                  "to reach a peer.",
        "does_not_cover": "A machine that crashed or shut down.",
    },
    "disk full": {
        "definition": "A machine ran out of local disk space.",
        "covers": "Failures to write or spill data, no space left on device, disk errors on output or "
                  "temporary files.",
        "does_not_cover": "Memory exhaustion or network problems.",
    },
}


def root_cause_question(criteria_style: str, order: list[str] | None = None) -> dict:
    """Jev Choice: which class explains the job? `order` lets us shuffle options (robustness check)."""
    order = order or config.CLASSES
    if criteria_style == "structured":
        criteria = {c: CLASS_DEFINITIONS_STRUCTURED[c] for c in order}
    else:
        criteria = {c: c for c in order}
    return {
        "type": "choice",
        "instructions": "Given the log evidence in `evidence` for the job in `question`, which option best "
                        "describes what happened to the job?",
        "criteria": criteria,
    }


def key_evidence_question(evidence_ids: list[str]) -> dict:
    """Jev Choice over the evidence items themselves (evidence-in-choices). Used for the Finding's citation."""
    criteria = {eid: f"Evidence item `evidence.{eid}`" for eid in evidence_ids}
    criteria["none"] = "No evidence item shows a fault; the job looks normal."
    return {
        "type": "choice",
        "instructions": "Which single item in `evidence` most directly shows the cause of the job's problem?",
        "criteria": criteria,
    }


def shuffled_orders(seed: int, k: int) -> list[list[str]]:
    """The k shuffled class orders used by BOTH Jev and the LLM for the same question (same seed -> same orders)."""
    rng = random.Random(seed)
    return [rng.sample(config.CLASSES, len(config.CLASSES)) for _ in range(k)]


def jev_questions(evidence_ids: list[str], variant: dict, seed: int = 0) -> dict:
    """All questions for ONE Jev request (fan-out). Shuffled copies of root_cause only if variant asks."""
    qs = {
        "root_cause": root_cause_question(variant["criteria"]),
        "key_evidence": key_evidence_question(evidence_ids),
    }
    for i, order in enumerate(shuffled_orders(seed, variant["shuffles"])):
        qs[f"root_cause_shuffle_{i}"] = root_cause_question(variant["criteria"], order)
    return qs


# ---------------------------------------------------------------------------------------------
# LLM baselines (gemini-3.8-flash, thinking off). Same evidence state as Jev for B1.
# ---------------------------------------------------------------------------------------------
LLM_SYSTEM = (
    "You are an SRE assistant. You diagnose why a Hadoop MapReduce job behaved as it did, using only "
    "the log information given. Answer with JSON only."
)

LLM_SAME_EVIDENCE = """Question: {question}

Log evidence for this job (computed by the database; E-ids are evidence items):
{state_json}

Choose exactly one class from: {classes}.{definitions_block}

Return JSON: {{"class": <one of the classes>, "confidence": <number 0-1, how sure you are>, "key_evidence": <E-id or "none">}}"""


def llm_definitions_block(criteria_style: str, order: list[str]) -> str:
    """Mirror of Jev's criteria: nothing extra for "plain" (label names only), the same structured definitions otherwise."""
    if criteria_style != "structured":
        return ""
    import json
    return "\nClass definitions: " + json.dumps({c: CLASS_DEFINITIONS_STRUCTURED[c] for c in order}, indent=1)

LLM_RAW_LOGS = """Question: {question}

Raw log lines of this job (all WARN/ERROR/FATAL lines plus the first and last lines; may be truncated):
{raw_logs}

Choose exactly one class from: {classes}.
Class definitions: {definitions}

Return JSON: {{"class": <one of the classes>, "confidence": <number 0-1, how sure you are>}}"""
