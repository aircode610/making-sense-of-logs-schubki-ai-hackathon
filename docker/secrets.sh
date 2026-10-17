#!/usr/bin/env bash
# Register API keys in SereneDB so SQL can call AI functions. Secrets are NOT persisted across
# container restarts: re-run after every `docker compose up/restart`. Reads keys from ./.env.
#   typesafe -> ai_system_one (Jev)                         needs TYPESAFE_API_KEY
#   gemini   -> ai_embed / ai_generate / ai_agg (Gemini)    needs GOOGLE_API_KEY (optional)
set -euo pipefail
cd "$(dirname "$0")/.."
[ -f .env ] && set -a && . ./.env && set +a
: "${TYPESAFE_API_KEY:?TYPESAFE_API_KEY is not set (put it in .env)}"
PSQL=(psql -h "${PGHOST:-localhost}" -p "${PGPORT:-7890}" -U "${PGUSER:-postgres}" -d "${PGDATABASE:-postgres}" -q)
"${PSQL[@]}" -v ts_key="$TYPESAFE_API_KEY" >/dev/null <<'SQL'
DROP SECRET IF EXISTS typesafe;
CREATE SECRET typesafe (TYPE typesafe, api_key :'ts_key');
SET GLOBAL sdb_ai_system_one_default_secret = 'typesafe';
SQL
echo "typesafe secret registered (default for ai_system_one)"
if [ -n "${GOOGLE_API_KEY:-}" ]; then
  "${PSQL[@]}" -v g_key="$GOOGLE_API_KEY" -v g_model="${GEMINI_SQL_MODEL:-gemini-2.5-flash}" >/dev/null <<'SQL'
DROP SECRET IF EXISTS gemini;
CREATE SECRET gemini (TYPE openai, base_url 'https://generativelanguage.googleapis.com/v1beta/openai',
  chat_path '/chat/completions', embeddings_path '/embeddings', api_key :'g_key', model :'g_model');
SET GLOBAL sdb_ai_text_default_secret = 'gemini';
SET GLOBAL sdb_ai_embedding_default_secret = 'gemini';
SQL
  echo "gemini secret registered (default for ai_embed / ai_generate / ai_agg)"
fi
