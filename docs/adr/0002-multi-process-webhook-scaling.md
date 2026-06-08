# ADR 0002: Multi-process scaling (webhook-first)

- **Status:** Accepted
- **Date:** 2026-06-07
- **Implemented:** 2026-06-08 (`spike/webhook-pool` → merge to `feature/workers`)

## Context

The service originally ran as a **single Python process** with an in-memory bot
registry (`BotManager._active_bots`) and in-process `asyncio.Lock` for draw
serialization. That model does not survive multiple webhook workers: each process
has its own memory, so bot lookup and draw races must be coordinated via the
database.

### Runtime modes

- **Polling** — master bot and all draw bots use long polling in one process.
  Telegram allows **one** active `getUpdates` connection per bot token. Scaling
  polling across multiple processes requires **bot sharding** (out of scope).
- **Webhook** — draw bots receive updates over HTTPS. Multiple HTTP workers can
  serve draw-bot webhooks without sharding. The master bot must not have
  duplicated polling or conflicting delivery mode across workers.

Polling remains useful for local development. Production multi-process scaling
uses **webhook mode**.

### Shared module `bot_admin`

`bot_admin` is a domain / use-case layer (ports + `RegisterBot`, `RemoveBot`,
`LoadActiveBots`, …), not a monolithic runtime. Master and draw flows use
separate aiogram dispatchers. Multi-process wiring changes **composition roots**
and runtime port implementations in `infra`, not `bot_admin`.

### Spike exploration (2026-06)

Three end-to-end webhook multi-process topologies were compared. All spikes that
scale draw webhooks beyond one process share the same **correctness baseline**
from `spike/webhook-pool`:

- resolve active draw bots from the database per webhook request (no in-process
  registry);
- `chat_draw_claims` for draw concurrency across workers.

Only **master placement** and **deploy shape** differed between spikes.

| Branch | Master | Deploy | Outcome |
| ------ | ------ | ------ | ------- |
| `spike/webhook-pool` | Webhook in the same worker pool as draw bots | Single deploy | **Accepted** |
| `spike/master-worker-zero` | Polling on worker #0 only; other workers HTTP only | Single deploy | Explored; **not for production** |
| `spike/split-entrypoints` | Separate process (second entry point) | Two processes | **Not implemented** |

**Spike 2 (`master-worker-zero`):** feasible — master is more isolated from the
public webhook ingress and does not share the draw webhook URL. Runtime wiring is
noticeably more complex (process supervisor, `APP_WORKER_INDEX`, special worker
#0 lifecycle, master-down if worker #0 fails). Isolation benefit did not justify
ops complexity for expected traffic; branch kept for reference, not production.

**Spike 3 (`split-entrypoints`):** not built. Would add a second deploy unit and
operational surface for blast-radius separation under load or DDoS. Neither is a
realistic concern for this service at current scale; existing webhook secret
validation and token handling are sufficient for the threat model.

Load testing assumptions and methodology are in **ADR 0003** (not a blocker for
this decision).

## Decision

**Adopt `webhook-pool` (spike 1):** one deploy, homogeneous uvicorn worker pool,
master bot on webhook alongside draw bots, DB-first bot resolution, and
`chat_draw_claims` for draw races.

- `WORKER_COUNT` defaults to `1`; increase when profiling (ADR 0003) shows benefit.
- Polling mode stays single-process.
- Polling sharding and multi-repo splits remain deferred.

## Consequences

- **Positive:** Single deploy and config; clean architecture preserved; correct
  multi-worker draw behaviour without Redis or bot sharding.
- **Negative:** Master private chat uses the same public webhook endpoint as draw
  bots (protected by secret token and `bot_id` routing). Each worker adds DB
  round-trips per webhook vs the old in-memory registry.
- **Database connection budget:** each worker process has its own SQLAlchemy pool.
  Upper bound: `WORKER_COUNT × (DB_POOL_SIZE + DB_MAX_OVERFLOW)`. Starting point
  for `WORKER_COUNT=2`: `DB_POOL_SIZE=3`, `DB_MAX_OVERFLOW=2` (10 connections).
  Documented in README; logged at startup.
- **`deactivate_inactive_bots`:** updates the database only; operators restart
  the service afterward so runtime and Telegram delivery realign.

## When to revisit

- Production traffic or latency exceeds assumptions in ADR 0003 → re-profile
  `WORKER_COUNT` and pool sizes.
- Master on public webhook becomes unacceptable (compliance, ingress policy) →
  reconsider spike 2 or 3 with updated requirements.
- Production requires polling-at-scale → new ADR for bot sharding.
