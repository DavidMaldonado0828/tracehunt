"""Operaciones de persistencia para alertas en DynamoDB."""

from typing import Any

from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.repositories.dynamo_client import get_dynamodb_resource
from app.schemas.alerts import AlertInDB


class AlertAlreadyExistsError(Exception):
    """Señala que ya existe una alerta con la clave primaria solicitada."""


class AlertNotFoundError(Exception):
    """Señala que no existe la alerta solicitada."""


class AlertStateConflictError(Exception):
    """Señala que el estado cambió desde que se leyó la alerta."""


def _get_alerts_table() -> Any:
    """Resuelve la tabla configurada para no duplicar construcción de clientes."""
    return get_dynamodb_resource().Table(get_settings().alerts_table)


def _is_conditional_failure(error: ClientError) -> bool:
    """Reconoce solo conflictos de condición; los demás errores se propagan."""
    return error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


def _item_to_alert(item: dict[str, Any]) -> AlertInDB:
    """Valida los datos leídos y convierte atributos de DynamoDB al contrato."""
    return AlertInDB.model_validate(item)


def _alert_to_item(alert: AlertInDB) -> dict[str, Any]:
    """Omite atributos opcionales ausentes para no persistir valores NULL."""
    return alert.model_dump(exclude_none=True)


def create_alert(alert: AlertInDB) -> AlertInDB:
    """Inserta condicionalmente para no reemplazar una alerta existente."""
    try:
        _get_alerts_table().put_item(
            Item=_alert_to_item(alert),
            ConditionExpression="attribute_not_exists(#alert_id)",
            ExpressionAttributeNames={"#alert_id": "alert_id"},
        )
    except ClientError as error:
        if _is_conditional_failure(error):
            raise AlertAlreadyExistsError("La alerta ya existe.") from None
        raise
    return alert


def get_alert(alert_id: str, *, consistent: bool = False) -> AlertInDB | None:
    """Lee una alerta por su clave primaria, con consistencia opcional."""
    response = _get_alerts_table().get_item(
        Key={"alert_id": alert_id},
        ConsistentRead=consistent,
    )
    item = response.get("Item")
    return _item_to_alert(item) if item is not None else None


def list_alerts(
    *,
    status: str | None = None,
    severity: str | None = None,
    owner_user_id: str | None = None,
    limit: int = 25,
    exclusive_start_key: dict[str, Any] | None = None,
) -> tuple[list[AlertInDB], dict[str, Any] | None]:
    """Consulta un GSI con prioridad por propietario, estado y severidad."""
    if not 1 <= limit <= 100:
        raise ValueError("limit debe estar entre 1 y 100.")

    if owner_user_id is not None:
        index_name = "OwnerCreatedIndex"
        partition_name = "owner_user_id"
        partition_value = owner_user_id
    elif status is not None:
        index_name = "StatusCreatedIndex"
        partition_name = "status"
        partition_value = status
    elif severity is not None:
        index_name = "SeverityCreatedIndex"
        partition_name = "severity"
        partition_value = severity
    else:
        raise ValueError("Debe indicarse owner_user_id, status o severity.")

    names = {
        "#partition_key": partition_name,
    }
    values = {":partition_value": partition_value}
    key_expression = "#partition_key = :partition_value"
    filter_clauses: list[str] = []

    if status is not None and partition_name != "status":
        names["#filter_status"] = "status"
        values[":filter_status"] = status
        filter_clauses.append("#filter_status = :filter_status")
    if severity is not None and partition_name != "severity":
        names["#filter_severity"] = "severity"
        values[":filter_severity"] = severity
        filter_clauses.append("#filter_severity = :filter_severity")

    query: dict[str, Any] = {
        "IndexName": index_name,
        "KeyConditionExpression": key_expression,
        "ExpressionAttributeNames": names,
        "ExpressionAttributeValues": values,
        "Limit": limit,
        "ScanIndexForward": False,
    }
    if filter_clauses:
        # DynamoDB filtra después de leer: una página puede traer menos que limit.
        query["FilterExpression"] = " AND ".join(filter_clauses)
    if exclusive_start_key is not None:
        query["ExclusiveStartKey"] = exclusive_start_key

    response = _get_alerts_table().query(**query)
    items = [_item_to_alert(item) for item in response.get("Items", [])]
    last_key = response.get("LastEvaluatedKey")
    return items, dict(last_key) if last_key else None


def update_status(
    alert_id: str,
    new_status: str,
    *,
    expected_status: str,
    updated_at: str,
) -> AlertInDB:
    """Actualiza estado solo si coincide el estado que observó el servicio."""
    try:
        response = _get_alerts_table().update_item(
            Key={"alert_id": alert_id},
            UpdateExpression="SET #status = :new_status, #updated_at = :updated_at",
            ConditionExpression=(
                "attribute_exists(#alert_id) AND #status = :expected_status"
            ),
            ExpressionAttributeNames={
                "#alert_id": "alert_id",
                "#status": "status",
                "#updated_at": "updated_at",
            },
            ExpressionAttributeValues={
                ":new_status": new_status,
                ":expected_status": expected_status,
                ":updated_at": updated_at,
            },
            ReturnValues="ALL_NEW",
        )
    except ClientError as error:
        if not _is_conditional_failure(error):
            raise
        if get_alert(alert_id) is None:
            raise AlertNotFoundError("La alerta no existe.") from None
        raise AlertStateConflictError("El estado de la alerta cambió.") from None

    return _item_to_alert(response["Attributes"])


def assign_alert(
    alert_id: str,
    assigned_to: str,
    *,
    updated_at: str,
) -> AlertInDB:
    """Guarda la asignación solo si la alerta todavía existe."""
    try:
        response = _get_alerts_table().update_item(
            Key={"alert_id": alert_id},
            UpdateExpression="SET #assigned_to = :assigned_to, #updated_at = :updated_at",
            ConditionExpression="attribute_exists(#alert_id)",
            ExpressionAttributeNames={
                "#alert_id": "alert_id",
                "#assigned_to": "assigned_to",
                "#updated_at": "updated_at",
            },
            ExpressionAttributeValues={
                ":assigned_to": assigned_to,
                ":updated_at": updated_at,
            },
            ReturnValues="ALL_NEW",
        )
    except ClientError as error:
        if _is_conditional_failure(error):
            raise AlertNotFoundError("La alerta no existe.") from None
        raise

    return _item_to_alert(response["Attributes"])
