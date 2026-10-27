"""Inicialización segura de la cuenta administradora."""

import logging
from datetime import datetime, timezone
from uuid import uuid4

from pydantic import ValidationError

from app.core.config import get_settings
from app.core.security import hash_password
from app.repositories.users import (
    UserAlreadyExistsError,
    create_user,
    get_by_email,
)
from app.schemas.users import UserCreate, UserInDB, normalize_email

logger = logging.getLogger("uvicorn.error")


def _utc_now() -> str:
    """Replica el formato UTC del repositorio sin acoplarse a su helper privado."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def ensure_initial_admin() -> None:
    """Crea el primer admin si está configurado y conserva intactas cuentas existentes."""
    try:
        settings = get_settings()
        if settings.admin_email is None or settings.admin_password is None:
            logger.warning("ADMIN_EMAIL/ADMIN_PASSWORD no configurados: no se crea el admin inicial")
            return

        try:
            # Pydantic valida aquí los mismos límites que se aplican a una solicitud de alta.
            admin_input = UserCreate(
                email=settings.admin_email,
                display_name="Administrator",
                password=settings.admin_password.get_secret_value(),
                role="admin",
            )
        except ValidationError as error:
            # Se omiten los valores de entrada porque los errores de Pydantic podrían incluir la contraseña.
            reasons = "; ".join(
                f"{'.'.join(str(part) for part in issue['loc'])}: {issue['msg']}"
                for issue in error.errors(include_input=False, include_url=False)
            )
            logger.error("ADMIN_EMAIL/ADMIN_PASSWORD no válidos: %s", reasons)
            return

        if get_by_email(admin_input.email):
            logger.info("admin inicial ya existe")
            return

        now = _utc_now()
        user = UserInDB(
            email_normalized=normalize_email(admin_input.email),
            user_id="usr-" + uuid4().hex,
            display_name="Administrator",
            password_hash=hash_password(admin_input.password),
            role="admin",
            status="active",
            created_at=now,
            updated_at=now,
        )
        create_user(user)
    except UserAlreadyExistsError:
        # La condición de escritura protege frente a dos procesos que arrancan simultáneamente.
        logger.info("admin inicial ya existe")
    except Exception as error:
        # El arranque continúa aunque la tabla falte o DynamoDB no esté disponible temporalmente.
        logger.error(
            "No se pudo asegurar el admin inicial (%s); revise que las tablas estén creadas y accesibles.",
            type(error).__name__,
        )
        return
    else:
        logger.info("admin inicial creado: %s", user.email_normalized)
