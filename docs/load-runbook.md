# Load test runbook

Пошаговый чеклист для воспроизводимых нагрузочных прогонов.
Цели и метрики — [ADR 0003](adr/0003-load-testing-multi-worker-webhook.md) (архитектурное решение о нагрузочном тестировании).
Инструментация приложения — [ADR 0004](adr/0004-production-observability.md) (метрики и наблюдаемость).

Сравнение вариантов A/B (AB-1 / AB-2) — в конце документа, [§ AB-сравнение](#ab-сравнение-порядок-работ).

## Конфиг

| Файл | После правки |
| ---- | ------------ |
| `.env.k6` | `make load-k6*` |
| `.env.load` | `make load-down-v load-up` → wait → `make load-seed load-restart` |

## Перед любым прогоном

1. Скопировать `.env.load.example` → `.env.load`, `.env.k6.example` → `.env.k6`; заполнить секреты.
2. Первый запуск / смена `.env.load` / смена кода:

   ```bash
   make load-build          # только если менялся код
   make load-down-v load-up
   make load-logs           # дождаться готовности (см. ниже)
   make load-seed load-restart
   ```

3. Поднять мониторинг (если ещё не): `make monitoring-up`.
4. **Прогрев после load-restart:**
   - webhook: ~15–20 с, в логах `loading bots count=<LOAD_BOT_COUNT>`
   - polling: ~30–60 с (100 длинных опросов (long-poll) к mock + отдельный диспетчер (dispatcher) на бота)

## Засечки времени (T0 / T1)

Prometheus хранит историю на диске — для «чистого» среза прогона нужен интервал времени, а не пересоздание всей базы данных временных рядов (TSDB).

| Момент | Когда фиксировать |
| ------ | ----------------- |
| **T0 / T1** | Блок `LOAD_TEST_T0` / `LOAD_TEST_T1` в **конце** вывода k6 (время UTC) |

В Grafana: выбор интервала (time picker) = `[T0, T1]`. В языке запросов Prometheus (PromQL) добавляйте `offset` или диапазон (range) внутри этого окна.

## Сценарии

k6 всегда в Docker, сеть `friends-bot-service_default` (см. `Makefile`).

### Ramp (`LOAD_K6_COMMAND`)

Один сценарий для `/stats`, `/run`, `/loser`. Команда и ramp-параметры — в `.env.k6` (`LOAD_K6_COMMAND`, `LOAD_RAMP_*`).

| Команда | `.env.load` | `.env.k6` |
| ------- | ----------- | --------- |
| `/stats` | `LOAD_SEED_DRAW_ENTRANTS=false` | `LOAD_K6_COMMAND=/stats` |
| `/run`, `/loser` | `LOAD_SEED_DRAW_ENTRANTS=true`, `LOAD_PLAYERS_PER_CHAT>=2` | `LOAD_K6_COMMAND=/run` или `/loser` |

Для draw: боты крутятся по формуле виртуального пользователя k6 (`__VU % botCount`); для успешных розыгрышей нужны `LOAD_BOT_COUNT >= RPS × длительность плато`, где RPS — запросов в секунду.

| Режим | Команда |
| ----- | ------- |
| webhook | `make load-k6-ramp` |
| polling | `make load-k6-ramp-polling` |

**k6:** ramp до `LOAD_RAMP_RPS_PEAK` (пик запросов в секунду).
**Ожидание k6:** `http_req_failed < 1%`.
**Grafana:** окно до падения скорости (rate) в ноль; обработчик (handler) — по `LOAD_K6_COMMAND`.

### Happy-path draw (`/run`)

**Happy-path** (досл. «счастливый путь») — сценарий без отклонений: один `/run` на бота в свой chat,
розыгрыш завершается успешно (`draw_completed`), без отказов `already_played`. Противоположность
**contention** (много параллельных `/run` в один chat). **Ramp** — отдельный профиль нагрузки по RPS,
не обязан давать только happy-path.

| Режим | `.env.load` | Команда |
| ----- | ----------- | ------- |
| webhook | `LOAD_SEED_DRAW_ENTRANTS=true`, `LOAD_PLAYERS_PER_CHAT=2`, `LOAD_K6_COMMAND=/run` | `make load-k6-run` |
| polling | то же + polling | `make load-k6-run-polling` |

**k6:** `LOAD_RUN_HAPPY_VUS` (default `LOAD_BOT_COUNT`) × 1 итерация — один `/run` на бота.
**Ожидание k6:** `http_req_failed < 1%`.
**Ожидание приложения** (за `[T0, T1]`):

```promql
increase(friends_bot_draw_completed_total{draw_type="winner"}[$__range])
# ≈ LOAD_BOT_COUNT (100 по умолчанию)

increase(friends_bot_draw_rejected_total{reason="already_played"}[$__range])
# ≈ 0
```

Дополнительно: `process_resident_memory_bytes` (резидентная память процесса), `rate(process_cpu_seconds_total[1m])` (загрузка центрального процессора) на `:METRICS_PORT` (default 8001).

### Contention draw (один bot/chat)

Только на **свежей базе данных (БД)** (после happy-path в те же боты чат уже «сыгран»).

| Режим | Команда |
| ----- | ------- |
| webhook | `make load-k6-run-contention` |
| polling | `make load-k6-run-contention-polling` |

Параметры: `LOAD_CONTENTION_VUS`, `LOAD_CONTENTION_ITERATIONS`, `LOAD_CONTENTION_MAX_DURATION`, опционально `LOAD_CONTENTION_BOT_ID` (default = `LOAD_BOT_ID_START`).

**Ожидание k6:** `http_req_failed < 1%`.
**Ожидание приложения:**

```promql
increase(friends_bot_draw_completed_total{draw_type="winner"}[$__range])
# = 1

increase(friends_bot_draw_rejected_total{reason="already_played"}[$__range])
# ≈ LOAD_CONTENTION_ITERATIONS - 1 (49 при 50 итерациях)
```

## Что k6 не проверяет

- Исход draw (`completed` / `already_played`) — только метрики приложения.
- Ответы `sendMessage` в telegram-mock — mock всегда `ok: true`.

## AB-сравнение: порядок работ

Сначала базовый прогон (baseline) на `main`, затем те же прогоны на `feature/workers` после переноса
load-инфраструктуры. Одинаковый `.env.load` + `.env.k6`, сценарий,
`load-down-v` → `load-up` → seed → restart → прогрев; меняется только код ветки.

| AB | Режим | Вопрос | `.env.load` |
| -- | ----- | ------ | ----------- |
| **AB-1** | webhook | реестр ботов в памяти (registry) на `main` vs webhook с запросом в БД на каждый update (db-first ingress) + несколько процессов (`WORKER_COUNT`) | `NGINX_ENABLED=1`, `BOT_MODE=webhook` |
| **AB-2** | polling | блокировка в памяти (lock) на `main` vs захват розыгрыша через БД (claim) на workers: стоимость claim на happy-path + страховка при конкуренции (contention) | `NGINX_ENABLED=0`, `BOT_MODE=polling` |

**AB-1 — webhook:** все три профиля — `/stats`, happy-path `/run`, contention.
**AB-2 — polling:** те же профили (`load-k6-ramp-polling`, `load-k6-run-polling`, `load-k6-run-contention-polling`).

Не смешивать AB-1 и AB-2 в одном прогоне (разный `BOT_MODE`).

### Фаза 1 — baseline (`main`)

1. Зафиксировать коммит/тег в таблице результатов.
2. Для **AB-1:** webhook-конфиг, прогнать сценарии (`load-k6-ramp`, `load-k6-run`, …).
3. Для **AB-2:** polling-конфиг, прогнать сценарии (`load-k6-ramp-polling`, `load-k6-run-polling`, `load-k6-run-contention-polling`).
4. На каждый прогон: `load-down-v load-up` → wait → `load-seed load-restart` → прогрев → T0/T1 → метрики.

### Фаза 2 — `feature/workers`

1. Вмержить load stack, `make load-build`, затем clean run (`load-down-v load-up` → seed → restart).
2. Повторить **те же** команды и сценарии для AB-1 (webhook) и AB-2 (polling).
3. Сравнить строки в `docs/load-results.md` (или своей таблице) внутри одного AB и одного сценария.

Общие правила:

- Одинаковый `VPS_SIM_CPUS`, `VPS_SIM_MEMORY`, `LOAD_BOT_COUNT`, seed.
- Сравнивать **внутри одного сценария**, не смешивать `/stats` и `/run`.
- Contention — только на свежей БД (до happy-path на тех же ботах).

## Куда писать результаты

Отдельный файл: [load-results.md](load-results.md) — таблица прогонов (копируйте строку-пример).

## Быстрая диагностика

```bash
curl -s http://127.0.0.1:8001/metrics | findstr /i "draw_ process_"
docker stats friends-bot-service-vps-sim-1 --no-stream
make load-logs
```
