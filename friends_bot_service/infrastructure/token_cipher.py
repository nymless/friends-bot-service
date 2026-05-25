from friends_bot_service.core.security import decrypt_token, encrypt_token
from friends_bot_service.usecases.ports.token_cipher import TokenCipherPort


class FernetTokenCipher:
    """Adapter that wraps application token encryption helpers."""

    def encrypt(self, plain_token: str) -> str:
        return encrypt_token(plain_token)

    def decrypt(self, encrypted_token: str) -> str:
        return decrypt_token(encrypted_token)


def default_token_cipher() -> TokenCipherPort:
    return FernetTokenCipher()
