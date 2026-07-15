# ADR 0002: Multi-process scaling (webhook-first)

- **Status:** Accepted (topology); production rollout deferred
- **Date:** 2026-06-07
- **Implemented:** 2026-06-08 (`spike/webhook-pool` → merge to `feature/workers`)
- **Revisited:** 2026-07-15 after AB load runs — see [load-results.md](../load-results.md)

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
| `spike/webhook-pool` | Webhook in the same worker pool as draw bots | Single deploy | **Accepted (topology)** |
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

**Scope of the 2026-06 decision:** we chose among spikes by **code and ops
simplicity**, not by load numbers. Load testing (ADR 0003) was explicitly **not**
a blocker for that topology choice. That made the decision **intentional but
incomplete**: it fixed *how* to run multi-process webhooks correctly; it did
**not** prove that DB-first ingress + dynamic `Bot` creation is cheap enough for
production, or when to raise `WORKER_COUNT`. Those questions needed AB runs
([load-results.md](../load-results.md)).

## Decision

**Adopt `webhook-pool` (spike 1) as the multi-process topology:** one deploy,
homogeneous uvicorn worker pool, master bot on webhook alongside draw bots,
DB-first bot resolution, and `chat_draw_claims` for draw races.

That adoption covers **architecture and correctness**. It does **not** by itself
mean “merge `feature/workers` to production as-is” or “scale with more workers
only”.

- `WORKER_COUNT` defaults to `1`. Raising it can help **long** handlers (e.g.
  `/run`) once one event loop / shared pools saturate; it often **hurts** light
  handlers (e.g. `/stats`) under the current DB-first + per-request `Bot` cost.
  See ADR 0003 and [load-results.md](../load-results.md).
- Prefer improving ingress (Bot cache / registry, less DB work per update) before
  treating more workers as the main scaling lever.
- Optional interim (without full workers merge): move the master bot to webhook
  even on today’s `main` topology to cut polling CPU waste.
- Polling mode stays single-process.
- Polling sharding and multi-repo splits remain deferred.

## Consequences

- **Positive:** Single deploy and config; clean architecture preserved; correct
  multi-worker draw behaviour without Redis or bot sharding.
- **Negative:** Master private chat uses the same public webhook endpoint as draw
  bots (protected by secret token and `bot_id` routing).
- **Negative (measured):** vs in-memory registry on `main`, every update pays
  DB lookup and often a new `Bot` instance. On light commands that cost dominates;
  multi-worker does not cancel it. Production merge without mitigating that cost
  is not recommended based on current AB results.
- **Database connection budget:** each worker process has its own SQLAlchemy pool.
  Upper bound: `WORKER_COUNT × (DB_POOL_SIZE + DB_MAX_OVERFLOW)`. More workers ⇒
  more total connections (and more RAM). Example sizing lives in README and is
  logged at startup as `database connection budget`.
- **`deactivate_inactive_bots`:** updates the database only; operators restart
  the service afterward so runtime and Telegram delivery realign.

## When to revisit

- Before production merge of `feature/workers` — address Bot cache / less DB-first
  work (or accept the measured regression); re-run required load profiles.
- Traffic or latency changes vs [load-results.md](../load-results.md) → re-profile
  `WORKER_COUNT` and pool sizes (ADR 0003).
- Master on public webhook becomes unacceptable (compliance, ingress policy) →
  reconsider spike 2 or 3 with updated requirements.
- Production requires polling-at-scale → new ADR for bot sharding.
