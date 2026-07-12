# Friends Bot Service

Русская версия: [README.ru.md](README.ru.md).

This repository contains a Telegram bot service for daily group draws such as
"User of the Day" and "Loser of the Day".

The core idea is simple: one private **master bot** acts as the backend for
multiple separate draw bots. At the same time, each connected draw bot remains
a full Telegram bot account with its own name, username, and avatar, all of
which can be changed independently by its owner. That is what makes this a
multi-bot service rather than a regular single bot.

The project was inspired by
[TheUserOfTheDayBot](https://github.com/DevDmitryN/TheUserOfTheDayBot), but the
idea here was reworked as a multi-bot service built on a modern Python stack.

## What It Does

- Runs daily draws in group chats.
- Stores draw entrants and draw statistics per bot and per chat.
- Lets the owner connect or disable draw bots through a master bot.
- Keeps bot tokens encrypted in the database.
- Deletes bot token messages from the master bot chat after processing.
- Can sync the default command list for connected bots.
- Includes a maintenance script for disabling stale bots (`make deactivate_inactive_bots`).

## How It Is Structured

- **Draw bots** work in groups and supergroups.
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
  draw/           daily draw flow and draw-bot draw commands
  draw_entrant/   /reg, /delete, /list
  draw_stats/     /stats, /loserstats
  master_bot/     master-bot handlers and orchestration use cases
  infra/          bootstrap, SQLAlchemy repos, bot manager, FastAPI webhook, texts
```

Runtime wiring (dispatchers, `UnitOfWork`, polling/webhook bootstrap) is in
`infra/bootstrap/`. SQLAlchemy models and repositories implement the feature
ports. User-facing strings are in `infra/texts/`.

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
WORKER_COUNT=1
DB_URL=postgresql+asyncpg://user:password@localhost:port/friends_bot_service
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_RECYCLE=3600
WEBHOOK_BASE_URL=https://example.com
WEBHOOK_SECRET_TOKEN=your_webhook_secret_token
MASTER_TOKEN=your_master_bot_token
ENCRYPTION_KEY=your_fernet_key
REGISTRATION_ENABLED=true
LOG_INBOUND_COMMANDS=false
```

Notes:

- `WORKER_COUNT` — number of uvicorn workers in webhook mode (default `1`). Each
  worker is a separate process with its own SQLAlchemy pool; see
  [Database connection budget](#database-connection-budget). With `WORKER_COUNT > 1`,
  metrics on `METRICS_BIND_PORT` aggregate all workers via `prometheus_client`
  multiprocess mode (mmap files in `.prometheus_multiproc/`).
- `METRICS_BIND_HOST` / `METRICS_BIND_PORT` — dedicated Prometheus scrape endpoint
  (default `127.0.0.1:8001`) in both polling and webhook modes; see
  [ADR 0005](docs/adr/0005-unified-metrics-http-export.md).
- `MASTER_TOKEN` is the token of the private control bot.
- `WEBHOOK_BASE_URL` is required in webhook mode and should point to the public base URL of the service.
- `WEBHOOK_SECRET_TOKEN` is required in webhook mode and is used to verify that webhook requests really come from Telegram.
- `ENCRYPTION_KEY` should be a valid Fernet key.
- Connected draw bots are added later through the master bot, not through `.env`.
- `REGISTRATION_ENABLED=false` disables both `/reg` and `/add_bot`, including repeated registrations, until the service is restarted with the flag enabled again.
- `LOG_INBOUND_COMMANDS=true` logs inbound slash-commands before handlers (access log).

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

- `polling` — long polling for the master bot and all connected draw bots
- `webhook` — FastAPI app for draw-bot and master-bot updates; `WORKER_COUNT` sets
  the number of uvicorn workers. The ASGI app is exported from
  [`friends_bot_service/asgi.py`](friends_bot_service/asgi.py) so each worker can
  load it; always start via `make run` (not by importing `asgi` directly).

Webhook mode usually requires additional server setup outside this repository,
such as a public HTTPS endpoint, TLS/SSL, and often a reverse proxy like Nginx.

## Workflow

1. Start the service.
2. Open the master bot in a private chat.
3. Send `/add_bot <token>` (token from @BotFather) as one message.
4. Add the connected draw bot to a group.
5. Use the draw commands in that group.

When a token is sent to the master bot, the service deletes that message from
the chat after processing it.

## Draw Commands

These commands are available in connected draw bots:

- `/reg` — join the draw
- `/delete` — leave the draw while keeping history
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
- The database still stores Telegram user/chat ids, display names, and per-chat draw
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

Prometheus metrics (see [ADR 0004](docs/adr/0004-production-observability.md) for
what to measure and [ADR 0005](docs/adr/0005-unified-metrics-http-export.md) for
how they are exported):

- **Both modes:** `GET /metrics` on `METRICS_BIND_HOST`:`METRICS_BIND_PORT`
  (default `127.0.0.1:8001`), separate from the webhook HTTP port.
- **Webhook with `WORKER_COUNT > 1`:** one metrics endpoint aggregates all uvicorn
  workers via `prometheus_client` multiprocess mode.

Key series:

- `friends_bot_webhook_request_duration_seconds` — HTTP latency by status
- `friends_bot_handler_duration_seconds` — request handler time by slash-command (except `/run`, `/loser`)
- `friends_bot_draw_handler_duration_seconds` — `/run` and `/loser` handler time (dense buckets around ~10s suspense)
- `friends_bot_draw_completed_total` / `friends_bot_draw_rejected_total` — draw outcomes
- `friends_bot_db_errors_total` — database unavailable events

Local Prometheus and Grafana scrape `host.docker.internal` while the app runs on
the host (`make monitoring-up`, default `METRICS_PORT=8001`):

```bash
make monitoring-up
```

Open Grafana at <http://localhost:3000> (default login `admin` / `admin`), add panels
for the metrics above, or import a dashboard later.

Handler metrics apply in both modes; webhook HTTP metrics only in webhook mode.
Metrics are not exposed on the public webhook URL or through nginx.

## Database connection budget

Each running process creates its own SQLAlchemy pool. In webhook mode with
`WORKER_COUNT > 1`, uvicorn forks one process per worker.

```text
total_max_connections ≈ workers × (DB_POOL_SIZE + DB_MAX_OVERFLOW)
```

- **Polling:** `workers = 1`.
- **Webhook:** `workers = WORKER_COUNT`.

Example: `WORKER_COUNT=2`, `DB_POOL_SIZE=3`, `DB_MAX_OVERFLOW=2` → at most **10**
connections from the service. Leave headroom under PostgreSQL `max_connections`
for migrations, `deactivate_inactive_bots`, and admin tools.

On startup the service logs `database connection budget` with the computed total.

## Notes

- Duplicate draws for the same bot/chat/day are prevented by `chat_draw_claims`
  and database constraints.
- Registered bots are loaded from the database on startup.
- `make deactivate_inactive_bots` marks bots inactive in the database after 60
  days without use (`last_draw_attempt_at`, or `created_at` if never used). It
  does not stop the running service or change Telegram webhooks. **Restart the
  service after the script** so runtime state matches the database (same in
  webhook and polling modes).
