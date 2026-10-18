#!/usr/bin/env bash
# Full reload: drop + recreate tables, load every dataset, publish the index, ownership, patterns/bursts/episodes (after
# publish: they read logs), Jev judgments + traits, pattern vectors, table macros, roles, then verify against references.
# Datasets: the base corpus (BGL, OpenStack) always; extra Loghub sets (load/3*.sql, load/4*.sql) when their raw files
# exist (scripts/download_data.sh --all linux healthapp). Usage: ./load/reload.sh [--skip-checks]
set -euo pipefail
cd "$(dirname "$0")/.."
PSQL=(psql -h "${PGHOST:-localhost}" -p "${PGPORT:-7890}" -U "${PGUSER:-postgres}" -d "${PGDATABASE:-postgres}" -v ON_ERROR_STOP=1 -q)
run() {  # stop on the first SQL error (psql's own exit status, not the grep's)
  echo "== $1"; local out; out=$("${PSQL[@]}" -f "$1" 2>&1) || { echo "$out" | tail -20; echo "FAILED: $1"; exit 1; }
  echo "$out" | grep -E '^Time' | tail -1 || true
}
echo "== load/00_cleanup.py"; .venv/bin/python load/00_cleanup.py
run load/00_schema.sql
run load/10_bgl.sql
run load/20_openstack.sql
# Extra datasets (plan 012: generic): every load/3*.sql / 4*.sql whose first line `-- requires: <file>` exists
# (or `-- requires: env NAME=1` is set, e.g. LOAD_OTEL=1 for the remote OTel slice). A new dataset = one more file.
for f in load/3*.sql load/4*.sql; do
  req=$(head -1 "$f" | sed -n 's/^-- requires: //p')
  if [[ "$req" == env\ * ]]; then kv=${req#env }; name=${kv%%=*}; [ "${!name:-0}" = "${kv#*=}" ] || continue
  elif [ -n "$req" ] && [ ! -f "$req" ]; then continue; fi
  run "$f"
done
for f in load/90_publish.sql load/93_examples.sql load/94_ownership.sql load/95_patterns_episodes.sql load/96_pattern_judgments.sql load/96b_ownership_inferred.sql \
         load/97_pattern_vectors.sql load/98_macros.sql; do
  run "$f"
done
echo "== load/99_roles.py"; .venv/bin/python load/99_roles.py
[ "${1:-}" = "--skip-checks" ] && exit 0
.venv/bin/python bench/check_counts.py
.venv/bin/python bench/check_patterns.py
[ -f bench/check_tools.py ] && .venv/bin/python bench/check_tools.py
exit 0
