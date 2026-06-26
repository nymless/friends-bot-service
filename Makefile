.PHONY: help install install_prod run run_api docker-build load-build load-up load-down load-down-v load-logs \
		load-seed load-restart load-k6 load-k6-polling load-k6-run load-k6-run-polling \
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
LOAD_COMPOSE = docker compose --env-file $(LOAD_ENV_FILE) -f $(COMPOSE_LOAD)
LOAD_NETWORK = friends-bot-service_default
LOAD_HTTP_PORT ?= 8080
LOAD_TELEGRAM_MOCK_PORT ?= 8081
K6_IMAGE ?= grafana/k6:latest
HOST ?= 127.0.0.1
PORT ?= 8000
METRICS_PORT ?= 8001
WEBHOOK_BIND_HOST = $(HOST)
WEBHOOK_BIND_PORT = $(PORT)
METRICS_BIND_HOST = $(HOST)
METRICS_BIND_PORT = $(METRICS_PORT)
export HOST
export PORT
export METRICS_PORT
export LOAD_TELEGRAM_MOCK_PORT
export WEBHOOK_BIND_HOST
export WEBHOOK_BIND_PORT
export METRICS_BIND_HOST
export METRICS_BIND_PORT
MONITORING_COMPOSE = docker compose -f compose.monitoring.yml
K6_DOCKER = docker run --rm -i --network $(LOAD_NETWORK) -v "$(CURDIR)/load/k6:/scripts" --env-file "$(CURDIR)/$(LOAD_ENV_FILE)" $(K6_IMAGE)

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

load-build: docker-build ## Build vps-sim image (override: LOAD_IMAGE=tag APP_IMAGE=tag)
	docker build -f load/vps-sim/Dockerfile -t $(LOAD_IMAGE) --build-arg APP_IMAGE=$(APP_IMAGE) .

load-up: ## Start vps-sim (copy .env.load.example to .env.load first)
	$(LOAD_COMPOSE) up -d --build

load-down: ## Stop vps-sim and remove containers
	$(LOAD_COMPOSE) down

load-down-v: ## Stop vps-sim and delete Postgres volume (required when POSTGRES_* changes)
	$(LOAD_COMPOSE) down -v

load-logs: ## Follow vps-sim logs
	$(LOAD_COMPOSE) logs -f vps-sim

load-seed: ## Insert synthetic bots (LOAD_* required in .env.load)
	$(LOAD_COMPOSE) exec vps-sim gosu appuser bash -c "cd /app && PYTHONPATH=/app /app/.venv/bin/python -m load.seed_bots"

load-restart: ## Restart vps-sim after seeding so bots reload from DB
	$(LOAD_COMPOSE) restart vps-sim

load-k6: ## Run k6 webhook /stats profile in Docker (BOT_MODE=webhook)
	$(K6_DOCKER) run -e LOAD_BASE_URL=http://vps-sim:80 /scripts/webhook_stats.js

load-k6-polling: ## Run k6 polling /stats profile in Docker (BOT_MODE=polling)
	$(K6_DOCKER) run -e LOAD_TELEGRAM_MOCK_URL=http://telegram-mock:8081 /scripts/polling_stats.js

load-k6-run: ## Run k6 webhook happy-path draw (LOAD_SEED_DRAW_ENTRANTS=true, BOT_MODE=webhook)
	$(K6_DOCKER) run -e LOAD_BASE_URL=http://vps-sim:80 /scripts/webhook_run.js

load-k6-run-polling: ## Run k6 polling happy-path draw (LOAD_SEED_DRAW_ENTRANTS=true, BOT_MODE=polling)
	$(K6_DOCKER) run -e LOAD_TELEGRAM_MOCK_URL=http://telegram-mock:8081 /scripts/polling_run.js

load-k6-run-contention: ## Run k6 webhook draw contention on one bot/chat
	$(K6_DOCKER) run -e LOAD_BASE_URL=http://vps-sim:80 /scripts/webhook_run_contention.js

load-k6-run-contention-polling: ## Run k6 polling draw contention on one bot/chat
	$(K6_DOCKER) run -e LOAD_TELEGRAM_MOCK_URL=http://telegram-mock:8081 /scripts/polling_run_contention.js

# ------------------------------------------------------------------------------
# Monitoring
# ------------------------------------------------------------------------------

##@ Monitoring

monitoring-up: ## Start Prometheus + Grafana (override: METRICS_PORT=8001 — matches metrics bind)
	$(MONITORING_COMPOSE) up -d

monitoring-up-load: ## Same as monitoring-up (METRICS_PORT from Makefile)
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

run: ## Start the service using BOT_MODE (override: HOST=0.0.0.0 PORT=80)
	uv run python -m friends_bot_service.main

run_api: ## Start the FastAPI app directly (override: PORT=80)
	uv run python -m friends_bot_service.main_api

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
