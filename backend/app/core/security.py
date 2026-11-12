"""JWT рекрутера, хэширование паролей, генерация и хэширование токенов ссылок кандидата."""

import hashlib
import secrets


def new_invite_token() -> tuple[str, str]:
    """Возвращает (token для ссылки, sha256-хэш для БД). Сам токен в БД не хранится."""
    token = secrets.token_urlsafe(32)
    return token, hash_token(token)


def hash_token(token: str) -> str:
    return hashlib.sha256(token.encode()).hexdigest()


# TODO: create_access_token / verify_access_token (python-jose), hash_password / verify_password (passlib)
