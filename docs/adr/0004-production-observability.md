# ADR 0004: Production observability (metrics and dashboards)

- **Status:** Proposed
- **Date:** 2026-06-09

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

Add **Prometheus-style application metrics** exposed from the service, scraped in
production, viewed in **Grafana** (self-hosted or cloud). Implementation lives
in a dedicated `infra/observability` package with thin hooks in bootstrap code.

### Goals

| Area | What to measure |
| ---- | ---------------- |
| **Ingress** | Webhook request duration (response status), RPS, 403/5xx rate |
| **Handlers** | Per-command or per-handler duration and count (`/run`, `/reg`, master commands, …) |
| **Draw flow** | Draw completed vs rejected (`already_played`, `not_registered`, …) |
| **Database** | Pool checkout time or saturation signals; optional connection gauge |
| **Errors** | Unhandled handler exceptions, `DatabaseUnavailableError` |

### Non-goals (initial phase)

- Distributed tracing (OpenTelemetry / Jaeger) — defer unless histograms are insufficient
- High-cardinality labels (`chat_id`, `user_id`) on Prometheus series — use logs or SQL for per-chat forensics
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

| Component | Role |
| --------- | ---- |
| `prometheus_client` | In-process metrics |
| Prometheus | Scrape `/metrics` on an interval |
| Grafana | Dashboards, p50/p95/p99, alerts |

Deploy Prometheus and Grafana on the VPS, or use a managed offering. Document
scrape target and ports in README when implemented.

### Phases

1. **Phase 1 (minimal prod):** metrics package, middleware, `/metrics`, scrape
   in production, one Grafana dashboard (webhook latency, command rate, errors).
2. **Phase 2:** draw outcome panels, DB pressure, alert rules (service down, high p95).
3. **Phase 3:** execute ADR 0003 load profiles using the same dashboards.

### Relationship to other ADRs

| ADR | Relationship |
| --- | -------------- |
| 0002 | Worker count is an optional label after merge; observability ships first |
| 0003 | Prerequisite; load tests read production metric names and dashboards |

### Branch and merge policy

- **This ADR and docs:** `main` (may temporarily skip ADR 0002 in the sequence).
- **Implementation:** `feature/observability` from `main`, merge to `main`
  independently of `feature/workers`.
- Before ADR 0003 multi-worker runs: `merge main` into `feature/workers`.

## Consequences

- **Positive:** Real user experience visible without manual testing; ADR 0003 uses
  one source of truth for latency and RPS.
- **Negative:** Operational surface (Prometheus, Grafana, scrape config); label
  discipline required to avoid cardinality blow-up.
- **Neutral:** Logs (`LOG_INBOUND_COMMANDS`) remain for audit; metrics complement,
  not replace, logs.

## Deliverables (when implemented)

- `friends_bot_service/infra/observability/` package
- `GET /metrics` on webhook app
- `docker-compose.monitoring.yml` (or documented VPS setup) for Prometheus + Grafana
- Example dashboard JSON or setup checklist
- README section: what to watch in production

## When to revisit

- Phase 1 deployed → set ADR to **Accepted** or **Accepted / Phase 1**.
- ADR 0003 completed → add documented RPS/worker assumptions to README or this ADR.
- Need per-request traces across DB and Telegram → new ADR or Phase 4 for OpenTelemetry.
