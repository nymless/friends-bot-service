#!/bin/bash
set -euo pipefail

export DB_URL="${DB_URL:-postgresql+asyncpg://${POSTGRES_USER}:${POSTGRES_PASSWORD}@127.0.0.1:5432/${POSTGRES_DB}}"

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
