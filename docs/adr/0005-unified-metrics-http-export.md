# ADR 0005: Unified metrics HTTP export

- **Status:** Accepted
- **Date:** 2026-07-05

## Context

ADR 0004 adds in-process Prometheus metrics (`prometheus_client`) for handlers,
draws, and (in webhook mode) HTTP ingress. The service runs in two modes:

- **Polling** — no HTTP application server; only aiogram long-polling loops.
- **Webhook** — FastAPI + uvicorn for `POST /webhook/{bot_id}` and ingress
  middleware.

A hybrid export model — one transport in polling and another in webhook — is
easy to reintroduce during merges (for example FastAPI `GET /metrics` on the
webhook port plus a separate `start_http_server` in polling). That splits scrape
configuration, compose port mapping, and security assumptions without a clear
benefit on a single-worker deployment.

ADR 0002 may run several uvicorn worker processes (`WORKER_COUNT > 1`). Any
metrics endpoint must still present **one** aggregated snapshot to Prometheus (see
ADR 0002). That constraint affects implementation on the workers branch; it
does not change the export shape decided here.

## Decision

Use **one metrics HTTP surface** in both `BOT_MODE` values:

| Concern | Choice |
| ------- | ------ |
| Transport | A dedicated metrics HTTP server (`prometheus_client` pattern), started from bootstrap — **not** a FastAPI route mounted only to expose `/metrics`. |
| Bind | `METRICS_BIND_HOST` / `METRICS_BIND_PORT` (default port **8001**), separate from `WEBHOOK_BIND_*`. |
| Polling | Start the metrics server at process startup. Do **not** add FastAPI or uvicorn solely for metrics. |
| Webhook | FastAPI remains for webhook ingress and HTTP instrumentation middleware only. Metrics are served on `METRICS_BIND_*`, not on the webhook application port. |
| Scrape | Prometheus (local or tunneled) targets `http://<host>:<METRICS_BIND_PORT>/metrics` in **both** modes. |
| Public ingress | Metrics are **not** exposed through nginx or the public webhook URL. Prefer `127.0.0.1` on the VPS and scrape via localhost or SSH tunnel (same ops model as ADR 0004). |

Handler and draw counters use the same middleware and definitions regardless of
mode (ADR 0004). Only the HTTP export path is unified.

When `WORKER_COUNT > 1`, the single metrics endpoint must aggregate all worker
processes before responding (ADR 0002). How that aggregation is implemented is
left to the workers runtime; this ADR requires only that there is still **one**
bind address and **one** scrape target.

## Consequences

- **Positive:** One scrape port and one transport in docs, compose, Makefile,
  and runbooks; merges are less likely to resurrect a dual export model.
- **Positive:** Webhook ingress (`WEBHOOK_BIND_*`) and ops scrape
  (`METRICS_BIND_*`) can use different bind and firewall rules.
- **Negative:** Local webhook debugging cannot use `curl :8000/metrics`; use
  `METRICS_BIND_PORT` instead.
- **Neutral:** ADR 0004 remains the source for *what* to measure; this ADR
  covers *how* metrics leave the process over HTTP.

## Relationship to other ADRs

| ADR | Relationship |
| --- | -------------- |
| 0004 | Metric names, middleware, local Prometheus/Grafana |
| 0002 | Multi-worker aggregation at the single metrics endpoint |
| 0003 | Load-test scrape uses the same `METRICS_BIND_PORT` in polling and webhook |

## When to revisit

- A need to expose metrics only on the same port as webhook without a separate
  bind (unlikely; conflicts with nginx and ingress security).
- Replacing Prometheus scrape with push or OpenTelemetry — new ADR or ADR 0004
  amendment.
