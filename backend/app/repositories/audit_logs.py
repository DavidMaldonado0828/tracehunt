"""Operaciones de agregado y consulta para el historial de alertas."""

from typing import Any

from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.repositories.dynamo_client import get_dynamodb_resource
from app.schemas.alerts import AuditLogRecord


class AuditLogAlreadyExistsError(Exception):
    """Señala que el identificador del cambio ya está registrado."""


def _get_audit_logs_table() -> Any:
    """Resuelve la tabla de auditoría configurada para la aplicación."""
    return get_dynamodb_resource().Table(get_settings().audit_logs_table)


def _is_conditional_failure(error: ClientError) -> bool:
    """Reconoce la colisión esperada de clave y propaga otros errores."""
    return error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


def _item_to_record(item: dict[str, Any]) -> AuditLogRecord:
    """Valida una fila leída del historial antes de devolverla."""
    return AuditLogRecord.model_validate(item)


def _record_to_item(record: AuditLogRecord) -> dict[str, Any]:
    """Omite opcionales ausentes para evitar persistir atributos NULL."""
    return record.model_dump(exclude_none=True)


def build_change_key(changed_at: str, change_id: str) -> str:
    """Construye la sort key para ordenar cronológicamente los cambios."""
    return f"{changed_at}#{change_id}"


def append_log(record: AuditLogRecord) -> AuditLogRecord:
    """Agrega un log sin reemplazar otro registro con las mismas claves."""
    try:
        _get_audit_logs_table().put_item(
            Item=_record_to_item(record),
            ConditionExpression=(
                "attribute_not_exists(#alert_id) AND "
                "attribute_not_exists(#change_key)"
            ),
            ExpressionAttributeNames={
                "#alert_id": "alert_id",
                "#change_key": "change_key",
            },
        )
    except ClientError as error:
        if _is_conditional_failure(error):
            raise AuditLogAlreadyExistsError(
                "El cambio de auditoría ya existe."
            ) from None
        raise
    return record


def list_logs(
    alert_id: str,
    *,
    limit: int = 50,
    exclusive_start_key: dict[str, Any] | None = None,
) -> tuple[list[AuditLogRecord], dict[str, Any] | None]:
    """Consulta el historial de una alerta en orden cronológico ascendente."""
    if not 1 <= limit <= 100:
        raise ValueError("limit debe estar entre 1 y 100.")

    query: dict[str, Any] = {
        "KeyConditionExpression": "#alert_id = :alert_id",
        "ExpressionAttributeNames": {"#alert_id": "alert_id"},
        "ExpressionAttributeValues": {":alert_id": alert_id},
        "Limit": limit,
        "ScanIndexForward": True,
    }
    if exclusive_start_key is not None:
        query["ExclusiveStartKey"] = exclusive_start_key

    response = _get_audit_logs_table().query(**query)
    items = [_item_to_record(item) for item in response.get("Items", [])]
    last_key = response.get("LastEvaluatedKey")
    return items, dict(last_key) if last_key else None


# Este repositorio es de agregado: no expone operaciones de actualización ni borrado.
