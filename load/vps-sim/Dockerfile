# Load-test / VPS simulation: PostgreSQL + optional nginx + app in one cgroup.
# The application image stays DB- and nginx-free; only this wrapper adds them.
ARG APP_IMAGE=friends-bot-service:local
FROM ${APP_IMAGE} AS app

FROM postgres:16-bookworm

RUN apt update \
    && apt install -y --no-install-recommends nginx \
    && rm -rf /var/lib/apt/lists/* /etc/nginx/sites-enabled/default \
    && useradd --create-home --uid 10001 appuser 2>/dev/null || true

COPY --from=app /usr/local /usr/local
COPY --from=app /bin/uv /bin/uvx /bin/
COPY --from=app --chown=appuser:appuser /app /app

ENV PATH="/usr/local/bin:/app/.venv/bin:${PATH}"

COPY load/vps-sim/nginx.conf /etc/nginx/conf.d/default.conf
COPY load/vps-sim/entrypoint.sh /usr/local/bin/vps-sim-entrypoint.sh
RUN chmod +x /usr/local/bin/vps-sim-entrypoint.sh

ENV NGINX_ENABLED=0 \
    PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    WEBHOOK_BIND_HOST=0.0.0.0 \
    WEBHOOK_BIND_PORT=8000

EXPOSE 80 8000

ENTRYPOINT ["vps-sim-entrypoint.sh"]
