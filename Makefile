.PHONY: help install install_prod run run_api docker-build load-build load-up load-down load-down-v load-logs monitoring-up monitoring-down deactivate_inactive_bots test type lint format check clean \
		hooks pre-commit db-init db-migrate db-upgrade db-downgrade db-history count

IMAGE ?= friends-bot-service:local
LOAD_IMAGE ?= friends-bot-vps-sim:local
APP_IMAGE ?= $(IMAGE)
COMPOSE_LOAD ?= compose.load.yml

docker-build: ## Build the production application image (override: make docker-build IMAGE=name:tag)
	docker build -t $(IMAGE) .

load-build: docker-build ## Build vps-sim image (override: make load-build IMAGE=tag APP_IMAGE=tag)
	docker build -f docker/Dockerfile.vps-sim -t $(LOAD_IMAGE) --build-arg APP_IMAGE=$(APP_IMAGE) .

load-up: ## Start vps-sim (copy .env.load.example to .env.load first)
	docker compose -f $(COMPOSE_LOAD) up -d --build

load-down: ## Stop vps-sim and remove the container
	docker compose -f $(COMPOSE_LOAD) down

load-down-v: ## Stop vps-sim and delete Postgres volume (required when switching main/workers)
	docker compose -f $(COMPOSE_LOAD) down -v

load-logs: ## Follow vps-sim logs
	docker compose -f $(COMPOSE_LOAD) logs -f vps-sim

help: ## Show available commands
	@awk 'BEGIN {FS = ": ## "}; /^[a-zA-Z0-9_-]+: ## / {printf "%-28s %s\n", $$1, $$2}' $(MAKEFILE_LIST)

install: ## Install all dependencies (including dev)
	uv sync
	uv run pre-commit install

hooks: ## Install git pre-commit hooks
	uv run pre-commit install

pre-commit: ## Run pre-commit on all files
	uv run pre-commit run --all-files

install_prod: ## Install production dependencies only
	uv sync --no-dev

HOST ?= 127.0.0.1
PORT ?= 8000

run: ## Start the service using BOT_MODE (override: make run HOST=0.0.0.0 PORT=80)
	WEBHOOK_BIND_HOST=$(HOST) WEBHOOK_BIND_PORT=$(PORT) uv run python -m friends_bot_service.main

run_api: ## Start the FastAPI app directly (override: make run_api PORT=80)
	WEBHOOK_BIND_HOST=$(HOST) WEBHOOK_BIND_PORT=$(PORT) uv run python -m friends_bot_service.main_api

monitoring-up: ## Start Prometheus + Grafana (override: make monitoring-up PORT=80)
	SCRAPE_PORT=$(PORT) docker compose -f compose.monitoring.yml up -d

monitoring-down: ## Stop Prometheus + Grafana
	docker compose -f compose.monitoring.yml stop

deactivate_inactive_bots: ## Deactivate bots inactive for 60 days
	uv run python -m friends_bot_service.infra.scripts.deactivate_inactive_bots

test: ## Run tests
	uv run pytest

check: ## Run test, format, lint, and type sequentially
	$(MAKE) test && $(MAKE) format && $(MAKE) lint && $(MAKE) type

type: ## Run mypy type checks
	uv run mypy

lint: ## Check code style and errors with Ruff
	uv run ruff check

format: ## Format code and fix imports
	uv run ruff format
	uv run ruff check --fix

clean: ## Remove cache files and virtual environment
	rm -rf `find . -name __pycache__`
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf .venv

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

count: ## Count lines of code
	uv run pygount --format=summary friends_bot_service
