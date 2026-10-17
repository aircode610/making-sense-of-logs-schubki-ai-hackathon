"""All tunable numbers and settings in one place. Calibration knobs are marked with [KNOB]."""
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# --- SereneDB ---------------------------------------------------------------
DB_DSN = "host=localhost port=7890 user=postgres dbname=postgres"
DEV_SCHEMA = "public"                                   # dev data + dev traces live here
DEV_OTLP_URL = "http://127.0.0.1:4318/v1/logs"          # OTLP listener for the dev schema
OTLP_AUTH = ("otel", "otel")
SERVICE_NAME = "hadoop-mapreduce"                       # resource service.name for every Hadoop record

# --- Data ---------------------------------------------------------------------
DEV_DIR = ROOT / "dataset" / "dev" / "hadoop"           # written by scripts/make_split.py
CLASSES = ["normal", "machine down", "network disconnection", "disk full"]

# --- Models -------------------------------------------------------------------
JEV_MODEL = "jev-1.13.0"            # pinned (D4), never "jev-latest"
LLM_MODEL = "gemini-3.8-flash"      # D1
LLM_THINKING_BUDGET = 0             # 0 = no thinking (default thinking took 18 s for a one-word answer)
JEV_PRICE_PER_INPUT_TOKEN = 0.042 / 1e6
LLM_PRICE_PER_INPUT_TOKEN = 0.50 / 1e6   # Gemini Flash list price assumption, update if it differs
LLM_PRICE_PER_OUTPUT_TOKEN = 3.00 / 1e6

# --- Pattern brick ------------------------------------------------------------
DRAIN_SIM_TH = 0.4                  # [KNOB] Drain3 similarity threshold (lower = fewer, broader templates)
DRAIN_DEPTH = 4                     # [KNOB] Drain3 parse-tree depth

# --- Evidence brick -----------------------------------------------------------
EVIDENCE_MIN_SEVERITY = 13          # [KNOB] 13 = WARN and worse (OTel severity numbers)
TOP_K_EVIDENCE = 12                 # [KNOB] evidence items handed to Jev / the LLM
EXAMPLE_LINE_CHARS = 300            # [KNOB] length of the raw example line attached to each evidence item
RARE_MAX_JOB_FRACTION = 0.25        # [KNOB] A4: a pattern counts as "rare" if it appears in <= this fraction of jobs

# --- Verdict / Finding --------------------------------------------------------
# [KNOB] experiment variant (ablations A0-A3 in plans/001): see pipeline/prompts.py
#        evidence: "basic" | "full" (WARN+ only) | "rarity" (A4: rare patterns at any severity + duration vs typical)
VARIANT = {"evidence": "full", "criteria": "structured", "shuffles": 0}
AUTO_THRESHOLD = 0.6                # [KNOB] Finding badge: confidence >= this -> "auto", else "needs review".
                                    #        Tuned on dev by experiments/001_hadoop/run_dev.py, then frozen.

# --- Baselines ----------------------------------------------------------------
RAW_LOG_HEAD_TAIL = 50              # B2: first/last N lines of the job
RAW_LOG_MAX_CHARS = 120_000         # B2: ~30k tokens cap
