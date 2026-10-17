#!/usr/bin/env bash
# Full reload: drop + recreate tables, load both datasets, publish the index, build patterns/bursts/episodes (after
# publish: they read logs), verify counts against the awk/grep references.
set -euo pipefail
cd "$(dirname "$0")/.."
PSQL=(psql -h "${PGHOST:-localhost}" -p "${PGPORT:-7890}" -U "${PGUSER:-postgres}" -d "${PGDATABASE:-postgres}" -v ON_ERROR_STOP=1 -q)
for f in load/00_schema.sql load/10_bgl.sql load/20_openstack.sql load/90_publish.sql load/95_patterns_episodes.sql; do
  echo "== $f"; "${PSQL[@]}" -f "$f" | grep -E '^Time' || true
done
.venv/bin/python bench/check_counts.py
