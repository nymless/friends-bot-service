#!/bin/bash
set -euo pipefail

: "${POSTGRES_USER:?POSTGRES_USER is required (set in .env.load)}"
: "${POSTGRES_PASSWORD:?POSTGRES_PASSWORD is required (set in .env.load)}"
: "${POSTGRES_DB:?POSTGRES_DB is required (set in .env.load)}"

# Single DB URL for alembic + app — always derived from POSTGRES_* (see .env.load).
export DB_URL="postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:5432/${POSTGRES_DB}"

/usr/local/bin/docker-entrypoint.sh postgres &
postgres_pid=$!

cleanup() {
    if [ -n "${postgres_pid:-}" ]; then
        kill -TERM "$postgres_pid" 2>/dev/null || true
        wait "$postgres_pid" 2>/dev/null || true
    fi
}
trap cleanup TERM INT

until pg_isready -U "${POSTGRES_USER}" -d "${POSTGRES_DB}" -q; do
    sleep 0.5
done

gosu appuser bash -c 'cd /app && /app/.venv/bin/alembic upgrade head'

if [ "${NGINX_ENABLED:-0}" = "1" ]; then
    rm -f /etc/nginx/sites-enabled/default
    nginx
fi

exec gosu appuser bash -c 'cd /app && /app/.venv/bin/python -m friends_bot_service.main'
