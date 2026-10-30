"""Transacciones atómicas entre Alerts y AuditLogs."""

from typing import Any

from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.repositories.alerts import (
    AlertNotFoundError,
    AlertStateConflictError,
    get_alert,
)
from app.repositories.dynamo_client import get_dynamodb_resource
from app.schemas.alerts import AlertInDB, AuditLogRecord


class AuditConflictError(Exception):
    """Señala que la clave del registro de auditoría ya está ocupada."""


def _transaction_cancelled(alert_id: str, error: ClientError) -> Exception:
    """Traduce condiciones fallidas conocidas y conserva los errores inesperados."""
    reasons = error.response.get("CancellationReasons", [])
    codes = [reason.get("Code") for reason in reasons]

    if codes and codes[0] == "ConditionalCheckFailed":
        # La lectura fuerte distingue una alerta ausente de un estado obsoleto.
        existing = get_alert(alert_id, consistent=True)
        if existing is None:
            return AlertNotFoundError("La alerta no existe.")
        return AlertStateConflictError("El estado de la alerta cambió.")
    if len(codes) > 1 and codes[1] == "ConditionalCheckFailed":
        return AuditConflictError("El registro de auditoría ya existe.")
    return error


def _run_transaction(
    alert_id: str,
    update: dict[str, Any],
    audit_record: AuditLogRecord,
) -> AlertInDB:
    """Envía las dos escrituras juntas para que estado y auditoría sean indivisibles."""
    settings = get_settings()
    client = get_dynamodb_resource().meta.client
    try:
        client.transact_write_items(
            TransactItems=[
                {"Update": {"TableName": settings.alerts_table, **update}},
                {
                    "Put": {
                        "TableName": settings.audit_logs_table,
                        "Item": audit_record.model_dump(exclude_none=True),
                        "ConditionExpression": (
                            "attribute_not_exists(#a) AND attribute_not_exists(#k)"
                        ),
                        "ExpressionAttributeNames": {
                            "#a": "alert_id",
                            "#k": "change_key",
                        },
                    }
                },
            ]
        )
    except ClientError as error:
        if error.response.get("Error", {}).get("Code") != "TransactionCanceledException":
            raise
        translated = _transaction_cancelled(alert_id, error)
        if translated is error:
            raise
        raise translated from None

    # La lectura consistente entrega el objeto con todos sus atributos persistidos.
    alert = get_alert(alert_id, consistent=True)
    if alert is None:
        raise AlertNotFoundError("La alerta no existe.")
    return alert


def update_status_with_audit(
    alert_id: str,
    new_status: str,
    *,
    expected_status: str,
    updated_at: str,
    audit_record: AuditLogRecord,
) -> AlertInDB:
    """Actualiza el estado y agrega su auditoría en una transacción."""
    update = {
        "Key": {"alert_id": alert_id},
        "UpdateExpression": "SET #s = :n, #u = :t",
        "ConditionExpression": "attribute_exists(#p) AND #s = :e",
        "ExpressionAttributeNames": {
            "#p": "alert_id",
            "#s": "status",
            "#u": "updated_at",
        },
        "ExpressionAttributeValues": {
            ":n": new_status,
            ":e": expected_status,
            ":t": updated_at,
        },
    }
    return _run_transaction(alert_id, update, audit_record)


def assign_with_audit(
    alert_id: str,
    assigned_to: str,
    *,
    updated_at: str,
    audit_record: AuditLogRecord,
) -> AlertInDB:
    """Asigna la alerta y agrega su auditoría en una transacción."""
    update = {
        "Key": {"alert_id": alert_id},
        "UpdateExpression": "SET #a = :v, #u = :t",
        "ConditionExpression": "attribute_exists(#p)",
        "ExpressionAttributeNames": {
            "#p": "alert_id",
            "#a": "assigned_to",
            "#u": "updated_at",
        },
        "ExpressionAttributeValues": {":v": assigned_to, ":t": updated_at},
    }
    return _run_transaction(alert_id, update, audit_record)
