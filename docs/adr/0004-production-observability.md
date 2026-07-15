# ADR 0004: Production observability (metrics and dashboards)

- **Status:** Accepted (Phase 1)
- **Date:** 2026-06-09
- **Accepted:** 2026-07-15 (shipped on `main`; see also ADR 0005 for unified metrics export)

## Context

Operating the service by manually using the bots is not enough to understand real
user experience: latency under load, which commands are used, error rates, and
database pressure remain invisible.

ADR 0003 (load testing) needs the **same** metrics in synthetic runs and in
production. Building load-test-only instrumentation would duplicate effort and
produce incomparable numbers.

Multi-worker webhook sizing (ADR 0002, on `feature/workers` until merge to
`main`) is a separate concern. Observability **does not depend** on
`WORKER_COUNT > 1` and should land on `main` first via `feature/observability`.

## Decision

Add **Prometheus-style application metrics** exposed from the service via `GET /metrics`
(`prometheus_client` in-process). Implementation lives in a dedicated
`infra/observability` package with thin hooks in bootstrap code.

**Prometheus and Grafana are not deployed on the production virtual private server (VPS).** They run
**locally** (`docker-compose.monitoring.yml`) when needed — load tests (ADR 0003),
manual debugging, Prometheus query language (PromQL) analysis. The deployed app only exposes `/metrics`; scrape
target is configured on the dev machine (e.g. `host.docker.internal` or tunnel).

Grafana dashboards and alert rules are **optional**; PromQL in Prometheus is
sufficient for Phase 1 and ADR 0003.

### Goals

| Area | What to measure |
| ---- | ---------------- |
| **Ingress** | Incoming webhook request duration (response status), requests per second (RPS), 403/5xx rate |
| **Handlers** | Per-command or per-handler duration and count (`/run`, `/reg`, master commands, …) |
| **Draw flow** | Draw completed vs rejected (`already_played`, `not_registered`, …) |
| **Database** | `db_errors_total` in Phase 1; pool/saturation gauges deferred until load tests show a need |
| **Errors** | Unhandled handler exceptions, `DatabaseUnavailableError` |

### Non-goals (initial phase)

- Distributed tracing (OpenTelemetry / Jaeger) — defer unless histograms are insufficient
- High-cardinality labels (`chat_id`, `user_id`) on Prometheus series — too many distinct label values; use logs or SQL for per-chat forensics
- Product analytics warehouse (ClickHouse, etc.)
- Metrics in CI by default — optional later

### Metric naming (initial set)

Counters and histograms use a consistent prefix, e.g. `friends_bot_`:

| Name | Type | Labels (low cardinality) | Notes |
| ---- | ---- | ------------------------ | ----- |
| `webhook_request_duration_seconds` | histogram | `status` | FastAPI `POST /webhook/{bot_id}` until HTTP response |
| `webhook_requests_total` | counter | `status` | |
| `handler_duration_seconds` | histogram | `command`, `bot_mode` | aiogram middleware around handler execution |
| `handler_invocations_total` | counter | `command`, `outcome` | outcome: ok / error / business_reject |
| `draw_completed_total` | counter | `draw_type` | After successful claim and commit |
| `draw_rejected_total` | counter | `draw_type`, `reason` | already_played, not_registered, no_entrants |
| `db_errors_total` | counter | `operation` | |

Optional after ADR 0002 is on `main`: label `worker_index` on webhook metrics when
`WORKER_COUNT > 1`.

**Important:** webhook returns 200 before `/run` suspense finishes. Track
`draw_completed_total` and `handler_duration` for user-visible draw latency, not
HTTP 200 alone.

### Where to instrument (code)

| Location | Responsibility |
| -------- | -------------- |
| `infra/observability/` | Metric definitions, `setup_observability()`, Prometheus registry |
| FastAPI app | HTTP middleware or route wrapper; mount `GET /metrics` |
| aiogram dispatcher | Middleware: resolve command name, time `feed_update` / handler chain |
| Draw handlers / use cases | Increment draw outcome counters at business result boundaries |
| `infra/bootstrap/runtime.py` | Call `setup_observability(app)` once in webhook lifespan (one line) |

Polling mode: handler middleware still applies; `/metrics` exists only when the
FastAPI webhook app runs (`make run` webhook or `make run_api`).

### Runtime stack

| Component | Where | Role |
| --------- | ----- | ---- |
| `prometheus_client` | App (VPS or local) | In-process metrics; `GET /metrics` on webhook app |
| Prometheus | **Local** (compose) | Scrape `/metrics` on an interval; time-series database (TSDB) history; PromQL |
| Grafana | **Local** (compose), optional | Dashboards; not required if PromQL suffices |

Document local scrape target and ports in README (`make monitoring-up`, `SCRAPE_PORT`).

### Phases

1. **Phase 1:** metrics package, middleware, `/metrics`, local scrape via compose,
   README metric list. Grafana dashboard JSON **optional** (webhook latency, command
   rate, errors) — PromQL covers the same queries.
2. **Phase 2 (on demand):** draw outcome panels in Grafana; DB pressure metrics or
   `postgres_exporter` if load tests are inconclusive; alert rules when always-on prod
   monitoring is worth the ops cost.
3. **Phase 3:** execute ADR 0003 load profiles using the **same metric names** and
   local Prometheus (Grafana optional).

### Relationship to other ADRs

| ADR | Relationship |
| --- | -------------- |
| 0002 | Worker count is an optional label after merge; observability ships first |
| 0003 | Prerequisite; load tests read the same metric names via local Prometheus |

### Branch and merge policy

- **This ADR and docs:** `main` (may temporarily skip ADR 0002 in the sequence).
- **Implementation:** `feature/observability` from `main`, merge to `main`
  independently of `feature/workers`.
- Before ADR 0003 multi-worker runs: `merge main` into `feature/workers`.

## Consequences

- **Positive:** Real user experience visible without manual testing; ADR 0003 uses
  one source of truth for latency and requests per second (RPS).
- **Negative:** Label discipline required to avoid cardinality blow-up; local
  Prometheus/Grafana stack when analysing runs (not on production VPS).
- **Neutral:** Logs (`LOG_INBOUND_COMMANDS`) remain for audit; metrics complement,
  not replace, logs.

## Deliverables

- `friends_bot_service/infra/observability/` package — **done** on `feature/observability`
- `GET /metrics` on webhook app — **done**
- `docker-compose.monitoring.yml` for **local** Prometheus + Grafana — **done**
- README section: metric names and local `make monitoring-up` — **done**
- Example Grafana dashboard JSON — optional (Phase 2)
- Prod VPS: app ships with `/metrics`; no Prometheus/Grafana co-located on the production server

## When to revisit

- ADR 0003 completed → keep load assumptions in [load-results.md](../load-results.md) / README in sync with production sizing.
- Need per-request traces across DB and Telegram → new ADR or Phase 4 for OpenTelemetry.
- Optional Phase 2+: richer Grafana dashboards / alerts if PromQL-only workflow is not enough.
