"""Trace viewer: every question's full path through the 4 bricks, with Jev and the LLM side by side.

    .venv/bin/streamlit run apps/trace_viewer.py                 # dev traces (schema public)
    .venv/bin/streamlit run apps/trace_viewer.py -- --schema X   # another schema

Fairness (plans/001 amendment 2): for every variant the LLM gets the identical evidence state and class options as Jev.
The "What each model received" panel checks that automatically for the selected question.
"""
import argparse
import json
import re
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline import db  # noqa: E402

ap = argparse.ArgumentParser()
ap.add_argument("--schema", default="public")
SCHEMA = ap.parse_args().schema

st.set_page_config(page_title="Trace viewer", layout="wide")
conn = db.connect()
q = lambda sql, *p: conn.execute(sql.format(s=SCHEMA), p).fetchall()  # noqa: E731


def one(run_id, qid, step):
    rows = q("SELECT * FROM {s}.traces WHERE run_id = %s AND qid = %s AND step = %s", run_id, qid, step)
    return rows[0] if rows else None


def out_of(row):
    return json.loads(row["output_json"]) if row and row["output_json"] else None


def llm_evidence(prompt: str):
    """The evidence state embedded in the LLM prompt (between the evidence header and 'Choose exactly one class')."""
    m = re.search(r"E-ids are evidence items\):\n(\{.*?\n\})\n\nChoose", prompt, re.S)
    return json.loads(m.group(1)) if m else None


def llm_options(prompt: str):
    """Class options as the LLM saw them: {class: definition-or-name}."""
    m = re.search(r"Class definitions: (\{.*\})\n\nReturn JSON", prompt, re.S)
    if m:
        return json.loads(m.group(1))
    m = re.search(r"Choose exactly one class from: (\[.*?\])", prompt)
    return {c: c for c in json.loads(m.group(1).replace("'", '"'))} if m else None


# ---- sidebar: session -> variant -> filters -> example ----------------------------------------------
runs = [r["run_id"] for r in q("SELECT DISTINCT run_id FROM {s}.traces ORDER BY 1 DESC")]
sessions = sorted({m.group(1) for r in runs if (m := re.match(r"(001-dev-\d{8}-\d{6})", r))}, reverse=True)
st.sidebar.title("Trace viewer")
st.sidebar.caption(f"schema: {SCHEMA}")
session = st.sidebar.selectbox("Session", sessions)
session_runs = [r for r in runs if r.startswith(session + "-")]
jev_runs = sorted(r for r in session_runs if re.search(r"-A\d_[^-]+$", r))
default = next((i for i, r in enumerate(jev_runs) if "A4_" in r), 0)
jev_run = st.sidebar.selectbox("Variant (same for Jev and LLM)", jev_runs, index=default,
                               format_func=lambda r: re.sub(r"^.*-(A\d_)", r"\1", r))
llm_run = jev_run + "-LLM" if jev_run + "-LLM" in session_runs else None
other_runs = sorted(r for r in session_runs if re.search(r"-B\d$", r))
if not llm_run:
    st.sidebar.warning("This session has no mirrored LLM run for this variant (older session).")

fin = q("SELECT qid, input_json FROM {s}.traces WHERE run_id = %s AND step = 'Finding'", jev_run)
llm_rows = {r["qid"]: json.loads(r["output_json"]) for r in
            q("SELECT qid, output_json FROM {s}.traces WHERE run_id = %s", llm_run)} if llm_run else {}
ex = {}
for r in fin:
    x = json.loads(r["input_json"])
    ex[r["qid"]] = {"label": x["label"], "jev": x["verdict"]["class"], "llm": llm_rows.get(r["qid"], {}).get("class")}
outcome = st.sidebar.selectbox("Outcome", ["all", "Jev right, LLM wrong", "LLM right, Jev wrong", "both wrong",
                                           "both right"])
labels = sorted({e["label"] for e in ex.values()})
f_label = st.sidebar.multiselect("Ground truth", labels, default=labels)


def keep(e):
    j, l = e["jev"] == e["label"], e["llm"] == e["label"]
    return e["label"] in f_label and {"all": True, "Jev right, LLM wrong": j and not l, "LLM right, Jev wrong": l and not j,
                                      "both wrong": not j and not l, "both right": j and l}[outcome]


shown = [k for k, e in sorted(ex.items()) if keep(e)]
mark = lambda ok: "✅" if ok else "❌"  # noqa: E731
qid = st.sidebar.selectbox(f"Question ({len(shown)} of {len(ex)})", shown,
                           format_func=lambda k: f"Jev {mark(ex[k]['jev'] == ex[k]['label'])} LLM "
                                                 f"{mark(ex[k]['llm'] == ex[k]['label'])}  {k}")

res_md = ROOT / "runs" / "001" / "dev_results.md"
with st.expander("Dev results table (runs/001/dev_results.md)", expanded=False):
    if res_md.exists():
        st.markdown(res_md.read_text())
if not qid:
    st.info("No question matches the filters.")
    st.stop()

# ---- header -------------------------------------------------------------------------------------------
pat, evi, ver, fnd = (one(jev_run, qid, s) for s in ("Pattern", "Evidence", "Verdict", "Finding"))
first = json.loads(pat["input_json"])
truth = first["label"]
st.header(first["question"])
st.write(f"**job** `{first['job']}` · **ground truth** `{truth}` · wording {first['wording']} · "
         f"**variant** `{re.sub(r'^.*-(A\\d_)', r'\\1', jev_run)}`")

# ---- shared bricks: Pattern + Evidence (identical input for both models) ---------------------------------
st.subheader("Shared bricks (built once, used by both models)")
po, eo = out_of(pat), out_of(evi)
with st.expander(f"1 · Pattern · {pat['latency_ms']:.0f} ms · {len(po['patterns'])} patterns from SQL"):
    st.dataframe([{k: v for k, v in p.items() if k != "example_line"} for p in po["patterns"]])
    st.write("Job facts:", po["job_facts"])
    for k, sql in po.get("sql", {}).items():
        st.code(sql, language="sql")
with st.expander(f"2 · Evidence · {len(eo['items'])} items", expanded=True):
    st.write("Job:", eo["job"])
    st.dataframe([{"id": k, **{kk: vv for kk, vv in v.items() if not kk.startswith('_')}} for k, v in eo["items"].items()])

# ---- what each model received ------------------------------------------------------------------------------
st.subheader("What each model received")
vo = out_of(ver)
lo = llm_rows.get(qid)
jev_state = vo["request"]["state"]
jev_opts = vo["request"]["questions"]["root_cause"]["criteria"]
if lo and lo.get("request"):
    same_ev = llm_evidence(lo["request"]["prompt"]) == jev_state
    same_opt = llm_options(lo["request"]["prompt"]) == jev_opts
    c1, c2 = st.columns(2)
    c1.metric("Evidence state identical", "yes ✅" if same_ev else "NO ❌")
    c2.metric("Class options identical", "yes ✅" if same_opt else "NO ❌")
left, right = st.columns(2)
with left:
    st.markdown("**Jev** (`jev-1.13.0`): state + questions, one request")
    st.json({"state": jev_state, "questions": vo["request"]["questions"]}, expanded=False)
with right:
    st.markdown("**LLM** (`gemini-3.8-flash`, thinking off): system + prompt")
    if lo and lo.get("request"):
        st.code(lo["request"]["system"], language="text")
        st.code(lo["request"]["prompt"], language="text")
    else:
        st.info("No mirrored LLM trace for this question.")

# ---- answers side by side ----------------------------------------------------------------------------------
st.subheader("Answers")
left, right = st.columns(2)
with left:
    st.markdown(f"**Jev** · {vo['class']} {mark(vo['class'] == truth)} · confidence {vo['confidence']:.2f} "
                f"(computed) · {vo['latency_ms']} ms · ${vo['cost_usd']:.6f}")
    st.bar_chart(vo["probabilities"])
    st.write({"key_evidence": vo["key_evidence"], "shuffle_agreement": vo["shuffle_agreement"],
              "finding": out_of(fnd)})
with right:
    if lo:
        st.markdown(f"**LLM** · {lo['class']} {mark(lo['class'] == truth)} · confidence "
                    f"{lo.get('self_reported_confidence')} (self-reported) · {lo['latency_ms']} ms · ${lo['cost_usd']:.6f}")
        st.write({"key_evidence": lo.get("key_evidence"), "shuffle_agreement": lo.get("shuffle_agreement"),
                  "shuffle_answers": lo.get("shuffle_answers"), "error": lo.get("error")})
        st.caption("Raw LLM reply")
        st.code(lo.get("raw_reply") or "", language="json")

# ---- other baselines ----------------------------------------------------------------------------------------
st.subheader("Other baselines (same question)")
for br in other_runs:
    b = q("SELECT * FROM {s}.traces WHERE run_id = %s AND qid = %s", br, qid)
    if not b:
        continue
    out = json.loads(b[0]["output_json"])
    with st.expander(f"{b[0]['step']} · {out.get('class')} {mark(out.get('class') == truth)} · {b[0]['latency_ms']:.0f} ms"):
        if out.get("request"):
            st.code(out["request"]["prompt"][:20000], language="text")
        st.write({k: out.get(k) for k in ("class", "self_reported_confidence", "probabilities", "latency_ms", "cost_usd")})
