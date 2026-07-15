# ADR 0003: Load testing for multi-worker webhook scaling

- **Status:** Accepted
- **Date:** 2026-06-07
- **Accepted:** 2026-07-15 (AB runs recorded in [load-results.md](../load-results.md))

## Prerequisites

- **ADR 0004 (observability):** production metrics and dashboards — required
  before meaningful load-test runs. Synthetic load (k6) and live traffic must use
  the **same** histograms and panels.
- **ADR 0002 (multi-worker webhook):** merged on `feature/workers`. Scenarios with
  `WORKER_COUNT > 1` are in scope after this merge.

## Context

ADR 0002 compares three webhook multi-process spikes by **architecture and ops**
(deploy topology, master placement, process count). Code review alone can judge
layering, correctness, and operability — but **not** whether `WORKER_COUNT > 1`
improves throughput or latency under realistic load.

After spike 1 (`webhook-pool`), the webhook path resolves each game bot from the
database (`get_active_by_id`) instead of an in-process registry. Even with
`WORKER_COUNT=1`, webhook mode therefore does **more database work per update**
than the previous single-process design with an in-memory cache. Multi-worker adds
further cost: N separate SQLAlchemy pools, N aiogram dispatchers, and process
overhead.

Telegram traffic for this service is typically **low to moderate requests per second (RPS)** per bot,
often sequential per chat. The workload is largely **input/output-bound (I/O-bound)**
(PostgreSQL, Telegram API). A single asyncio worker may spend most of its time waiting —
so additional workers may show **no benefit on short handlers** until load is high enough.
**Nuance (confirmed in AB runs):** long handlers such as `/run` (~10+ s wall time with
many awaits) create a large in-flight coroutine set; one event loop can saturate on
scheduling and shared pools even while mostly waiting on I/O. Multiple processes then
help by providing **independent event loops and pools**. That does not cancel the
per-request cost of DB-first ingress + dynamic `Bot` creation.

Without load testing we cannot answer:

- At what RPS does a second worker start to help?
- When does the benefit become **significant** (e.g. 95th percentile latency (p95) improvement)?
- Does the database-first webhook design (DB-first webhook) regress single-worker performance vs the old
  cached registry at typical load?
- Does the connection budget (`WORKER_COUNT × (pool_size + overflow)`) become the
  bottleneck before CPU?

Unit and integration tests with in-memory SQLite do **not** substitute: different
engine, no network latency, no real pool contention.

## Decision

**Treat load testing as a separate, planned step** — not a blocker for accepting
an architecture spike on code/ops grounds, but **required before production sizing
decisions** (`WORKER_COUNT`, pool sizes, virtual private server (VPS) tier).

### Planned A/B comparisons

Load infrastructure establishes a **baseline** on `main`. The same scenarios are
re-run on `feature/workers`. Two comparisons are in scope; they use **different**
`BOT_MODE` values — do not mix them in one run.

| ID | Mode | Branches / variants | What changes | Primary question |
| -- | ---- | ------------------- | ------------ | ---------------- |
| **AB-1** | `BOT_MODE=webhook` | `main` → `feature/workers` | In-memory bot registry + single process vs database-first webhook ingress (DB-first); `WORKER_COUNT` | Throughput/latency regression and multi-worker gain |
| **AB-2** | `BOT_MODE=polling` | `main` → `feature/workers` | In-process lock vs database **claim** on draw | Claim cost on ramp `/run`; contention as correctness safety net |

**Required profiles (both AB-1 and AB-2):**

1. **Ramp `/stats`** — light handler / ingress and DB-first overhead
2. **Ramp `/run` with `LOAD_RAMP_BOT_PICK=round_robin`** — heavy handler; enough
   `(bot, chat)` slots so requests are successful draws while RPS ≤ slot budget
3. **Contention `/run`** — parallel `/run` on one `(bot_id, chat_id)`; expect
   `draw_completed` = 1, `already_played` ≈ iterations − 1

**Optional:** happy-path `make load-k6-run*` (one `/run` per bot) as a short smoke.
It is **not** required for AB once ramp `/run` + `round_robin` is used.

**AB-1:** `NGINX_ENABLED=1`. **AB-2:** `NGINX_ENABLED=0`.

Operational steps: [load-runbook.md](../load-runbook.md).
Recorded results: [load-results.md](../load-results.md).

### Goals

| Question | How to answer |
| -------- | ------------- |
| Multi-worker vs single-worker | Same scenarios; vary `WORKER_COUNT` / VPS profile on identical seeds |
| When gain appears | Ramp RPS; record knee where throughput or success rate improves with workers |
| Cost of DB-first webhook | `main` registry vs workers DB-first (+ dynamic `Bot`), especially `/stats` |
| Cost of database claim vs in-memory lock (polling) | Ramp `/run` on workers vs main — success rate, handler latency, DB errors |
| Correctness under contention | Contention scenario — safety check, not the only A/B signal |

### Metrics (record every run)

Use the **production observability stack from ADR 0004** (do not maintain a
separate ad-hoc metrics path for load tests only). At minimum per run:

- **RPS** sustained / peak from handler invocation rate (and k6 totals where useful)
- **Handler / draw-handler latency** — primary client-facing duration signal for AB
  (`friends_bot_handler_duration_seconds`, `friends_bot_draw_handler_duration_seconds`).
  HTTP `POST /webhook` → 200 is secondary on webhook (response often returns before
  the handler finishes).
- **Error rate** — DB pool timeouts (`friends_bot_db_errors_total`), handler
  `outcome="error"` (e.g. Telegram client timeouts), draw completed vs rejected
- **CPU % / RAM** — application (and host contention when VPS sim uses all cores)
- **Claim / draw correctness** — no duplicate winners under contention

### Test environment

Use **PostgreSQL as in production** (same driver, migrations, async pool). Recommended
local setup: Docker Compose load stack with cgroup limits approximating a VPS
(app + Postgres + Nginx inside the guest). Typical matrix used in AB:
**VPS_1** (1 CPU / 2g), **VPS_4** (4 / 8g), optionally **VPS_8** (8 / 16g).

**Why Docker limits:** a powerful dev PC does not reflect a modest VPS. Limits on
the simulated guest make **relative** comparisons reproducible.

**Caveats (accept, do not ignore):**

- Docker Desktop on Windows — networking and I/O differ from Linux VPS; use
  results for **variant comparison**, not absolute SLA numbers.
- CPU throttling in cgroups is approximate, not identical to a slow VPS.
- When the VPS sim is given **all host cores** (e.g. VPS_8 on an 8-core laptop),
  k6 / Docker / the host contend for the same CPUs — absolute ceilings are
  pessimistic vs a dedicated cloud VPS; A vs B on that stand remains valid.
- Flooding `/webhook` without realistic `Update` bodies measures FastAPI only,
  not full handler + DB + Telegram behaviour.

**Optional validation:** one confirmation run on the **target VPS** before final
pool/worker sizing.

### Load profiles

1. **Light** — ramp `/stats` across rising RPS peaks until plateaus / errors.
2. **Heavy** — ramp `/run` (`round_robin`, enough chat slots) until degradation.
3. **Contention** — parallel `/run` on one bot/chat.

Vary `WORKER_COUNT` with guest CPU (often `WORKER_COUNT` = guest CPUs on the
workers branch) and keep seeds identical across A/B for a given scenario.

### Synthetic load tool

Prefer **k6**:

- Webhook: `POST /webhook/{bot_id}` with valid secret and Telegram `Update` JSON
- Polling: inject path via telegram-mock (see runbook)
- Mock Telegram HTTP for outbound Bot API

Document narrative + numbers in [load-results.md](../load-results.md).

### Relationship to ADR 0002 spikes

- **Spikes 2 and 3** may be reviewed on **ops/architecture** without a full load
  matrix for each branch.
- **Load comparison** runs on the **chosen** architecture (or on spike 1 if
  webhook-pool is accepted early), using the profiles above.
- Fair cross-spike comparison requires the **same** database-per-request handler semantics;
  only topology (workers, master placement) may differ.

### Deliverables (when implemented)

- ADR 0004 observability in `main` (see prerequisites)
- Compose load stack with resource limits
- k6 scripts and [load-runbook.md](../load-runbook.md)
- Results: [load-results.md](../load-results.md)

## Consequences

- Architecture spikes (ADR 0002) can be **Accepted** on correctness and ops without
  waiting for load infrastructure — but production worker count must cite load
  results or explicit “low-traffic, 1 worker sufficient” assumption.
- Expect **DB-first webhook** to regress light handlers (`/stats`) vs in-memory
  registry; multi-worker helps more on **long** handlers (`/run`) once event-loop /
  pool saturation appears — still not a free win without caching `Bot` / reducing
  ingress DB work (see AB conclusions in load-results).
- Load tooling is **not** part of CI by default; optional CI job with fixed limits
  can guard regressions later.

## When to revisit

- ADR 0002 merged to `main` with architecture changes → re-run required profiles.
- Production traffic exceeds documented RPS assumptions → re-run and adjust
  `WORKER_COUNT` / pool / VPS tier.
- Handler path changes materially (caching, fewer DB round-trips) → re-baseline.
- Open-loop / arrival-rate k6 profiles may be added later to stress ingress without
  VU hold-back on slow HTTP (see load-results recommendations).
