# Friends Bot Service

English version: [README.md](README.md).

Этот репозиторий содержит сервис Telegram-ботов для ежедневных розыгрышей вроде
"Юзера дня" и "Лузера дня".

Идея простая: один приватный **мастер-бот** выступает как бэкенд-сервис для
нескольких отдельных игровых ботов. При этом каждый подключённый игровой бот
остаётся полноценным Telegram-ботом со своими именем, username и аватаркой,
которые его владелец может менять независимо от сервиса. Именно это и отличает
мультибот-сервис от обычного бота.

Проект вдохновлён
[TheUserOfTheDayBot](https://github.com/DevDmitryN/TheUserOfTheDayBot), но здесь
идея переосмыслена в формате мультибот-сервиса на современном Python-стеке.

## Что делает сервис

- Проводит ежедневные розыгрыши в групповых чатах.
- Хранит игроков и статистику отдельно для каждого бота и каждого чата.
- Позволяет владельцу подключать и отключать игровые боты через мастер-бота.
- Хранит токены ботов в зашифрованном виде в базе данных.
- Удаляет сообщения с токенами из чата мастер-бота после обработки.
- Может обновлять список команд по умолчанию у подключённых ботов.
- Включает maintenance-скрипт для отключения давно неиспользуемых ботов (`make deactivate_inactive_bots`).

## Как это устроено

- **Игровые боты** работают в группах и супергруппах.
- **Мастер-бот** работает в личке и обрабатывает сервисные команды, такие как:
  - `/add_bot`
  - `/remove_bot`
  - `/set_default_commands`
- **База данных** хранит зарегистрированных ботов, участников розыгрышей и статистику.
- **Менеджер ботов** запускает и останавливает подключённых ботов из базы.

## Структура проекта

Код разбит на feature-модули. У каждого обычно есть `domain/`, `interfaces/`
(порты), `usecases/` и `handlers/` (тонкие aiogram-адаптеры). Инфраструктура —
в `infra/`.

```text
friends_bot_service/
  bot_admin/      зарегистрированные боты: domain, ports, use cases
  draw/           розыгрыш и игровые команды /run, /loser
  draw_entrant/   /reg, /delete, /list
  draw_stats/     /stats, /loserstats
  master_bot/     хендлеры мастер-бота и orchestration use cases
  infra/          bootstrap, SQLAlchemy repos, bot manager, FastAPI webhook, texts
```

Сборка рантайма (dispatchers, `UnitOfWork`, polling/webhook) — в
`infra/bootstrap/`. SQLAlchemy-модели и репозитории реализуют порты feature-модулей.
Тексты для пользователя — в `infra/texts/`.

В базе пока legacy-имена таблиц из первой схемы: `players` для участников
розыгрыша и `stats` для статистики. В ORM это `DrawEntrantORM` и `DrawStatsORM`.
План переименования — [ADR 0001](docs/adr/0001-legacy-database-table-names.md).

Диаграмма компонентов: [uml/friends-bot.drawio.png](uml/friends-bot.drawio.png).

## Стек

- Python 3.12+
- aiogram 3.x
- FastAPI
- SQLAlchemy asyncio
- PostgreSQL через asyncpg
- Alembic
- uv

Инструменты разработки в репозитории:

- pytest
- mypy
- ruff

## Конфигурация

Создайте файл `.env` в корне проекта:

```env
BOT_MODE=polling
WEBHOOK_BASE_URL=https://example.com
WEBHOOK_SECRET_TOKEN=your_webhook_secret_token
REGISTRATION_ENABLED=true
MASTER_TOKEN=ваш_токен_мастер_бота
ENCRYPTION_KEY=ваш_fernet_ключ
DB_URL=postgresql+asyncpg://user:password@localhost:port/friends_bot_service
DB_POOL_SIZE=5
DB_MAX_OVERFLOW=10
DB_POOL_RECYCLE=3600
```

Примечания:

- `MASTER_TOKEN` — токен приватного управляющего бота.
- `WEBHOOK_BASE_URL` обязателен в режиме webhook и должен указывать на публичный базовый URL сервиса.
- `WEBHOOK_SECRET_TOKEN` обязателен в режиме webhook и используется для проверки, что запросы действительно приходят от Telegram.
- `REGISTRATION_ENABLED=false` отключает и `/reg`, и `/add_bot`, включая повторные регистрации, до следующего запуска сервиса с включённым флагом.
- `LOG_INBOUND_COMMANDS=true` пишет access-log входящих команд с `/` до хендлеров.
- `ENCRYPTION_KEY` должен быть корректным Fernet-ключом.
- Игровые боты добавляются позже через мастер-бота, а не через `.env`.

## Установка

С помощью `Makefile`:

```bash
make install
```

Или напрямую через `uv`:

```bash
uv sync
```

Перед запуском сервиса примените миграции базы данных:

```bash
uv run alembic upgrade head
```

## Запуск

Основной launcher:

```bash
make run
```

`make run` запускает сервис в соответствии со значением `BOT_MODE`:

- `polling` — long polling для мастер-бота и всех подключённых игровых ботов
- `webhook` — FastAPI-приложение для апдейтов игровых ботов; мастер-бот всё равно на polling

В репозитории также есть прямой FastAPI entry point (только webhook-режим):

```bash
make run_api
```

Режим webhook обычно требует дополнительной серверной настройки вне этого
репозитория: публичного HTTPS endpoint, TLS/SSL и часто reverse proxy вроде
Nginx.

## Сценарий работы

1. Запустите сервис.
2. Откройте мастер-бота в личном чате.
3. Отправьте `/add_bot <токен>` (токен из @BotFather) одним сообщением.
4. Добавьте подключённого игрового бота в группу.
5. Используйте игровые команды в этой группе.

Когда токен отправляется мастер-боту, сервис удаляет это сообщение из чата
после обработки.

## Команды игрового бота

Эти команды доступны у подключённых игровых ботов:

- `/reg` — вступить в игру
- `/delete` — выйти из игры с сохранением истории
- `/list` — кто участвует в розыгрыше в этом чате
- `/run` — запустить розыгрыш победителя
- `/loser` — запустить розыгрыш проигравшего
- `/stats` — показать статистику победителей
- `/loserstats` — показать статистику проигравших

## Команды мастер-бота

- `/add_bot <токен>` — зарегистрировать или повторно активировать бота
- `/remove_bot <токен>` — отключить бота в сервисе
- `/set_default_commands` — обновить список команд по умолчанию у подключённых ботов

## Конфиденциальность и безопасность

- Токены ботов в БД шифруются (Fernet, `ENCRYPTION_KEY`).
- После `/add_bot` и `/remove_bot` сообщение с токеном удаляется из чата
  мастер-бота, если Telegram это позволяет.
- `LOG_INBOUND_COMMANDS=true` включает access-log только для команд с `/`; у `/add_bot` и `/remove_bot` — только имя команды.
- В webhook-режиме проверяется заголовок `X-Telegram-Bot-Api-Secret-Token` против
  `WEBHOOK_SECRET_TOKEN`.
- В БД остаются Telegram user/chat id, отображаемые имена и статистика по чатам —
  защищайте `.env`, БД и логи как production-секреты.

## Разработка

```bash
make test      # pytest (handlers, repositories, use cases, infra)
make type      # mypy
make lint      # ruff check
make format    # ruff format + ruff check --fix
make check     # test, format, lint, type
make hooks     # установить git pre-commit hooks (также при make install)
make pre-commit  # прогнать pre-commit по всем файлам
```

## Примечания

- Сервис использует in-memory lock и ограничения базы данных, чтобы уменьшить
  вероятность повторного розыгрыша для одного и того же бота, чата и дня.
- Зарегистрированные боты загружаются из базы при старте приложения.
- Очистка неактивных ботов опирается на `last_game_attempt_at`, а если бот ещё
  ни разу не использовался — на `created_at`. Запуск: `make deactivate_inactive_bots`
  (60 дней без активности).
