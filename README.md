# Friends Bot Service

Русская версия: [README.ru.md](README.ru.md).

This repository contains a Telegram bot service for daily group draws such as
"User of the Day" and "Loser of the Day".

The core idea is simple: one private **master bot** acts as the backend for
multiple separate game bots. At the same time, each connected game bot remains
a full Telegram bot account with its own name, username, and avatar, all of
which can be changed independently by its owner. That is what makes this a
multi-bot service rather than a regular single bot.

The project was inspired by
[TheUserOfTheDayBot](https://github.com/DevDmitryN/TheUserOfTheDayBot), but the
idea here was reworked as a multi-bot service built on a modern Python stack.

## What It Does

- Runs daily draws in group chats.
- Stores players and draw statistics per bot and per chat.
- Lets the owner connect or disable game bots through a master bot.
- Keeps bot tokens encrypted in the database.
- Deletes bot token messages from the master bot chat after processing.
- Can sync the default command list for connected bots.
- Includes a maintenance script for disabling stale bots (`make deactivate_inactive_bots`).

## How It Is Structured

- **Game bots** work in groups and supergroups.
- **Master bot** works in private chat and handles service actions such as:
  - `/add_bot`
  - `/remove_bot`
  - `/set_default_commands`
- **Database** stores registered bots, draw entrants, and draw statistics.
- **Bot manager** starts and stops connected bots from the database.

## Project Layout

The codebase is split into feature modules. Each feature usually has `domain/`,
`interfaces/` (ports), `usecases/`, and `handlers/` (thin aiogram adapters).
Infrastructure lives under `infra/`.

```text
friends_bot_service/
  bot_admin/      registered bots: domain, ports, use cases
  draw/           daily draw flow and game-bot draw commands
  draw_entrant/   /reg, /delete, /list
  draw_stats/     /stats, /loserstats
  master_bot/     master-bot handlers and orchestration use cases
  infra/          bootstrap, SQLAlchemy repos, bot manager, FastAPI webhook, texts
```

Runtime wiring (dispatchers, `UnitOfWork`, polling/webhook bootstrap) is in
`infra/bootstrap/`. SQLAlchemy models and repositories implement the feature
ports. User-facing strings are in `infra/texts/`.

Database tables still use legacy names from the first schema: `players` for draw
entrants and `stats` for draw statistics. ORM models are named
`DrawEntrantORM` and `DrawStatsORM`. See
[ADR 0001](docs/adr/0001-legacy-database-table-names.md) for the rename plan.

Component diagram: [uml/friends-bot.drawio.png](uml/friends-bot.drawio.png).

## Stack

- Python 3.12+
- aiogram 3.x
- FastAPI
- SQLAlchemy asyncio
- PostgreSQL via asyncpg
- Alembic
- uv

Development tools used in the repository:

- pytest
- mypy
- ruff

## Configuration

Create a `.env` file in the project root:

```env
BOT_MODE=polling
WEBHOOK_BASE_URL=https://example.com
WEBHOOK_SECRET_TOKEN=your_webhook_secret_token
REGISTRATION_ENABLED=true
MASTER_TOKEN=your_master_bot_token
ENCRYPTION_KEY=your_fernet_key
DB_URL=postgresql+asyncpg://user:password@localhost:port/friends_bot_service
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_RECYCLE=3600
```

Notes:

- `MASTER_TOKEN` is the token of the private control bot.
- `WEBHOOK_BASE_URL` is required in webhook mode and should point to the public base URL of the service.
- `WEBHOOK_SECRET_TOKEN` is required in webhook mode and is used to verify that webhook requests really come from Telegram.
- `REGISTRATION_ENABLED=false` disables both `/reg` and `/add_bot`, including repeated registrations, until the service is restarted with the flag enabled again.
- `LOG_INBOUND_COMMANDS=true` logs inbound slash-commands before handlers (access log).
- `ENCRYPTION_KEY` should be a valid Fernet key.
- Connected game bots are added later through the master bot, not through `.env`.

## Installation

Using the included `Makefile`:

```bash
make install
```

Or directly with `uv`:

```bash
uv sync
```

Run database migrations before starting the service:

```bash
uv run alembic upgrade head
```

## Running

Main launcher:

```bash
make run
```

`make run` starts the service according to `BOT_MODE`:

- `polling` — long polling for the master bot and all connected game bots
- `webhook` — FastAPI app for game-bot updates; the master bot still polls

The repository also includes a direct FastAPI entry point (webhook mode only):

```bash
make run_api
```

Webhook mode usually requires additional server setup outside this repository,
such as a public HTTPS endpoint, TLS/SSL, and often a reverse proxy like Nginx.

## Workflow

1. Start the service.
2. Open the master bot in a private chat.
3. Send `/add_bot <token>` (token from @BotFather) as one message.
4. Add the connected game bot to a group.
5. Use the game commands in that group.

When a token is sent to the master bot, the service deletes that message from
the chat after processing it.

## Game Commands

These commands are available in connected game bots:

- `/reg` — join the game
- `/delete` — leave the game while keeping history
- `/list` — show registered draw entrants in this chat
- `/run` — run the winner draw
- `/loser` — run the loser draw
- `/stats` — show winner statistics
- `/loserstats` — show loser statistics

## Master Bot Commands

- `/add_bot <token>` — register or reactivate a bot
- `/remove_bot <token>` — disable a bot in the service
- `/set_default_commands` — sync the default command list for connected bots

## Privacy and Security

- Bot tokens in the database are encrypted (Fernet, `ENCRYPTION_KEY`).
- After `/add_bot` or `/remove_bot`, the token message is deleted from the master
  chat when Telegram allows it.
- Optional `LOG_INBOUND_COMMANDS=true` enables inbound access logs for slash-commands
  only; `/add_bot` and `/remove_bot` log the command name only.
- Webhook mode validates `X-Telegram-Bot-Api-Secret-Token` against
  `WEBHOOK_SECRET_TOKEN`.
- The database still stores Telegram user/chat ids, display names, and per-chat game
  stats — protect `.env`, DB, and logs accordingly.

## Development

```bash
make test      # pytest (handlers, repositories, use cases, infra)
make type      # mypy
make lint      # ruff check
make format    # ruff format + ruff check --fix
make check     # test, format, lint, type
make hooks     # install git pre-commit hooks (also runs on make install)
make pre-commit  # run pre-commit on all files
```

## Observability

Webhook mode exposes Prometheus metrics at `GET /metrics` (see ADR 0004).

Key series:

- `friends_bot_webhook_request_duration_seconds` — HTTP latency by status
- `friends_bot_handler_duration_seconds` — handler time by slash-command
- `friends_bot_draw_completed_total` / `friends_bot_draw_rejected_total` — draw outcomes
- `friends_bot_db_errors_total` — database unavailable events

Local Prometheus and Grafana (scrape `host.docker.internal:8000` while the app runs on
the host):

```bash
docker compose -f compose.monitoring.yml up
```

Open Grafana at http://localhost:3000 (default login `admin` / `admin`), add panels
for the metrics above, or import a dashboard later.

Handler metrics also apply in polling mode; `/metrics` is available when the FastAPI
webhook app is running.

## Notes

- The service uses an in-memory lock and database constraints to reduce duplicate
  draws for the same bot/chat/day.
- Registered bots are loaded from the database on startup.
- Bot inactivity cleanup is based on `last_game_attempt_at`, or `created_at` if the
  bot has never been used. Run `make deactivate_inactive_bots` to deactivate bots
  inactive for 60 days.
