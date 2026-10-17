"""Pattern brick: Drain3 template mining with GENERIC masks (no dataset-specific rules).

The template is mined from the first line of the message only (stack traces vary too much).
State is saved as JSON so a later run (e.g. held-out evaluation) continues from the dev-fitted miner.
"""
import json
from pathlib import Path

import jsonpickle
from drain3 import TemplateMiner
from drain3.masking import MaskingInstruction
from drain3.template_miner_config import TemplateMinerConfig

from pipeline import config

# [KNOB] Generic masks, applied before mining. Order matters (most specific first).
MASKS = [
    (r"[0-9a-fA-F]{8}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{4}-[0-9a-fA-F]{12}", "UUID"),
    (r"\b[A-Za-z]+(?:_[0-9A-Za-z]+){2,}\b", "ID"),                 # e.g. container_1445_0011_01_000002
    (r"\b\d{1,3}(?:\.\d{1,3}){3}(?::\d+)?\b", "IP"),                # 10.0.0.7 or 10.0.0.7:5432
    (r"\b[\w.-]+:\d{2,5}\b", "HOSTPORT"),                           # host:port
    (r"(?:/[\w.@-]+){2,}/?", "PATH"),                               # /a/b/c
    (r"\b0x[0-9a-fA-F]+\b|\b[0-9a-fA-F]{16,}\b", "HEX"),
    (r"(?<![A-Za-z])-?\d+(?:\.\d+)?", "NUM"),
]


def new_miner() -> TemplateMiner:
    cfg = TemplateMinerConfig()
    cfg.drain_sim_th = config.DRAIN_SIM_TH
    cfg.drain_depth = config.DRAIN_DEPTH
    cfg.masking_instructions = [MaskingInstruction(p, name) for p, name in MASKS]
    cfg.mask_prefix, cfg.mask_suffix = "<", ">"
    return TemplateMiner(config=cfg)


def assign(miner: TemplateMiner, records: list[dict]) -> None:
    """Adds `pattern_id` (str) to every record, in place. Online: unseen lines create new patterns."""
    for r in records:
        first_line = r["message"].split("\n", 1)[0]
        r["pattern_id"] = f"P{miner.add_log_message(first_line)['cluster_id']}"


def templates(miner: TemplateMiner) -> dict[str, str]:
    return {f"P{c.cluster_id}": c.get_template() for c in miner.drain.clusters}


def save(miner: TemplateMiner, path: Path) -> None:
    """Saves the Drain tree as JSON text (jsonpickle, the same format drain3 uses internally)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(jsonpickle.dumps(miner.drain, keys=True))


def load(path: Path) -> TemplateMiner:
    miner = new_miner()
    miner.drain = jsonpickle.loads(path.read_text(), keys=True)
    return miner


def dump_templates(miner: TemplateMiner, path: Path) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(templates(miner), indent=1))
