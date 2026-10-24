"""Hash de contraseñas y emisión/verificación de tokens de acceso."""

from datetime import datetime, timedelta, timezone
from typing import Any

import jwt
from pwdlib import PasswordHash

from app.core.config import get_settings


class TokenError(Exception):
    """Indica que un token no puede aceptarse como token de acceso válido."""


_password_hash = PasswordHash.recommended()


def hash_password(password: str) -> str:
    """Guarda contraseñas mediante Argon2 para evitar almacenar texto recuperable."""
    return _password_hash.hash(password)


def verify_password(password: str, password_hash: str) -> bool:
    """Devuelve un resultado negativo uniforme ante hashes inválidos o desconocidos."""
    try:
        return _password_hash.verify(password, password_hash)
    except Exception:
        # Los formatos corruptos no deben convertir una verificación de credenciales en un error del servicio.
        return False


def _get_jwt_secret() -> str:
    """Valida el secreto al usar JWT para que otros módulos puedan cargar sin él."""
    secret = get_settings().jwt_secret
    if secret is None or not secret.strip() or len(secret) < 32:
        raise RuntimeError("JWT_SECRET debe tener al menos 32 caracteres para usar tokens.")
    return secret


def create_access_token(
    subject: str,
    role: str,
    expires_minutes: int | None = None,
) -> str:
    """Firma un token con expiración UTC para limitar el tiempo de validez."""
    settings = get_settings()
    now = datetime.now(timezone.utc)
    lifetime = settings.jwt_expire_minutes if expires_minutes is None else expires_minutes
    payload: dict[str, Any] = {
        "sub": subject,
        "role": role,
        "iat": now,
        "exp": now + timedelta(minutes=lifetime),
    }
    return jwt.encode(payload, _get_jwt_secret(), algorithm=settings.jwt_algorithm)


def decode_access_token(token: str) -> dict:
    """Valida firma y claims requeridos, exponiendo un error genérico al consumidor."""
    settings = get_settings()
    try:
        return jwt.decode(
            token,
            _get_jwt_secret(),
            algorithms=[settings.jwt_algorithm],
            options={"require": ["exp", "sub", "role"]},
        )
    except Exception as exc:
        # No se propagan errores del parser o de firma que puedan revelar detalles del token.
        raise TokenError("Token inválido o expirado.") from None