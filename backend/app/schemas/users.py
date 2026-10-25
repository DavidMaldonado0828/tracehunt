"""Contratos validados para crear, actualizar y representar usuarios."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field, field_validator, model_validator

Role = Literal["admin", "analyst"]
UserStatus = Literal["active", "disabled"]


def normalize_email(email: str) -> str:
    """Usa una única forma canónica para persistir y buscar correos."""
    return email.strip().lower()


class UserCreate(BaseModel):
    """Datos de alta; las longitudes de contraseña son límites iniciales del MVP."""

    email: EmailStr
    display_name: str = Field(min_length=1, max_length=100)
    password: str = Field(min_length=8, max_length=128)
    role: Role

    @field_validator("email", mode="before")
    @classmethod
    def normalize_email_value(cls, value: str) -> str:
        return normalize_email(value)

    model_config = {"extra": "forbid"}


class UserUpdate(BaseModel):
    """Permite cambiar únicamente nombre visible, rol y estado de cuenta."""

    display_name: str | None = Field(default=None, min_length=1, max_length=100)
    role: Role | None = None
    status: UserStatus | None = None

    @model_validator(mode="after")
    def require_at_least_one_change(self) -> "UserUpdate":
        # Se rechaza un cuerpo vacío o valores nulos porque estos atributos persistidos no son anulables.
        if not self.model_fields_set or any(getattr(self, name) is None for name in self.model_fields_set):
            raise ValueError("Debe indicarse al menos un cambio válido.")
        return self

    model_config = {"extra": "forbid"}


class UserPublic(BaseModel):
    """Representación segura para respuestas que nunca incluye el hash."""

    user_id: str
    email: EmailStr
    display_name: str
    role: Role
    status: UserStatus
    created_at: str
    last_login_at: str | None = None


class UserInDB(BaseModel):
    """Representación persistida que conserva el hash solo en la capa interna."""

    email_normalized: str
    user_id: str
    display_name: str
    password_hash: str
    role: Role
    status: UserStatus
    created_at: str
    updated_at: str
    last_login_at: str | None = None

    def to_public(self) -> UserPublic:
        """Construye una salida explícita para evitar filtrar campos internos."""
        return UserPublic(
            user_id=self.user_id,
            email=self.email_normalized,
            display_name=self.display_name,
            role=self.role,
            status=self.status,
            created_at=self.created_at,
            last_login_at=self.last_login_at,
        )
