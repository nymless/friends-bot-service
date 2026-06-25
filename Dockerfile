# Production image: application only. PostgreSQL is provided externally (host, compose, or vps-sim wrapper).
FROM python:3.12-slim-bookworm

COPY --from=ghcr.io/astral-sh/uv:0.6.14 /uv /uvx /bin/

WORKDIR /app

ENV PYTHONUNBUFFERED=1 \
    PYTHONDONTWRITEBYTECODE=1 \
    UV_COMPILE_BYTECODE=1 \
    UV_LINK_MODE=copy \
    WEBHOOK_BIND_HOST=0.0.0.0 \
    WEBHOOK_BIND_PORT=8000

# Install dependencies before application code for better layer caching.
COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-dev --no-install-project

COPY alembic.ini ./
COPY alembic/ alembic/
COPY friends_bot_service/ friends_bot_service/
RUN uv sync --frozen --no-dev

RUN useradd --create-home --uid 10001 appuser \
    && chown -R appuser:appuser /app
USER appuser

EXPOSE 8000

CMD ["uv", "run", "python", "-m", "friends_bot_service.main"]
