.PHONY: install prod-install run test type lint format clean

install: ## Установить все зависимости (включая dev)
	uv sync

prod-install: ## Установить все зависимости (без dev)
	uv sync --no-dev

run: ## Запустить бота
	uv run python -m friends_bot.main

test: ## Запустить тесты
	uv run pytest

type: ## Проверить типизацию через mypy
	uv run mypy

lint: ## Проверить код на ошибки и стиль через Ruff
	uv run ruff check

format: ## Автоматически поправить стиль и импорты
	uv run ruff format
	uv run ruff check --fix

clean: ## Удалить временные файлы, кэш и окружение
	rm -rf `find . -name __pycache__`
	rm -rf .pytest_cache
	rm -rf .mypy_cache
	rm -rf .ruff_cache
	rm -rf .venv
