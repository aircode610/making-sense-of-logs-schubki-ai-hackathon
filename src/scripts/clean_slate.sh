#!/usr/bin/env bash
# Start from zero for a clean demo: an EMPTY SereneDB and no local run state of this project.
# Removes: the serenedb container, this project's data volume (all loaded datasets), runs/ (session reports, agent runs),
# downloaded logs in data/raw/ (only with --raw), generated loaders in src/sql/gen/.
# Keeps: your .env, the code, docker images. Other projects' volumes are not touched.
#   src/scripts/clean_slate.sh           # empty database, keep downloaded logs (faster re-load)
#   src/scripts/clean_slate.sh --raw     # also delete downloaded logs (re-download from Zenodo)
set -euo pipefail
cd "$(dirname "$0")/../.."
project="$(basename "$PWD")"          # docker compose project name = folder name (two clones with the same folder
                                      # name share one volume: that is why a fresh clone can see old data)
echo "stopping SereneDB and deleting its data volume (project: $project)"
docker compose down -v --remove-orphans 2>/dev/null || true
docker rm -f "${SERENEDB_CONTAINER:-serenedb}" >/dev/null 2>&1 || true   # a container with this name from another clone
docker volume rm "${project}_serenedb-data" >/dev/null 2>&1 || true
rm -rf runs/sessions runs/agent runs/cc_ab src/sql/gen
[ "${1:-}" = "--raw" ] && rm -rf data/raw && echo "deleted data/raw/ (logs will be downloaded again)"
docker compose up -d
for _ in $(seq 1 60); do
  docker exec "${SERENEDB_CONTAINER:-serenedb}" true 2>/dev/null && \
    (command -v psql >/dev/null && psql -h localhost -p "${SERENEDB_PORT:-7890}" -U postgres -d postgres -Atc "select 1" >/dev/null 2>&1 \
     || uv run --quiet python -c "import psycopg; psycopg.connect(host='localhost', port=${SERENEDB_PORT:-7890}, user='postgres', dbname='postgres').close()" 2>/dev/null) && break
  sleep 2
done
echo "clean: empty SereneDB on localhost:${SERENEDB_PORT:-7890}. Next: claude  →  \"Load the base corpus\""
