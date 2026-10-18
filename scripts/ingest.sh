#!/usr/bin/env bash
# One command for an unseen log file (plan 057 part 3, Konark; since plan 016 a wrapper around the loader, the same code
# as the MCP tool load_logs): detect the format from the lnav definitions (loader/detect.py), load ONLY this dataset,
# run the Jev judgments / areas / embeddings inside SereneDB when keys are set (else problem tools use log levels).
# A file under data/ also gets a committed loader load/gen/<name>.sql (re-run by every full reload).
#   scripts/ingest.sh <file> <name> [--year 2017]
set -euo pipefail
cd "$(dirname "$0")/.."
file=$1; name=$2; shift 2
uv run --quiet python -m loader load "$file" --name "$name" "$@"
