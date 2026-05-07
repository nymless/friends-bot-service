# Friends Bot

Версия на русском: [README.ru.md](README.ru.md).

A Telegram bot for daily "Winner of the Day" and "Loser of the Day" draws. Inspired by [TheUserOfTheDayBot](https://github.com/DevDmitryN/TheUserOfTheDayBot) repository, but completely rewritten in Python with a focus on modern practices.

## Key Features

- **Tech Stack:** Python 3.12+, `aiogram 3.x`, `SQLite`.
- **Package Management:** Powered by `uv` for lightning-fast dependency handling.
- **Reliability:** Static type hinting `mypy`, unit tests `pytest`, and logging.
- **Security:** Strict access control via `ALLOWED_CHAT_ID` (prevents usage in other groups).
- **Asynchrony:** Dual-layer protection against potential race conditions (code-level and database-level).
- **Architecture:** Clean modular structure (Handlers / Database / Config separation).

## Getting Started

### 1. Configuration

Create a `.env` file in the root directory:

```env
BOT_TOKEN=your_bot_token_from_botfather
DB_PATH=friends_bot.db
ALLOWED_CHAT_ID=your_telegram_group_id
```

### 2. Installation & Usage

Manage the project easily using the provided `Makefile`:

```bash
make install    # Install dependencies (including dev)
make run        # Start the bot
make test       # Run all tests
make type       # Run static type analysis
make lint       # Run code style checking
make format     # Autoformat code
make clean      # Clear cache and virtual environment
```

## Available Commands

- `/reg` — Register for the daily games.
- `/run` — Run the "Winner of the Day" draw.
- `/pidor` — Run the "Loser of the Day" draw.
- `/stats` — View the leaderboard.
- `/pidorstats` — View losers leaderboard.
- `/delete` — Opt-out of the game (your history is preserved).
