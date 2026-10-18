"""Setup tools (plan 016): the MCP server sets itself up, so a user needs only Docker + Claude. Load the base corpus or
their own log file from the chat, see progress, switch datasets, remove one. Loading runs in a background thread
(downloads and big files take minutes; an MCP call would time out); setup_status reports the job. The work itself is
the loader package (loader/core.py), the same code as the CLI `uv run python -m loader`.
"""
import sys
import threading
import time
import traceback
from datetime import datetime
from pathlib import Path
from typing import Annotated, Optional

from pydantic import Field

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))
from loader import core as loader  # noqa: E402

import core  # noqa: E402

_jobs: list[dict] = []
_lock = threading.Lock()


def _job_view(j: dict) -> dict:
    out = {k: v for k, v in j.items() if k not in ("thread", "log")}
    out["log_tail"] = j["log"][-8:]
    if j["state"] == "running":
        out["running_s"] = round(time.time() - j["t0"])
    del out["t0"]
    return out


def setup_status() -> dict:
    """Is the database ready, which datasets are loaded, which one is active, and how is a running load doing?

    Use when: the first call of a session, before any analysis tool; after load_logs to follow its progress; when a
    tool says no dataset is loaded; to list datasets before use_dataset.
    Not for: what a dataset contains (describe_corpus), the format detection of one dataset (ingest_report).
    Returns: database version and reachability, schema ready, loaded datasets (lines, span, judged by Jev or not),
    the active dataset, AI keys registered (typesafe = Jev, gemini = embeddings), the loadable catalog (the brief's
    Loghub table) and load jobs (state, last log lines, result).
    Caveats: a running load keeps the previous active dataset until it finishes.
    Example: setup_status()
    Next: load_logs(source='base') for the base corpus; use_dataset(name).
    """
    t0 = time.perf_counter()
    out: dict = {"tool": "setup_status"}
    try:
        c = loader.connect()
        out["database"] = c.execute("SELECT version()").fetchone()[0]
        out["schema_ready"] = loader.schema_version(c) == loader.SCHEMA_VERSION
        out["ai_secrets"] = sorted(loader.jev.secrets(c) or loader.register_secrets(c))
        rows = c.execute("SELECT d.dataset, d.title, (SELECT count(*) FROM logs l WHERE l.dataset = d.dataset) AS lines, "
                         "(SELECT min(ts) FROM logs l WHERE l.dataset = d.dataset) AS first_ts, "
                         "(SELECT max(ts) FROM logs l WHERE l.dataset = d.dataset) AS last_ts, "
                         "EXISTS (SELECT 1 FROM pattern_judgments j WHERE j.dataset = d.dataset) AS judged "
                         "FROM datasets d ORDER BY d.pattern_base").fetchall() if out["schema_ready"] else []
        out["datasets"] = [dict(zip(("dataset", "title", "lines", "first_ts", "last_ts", "judged"),
                                    [str(x) if isinstance(x, datetime) else x for x in r])) for r in rows]
    except Exception as e:  # noqa: BLE001
        out["database"] = f"NOT REACHABLE: {e}".splitlines()[0]
        out["hints"] = ["Start SereneDB: `docker compose up -d` in the repo folder (README, Setup), then call setup_status "
                        "again."]
        return out
    out["active_dataset"] = core.active() if core.single() else "(multi-dataset server: every tool takes `dataset`)"
    cat = loader.catalog()
    out["catalog"] = [{"name": n, "lines": int(e["lines"]), "download": e["size"], "title": e["title"],
                       "loader": e["loader"] or "format auto-detection"} for n, e in cat.items()]
    with _lock:
        out["jobs"] = [_job_view(j) for j in _jobs]
    hints = []
    if not out["datasets"] and not any(j["state"] == "running" for j in _jobs):
        hints.append("Nothing loaded: load_logs(source='base') loads the base corpus (" + ", ".join(loader.base_corpus())
                     + ": download per the brief, our loaders, committed Jev judgments); or load_logs(source='/path/to/file.log').")
    if any(j["state"] == "running" for j in _jobs):
        hints.append("A load is running: call setup_status again in ~30 s.")
    out["hints"] = hints
    out["elapsed_ms"] = round((time.perf_counter() - t0) * 1000, 1)
    return out


def _run(job: dict) -> None:
    def log(m: str) -> None:
        job["log"].append(f"{datetime.now():%H:%M:%S} {m}")
    try:
        sources = loader.base_corpus() if job["source"] == "base" else [job["source"]]
        reps = []
        for src in sources:
            rep = loader.load(src, job.get("name"), job.get("year"), job["judge"], job["confirm_large"], log=log)
            reps.append(rep)
            if rep.get("ok"):
                core.refresh()
                if core.single() and (len(reps) == 1):  # the first dataset loaded becomes the active one
                    core.set_active(rep["dataset"])
            else:
                break
        job["result"] = reps[0] if len(reps) == 1 else {"ok": all(r.get("ok") for r in reps), "datasets": reps,
                                                        "dataset": reps[0].get("dataset")}
        job["state"] = "done" if job["result"].get("ok") else "refused"
    except Exception as e:  # noqa: BLE001
        job["state"] = "failed"
        job["error"] = f"{type(e).__name__}: {e}"[:600]
        log(traceback.format_exc().splitlines()[-1])
    job["seconds"] = round(time.time() - job["t0"], 1)


def load_logs(
    source: Annotated[str, Field(description="'base' = the base corpus (every catalog dataset marked base), a dataset "
                                             "name from the catalog (setup_status lists them: other Loghub sets), or "
                                             "the path of a log file on this machine (any folder; '~' allowed).")],
    name: Annotated[Optional[str], Field(description="Dataset name for a file (lower case, digits, _); default: "
                                                     "the file name. Loading the same name again replaces it.")] = None,
    year: Annotated[Optional[int], Field(description="Year for formats that log none (e.g. syslog); stated in the "
                                                     "dataset description.")] = None,
    judge: Annotated[bool, Field(description="Judge new patterns with Jev inside SereneDB (needs TYPESAFE_API_KEY in "
                                             ".env). Catalog datasets use committed judgments either way.")] = True,
    confirm_large: Annotated[bool, Field(description="Allow catalog datasets above 20M lines (multi-GB downloads).")] = False,
    wait_s: Annotated[int, Field(ge=0, le=50, description="Seconds to wait for the load to finish before returning "
                                                         "(it keeps running in the background).")] = 40,
) -> dict:
    """Load logs into SereneDB: the base corpus, another Loghub dataset, or the user's own log file.

    Use when: setup_status shows nothing loaded, the user asks to load / add / analyse a log file or a dataset, or a
    question needs a dataset that is not loaded yet.
    Not for: switching between loaded datasets (use_dataset), deleting one (remove_dataset).
    Returns: the load job: state (running / done / refused / failed), log lines, and when done the dataset name, lines,
    time span, patterns, whether Jev judged it, the detected format and its sample coverage (files).
    Caveats: catalog names download from the brief's Zenodo links (BGL 709 MB, a few minutes) and use our loaders;
    a file is streamed in, its format detected from 76 lnav formats and loaded only at >= 95 % sample coverage
    (else refused with the closest formats; nothing guessed). Without a Jev key a new file's problems use log levels
    only (stated in results). The finished dataset becomes the active one.
    Example: load_logs(source='base'); load_logs(source='~/logs/app.log', name='app')
    Next: setup_status() while running; then describe_corpus(), ingest_report() for a file, top_patterns().
    """
    with _lock:
        if any(j["state"] == "running" for j in _jobs):
            raise ValueError("A load is already running (setup_status shows it); start the next one when it is done.")
        job = {"id": len(_jobs) + 1, "source": source, "name": name, "year": year, "judge": "auto" if judge else "never",
               "confirm_large": confirm_large, "state": "running", "log": [], "t0": time.time(),
               "started": datetime.now().isoformat(timespec="seconds")}
        _jobs.append(job)
    job["thread"] = threading.Thread(target=_run, args=(job,), daemon=True)
    job["thread"].start()
    job["thread"].join(wait_s)
    out = {"tool": "load_logs", "job": _job_view(job)}
    if job["state"] == "running":
        out["hints"] = ["Still loading in the background: call setup_status in ~30 s (downloads and large files take "
                        "minutes)."]
    elif job["state"] == "done":
        out["hints"] = [f"Active dataset is now {job['result']['dataset']}: describe_corpus() to see it"
                        + ("; ingest_report() for how its format was detected." if job["result"].get("format") else ".")]
    return out


def use_dataset(
    name: Annotated[str, Field(description="A loaded dataset (setup_status lists them).")],
) -> dict:
    """Switch the dataset every tool works on.

    Use when: several datasets are loaded and the question is about another one, a whole-corpus answer needs each
    dataset in turn, or the user names a dataset.
    Not for: loading a new one (load_logs).
    Returns: the new active dataset and its field guide (span, levels, components, field meanings, teams).
    Caveats: tools have no dataset parameter; every later call uses this dataset until the next switch or load.
    Example: use_dataset(name=<a dataset from setup_status>)
    Next: describe_corpus() for the dataset's details.
    """
    if not core.single():
        raise ValueError("Multi-dataset server (LOGS_DATASET='*'): pass `dataset` to each tool instead.")
    core.refresh()
    have = core.loaded_datasets()
    if name not in have:
        raise ValueError(f"{name!r} is not loaded; loaded: {', '.join(have) or 'none'} (load_logs to add it).")
    core.set_active(name)
    return {"tool": "use_dataset", "active_dataset": name, "field_guide": core.field_guide()}


def remove_dataset(
    name: Annotated[str, Field(description="The dataset to delete (setup_status lists them).")],
) -> dict:
    """Delete one loaded dataset from SereneDB (its lines, patterns, judgments and ownership rows).

    Use when: the user asks to remove or unload a dataset, or to start over with a file (loading the same name again
    also replaces it).
    Not for: switching datasets (use_dataset).
    Returns: the dataset removed, log lines deleted, the datasets left and the new active dataset.
    Caveats: cannot be undone; a catalog dataset can be loaded again with load_logs (files under data/raw are kept).
    Example: remove_dataset(name='myapp')
    Next: setup_status().
    """
    core.refresh()
    if name not in core.loaded_datasets():
        raise ValueError(f"{name!r} is not loaded; loaded: {', '.join(core.loaded_datasets()) or 'none'}.")
    c = loader.connect()
    n = loader.remove(c, name, log=lambda _: None)
    if core.active() == name:
        core.set_active(None)
    core.refresh()
    return {"tool": "remove_dataset", "removed": name, "lines_deleted": n, "loaded": list(core.loaded_datasets()),
            "active_dataset": core.active()}
