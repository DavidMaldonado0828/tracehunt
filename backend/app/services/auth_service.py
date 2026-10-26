"""Casos de uso de autenticación, separados de las rutas HTTP."""

from functools import lru_cache
import logging

from app.core.config import get_settings
from app.core.security import create_access_token, hash_password, verify_password
from app.repositories.users import get_by_email, touch_last_login
from app.schemas.users import UserInDB, normalize_email

logger = logging.getLogger("uvicorn.error")


@lru_cache(maxsize=1)
def _dummy_password_hash() -> str:
    """Reutiliza un hash costoso para igualar el trabajo ante correos inexistentes."""
    return hash_password("tracehunt-dummy-password-never-used")


def authenticate_user(email: str, password: str) -> UserInDB | None:
    """Valida credenciales sin revelar existencia ni estado de la cuenta."""
    user = get_by_email(normalize_email(email), consistent=True)
    if user is None:
        verify_password(password, _dummy_password_hash())
        logger.warning("Login fallido")
        return None

    password_matches = verify_password(password, user.password_hash)
    if not password_matches or user.status != "active":
        logger.warning("Login fallido")
        return None

    try:
        touch_last_login(user.email_normalized)
    except Exception:
        # El registro de último acceso es auxiliar y no debe impedir un login válido.
        logger.warning("No se pudo actualizar la fecha del último login")
    logger.info("Login exitoso user_id=%s", user.user_id)
    return user


def create_token_for(user: UserInDB) -> tuple[str, int]:
    """Emite el bearer token y comunica el mismo plazo configurado en minutos."""
    settings = get_settings()
    token = create_access_token(subject=user.email_normalized, role=user.role)
    return token, settings.jwt_expire_minutes * 60
