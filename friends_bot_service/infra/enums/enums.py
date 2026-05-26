from enum import StrEnum


class BotMode(StrEnum):
    """Bot mode enum."""

    POLLING = "polling"
    WEBHOOK = "webhook"
