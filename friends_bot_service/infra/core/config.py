from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """PyDantic settings for the application."""

    BOT_MODE: str
    WEBHOOK_BIND_HOST: str = "127.0.0.1"
    WEBHOOK_BIND_PORT: int = 8000
    METRICS_BIND_HOST: str = "127.0.0.1"
    METRICS_BIND_PORT: int = 8001
    WEBHOOK_BASE_URL: str | None = None
    WEBHOOK_SECRET_TOKEN: str | None = None
    TELEGRAM_API_BASE_URL: str | None = None
    REGISTRATION_ENABLED: bool = True
    LOG_INBOUND_COMMANDS: bool = False
    ENCRYPTION_KEY: str
    MASTER_TOKEN: str
    DB_URL: str
    DB_POOL_SIZE: int
    DB_MAX_OVERFLOW: int
    DB_POOL_RECYCLE: int

    model_config = SettingsConfigDict(env_file=".env", env_file_encoding="utf-8")


settings = Settings()
