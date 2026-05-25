from dataclasses import dataclass


@dataclass(slots=True)
class RegisteredBot:
    bot_id: int
    username: str
    encrypted_token: str
    owner_id: int
    is_active: bool
