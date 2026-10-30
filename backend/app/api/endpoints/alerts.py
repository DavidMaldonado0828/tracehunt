"""Endpoints HTTP para consultar y gestionar alertas autorizadas."""

import logging
from typing import NoReturn

from fastapi import APIRouter, Depends, HTTPException, Query, status

from app.api.deps import require_staff
from app.api.endpoints.simulations import (
    _decode_cursor as decode_cursor,
    _encode_cursor as encode_cursor,
)
from app.repositories.alert_transactions import AuditConflictError
from app.repositories.alerts import AlertNotFoundError, AlertStateConflictError
from app.schemas.alerts import (
    AlertAssign,
    AlertListResponse,
    AlertPublic,
    AlertStatus,
    AlertStatusUpdate,
    AuditLogListResponse,
    Severity,
)
from app.schemas.users import UserInDB
from app.services import alert_manager
from app.services.pagination import (
    InvalidAlertCursorError,
    decode_alert_cursor,
    encode_alert_cursor,
)

logger = logging.getLogger("uvicorn.error")
router = APIRouter(tags=["alerts"])


def _raise_service_error(error: Exception) -> NoReturn:
    """Traduce fallos del servicio sin revelar si una alerta ajena existe."""
    if isinstance(error, AlertNotFoundError):
        raise HTTPException(
            status_code=status.HTTP_404_NOT_FOUND,
            detail="Alerta no encontrada",
        ) from None
    if isinstance(error, alert_manager.InvalidTransitionError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail=str(error),
        ) from None
    if isinstance(error, AlertStateConflictError):
        raise HTTPException(
            status_code=status.HTTP_409_CONFLICT,
            detail="El estado de la alerta cambió; vuelve a intentarlo.",
        ) from None
    if isinstance(error, alert_manager.InvalidAssigneeError):
        raise HTTPException(
            status_code=status.HTTP_422_UNPROCESSABLE_ENTITY,
            detail=str(error),
        ) from None

    if isinstance(error, AuditConflictError):
        logger.error("Conflicto al guardar la auditoría de una alerta")
    else:
        logger.error("Error inesperado al procesar una alerta")
    raise HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="No fue posible procesar la solicitud.",
    ) from None


@router.get("", response_model=AlertListResponse)
def list_alerts(
    current_user: UserInDB = Depends(require_staff),
    alert_status: AlertStatus | None = Query(default=None, alias="status"),
    severity: Severity | None = Query(default=None),
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> AlertListResponse:
    """Lista una página y delega alcance por propietario al servicio."""
    try:
        cursor_state = decode_alert_cursor(
            cursor,
            actor=current_user,
            status=alert_status,
            severity=severity,
            limit=limit,
        )
    except InvalidAlertCursorError:
        raise HTTPException(
            status_code=status.HTTP_400_BAD_REQUEST,
            detail="Cursor inválido o incompatible con la consulta.",
        ) from None

    try:
        alerts, next_state = alert_manager.list_alerts_for_actor(
            actor=current_user,
            status=alert_status,
            severity=severity,
            limit=limit,
            cursor_state=cursor_state,
        )
        return AlertListResponse(
            items=[alert.to_public() for alert in alerts],
            next_cursor=encode_alert_cursor(
                next_state,
                actor=current_user,
                status=alert_status,
                severity=severity,
                limit=limit,
            ),
        )
    except Exception as error:
        _raise_service_error(error)


@router.get("/{alert_id}", response_model=AlertPublic)
def get_alert(
    alert_id: str,
    current_user: UserInDB = Depends(require_staff),
) -> AlertPublic:
    """Consulta el detalle y deja la comprobación de propietario al servicio."""
    try:
        return alert_manager.get_alert_for_actor(
            alert_id,
            actor=current_user,
        ).to_public()
    except Exception as error:
        _raise_service_error(error)


@router.patch("/{alert_id}/status", response_model=AlertPublic)
def update_alert_status(
    alert_id: str,
    body: AlertStatusUpdate,
    current_user: UserInDB = Depends(require_staff),
) -> AlertPublic:
    """Solicita el cambio al servicio para mantener la política fuera del router."""
    try:
        alert = alert_manager.change_status(
            alert_id,
            body.status,
            actor=current_user,
            comment=body.comment,
        )
        return alert.to_public()
    except Exception as error:
        _raise_service_error(error)


@router.patch("/{alert_id}/assignment", response_model=AlertPublic)
def assign_alert(
    alert_id: str,
    body: AlertAssign,
    current_user: UserInDB = Depends(require_staff),
) -> AlertPublic:
    """Delega al servicio la autorización del actor y la validación del asignado."""
    try:
        alert = alert_manager.assign_to(
            alert_id,
            assignee_user_id=body.assigned_to,
            actor=current_user,
        )
        return alert.to_public()
    except Exception as error:
        _raise_service_error(error)


@router.get("/{alert_id}/history", response_model=AuditLogListResponse)
def get_alert_history(
    alert_id: str,
    current_user: UserInDB = Depends(require_staff),
    limit: int = Query(default=50, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> AuditLogListResponse:
    """Autoriza primero el acceso mediante el servicio y pagina su auditoría."""
    exclusive_start_key = decode_cursor(cursor)
    try:
        records, last_key = alert_manager.get_history_for_actor(
            alert_id,
            actor=current_user,
            limit=limit,
            exclusive_start_key=exclusive_start_key,
        )
        return AuditLogListResponse(
            items=[record.to_public() for record in records],
            next_cursor=encode_cursor(last_key),
        )
    except Exception as error:
        _raise_service_error(error)
