"""Construcción y consulta de registros de auditoría de alertas."""

from uuid import uuid4

from app.repositories.audit_logs import append_log, build_change_key, list_logs
from app.schemas.alerts import AlertInDB, AuditLogRecord
from app.schemas.users import UserInDB

SYSTEM_ACTOR_ID = "detection-engine"


def _build_record(
    alert_id: str,
    *,
    actor_type: str,
    actor_id: str,
    actor_email: str | None,
    action: str,
    changed_at: str,
    previous_status: str | None = None,
    new_status: str | None = None,
    comment: str | None = None,
) -> AuditLogRecord:
    """Genera claves del evento en un solo lugar para mantenerlas coherentes."""
    change_id = str(uuid4())
    return AuditLogRecord(
        alert_id=alert_id,
        change_key=build_change_key(changed_at, change_id),
        change_id=change_id,
        actor_type=actor_type,
        actor_id=actor_id,
        actor_email=actor_email,
        action=action,
        previous_status=previous_status,
        new_status=new_status,
        changed_at=changed_at,
        comment=comment,
    )


def record_alert_created(alert: AlertInDB) -> AuditLogRecord:
    """Persiste la creación con identidad de sistema y devuelve el registro."""
    record = _build_record(
        alert.alert_id,
        actor_type="system",
        actor_id=SYSTEM_ACTOR_ID,
        actor_email=None,
        action="alert_created",
        new_status=alert.status,
        changed_at=alert.created_at,
    )
    return append_log(record)


def build_status_change_record(
    alert_id: str,
    *,
    actor: UserInDB,
    previous_status: str,
    new_status: str,
    changed_at: str,
    comment: str | None = None,
) -> AuditLogRecord:
    """Construye sin persistir el evento que acompaña una transición atómica."""
    return _build_record(
        alert_id,
        actor_type="user",
        actor_id=actor.user_id,
        actor_email=actor.email_normalized,
        action="status_changed",
        previous_status=previous_status,
        new_status=new_status,
        changed_at=changed_at,
        comment=comment,
    )


def build_assignment_record(
    alert_id: str,
    *,
    actor: UserInDB,
    assignee_user_id: str,
    changed_at: str,
    comment: str | None = None,
) -> AuditLogRecord:
    """Construye la auditoría de asignación sin añadir campos al contrato."""
    assignment_comment = f"assigned_to={assignee_user_id}"
    if comment:
        assignment_comment = f"{assignment_comment}; {comment}"
    return _build_record(
        alert_id,
        actor_type="user",
        actor_id=actor.user_id,
        actor_email=actor.email_normalized,
        action="alert_assigned",
        changed_at=changed_at,
        comment=assignment_comment,
    )


def get_history(
    alert_id: str,
    *,
    limit: int = 50,
    exclusive_start_key: dict | None = None,
) -> tuple[list[AuditLogRecord], dict | None]:
    """Devuelve una página cronológica del historial de una alerta."""
    return list_logs(
        alert_id,
        limit=limit,
        exclusive_start_key=exclusive_start_key,
    )
