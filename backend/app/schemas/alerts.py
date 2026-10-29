"""Contratos validados para alertas y su historial de auditoría."""

from datetime import datetime
from typing import Literal

from pydantic import (
    BaseModel,
    ConfigDict,
    Field,
    field_validator,
    model_validator,
)


Severity = Literal["high", "medium", "low"]
AlertStatus = Literal["open", "investigating", "resolved"]
ActorType = Literal["user", "system"]

# Límite provisional alineado con el SRS: evidencia embebida acotada a 20 IDs.
MAX_RELATED_EVENT_IDS = 20


def _require_utc_z(value: str) -> str:
    """Exige ISO-8601 con sufijo Z para persistir instantes siempre en UTC."""
    if not isinstance(value, str) or not value.endswith("Z"):
        raise ValueError("El instante debe ser una cadena ISO-8601 UTC terminada en Z.")

    try:
        datetime.fromisoformat(value[:-1] + "+00:00")
    except ValueError as error:
        raise ValueError("El instante debe tener formato ISO-8601 válido.") from error

    return value


class AlertInDB(BaseModel):
    """Representación interna de una alerta persistida."""

    alert_id: str
    rule_id: str
    title: str
    description: str
    severity: Severity
    status: AlertStatus
    created_at: str
    created_at_alert: str
    first_event_at: str
    last_event_at: str
    related_event_ids: list[str] = Field(max_length=MAX_RELATED_EVENT_IDS)
    simulation_id: str | None = None
    assigned_to: str | None = None
    owner_user_id: str | None = None
    updated_at: str

    @field_validator(
        "created_at",
        "first_event_at",
        "last_event_at",
        "updated_at",
    )
    @classmethod
    def validate_utc_timestamps(cls, value: str) -> str:
        return _require_utc_z(value)

    @model_validator(mode="after")
    def validate_created_at_alert(self) -> "AlertInDB":
        # La sort key incluye el ID y debe corresponder al instante de creación persistido.
        expected = f"{self.created_at}#{self.alert_id}"
        if self.created_at_alert != expected:
            raise ValueError(
                "created_at_alert debe coincidir con "
                "f'{created_at}#{alert_id}'."
            )
        return self

    def to_public(self) -> "AlertPublic":
        """Omite la clave de orden interna antes de exponer la alerta."""
        values = self.model_dump(exclude={"created_at_alert"})
        return AlertPublic.model_validate(values)


class AlertPublic(BaseModel):
    """Campos de alerta permitidos en respuestas de API."""

    alert_id: str
    rule_id: str
    title: str
    description: str
    severity: Severity
    status: AlertStatus
    created_at: str
    first_event_at: str
    last_event_at: str
    related_event_ids: list[str] = Field(max_length=MAX_RELATED_EVENT_IDS)
    simulation_id: str | None = None
    assigned_to: str | None = None
    owner_user_id: str | None = None
    updated_at: str

    @field_validator(
        "created_at",
        "first_event_at",
        "last_event_at",
        "updated_at",
    )
    @classmethod
    def validate_utc_timestamps(cls, value: str) -> str:
        return _require_utc_z(value)


class AlertStatusUpdate(BaseModel):
    """Entrada para solicitar un estado y un comentario opcional."""

    status: AlertStatus
    comment: str | None = Field(default=None, max_length=500)

    model_config = ConfigDict(extra="forbid")


class AlertAssign(BaseModel):
    """Entrada para asignar la alerta a un identificador de usuario."""

    assigned_to: str = Field(min_length=1, max_length=100)

    model_config = ConfigDict(extra="forbid")


class AuditLogRecord(BaseModel):
    """Representación interna inmutable por diseño de un cambio auditado."""

    alert_id: str
    change_key: str
    change_id: str
    actor_type: ActorType
    actor_id: str
    actor_email: str | None = None
    action: str
    previous_status: AlertStatus | None = None
    new_status: AlertStatus | None = None
    changed_at: str
    comment: str | None = None

    @field_validator("changed_at")
    @classmethod
    def validate_utc_timestamp(cls, value: str) -> str:
        return _require_utc_z(value)

    @model_validator(mode="after")
    def validate_change_key(self) -> "AuditLogRecord":
        # La sort key compuesta debe conservar el instante y la identidad del cambio.
        expected = f"{self.changed_at}#{self.change_id}"
        if self.change_key != expected:
            raise ValueError(
                "change_key debe coincidir con f'{changed_at}#{change_id}'."
            )
        return self

    def to_public(self) -> "AuditLogPublic":
        """Omite la sort key interna del registro de auditoría."""
        values = self.model_dump(exclude={"change_key"})
        return AuditLogPublic.model_validate(values)


class AuditLogPublic(BaseModel):
    """Campos de auditoría permitidos en respuestas de API."""

    alert_id: str
    change_id: str
    actor_type: ActorType
    actor_id: str
    actor_email: str | None = None
    action: str
    previous_status: AlertStatus | None = None
    new_status: AlertStatus | None = None
    changed_at: str
    comment: str | None = None

    @field_validator("changed_at")
    @classmethod
    def validate_utc_timestamp(cls, value: str) -> str:
        return _require_utc_z(value)


class AlertListResponse(BaseModel):
    """Página de alertas y cursor opaco para continuar la consulta."""

    items: list[AlertPublic]
    next_cursor: str | None


class AuditLogListResponse(BaseModel):
    """Página de auditoría y cursor opaco para continuar la consulta."""

    items: list[AuditLogPublic]
    next_cursor: str | None
