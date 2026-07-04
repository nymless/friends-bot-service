.PHONY: help install install_prod run run_api docker-build load-build load-up load-down load-down-v load-logs \
		load-seed load-restart load-k6-ramp load-k6-ramp-polling load-k6-run load-k6-run-polling \
		load-k6-run-contention load-k6-run-contention-polling monitoring-up monitoring-up-load monitoring-down deactivate_inactive_bots \
		test type lint format check clean hooks pre-commit db-init db-migrate db-upgrade db-downgrade db-history count

# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------

IMAGE ?= friends-bot-service:local
LOAD_IMAGE ?= friends-bot-vps-sim:local
APP_IMAGE ?= $(IMAGE)
COMPOSE_LOAD ?= compose.load.yml
LOAD_ENV_FILE ?= .env.load
K6_ENV_FILE ?= .env.k6
LOAD_COMPOSE = docker compose --env-file $(LOAD_ENV_FILE) -f $(COMPOSE_LOAD)
LOAD_NETWORK = friends-bot-service_default
LOAD_HTTP_PORT ?= 8080
LOAD_TELEGRAM_MOCK_PORT ?= 8081
K6_IMAGE ?= grafana/k6:latest
K6_ENV_FILES = --env-file "$(CURDIR)/$(LOAD_ENV_FILE)"
ifneq (,$(wildcard $(K6_ENV_FILE)))
K6_ENV_FILES += --env-file "$(CURDIR)/$(K6_ENV_FILE)"
endif
HOST ?= 127.0.0.1
PORT ?= 8000
METRICS_PORT ?= 8001
SCRAPE_INTERVAL ?= 15s
WEBHOOK_BIND_HOST = $(HOST)
WEBHOOK_BIND_PORT = $(PORT)
METRICS_BIND_HOST = $(HOST)
METRICS_BIND_PORT = $(METRICS_PORT)
export HOST
export PORT
export METRICS_PORT
export SCRAPE_INTERVAL
export LOAD_TELEGRAM_MOCK_PORT
export WEBHOOK_BIND_HOST
export WEBHOOK_BIND_PORT
export METRICS_BIND_HOST
export METRICS_BIND_PORT
MONITORING_COMPOSE = docker compose -f compose.monitoring.yml
K6_DOCKER = docker run --rm -i --network $(LOAD_NETWORK) -v "$(CURDIR)/load/k6:/scripts" $(K6_ENV_FILES) $(K6_IMAGE)

# ------------------------------------------------------------------------------
# Help
# ------------------------------------------------------------------------------

help: ## Show available commands
	@powershell -NoProfile -Command "Write-Host 'Usage: make <target>'; $$section=''; Get-Content '$(CURDIR)/Makefile' | ForEach-Object { if ($$_ -match '^##@ (.+)') { Write-Host ''; Write-Host $$Matches[1] } elseif ($$_ -match '^([a-zA-Z0-9_.-]+):.*## (.+)') { Write-Host ('  {0,-24} {1}' -f $$Matches[1], $$Matches[2]) } }"

# ------------------------------------------------------------------------------
# Docker
# ------------------------------------------------------------------------------

##@ Docker

docker-build: ## Build the production application image (override: IMAGE=name:tag)
	docker build -t $(IMAGE) .

# ------------------------------------------------------------------------------
# Load test
# ------------------------------------------------------------------------------

##@ Load test
#
#   .env.k6 changed → make load-k6*
#
#   Clean run (.env.load / code change):
#     make load-down-v load-up
#     wait until logs show app ready (webhook ~20s, polling ~60s for long-poll startup)
#     make load-seed load-restart

load-build: docker-build ## Rebuild app image + vps-sim wrapper
	docker build -f load/vps-sim/Dockerfile -t $(LOAD_IMAGE) --build-arg APP_IMAGE=$(APP_IMAGE) .

load-up: ## Start load stack from .env.load
	$(LOAD_COMPOSE) up -d --build

load-down: ## Stop load stack
	$(LOAD_COMPOSE) down

load-down-v: ## Stop stack and delete Postgres volume
	$(LOAD_COMPOSE) down -v

load-logs: ## Follow vps-sim logs
	$(LOAD_COMPOSE) logs -f vps-sim

load-seed: ## Seed bots from .env.load (run after load-up, when Postgres is ready)
	$(LOAD_COMPOSE) exec vps-sim gosu appuser bash -c "cd /app && PYTHONPATH=/app /app/.venv/bin/python -m load.seed_bots"

load-restart: ## Restart app after seed (reload bots from database)
	$(LOAD_COMPOSE) restart vps-sim

load-k6-ramp: ## Run k6 webhook ramp (LOAD_K6_COMMAND=/stats|/run|/loser)
	$(K6_DOCKER) run -e LOAD_BASE_URL=http://vps-sim:80 /scripts/webhook_ramp.js

load-k6-ramp-polling: ## Run k6 polling ramp (LOAD_K6_COMMAND=/stats|/run|/loser)
	$(K6_DOCKER) run -e LOAD_TELEGRAM_MOCK_URL=http://telegram-mock:8081 /scripts/polling_ramp.js

load-k6-run: ## Run k6 webhook happy-path /run (LOAD_SEED_DRAW_ENTRANTS=true)
	$(K6_DOCKER) run -e LOAD_BASE_URL=http://vps-sim:80 /scripts/webhook_run.js

load-k6-run-polling: ## Run k6 polling happy-path /run (LOAD_SEED_DRAW_ENTRANTS=true)
	$(K6_DOCKER) run -e LOAD_TELEGRAM_MOCK_URL=http://telegram-mock:8081 /scripts/polling_run.js

load-k6-run-contention: ## Run k6 webhook draw contention on one bot/chat
	$(K6_DOCKER) run -e LOAD_BASE_URL=http://vps-sim:80 /scripts/webhook_run_contention.js

load-k6-run-contention-polling: ## Run k6 polling draw contention on one bot/chat
	$(K6_DOCKER) run -e LOAD_TELEGRAM_MOCK_URL=http://telegram-mock:8081 /scripts/polling_run_contention.js

# ------------------------------------------------------------------------------
# Monitoring
# ------------------------------------------------------------------------------

##@ Monitoring

monitoring-up: ## Start Prometheus + Grafana (METRICS_PORT, SCRAPE_INTERVAL)
	$(MONITORING_COMPOSE) up -d

monitoring-up-load: ## Same as monitoring-up
	$(MONITORING_COMPOSE) up -d

monitoring-down: ## Stop Prometheus + Grafana
	$(MONITORING_COMPOSE) down

# ------------------------------------------------------------------------------
# Local development
# ------------------------------------------------------------------------------

##@ Local development

install: ## Install all dependencies (including dev)
	uv sync
	uv run pre-commit install

install_prod: ## Install production dependencies only
	uv sync --no-dev

hooks: ## Install git pre-commit hooks
	uv run pre-commit install

pre-commit: ## Run pre-commit on all files
	uv run pre-commit run --all-files

WORKERS ?= 1

run: ## Start the service using BOT_MODE (override: HOST=0.0.0.0 PORT=80 WORKERS=2)
	WEBHOOK_BIND_HOST=$(HOST) WEBHOOK_BIND_PORT=$(PORT) METRICS_BIND_HOST=$(HOST) METRICS_BIND_PORT=$(METRICS_PORT) WORKER_COUNT=$(WORKERS) uv run python -m friends_bot_service.main

run_api: ## Start the FastAPI app directly (override: PORT=80)
	WEBHOOK_BIND_HOST=$(HOST) WEBHOOK_BIND_PORT=$(PORT) uv run python -m friends_bot_service.main_api

deactivate_inactive_bots: ## Deactivate bots inactive for 60 days
	uv run python -m friends_bot_service.infra.scripts.deactivate_inactive_bots

# ------------------------------------------------------------------------------
# Quality
# ------------------------------------------------------------------------------

##@ Quality

test: ## Run tests
	uv run pytest

type: ## Run mypy type checks
	uv run mypy

lint: ## Check code style and errors with Ruff
	uv run ruff check

format: ## Format code and fix imports
	uv run ruff format
	uv run ruff check --fix

check: ## Run test, format, lint, and type sequentially
	$(MAKE) test && $(MAKE) format && $(MAKE) lint && $(MAKE) type

# ------------------------------------------------------------------------------
# Database
# ------------------------------------------------------------------------------

##@ Database

db-init: ## Initialize Alembic in the project
	uv run alembic init migrations

db-migrate: ## Create a new migration: `make db-migrate m="message"`
	uv run alembic revision --autogenerate -m "$(m)"

db-upgrade: ## Apply all migrations up to the latest
	uv run alembic upgrade head

db-downgrade: ## Roll back one migration
	uv run alembic downgrade -1

db-history: ## Show migration history
	uv run alembic history --indicate-current

# ------------------------------------------------------------------------------
# Utilities
# ------------------------------------------------------------------------------

##@ Utilities

count: ## Count lines of code
	uv run pygount --format=summary friends_bot_service

clean: ## Remove cache files and virtual environment
	rm -rf `find . -name __pycache__`
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf .venv
