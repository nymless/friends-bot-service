from typing import Protocol


class TokenCipherPort(Protocol):
    def encrypt(self, plain_token: str) -> str: ...

    def decrypt(self, encrypted_token: str) -> str: ...
