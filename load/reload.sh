#!/usr/bin/env bash
# Full reload: drop + recreate the tables, load every dataset whose raw file is present (data/catalog.csv; base corpus
# BGL + OpenStack first; LOAD_OTEL=1 adds the remote OpenTelemetry slice), then build each dataset's patterns / bursts /
# ownership / stored Jev judgments / pattern index (load/lib/build_dataset.sql), macros, roles; then the checks.
# Plan 016: runs through the Python loader (no psql needed); to add ONE dataset without a reload, use
# `uv run python -m loader load <name|file>` or the MCP tool load_logs. Usage: ./load/reload.sh [--skip-checks] [names…]
set -euo pipefail
cd "$(dirname "$0")/.."
PY=(uv run --quiet python)
command -v uv >/dev/null || PY=(.venv/bin/python)
skip=0
if [ "${1:-}" = "--skip-checks" ]; then skip=1; shift; fi
"${PY[@]}" -m loader reload "$@"
[ "$skip" = 1 ] && exit 0
"${PY[@]}" bench/check_counts.py
"${PY[@]}" bench/check_patterns.py
LOGS_DATASET="*" "${PY[@]}" bench/check_tools.py
