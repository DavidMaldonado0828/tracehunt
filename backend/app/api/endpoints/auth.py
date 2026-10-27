"""Endpoints de inicio de sesión y consulta del usuario autenticado."""

from fastapi import APIRouter, Depends, HTTPException, Request, status

from app.api.deps import get_current_user
from app.schemas.auth import LoginRequest, TokenResponse
from app.schemas.users import UserInDB, UserPublic
from app.services.auth_service import authenticate_user, create_token_for
from app.services.login_rate_limit import clear_failures, reserve_attempt

router = APIRouter(tags=["auth"])


@router.post("/login", response_model=TokenResponse)
def login(payload: LoginRequest, request: Request) -> TokenResponse:
    """Entrega una respuesta genérica para credenciales o cuentas no válidas."""
    client_ip = request.client.host if request.client else "unknown"
    retry_after = reserve_attempt(str(payload.email), client_ip)
    if retry_after is not None:
        raise HTTPException(
            status_code=status.HTTP_429_TOO_MANY_REQUESTS,
            detail="Demasiados intentos de inicio de sesión. Inténtalo más tarde.",
            headers={"Retry-After": str(retry_after)},
        )
    user = authenticate_user(str(payload.email), payload.password)
    if user is None:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Credenciales inválidas",
            headers={"WWW-Authenticate": "Bearer"},
        )
    clear_failures(str(payload.email), client_ip)
    token, expires_in = create_token_for(user)
    return TokenResponse(access_token=token, expires_in=expires_in)


@router.get("/me", response_model=UserPublic)
def get_me(current_user: UserInDB = Depends(get_current_user)) -> UserPublic:
    """Devuelve el perfil público sin exponer el hash persistido."""
    return current_user.to_public()
