# ADR 0003: Load testing for multi-worker webhook scaling

- **Status:** Proposed
- **Date:** 2026-06-07

## Prerequisites

- **ADR 0004 (observability):** production metrics and dashboards — required
  before meaningful load-test runs. Synthetic load (k6) and live traffic must use
  the **same** histograms and panels.
- **ADR 0002 (multi-worker webhook):** not on `main` until `feature/workers`
  merges. Scenarios with `WORKER_COUNT > 1` run after that merge; until then,
  profiles on `main` may use `WORKER_COUNT=1` only.

## Context

ADR 0002 (on `feature/workers`, pending merge to `main`) compares three webhook
multi-process spikes by **architecture and ops**
(deploy topology, master placement, process count). Code review alone can judge
layering, correctness, and operability — but **not** whether `WORKER_COUNT > 1`
improves throughput or latency under realistic load.

After spike 1 (`webhook-pool`), the webhook path resolves each game bot from the
database (`get_active_by_id`) instead of an in-process registry. Even with
`WORKER_COUNT=1`, webhook mode therefore does **more database work per update**
than the previous single-process design with an in-memory cache. Multi-worker adds
further cost: N separate SQLAlchemy pools, N aiogram dispatchers, and process
overhead.

Telegram traffic for this service is typically **low to moderate RPS** per bot,
often sequential per chat. The workload is **I/O-bound** (PostgreSQL, Telegram API).
A single asyncio worker on one or two cores may already spend most of its time
waiting — so **additional workers may show no benefit until load is high enough**
that one process saturates CPU or the event loop.

Without load testing we cannot answer:

- At what RPS does a second worker start to help?
- When does the benefit become **significant** (e.g. p95 latency improvement)?
- Does the DB-first webhook design regress single-worker performance vs the old
  cached registry at typical load?
- Does the connection budget (`WORKER_COUNT × (pool_size + overflow)`) become the
  bottleneck before CPU?

Unit and integration tests with in-memory SQLite do **not** substitute: different
engine, no network latency, no real pool contention.

## Decision

**Treat load testing as a separate, planned step** — not a blocker for accepting
an architecture spike on code/ops grounds, but **required before production sizing
decisions** (`WORKER_COUNT`, pool sizes, VPS tier).

### Planned AB comparisons

Load infrastructure on `feature/load-test` (based on `main`) establishes a
**baseline** first. The same scenarios are re-run after merging that tooling into
`feature/workers`. Two comparisons are in scope; they use **different** `BOT_MODE`
values — do not mix them in one run.

| ID | Mode | Branches / variants | What changes | Primary question |
| -- | ---- | ------------------- | ------------ | ---------------- |
| **AB-1** | `BOT_MODE=webhook` | `main` → `feature/workers` | In-memory bot registry + single process vs DB-first webhook ingress; later `WORKER_COUNT` | Throughput/latency regression and multi-worker gain |
| **AB-2** | `BOT_MODE=polling` | `main` → `feature/workers` | In-process lock vs DB **claim** on draw | Extra DB work on happy-path `/run`; contention as a correctness safety net |

**AB-1 (webhook):** `NGINX_ENABLED=1`. k6 → `make load-k6*`, `make load-k6-run*`,
`make load-k6-run-contention*`. Run all three profiles; compare ingress, heavy handler,
and parallel `/run` on one chat.

**AB-2 (polling):** `NGINX_ENABLED=0`. k6 → `make load-k6-polling`,
`make load-k6-run-polling`, `make load-k6-run-contention-polling`. Run **all three**.
Happy-path `/run` is the main place to see claim overhead (extra DB round-trips per
draw). Contention is not expected to disprove correctness of lock or claim; it is a
belt-and-braces check under parallel `/run` on one `(bot_id, chat_id)` — expect
`draw_completed` = 1, `draw_rejected{reason="already_played"}` ≈ iterations − 1, no
duplicate winners in `stats`.

**Order:** implement and run all profiles on `main` (baseline); merge load stack
to `feature/workers`; repeat the **same** checklist for each AB row.

Operational steps: [load-runbook.md](../load-runbook.md).

### Goals

| Question | How to answer |
| -------- | ------------- |
| Multi-worker vs single-worker | Same handler code; vary only `WORKER_COUNT` on identical hardware profile |
| When gain appears | Ramp RPS; record knee where p95 improves with workers |
| Cost of DB-first webhook | Baseline: `WORKER_COUNT=1` current spike vs legacy single-process + cache (if branch/tag available) |
| Cost of DB claim vs in-memory lock (polling) | Happy-path `/run` on workers vs main — handler latency, DB load |
| Correctness under contention | Contention scenario: parallel `/run` on same `(bot_id, chat_id)` — safety check, not the only AB signal |

### Metrics (record every run)

Use the **production observability stack from ADR 0004** (do not maintain a
separate ad-hoc metrics path for load tests only). At minimum per run:

- **RPS** sustained and peak before errors
- **p50 / p95 / p99** latency for `POST /webhook/{bot_id}` → 200
- **Handler / command latency** — same series as production (`handler_duration`, etc.)
- **Error rate** — 403, 5xx, pool timeouts, `IntegrityError` on claims
- **CPU %** — application and PostgreSQL
- **Active DB connections** — observed max vs configured budget
- **Claim / draw correctness** — no duplicate winners under parallel `/run`

### Test environment

Use **PostgreSQL as in production** (same driver, migrations, async pool). Recommended
local setup:

```text
docker compose (load profile)
  postgres   — cpu/memory limits (e.g. 1 CPU, 512m–1g)
  app        — webhook mode, cpu/memory limits (e.g. 1–2 CPU, 512m–1g)
  load tool  — k6 or Locust (host or container)
```

**Why Docker limits:** a powerful dev PC does not reflect a modest VPS. Cgroup
limits on **both** app and Postgres approximate constrained production hardware
and make comparisons **relative** (1 vs 2 workers on the **same** profile)
reproducible.

**Caveats (accept, do not ignore):**

- Docker Desktop on Windows — networking and I/O differ from Linux VPS; use
  results for **variant comparison**, not absolute SLA numbers.
- CPU throttling in cgroups is approximate, not identical to a slow VPS.
- Flooding `/webhook` without realistic `Update` bodies measures FastAPI only,
  not full handler + DB + Telegram behaviour.

**Optional validation:** one confirmation run on the **target VPS** before final
pool/worker sizing.

### Load profiles

1. **Low** — 5–20 RPS, one `bot_id`. Expect **no multi-worker gain**; establishes
   baseline and possible DB-first regression vs cache.
2. **Medium** — 50–200 RPS, many `bot_id` values. Stress pool and worker dispatch.
3. **Peak** — ramp until p95 or error rate degrades; find knee of the curve.
4. **Heavy handler** — lower RPS but `/run`-like path (claim + suspense); closer to
   production than bare POST.

Each profile: run `WORKER_COUNT ∈ {1, 2, 4}` (or 2 only if CPU limit is 1) with
identical seeds (N bots in DB, valid secret token, `alembic upgrade head`).

### Synthetic load tool

Prefer **k6** or **Locust**:

- `POST /webhook/{bot_id}` with valid `X-Telegram-Bot-Api-Secret-Token`
- Minimal valid Telegram `Update` JSON
- For end-to-end DB path: full handler, **mock Telegram HTTP** (no real Bot API)
  unless explicitly testing outbound calls

Document results in a table, e.g.:

| WORKER_COUNT | CPU limit | Max RPS @ p95 < 200ms | p95 @ 50 RPS | DB conn max |
| ------------ | --------- | --------------------- | ------------ | ----------- |
| 1            | 1         | …                     | …            | …           |
| 2            | 1         | …                     | …            | …           |

### Relationship to ADR 0002 spikes

- **Spikes 2 and 3** may be reviewed on **ops/architecture** without a full load
  matrix for each branch.
- **Load comparison** runs once on the **chosen** architecture (or on spike 1 if
  webhook-pool is accepted early), using the same profiles above.
- Fair cross-spike comparison requires the **same** DB-per-request handler semantics;
  only topology (workers, master placement) may differ.

### Deliverables (when implemented)

- ADR 0004 observability in `main` (see prerequisites)
- `docker-compose.load.yml` (or documented compose override) with resource limits
- k6/Locust script and run checklist — see [load-runbook.md](../load-runbook.md)
- Short results section in README or linked doc — expected order of RPS, when
  `WORKER_COUNT > 1` is worth considering

## Consequences

- Architecture spikes (ADR 0002) can be **Accepted** on correctness and ops without
  waiting for load infrastructure — but production worker count must cite load
  results or explicit “low-traffic, 1 worker sufficient” assumption.
- Expect **single-worker DB-first webhook** to be slightly slower than in-memory
  registry at low load; that is an acceptable trade for multi-worker correctness.
- Load tooling is **not** part of CI by default; optional CI job with fixed limits
  can guard regressions later.

## When to revisit

- ADR 0004 minimal phase deployed → begin load profiles on a suitable environment.
- ADR 0002 merged to `main` → run multi-worker matrix (`WORKER_COUNT` 1 vs 2).
- Load plan executed → update this ADR to **Accepted** with recorded assumptions.
- Production traffic exceeds documented RPS assumptions → re-run profiles and adjust
  `WORKER_COUNT` / pool / VPS tier.
- Handler path changes materially (caching, fewer DB round-trips) → re-baseline.
