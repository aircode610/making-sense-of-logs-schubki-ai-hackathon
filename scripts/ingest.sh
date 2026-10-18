#!/usr/bin/env bash
# One command for an unseen log file (plan 057 part 3): detect the format and write load/gen/<name>.sql
# (scripts/ingest.py), load everything, run the Jev judgments / areas / embeddings for the new dataset (skipped
# without keys: tools still work, problem detection then relies on log levels), reload with all checks, print the report.
#   scripts/ingest.sh data/raw/<dir>/<file>.log <name> [--year 2017] [--title "…"] [--min-coverage 0.95]
set -euo pipefail
cd "$(dirname "$0")/.."
file=$1; name=$2; shift 2
.venv/bin/python scripts/ingest.py "$file" "$name" "$@"
./docker/secrets.sh >/dev/null 2>&1 || echo "no AI keys registered: Jev judgments / embeddings will be skipped"
./load/reload.sh --skip-checks
# Jev call cap: the default 5000 is per query; a large new dataset needs one call per pattern
export AI_CAP=$(( $(psql -h "${PGHOST:-localhost}" -p "${PGPORT:-7890}" -U "${PGUSER:-postgres}" -d "${PGDATABASE:-postgres}" -X -At \
  -c "SELECT count(*) FROM patterns WHERE dataset = '$name'") + 100 ))
scripts/judge_patterns.sh "$name" || echo "Jev pattern judgments skipped"
.venv/bin/python scripts/judge_traits.py "$name" || echo "Jev traits skipped"
.venv/bin/python scripts/judge_areas.py "$name" || echo "Jev areas skipped"
.venv/bin/python scripts/embed_patterns.py "$name" || echo "embeddings skipped"
./load/reload.sh
psql -h "${PGHOST:-localhost}" -p "${PGPORT:-7890}" -U "${PGUSER:-postgres}" -d "${PGDATABASE:-postgres}" -X -c "
SELECT r.dataset, r.format, round(r.sample_matched::DOUBLE / r.sample_lines, 4) AS sample_coverage,
       (SELECT count(*) FROM logs l WHERE l.dataset = r.dataset) AS lines_loaded,
       (SELECT count(*) FROM ingest_unparsed u WHERE u.dataset = r.dataset) AS lines_unmatched,
       (SELECT count(*) FROM patterns p WHERE p.dataset = r.dataset) AS patterns, r.ts_format, r.year_assumed
FROM ingest_runs r WHERE r.dataset = '$name'"
echo "raw lines: $(wc -l < "$file")"
