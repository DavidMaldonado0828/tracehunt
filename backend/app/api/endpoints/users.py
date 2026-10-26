"""Operaciones administrativas de cuentas."""

from fastapi import APIRouter, Depends, HTTPException, status

from app.api.deps import require_admin
from app.repositories.users import UserAlreadyExistsError, UserNotFoundError
from app.schemas.users import UserCreate, UserInDB, UserPublic, UserRoleUpdate, UserStatusUpdate
from app.services.user_management import (
    LastActiveAdminError,
    create_account,
    list_accounts,
    update_account_role,
    update_account_status,
)

router = APIRouter(tags=["users"])


@router.post("", response_model=UserPublic, status_code=status.HTTP_201_CREATED)
def create_user(payload: UserCreate, _: UserInDB = Depends(require_admin)) -> UserPublic:
    try:
        return create_account(payload.email, payload.display_name, payload.password, payload.role)
    except UserAlreadyExistsError:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail="El usuario ya existe.") from None


@router.get("", response_model=list[UserPublic])
def get_users(_: UserInDB = Depends(require_admin)) -> list[UserPublic]:
    return list_accounts()


@router.patch("/{email}/role", response_model=UserPublic)
def change_role(email: str, payload: UserRoleUpdate, _: UserInDB = Depends(require_admin)) -> UserPublic:
    try:
        return update_account_role(email, payload.role)
    except UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El usuario no existe.") from None
    except LastActiveAdminError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None


@router.patch("/{email}/status", response_model=UserPublic)
def change_status(email: str, payload: UserStatusUpdate, _: UserInDB = Depends(require_admin)) -> UserPublic:
    try:
        return update_account_status(email, payload.status)
    except UserNotFoundError:
        raise HTTPException(status_code=status.HTTP_404_NOT_FOUND, detail="El usuario no existe.") from None
    except LastActiveAdminError as error:
        raise HTTPException(status_code=status.HTTP_409_CONFLICT, detail=str(error)) from None
