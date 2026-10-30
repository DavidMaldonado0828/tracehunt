"""Casos de uso para registrar, consultar y gestionar alertas."""

from dataclasses import dataclass, field
import hashlib
import logging
from typing import Any

from app.core.time_utils import utc_now_iso
from app.repositories.alert_transactions import (
    assign_with_audit,
    update_status_with_audit,
)
from app.repositories.alerts import (
    AlertAlreadyExistsError,
    AlertNotFoundError,
    create_alert,
    get_alert,
    list_alerts,
    list_alerts_all_statuses,
)
from app.repositories.users import get_by_user_id
from app.schemas.alerts import (
    AlertInDB,
    AlertMatch,
    AuditLogRecord,
    MAX_RELATED_EVENT_IDS,
)
from app.schemas.users import UserInDB
from app.services import audit_service

logger = logging.getLogger("uvicorn.error")

ALLOWED_TRANSITIONS = {
    "open": {"investigating"},
    "investigating": {"resolved"},
    "resolved": set(),
}


class InvalidTransitionError(Exception):
    """Señala una transición de estado que la política no permite."""


class InvalidAssigneeError(Exception):
    """Señala que el actor no puede usar el destinatario solicitado."""


@dataclass
class RegisterResult:
    """Resumen de resultados del registro independiente de coincidencias."""

    created: int = 0
    existing: int = 0
    failed: int = 0
    alert_ids: list[str] = field(default_factory=list)


def build_alert_id(rule_id: str, grouping_key: str, simulation_id: str | None) -> str:
    """Deriva un identificador estable para evitar duplicar la misma coincidencia."""
    identity = f"{rule_id}|{grouping_key}|{simulation_id or 'NONE'}"
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return f"{rule_id}-{digest[:20]}"


def register_matches(matches: list[AlertMatch]) -> RegisterResult:
    """Persiste coincidencias de forma idempotente y sigue tras fallos aislados."""
    result = RegisterResult()
    for match in matches:
        alert_id = build_alert_id(
            match.rule_id, match.grouping_key, match.simulation_id
        )
        try:
            related_event_ids = match.related_event_ids[:MAX_RELATED_EVENT_IDS]
            if len(match.related_event_ids) > MAX_RELATED_EVENT_IDS:
                logger.warning(
                    "Evidencia de alerta recortada alert_id=%s original_count=%d limit=%d",
                    alert_id,
                    len(match.related_event_ids),
                    MAX_RELATED_EVENT_IDS,
                )
            created_at = utc_now_iso()
            alert = AlertInDB(
                alert_id=alert_id,
                rule_id=match.rule_id,
                title=match.title,
                description=match.description,
                severity=match.severity,
                status="open",
                created_at=created_at,
                created_at_alert=f"{created_at}#{alert_id}",
                first_event_at=match.first_event_at,
                last_event_at=match.last_event_at,
                related_event_ids=related_event_ids,
                simulation_id=match.simulation_id,
                assigned_to=match.owner_user_id,
                owner_user_id=match.owner_user_id,
                updated_at=created_at,
            )
            create_alert(alert)
        except AlertAlreadyExistsError:
            result.existing += 1
            result.alert_ids.append(alert_id)
            continue
        except Exception as error:
            result.failed += 1
            logger.error(
                "No se pudo registrar coincidencia alert_id=%s error_type=%s",
                alert_id,
                type(error).__name__,
            )
            continue

        result.created += 1
        result.alert_ids.append(alert_id)
        try:
            audit_service.record_alert_created(alert)
        except Exception as error:
            # La creación ya quedó persistida; el registro auxiliar no puede revertirla.
            logger.error(
                "No se pudo auditar creación alert_id=%s error_type=%s",
                alert_id,
                type(error).__name__,
            )
    return result


def get_alert_for_actor(alert_id: str, *, actor: UserInDB) -> AlertInDB:
    """Devuelve una alerta solo cuando el rol y su propietario lo permiten."""
    alert = get_alert(alert_id, consistent=True)
    if alert is None or (
        actor.role == "analyst" and alert.owner_user_id != actor.user_id
    ):
        # El mismo error evita revelar la existencia de alertas ajenas.
        raise AlertNotFoundError("La alerta no existe.")
    return alert


def list_alerts_for_actor(
    *,
    actor: UserInDB,
    status: str | None = None,
    severity: str | None = None,
    limit: int = 25,
    cursor_state: dict[str, Any] | None = None,
) -> tuple[list[AlertInDB], dict[str, Any] | None]:
    """Aplica el alcance por rol y delega la paginación al repositorio."""
    if actor.role == "admin" and status is None and severity is None:
        if cursor_state is not None and cursor_state.get("mode") != "all_statuses":
            raise ValueError("El cursor no corresponde a la consulta de alertas.")
        return list_alerts_all_statuses(
            limit=limit,
            cursor_state=cursor_state,
        )

    if cursor_state is not None and cursor_state.get("mode") != "single":
        raise ValueError("El cursor no corresponde a la consulta de alertas.")

    owner_user_id = actor.user_id if actor.role == "analyst" else None
    alerts, last_key = list_alerts(
        status=status,
        severity=severity,
        owner_user_id=owner_user_id,
        limit=limit,
        exclusive_start_key=(cursor_state or {}).get("exclusive_start_key"),
    )
    next_state = (
        {"mode": "single", "exclusive_start_key": last_key}
        if last_key is not None
        else None
    )
    return alerts, next_state


def change_status(
    alert_id: str,
    new_status: str,
    *,
    actor: UserInDB,
    comment: str | None = None,
) -> AlertInDB:
    """Valida permisos y guarda estado más auditoría en una única transacción."""
    alert = get_alert_for_actor(alert_id, actor=actor)
    if new_status not in ALLOWED_TRANSITIONS.get(alert.status, set()):
        if alert.status == "resolved":
            raise InvalidTransitionError("La alerta ya está resuelta y su estado es final.")
        if new_status == "open":
            raise InvalidTransitionError("No se puede retroceder el estado de una alerta.")
        if alert.status == "open" and new_status == "resolved":
            raise InvalidTransitionError(
                "No se puede pasar de 'open' a 'resolved': primero debe pasar a 'investigating'."
            )
        raise InvalidTransitionError(
            f"La transición {alert.status} -> {new_status} no permitida."
        )

    changed_at = utc_now_iso()
    audit_record = audit_service.build_status_change_record(
        alert_id,
        actor=actor,
        previous_status=alert.status,
        new_status=new_status,
        changed_at=changed_at,
        comment=comment,
    )
    return update_status_with_audit(
        alert_id,
        new_status,
        expected_status=alert.status,
        updated_at=changed_at,
        audit_record=audit_record,
    )


def assign_to(
    alert_id: str,
    assignee_user_id: str,
    *,
    actor: UserInDB,
    comment: str | None = None,
) -> AlertInDB:
    """Valida el destinatario y guarda asignación y auditoría atómicamente."""
    get_alert_for_actor(alert_id, actor=actor)
    if actor.role != "admin":
        raise InvalidAssigneeError("Solo un administrador puede asignar alertas.")
    assignee = get_by_user_id(assignee_user_id)
    if assignee is None or assignee.status != "active":
        raise InvalidAssigneeError("El usuario asignado no existe o no está activo.")
    changed_at = utc_now_iso()
    audit_record = audit_service.build_assignment_record(
        alert_id,
        actor=actor,
        assignee_user_id=assignee_user_id,
        changed_at=changed_at,
        comment=comment,
    )
    return assign_with_audit(
        alert_id,
        assignee_user_id,
        updated_at=changed_at,
        audit_record=audit_record,
    )


def get_history_for_actor(
    alert_id: str,
    *,
    actor: UserInDB,
    limit: int = 50,
    exclusive_start_key: dict[str, Any] | None = None,
) -> tuple[list[AuditLogRecord], dict[str, Any] | None]:
    """Autoriza la alerta antes de devolver una página de su historial."""
    get_alert_for_actor(alert_id, actor=actor)
    return audit_service.get_history(
        alert_id,
        limit=limit,
        exclusive_start_key=exclusive_start_key,
    )
