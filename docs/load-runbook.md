# Load test runbook

Пошаговый чеклист для воспроизводимых прогонов на ветке `feature/load-test`.
Цели и метрики — [ADR 0003](adr/0003-load-testing-multi-worker-webhook.md).
Инструментация приложения — [ADR 0004](adr/0004-production-observability.md).

## Две AB-матрицы

Сначала **baseline на `main`** (текущая ветка `feature/load-test`), затем те же
прогоны на `feature/workers` после переноса load-инфраструктуры. Одинаковый
`.env.load`, сценарий, `load-down-v` → seed → прогрев; меняется только код ветки.

| AB | Режим | Вопрос | `.env.load` |
| -- | ----- | ------ | ----------- |
| **AB-1** | webhook | registry (main) vs db-first ingress + workers (`WORKER_COUNT`) | `NGINX_ENABLED=1`, `BOT_MODE=webhook` |
| **AB-2** | polling | lock (main) vs DB **claim** (workers): стоимость claim на happy-path + страховка contention | `NGINX_ENABLED=0`, `BOT_MODE=polling` |

**AB-1 — webhook:** все три профиля — `/stats`, happy-path `/run`, contention.
**AB-2 — polling:** те же три профиля (`load-k6-polling`, `load-k6-run-polling`, `load-k6-run-contention-polling`). Для AB-2 особенно смотреть happy-path `/run` (claim добавляет обращения в БД на каждый draw) и contention (на всякий случай — гонка на одном чате). Ни один профиль не заменяет другие.

Не смешивать AB-1 и AB-2 в одном прогоне (разный `BOT_MODE`).

## Перед любым прогоном

1. Скопировать `.env.load.example` → `.env.load`, заполнить секреты.
2. После смены кода приложения: `make docker-build load-build`.
3. Поднять мониторинг (если ещё не): `make monitoring-up`.
4. **Чистая БД** перед каждым вариантом сравнения:

   ```bash
   make load-down-v
   make load-up
   make load-seed
   make load-restart
   ```

5. **Прогрев после restart:**
   - webhook: ~15–20 с, в логах `loading bots count=<LOAD_BOT_COUNT>`
   - polling: ~30–60 с (100 long-poll на mock + отдельный dispatcher на бота)

## Засечки времени (T0 / T1)

Prometheus хранит историю на диске — для «чистого» среза прогона нужен интервал, а не пересоздание TSDB.

| Момент | Когда фиксировать |
| ------ | ----------------- |
| **T0** | Сразу перед `make load-k6*` (или первая строка вывода k6) |
| **T1** | k6 завершился + **~15 с** хвост (webhook 200 приходит до suspense `/run`) |

В Grafana: time picker = `[T0, T1]`. В PromQL добавляйте `offset` или range внутри этого окна.

## Сценарии

k6 всегда в Docker, сеть `friends-bot-service_default` (см. `Makefile`).

### Лёгкий ingress (`/stats`)

| Режим | `.env.load` | Команда |
| ----- | ----------- | ------- |
| webhook | `NGINX_ENABLED=1`, `BOT_MODE=webhook`, `LOAD_SEED_DRAW_ENTRANTS=false` | `make load-k6` |
| polling | `NGINX_ENABLED=0`, `BOT_MODE=polling`, `LOAD_SEED_DRAW_ENTRANTS=false` | `make load-k6-polling` |

**k6:** ramp ~50 RPS, 2 мин.
**Ожидание:** `http_req_failed < 1%`; рост `friends_bot_handler_invocations_total{command="/stats"}`.

### Happy-path draw (`/run`)

| Режим | `.env.load` | Команда |
| ----- | ----------- | ------- |
| webhook | `LOAD_SEED_DRAW_ENTRANTS=true`, `LOAD_PLAYERS_PER_CHAT=2`, `LOAD_DRAW_COMMAND=/run` | `make load-k6-run` |
| polling | то же + polling | `make load-k6-run-polling` |

**k6:** `LOAD_BOT_COUNT` VU × 1 итерация — один `/run` на бота.
**Ожидание k6:** `http_req_failed < 1%`.
**Ожидание приложения** (за `[T0, T1]`):

```promql
increase(friends_bot_draw_completed_total{draw_type="winner"}[$__range])
# ≈ LOAD_BOT_COUNT (100 по умолчанию)

increase(friends_bot_draw_rejected_total{reason="already_played"}[$__range])
# ≈ 0
```

Дополнительно: `process_resident_memory_bytes`, `rate(process_cpu_seconds_total[1m])` на `:METRICS_PORT` (default 8001).

### Contention draw (один bot/chat)

Только на **свежей БД** (после happy-path в те же боты чат уже «сыгран»).

| Режим | Команда |
| ----- | ------- |
| webhook | `make load-k6-run-contention` |
| polling | `make load-k6-run-contention-polling` |

Параметры: `LOAD_CONTENTION_VUS` (параллелизм), `LOAD_CONTENTION_ITERATIONS` (всего запросов), опционально `LOAD_CONTENTION_BOT_ID` (default = `LOAD_BOT_ID_START`).

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

### Фаза 1 — baseline (`main` / `feature/load-test`)

1. Зафиксировать коммит/тег ветки в таблице результатов.
2. Для **AB-1:** webhook-конфиг, прогнать сценарии (`load-k6`, `load-k6-run`, …).
3. Для **AB-2:** polling-конфиг, прогнать сценарии (`load-k6-polling`, `load-k6-run-polling`, **`load-k6-run-contention-polling`**).
4. На каждый прогон: `load-down-v` → seed → restart → прогрев → T0/T1 → метрики.

### Фаза 2 — `feature/workers`

1. Вмержить load stack, `make docker-build load-build`, `load-down-v load-up`.
2. Повторить **те же** команды и сценарии для AB-1 (webhook) и AB-2 (polling).
3. Сравнить строки в `docs/load-results.md` (или своей таблице) внутри одного AB и одного сценария.

Общие правила:

- Одинаковый `VPS_SIM_CPUS`, `VPS_SIM_MEMORY`, `LOAD_BOT_COUNT`, seed.
- Сравнивать **внутри одного сценария**, не смешивать `/stats` и `/run`.
- Contention — только на свежей БД (до happy-path на тех же ботах).

## Куда писать результаты

Отдельный файл (по желанию): `docs/load-results.md` — одна строка на прогон:

| date | branch | AB | scenario | BOT_MODE | T0–T1 | draw_completed | already_played | k6 errors | notes |

Сырые логи k6 — в `load/results/` (можно в `.gitignore`), в git — только сводная таблица.

## Быстрая диагностика

```bash
curl -s http://127.0.0.1:8001/metrics | findstr /i "draw_ process_"
docker stats friends-bot-service-vps-sim-1 --no-stream
make load-logs
```
