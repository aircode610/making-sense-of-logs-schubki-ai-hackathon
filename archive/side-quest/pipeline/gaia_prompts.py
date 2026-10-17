"""Every Jev question for GAIA (plan 002 §4.1), per role, and the LLM mirror (D11).

Rules (docs/jev/NOTES.md): one narrow judgment per question, full meaning in `instructions`, backticked state paths,
numbers already turned into words by SQL + code, generic definitions (never dataset log strings).
The LLM mirror is built FROM the Jev questions (same instructions, same options and definitions, same state), so the
two models always answer the identical form.
"""
import json
import random

# ------------------------------------------------------------------ engineer ---------------------------------------
FAULT = {   # label -> option text (option keys are what both models answer with)
    "file_missing": "missing file or resource",
    "permission_denied": "permission denied",
    "none": "no fault visible",
}
CANT_TELL = "cannot tell from these logs"
OPTIONS = list(FAULT.values())                    # Q0 class options, fixed order
LABEL_OF = {v: k for k, v in FAULT.items()} | {CANT_TELL: "none"}   # pre-registered: "can't tell" scores as "none"

FAULT_DEFINITIONS = {
    "missing file or resource": {
        "definition": "A component cannot find a file, resource or configuration it needs.",
        "covers": "Errors saying a file, path, resource or config does not exist or cannot be found or loaded, "
                  "appearing new or far more often than usual.",
        "does_not_cover": "The resource exists but access to it is refused; slow or unavailable dependencies.",
    },
    "permission denied": {
        "definition": "A component is refused access to a resource or to a service it depends on.",
        "covers": "Access denied, permission or authorization errors, a service refusing requests from its callers, "
                  "and callers then reporting errors from that dependency.",
        "does_not_cover": "Missing files or resources; dependencies that are only slow.",
    },
    "no fault visible": {
        "definition": "The logs in this window look like the system's usual behaviour.",
        "covers": "Routine errors and warnings at about their usual rate, informational messages, small fluctuations.",
        "does_not_cover": "A burst of errors that are new or much more frequent than in the previous 24 hours.",
    },
    CANT_TELL: {
        "definition": "The evidence is too weak or ambiguous to say whether there was a fault.",
        "covers": "Small or mixed changes that could be noise or an early sign of a problem.",
        "does_not_cover": "A clear new error burst, or clearly usual behaviour.",
    },
}

INSTR_FAULT = ("`question` asks about a time window of a multi-service system. `evidence` lists the log patterns of that "
               "window that are new or more frequent than in the previous 24 hours; `window` summarises log volume. "
               "Which option best describes what happened in this window?")


def _fault_choice(options: list[str], instructions: str = INSTR_FAULT) -> dict:
    return {"type": "choice", "instructions": instructions, "criteria": {o: FAULT_DEFINITIONS[o] for o in options}}


def key_evidence(evidence_ids: list[str]) -> dict:
    criteria = {eid: f"Evidence item `evidence.{eid}`" for eid in evidence_ids}
    criteria["none"] = "No evidence item shows a fault."
    return {"type": "choice", "criteria": criteria,
            "instructions": "Which single item in `evidence` most directly shows the cause of a problem in this window?"}


def root_service(candidates: dict[str, str]) -> dict:
    """Q7: evidence-in-choices over services (descriptions come from SQL), plus none."""
    criteria = dict(candidates)
    criteria["none"] = "No service has a fault in this window."
    return {"type": "choice", "criteria": criteria,
            "instructions": "Which service is the root cause of the problem in this window (where the fault started, "
                            "not a service that only reports errors from a dependency)?"}


def engineer_questions(design: str, evidence_ids: list[str], service_candidates: dict[str, str]) -> dict:
    """Q0 base | Q1 abstain | Q2 two-stage | Q7 = Q0 + root-cause service; "<base>+Q7" adds Q7 to Q1/Q2."""
    base, _, extra = design.partition("+")
    if base == "Q7" or extra == "Q7":
        qs = engineer_questions("Q0" if base == "Q7" else base, evidence_ids, {})
        qs["root_service"] = root_service(service_candidates)
        return qs
    if design == "Q1":
        return {"fault": _fault_choice(OPTIONS + [CANT_TELL]), "key_evidence": key_evidence(evidence_ids)}
    if design == "Q2":
        return {"is_fault": {"type": "noul", "instructions":
                             "Do the logs described in `evidence` and `window` show a fault in this window: errors that "
                             "are new or much more frequent than in the previous 24 hours?",
                             "criteria": {"true": "A clear fault is visible in this window.",
                                          "false": "The window looks like usual behaviour."}},
                "fault_type": _fault_choice(OPTIONS[:2], "If there is a fault in this window (see `evidence`), which "
                                                         "kind of fault is it?"),
                "key_evidence": key_evidence(evidence_ids)}
    return {"fault": _fault_choice(OPTIONS), "key_evidence": key_evidence(evidence_ids)}


# Q6 / L1: broad, dataset-independent taxonomy (mapped to GAIA labels in code; also used to group incidents).
BROAD = {
    "host or process crash": "A machine, container or process stopped.",
    "network problem": "Connections time out, are refused or dropped between components.",
    "missing file or configuration": "A needed file, path, resource or configuration does not exist.",
    "permission or authorization error": "Access to a resource or a service is denied.",
    "resource exhaustion": "Memory, disk, CPU or connection pools run out.",
    "slow or failing dependency": "A downstream service is slow or returns errors, and callers fail.",
    "application bug": "Wrong code behaviour: exceptions, bad queries, unexpected values.",
    "no fault visible": "The window looks like usual behaviour.",
}
BROAD_TO_LABEL = {"missing file or configuration": "file_missing", "permission or authorization error": "permission_denied"}


def broad_question() -> dict:
    return {"type": "choice", "criteria": BROAD,
            "instructions": "Which kind of problem best describes what the logs in `evidence` show for this window?"}


# ------------------------------------------------------------------ lead ------------------------------------------
def lead_same_problem() -> dict:
    return {"type": "noul", "instructions":
            "Do `incident_a` and `incident_b` show the same underlying problem (the same kind of fault starting in the "
            "same service), even if they happened at different times?",
            "criteria": {"true": "Same kind of fault in the same service.",
                         "false": "Different kinds of fault, or the same kind in a different service, or one of them "
                                  "shows no fault."}}


def lead_repeat(known_ids: list[str]) -> dict:
    criteria = {k: f"The same problem as `known_problems.{k}`" for k in known_ids}
    criteria["new"] = "A problem that matches none of `known_problems`."
    return {"type": "choice", "criteria": criteria,
            "instructions": "Is `incident` a repeat of one of the problems in `known_problems` (same kind of fault in "
                            "the same service), or a new problem?"}


# ------------------------------------------------------------------ manager ---------------------------------------
def manager_first(order: list[str]) -> dict:
    return {"type": "choice", "criteria": {k: f"Fix `problems.{k}` first" for k in order},
            "instructions": "A team lead must choose which problem in `problems` to fix first this week. Consider how "
                            "many users were affected (`extra_failed_requests`), whether customers see it, how often it "
                            "happened and for how long. Which should be fixed first?"}


IMPACT_LEVELS = ["No user impact", "A few users see errors", "Many users see errors on a key action",
                 "A core user flow is broken for most users"]


def manager_impact() -> dict:
    return {"type": "score", "criteria": IMPACT_LEVELS,
            "instructions": "How large is the user impact of `problem` this week, given its numbers and whether "
                            "customers see it?"}


# ------------------------------------------------------------------ LLM mirror (D11) ------------------------------
LLM_SYSTEM = ("You are an SRE assistant for a multi-service system. Answer only from the information given. "
              "Reply with JSON only.")

LLM_FORM = """State (computed by the database):
{state_json}

Answer every question below. Each question has an "instructions" text and either "options" (choose exactly one option
key) or is a yes/no question (answer true or false). Option descriptions explain what each option means.
Questions:
{questions_json}

Return JSON with one entry per question id: {{"<question id>": {{"answer": <option key, or true/false>, "confidence": <number 0-1, how sure you are>}}}}"""


def llm_form(state: dict, questions: dict) -> str:
    """The LLM gets the IDENTICAL state and, per question, the identical instructions + options + definitions."""
    form = {}
    for qid, q in questions.items():
        entry = {"instructions": q["instructions"]}
        if q["type"] == "noul":
            entry["type"] = "yes/no"
            if "criteria" in q:
                entry["meaning"] = {"true": q["criteria"]["true"], "false": q["criteria"]["false"]}
        elif q["type"] == "score":
            entry["type"] = "ordered levels"
            entry["options"] = {str(i): lvl for i, lvl in enumerate(q["criteria"])}
        else:
            entry["type"] = "choice"
            entry["options"] = q["criteria"]
        form[qid] = entry
    return LLM_FORM.format(state_json=json.dumps(state, indent=1), questions_json=json.dumps(form, indent=1))


def shuffled(questions: dict, seed: int) -> dict:
    """Same questions with each Choice's option order shuffled (both models get the same order for a given seed)."""
    rng = random.Random(seed)
    out = {}
    for qid, q in questions.items():
        if q["type"] == "choice":
            keys = list(q["criteria"])
            rng.shuffle(keys)
            q = {**q, "criteria": {k: q["criteria"][k] for k in keys}}
        out[qid] = q
    return out
