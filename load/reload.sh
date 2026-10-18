#!/usr/bin/env bash
# Full reload: drop + recreate tables, load every dataset, publish the index, ownership, patterns/bursts/episodes (after
# publish: they read logs), Jev judgments + traits, pattern vectors, table macros, roles, then verify against references.
# Datasets: the base corpus (BGL, OpenStack) always; extra Loghub sets (load/3*.sql) when their raw files exist
# (scripts/download_data.sh --all). Usage: ./load/reload.sh [--skip-checks]
set -euo pipefail
cd "$(dirname "$0")/.."
PSQL=(psql -h "${PGHOST:-localhost}" -p "${PGPORT:-7890}" -U "${PGUSER:-postgres}" -d "${PGDATABASE:-postgres}" -v ON_ERROR_STOP=1 -q)
run() { echo "== $1"; "${PSQL[@]}" -f "$1" | grep -E '^Time' | tail -1 || true; }
echo "== load/00_cleanup.py"; .venv/bin/python load/00_cleanup.py
run load/00_schema.sql
run load/10_bgl.sql
run load/20_openstack.sql
[ -f data/raw/zookeeper/Zookeeper.log ] && run load/30_zookeeper.sql
[ -f data/raw/apache/Apache.log ] && run load/31_apache.sql
[ -f data/raw/ssh/SSH.log ] && run load/32_ssh.sql
for f in load/90_publish.sql load/94_ownership.sql load/95_patterns_episodes.sql load/96_pattern_judgments.sql \
         load/97_pattern_vectors.sql load/98_macros.sql; do
  run "$f"
done
echo "== load/99_roles.py"; .venv/bin/python load/99_roles.py
[ "${1:-}" = "--skip-checks" ] && exit 0
.venv/bin/python bench/check_counts.py
.venv/bin/python bench/check_patterns.py
[ -f bench/check_tools.py ] && .venv/bin/python bench/check_tools.py
exit 0
