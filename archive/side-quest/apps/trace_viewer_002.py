"""Trace viewer for experiment 002: one question, Jev and the LLM side by side (exact inputs + answers).

    .venv/bin/streamlit run apps/trace_viewer_002.py

Steps are named "<model>:<variant>" (e.g. jev:E1/Q0, llm:E1/Q0, jev:L0, B2_llm_raw_logs). Fairness = the LLM prompt
contains Jev's exact state JSON and every Choice option key (same check as experiments/002_gaia/core.fairness_ok).
"""
import json
import sys
from pathlib import Path

import streamlit as st

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from pipeline import db  # noqa: E402

st.set_page_config(page_title="Trace viewer 002", layout="wide")
conn = db.connect()
q = lambda sql, *p: conn.execute(sql, p).fetchall()  # noqa: E731

runs = [r["run_id"] for r in q("SELECT DISTINCT run_id FROM public.traces WHERE run_id LIKE '002-dev-%' ORDER BY 1 DESC")]
st.sidebar.title("Trace viewer 002")
run_id = st.sidebar.selectbox("Run", runs)
steps = sorted({r["step"] for r in q("SELECT DISTINCT step FROM public.traces WHERE run_id = %s", run_id)})
variants = sorted({s.split(":", 1)[1] for s in steps if ":" in s})
variant = st.sidebar.selectbox("Variant", variants)
qids = [r["qid"] for r in q("SELECT DISTINCT qid FROM public.traces WHERE run_id = %s AND step = %s ORDER BY 1",
                            run_id, f"jev:{variant}")]
qid = st.sidebar.selectbox(f"Question ({len(qids)})", qids)


def row(step):
    r = q("SELECT * FROM public.traces WHERE run_id = %s AND qid = %s AND step = %s", run_id, qid, step)
    return r[0] if r else None


jv, lm = row(f"jev:{variant}"), row(f"llm:{variant}")
ji = json.loads(jv["input_json"]) if jv else {}
li = json.loads(lm["input_json"]) if lm else {}
if ji and li:
    prompt = li.get("prompt", "")
    same_state = json.dumps(ji["state"], indent=1) in prompt
    same_opts = all(json.dumps(k) in prompt for qq in ji["questions"].values() if qq["type"] == "choice" for k in qq["criteria"])
    (st.success if same_state and same_opts else st.error)(
        f"Fairness: identical state {'✅' if same_state else '❌'} · identical options {'✅' if same_opts else '❌'}")
c1, c2 = st.columns(2)
with c1:
    st.subheader(f"Jev ({jv['latency_ms']:.0f} ms)" if jv else "Jev")
    if jv:
        st.json(json.loads(jv["output_json"]), expanded=True)
        st.caption("State")
        st.json(ji.get("state"), expanded=False)
        st.caption("Questions")
        st.json(ji.get("questions"), expanded=False)
with c2:
    st.subheader(f"LLM ({lm['latency_ms']:.0f} ms)" if lm else "LLM")
    if lm:
        st.json(json.loads(lm["output_json"]), expanded=True)
        st.caption("Prompt")
        st.code(li.get("prompt", ""), language="json")
