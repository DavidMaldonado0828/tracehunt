"""Contratos de entrada y salida para iniciar una sesión."""

from typing import Literal

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    """Limita los datos aceptados para evitar campos inesperados en el login."""

    email: EmailStr
    password: str = Field(min_length=1, max_length=128)

    model_config = {"extra": "forbid"}


class TokenResponse(BaseModel):
    """Expone solo el token de acceso y el tiempo de vida comunicado al cliente."""

    access_token: str
    token_type: Literal["bearer"] = "bearer"
    expires_in: int
