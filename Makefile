.PHONY: help install install_prod run run_api docker-build load-build load-up load-down load-down-v load-logs \
		load-seed load-restart load-k6 monitoring-up monitoring-down deactivate_inactive_bots test type lint \
		format check clean hooks pre-commit db-init db-migrate db-upgrade db-downgrade db-history count

# ------------------------------------------------------------------------------
# Configuration
# ------------------------------------------------------------------------------

IMAGE ?= friends-bot-service:local
LOAD_IMAGE ?= friends-bot-vps-sim:local
APP_IMAGE ?= $(IMAGE)
COMPOSE_LOAD ?= compose.load.yml
LOAD_ENV_FILE ?= .env.load
LOAD_COMPOSE = docker compose --env-file $(LOAD_ENV_FILE) -f $(COMPOSE_LOAD)
LOAD_HTTP_PORT ?= 8080
HOST ?= 127.0.0.1
PORT ?= 8000

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

load-restart: ## Restart vps-sim after seeding so webhooks reload from DB
	$(LOAD_COMPOSE) restart vps-sim

load-k6: ## Run k6 stats webhook profile (k6 on PATH; reads .env.load)
	k6 run --env-file $(LOAD_ENV_FILE) -e LOAD_BASE_URL=http://localhost:$(LOAD_HTTP_PORT) load/k6/webhook_stats.js

# ------------------------------------------------------------------------------
# Monitoring
# ------------------------------------------------------------------------------

##@ Monitoring

monitoring-up: ## Start Prometheus + Grafana (override: PORT=80)
	SCRAPE_PORT=$(PORT) docker compose -f compose.monitoring.yml up -d

monitoring-down: ## Stop Prometheus + Grafana
	docker compose -f compose.monitoring.yml stop

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
	WEBHOOK_BIND_HOST=$(HOST) WEBHOOK_BIND_PORT=$(PORT) uv run python -m friends_bot_service.main

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
