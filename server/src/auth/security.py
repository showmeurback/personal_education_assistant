"""Хеширование паролей (PBKDF2-SHA256) и подписанные токены доступа (JWT HS256)."""
from __future__ import annotations

import base64
import hashlib
import hmac
import os
from datetime import datetime, timedelta, timezone

import jwt

from settings import auth_settings

_DEFAULT_SECRET = "change-me-in-production"
_MIN_SECRET_LEN = 32
_secret_cache: str | None = None


def signing_secret() -> str:
    """Ключ подписи токенов.

    Если AUTH_SECRET не задан или слишком короткий, ключ по умолчанию из открытого кода
    не используется: генерируется случайный ключ и сохраняется в каталоге загрузок
    (том Docker), чтобы токены оставались действительными после перезапуска.
    """
    global _secret_cache
    if _secret_cache:
        return _secret_cache
    secret = auth_settings.secret or ""
    if secret in (_DEFAULT_SECRET, "замените-на-длинную-случайную-строку") or len(secret) < _MIN_SECRET_LEN:
        from pathlib import Path
        import secrets as _secrets

        from log import logger
        from settings import settings

        path = Path(settings.uploads_dir) / ".auth_secret"
        try:
            secret = path.read_text(encoding="utf-8").strip()
        except OSError:
            secret = ""
        if len(secret) < _MIN_SECRET_LEN:
            secret = _secrets.token_hex(32)
            try:
                path.parent.mkdir(parents=True, exist_ok=True)
                path.write_text(secret, encoding="utf-8")
                path.chmod(0o600)
            except OSError as exc:  # без сохранения токены сбросятся при перезапуске
                logger.warning(f"Не удалось сохранить ключ подписи токенов: {exc}")
        logger.warning("AUTH_SECRET не задан или короче 32 символов — используется случайный ключ "
                       f"из {path}. Задайте AUTH_SECRET в .env для промышленного развёртывания.")
    _secret_cache = secret
    return secret


_ITERATIONS = 200_000
_PREFIX = "pbkdf2_sha256"


def hash_password(password: str) -> str:
    salt = os.urandom(16)
    digest = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, _ITERATIONS)
    return f"{_PREFIX}${_ITERATIONS}${base64.b64encode(salt).decode()}${base64.b64encode(digest).decode()}"


def verify_password(password: str, stored: str) -> bool:
    if not stored:
        return False
    if not stored.startswith(_PREFIX + "$"):
        # учётные записи, созданные до введения хеширования (пароль в открытом виде)
        return hmac.compare_digest(password, stored)
    try:
        _, iterations, salt_b64, digest_b64 = stored.split("$")
        salt = base64.b64decode(salt_b64)
        expected = base64.b64decode(digest_b64)
    except ValueError:
        return False
    actual = hashlib.pbkdf2_hmac("sha256", password.encode(), salt, int(iterations))
    return hmac.compare_digest(actual, expected)


def needs_rehash(stored: str) -> bool:
    return not stored.startswith(_PREFIX + "$")


def create_token(user_id: int, role: str, name: str = "") -> str:
    now = datetime.now(timezone.utc)
    payload = {
        "sub": str(user_id),
        "role": role,
        "name": name,
        "iat": now,
        "exp": now + timedelta(hours=auth_settings.token_ttl_hours),
    }
    return jwt.encode(payload, signing_secret(), algorithm="HS256")


def decode_token(token: str) -> dict:
    return jwt.decode(token, signing_secret(), algorithms=["HS256"])
