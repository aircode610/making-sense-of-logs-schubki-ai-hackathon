"""Probe Jev capabilities on the tutorial incident (needs: docker compose up, tutorial/send_logs.py loaded,
log_templates table from tutorial/ADVANCED.md section A6, TYPESAFE_API_KEY in env).

Runs 5 experiments and prints latency, answers, probabilities and confidence:
  1. evidence-in-choices: "which template is the root cause?" with evidence packed into each option
  2. same, options shuffled 3x  -> option-order robustness
  3. same request 3x            -> self-consistency
  4. fan-out: 1 request with 1 question vs 1 request with 12 questions -> latency/cost of extra questions
  5. symptom-vs-cause Nouls per template with structured criteria

Usage: python3 tutorial/jev_capabilities.py
"""
import csv
import io
import json
import os
import random
import subprocess
import time
import urllib.request

API = "https://api.typesafe.ai/v1/systemone"
KEY = os.environ["TYPESAFE_API_KEY"]


def sql(query):
    out = subprocess.run(["psql", "-h", "localhost", "-p", "7890", "-U", "postgres", "-d", "postgres", "--csv", "-c", query],
                         capture_output=True, text=True, check=True).stdout
    return list(csv.DictReader(io.StringIO(out)))


def jev(state, questions):
    body = json.dumps({"model": "jev-latest", "state": state, "questions": questions}).encode()
    req = urllib.request.Request(API, data=body, method="POST",
                                 headers={"Authorization": f"Bearer {KEY}", "Content-Type": "application/json"})
    t0 = time.perf_counter()
    with urllib.request.urlopen(req) as r:
        res = json.load(r)
    res["_ms"] = round((time.perf_counter() - t0) * 1000)
    return res


# ---- evidence from SereneDB (all numbers computed in SQL, not by any model) ----
rows = sql("""
  SELECT id, template, n, services[1] AS service,
         epoch_ms(first_seen) - min(epoch_ms(first_seen)) OVER () AS ms_after_first_anomaly
  FROM log_templates
  WHERE id IN (SELECT id FROM log_templates WHERE template ~ 'Timeout|failed|Bad Gateway|slow')
  ORDER BY first_seen, id""")
# relative order computed in code (Jev is weak at comparing timestamps)
evidence = {
    f"T{r['id']}": {
        "log_template": r["template"],
        "service": r["service"],
        "occurrences_in_incident": int(r["n"]),
        "first_appearance": "first anomaly in the incident" if r["ms_after_first_anomaly"] == "0"
                            else f"{r['ms_after_first_anomaly']} ms after the first anomaly",
    }
    for r in rows
}
evidence["none"] = "None of these templates is the root cause; the cause is not visible in these logs."
state = {
    "question": "Why did checkout fail between 14:05 and 14:12?",
    "call_chain": "frontend calls checkout, checkout calls payment, payment calls the external provider Stripe",
}
root_q = {
    "type": "choice",
    "instructions": "Which log template in the criteria is closest to the root cause of the failure in `question`? "
                    "A root cause is the earliest failure that the other failures follow from, not a downstream symptom.",
    "criteria": evidence,
}

print("== 1. evidence-in-choices")
r = jev(state, {"root_cause": root_q})
a = r["answers"]["root_cause"]
print(f"  {r['_ms']} ms | choice={a['choice']} confidence={a['confidence']} | probs={a['probabilities']}")
print(f"  -> {evidence.get(a['choice'], {}).get('log_template') if a['choice'] != 'none' else 'none'}")

print("== 2. option-order robustness (shuffled 3x)")
keys = list(evidence)
for i in range(3):
    random.seed(i)
    shuffled = random.sample(keys, len(keys))
    q = dict(root_q, criteria={k: evidence[k] for k in shuffled})
    a = jev(state, {"root_cause": q})["answers"]["root_cause"]
    print(f"  order={shuffled} -> {a['choice']} (conf {a['confidence']})")

print("== 3. self-consistency (same request 3x)")
for _ in range(3):
    a = jev(state, {"root_cause": root_q})["answers"]["root_cause"]
    print(f"  {a['choice']} p={a['probabilities'][a['choice']]}")

print("== 4. fan-out cost: 1 question vs many questions in ONE request")
r1 = jev(state, {"root_cause": root_q})
many = {"root_cause": root_q}
for k, v in evidence.items():
    if k == "none":
        continue
    many[f"{k}_symptom"] = {"type": "noul", "instructions": f"Is template {k} in `evidence` a downstream symptom of a failure in another service?"}
    many[f"{k}_customer"] = {"type": "noul", "instructions": f"Would the failure in template {k} of `evidence` be directly visible to a customer?"}
many["severity"] = {"type": "score", "instructions": "How severe is the incident described in `evidence` for the business?",
                    "criteria": ["No impact", "Degraded but working", "Some customers blocked from a key action", "Core flow down for everyone"]}
many["category"] = {"type": "choice", "instructions": "What kind of failure is the incident in `evidence`?",
                    "criteria": {"external_dependency": "A third-party service failed or was slow.",
                                 "our_code": "A bug in our own code.",
                                 "infrastructure": "Our hosts, network, disks or containers.",
                                 "unknown": "Cannot tell from the evidence."}}
state_many = dict(state, evidence={k: v for k, v in evidence.items() if k != "none"})
rm = jev(state_many, many)
print(f"  1 question : {r1['_ms']} ms, {r1['usage']['input_tokens']} input tokens")
print(f"  {len(many)} questions: {rm['_ms']} ms, {rm['usage']['input_tokens']} input tokens")
ans = rm["answers"]
print(f"  root_cause={ans['root_cause']['choice']} severity={ans['severity']['score']} category={ans['category']['choice']} (conf {ans['category']['confidence']})")
for k in evidence:
    if k != "none":
        print(f"  {k}: symptom={ans[f'{k}_symptom']['noul']} customer_visible={ans[f'{k}_customer']['noul']}  [{evidence[k]['log_template'][:50]}]")
price = 0.042 / 1e6
print(f"  cost of the many-question request: ${rm['usage']['input_tokens'] * price:.6f}")
