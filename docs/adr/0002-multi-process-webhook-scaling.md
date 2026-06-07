# ADR 0002: Multi-process scaling (webhook-first exploration)

- **Status:** Proposed
- **Date:** 2026-06-07

## Context

The service runs as a **single Python process** today. The database is the source
of truth for registered bots, draw entrants, and statistics. An in-memory
**bot registry** (`BotManager._active_bots`) tracks which `Bot` instances are
active in the current process. Draw handlers serialize work per `(bot_id, chat_id)`
with an **in-process `asyncio.Lock`**; PostgreSQL unique constraints on
`(bot_id, chat_id, last_win|last_lose)` provide a partial safety net but do not
prevent duplicate winner announcements if two processes race through prepare.

### Runtime modes

- **Polling** — master bot and all game bots use long polling in one process.
  Telegram allows **one** active `getUpdates` connection per bot token. Scaling
  polling across multiple processes requires **bot sharding** (each bot owned by
  exactly one worker) plus coordination when the master adds or removes bots.
- **Webhook** — game bots receive updates over HTTPS; the master bot still polls
  in the same process as FastAPI today. Multiple HTTP workers can serve webhooks
  without sharding game bots, but **master polling must not be duplicated** across
  workers (same single-poller rule as any bot token).

Polling is useful for local development and temporary deployments without a public
HTTPS endpoint. Production scaling is expected to focus on **webhook mode**.

### Shared module `bot_admin`

`bot_admin` is a **domain / use-case layer** (ports + `RegisterBot`, `RemoveBot`,
`LoadActiveBots`, …), not a monolithic runtime:

| Consumer | Uses from `bot_admin` |
| -------- | --------------------- |
| `master_bot` | use cases + `BotRuntimePort` (`start_bot` / `stop_bot`) after persist |
| `draw` | `BotRepository` only (`TouchBotGameAttempt`) |
| `infra` | repository and `BotManager` implementations |

Master and game flows already use **separate aiogram dispatchers**
(`get_master_bot_dispatcher` vs `get_bot_dispatcher`). Splitting master and webhooks
across processes requires different **composition roots** and runtime port
implementations, not a fork of `bot_admin`.

### Deferred for now

- **Polling + N workers + bot sharding** — out of scope; polling stays single-process.
- **Two separate repositories** — out of scope for this exploration.

## Decision

**No final architecture is chosen yet.**

Compare three **end-to-end** spikes — each a complete, runnable webhook multi-process
setup:

| Branch | Master | Deploy |
| ------ | ------ | ------ |
| `spike/webhook-pool` | Webhook in the same worker pool as game bots | Single deploy |
| `spike/master-worker-zero` | Polling on worker #0 only; other workers HTTP only | Single deploy |
| `spike/split-entrypoints` | Separate process (second entry point, same repo) | Two processes |

After review, update this ADR to **Accepted** (or supersede with ADR 0003) with one
chosen approach.

## Consequences

- Polling sharding and multi-repo splits are explicitly deferred.
- `WORKER_COUNT` default and connection pool sizing to be fixed in the accepted ADR.

## Open questions for spikes to answer

- **webhook-pool:** Operational simplicity of one homogeneous pool; master private chat
  on the public webhook endpoint.
- **master-worker-zero:** Acceptability of a special worker #0 on deploy and failure.
- **split-entrypoints:** Whether master isolation justifies two processes in ops.

## When to revisit

- Spike review complete → **Accepted** or **Rejected**, or superseded by ADR 0003.
- Production requires polling-at-scale → new ADR for sharding.
