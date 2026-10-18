#!/usr/bin/env bash
# Regenerate Jev pattern judgments (plan 006) → data/pattern_judgments_<dataset>.csv (committed; reload.sh loads it).
# Needs the TypeSafe key in .env and the secret registered (./docker/secrets.sh). Usage: scripts/judge_patterns.sh [bgl]
set -euo pipefail
cd "$(dirname "$0")/../.."
ds="${1:-bgl}"
PSQL=(psql -h "${PGHOST:-localhost}" -p "${PGPORT:-7890}" -U "${PGUSER:-postgres}" -d "${PGDATABASE:-postgres}" -X -q -v ON_ERROR_STOP=1)
out="data/jev/pattern_judgments_${ds}.csv"
time "${PSQL[@]}" -v ai_cap="${AI_CAP:-5000}" -v where="p.dataset = '${ds}'" -f src/scripts/judge_patterns.sql > "$out.tmp"
mv "$out.tmp" "$out"
echo "$(($(wc -l < "$out") - 1)) judgments → $out"
