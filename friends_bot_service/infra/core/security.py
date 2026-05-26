from cryptography.fernet import Fernet

from friends_bot_service.infra.core.config import settings

# The key should be generated with `Fernet.generate_key().decode()`
_cipher = Fernet(settings.ENCRYPTION_KEY.encode())


def encrypt_token(token: str) -> str:
    """Encrypts a token."""

    return _cipher.encrypt(token.encode()).decode()


def decrypt_token(encrypted: str) -> str:
    """Decrypts a token."""

    return _cipher.decrypt(encrypted.encode()).decode()
