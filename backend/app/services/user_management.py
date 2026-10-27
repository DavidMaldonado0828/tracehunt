"""Casos de uso de administración de cuentas."""

from datetime import datetime, timezone
from uuid import uuid4

from app.core.security import hash_password
from app.repositories.users import (
    UserAlreadyExistsError,
    UserNotFoundError,
    create_user as persist_user,
    list_users as load_users,
    update_user as persist_user_update,
)
from app.schemas.users import UserInDB, UserPublic, UserUpdate, normalize_email


class LastActiveAdminError(Exception):
    """La operación dejaría al sistema sin administradores activos."""


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def create_account(email: str, display_name: str, password: str, role: str) -> UserPublic:
    user = UserInDB(
        email_normalized=normalize_email(email),
        user_id=str(uuid4()),
        display_name=display_name,
        password_hash=hash_password(password),
        role=role,
        status="active",
        created_at=_utc_now(),
        updated_at=_utc_now(),
    )
    return persist_user(user).to_public()


def list_accounts() -> list[UserPublic]:
    return [user.to_public() for user in load_users()]


def update_account_role(email: str, role: str) -> UserPublic:
    _protect_last_active_admin(email, role=role)
    return persist_user_update(email, UserUpdate(role=role)).to_public()


def update_account_status(email: str, status: str) -> UserPublic:
    _protect_last_active_admin(email, status=status)
    return persist_user_update(email, UserUpdate(status=status)).to_public()


def _protect_last_active_admin(email: str, *, role: str | None = None, status: str | None = None) -> None:
    target_email = normalize_email(email)
    accounts = load_users()
    target = next((user for user in accounts if user.email_normalized == target_email), None)
    if target is None:
        raise UserNotFoundError("El usuario no existe.")

    removing_admin = target.role == "admin" and target.status == "active" and (
        role is not None and role != "admin" or status is not None and status != "active"
    )
    active_admins = sum(user.role == "admin" and user.status == "active" for user in accounts)
    if removing_admin and active_admins <= 1:
        raise LastActiveAdminError("Debe permanecer al menos un administrador activo.")
