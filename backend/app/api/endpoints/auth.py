"""Endpoints de inicio de sesión y consulta del usuario autenticado."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import get_current_user
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.users import UserInDB, UserPublic
from app.services.auth_service import authenticate_user, create_token_for

router = APIRouter(tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest) -> TokenResponse:
    """Entrega una respuesta genérica para credenciales o cuentas no válidas."""
    user = authenticate_user(str(payload.email), payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    token, expires_in = create_token_for(user)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserPublic)
def get_me(current_user: UserInDB = Depends(get_current_user)) -> UserPublic:
    """Devuelve el perfil público sin exponer el hash persistido."""
    return current_user.to_public()
