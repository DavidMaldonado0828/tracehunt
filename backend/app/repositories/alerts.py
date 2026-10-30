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


def list_alerts_all_statuses(
    *,
    limit: int = 25,
    cursor_state: dict[str, Any] | None = None,
) -> tuple[list[AlertInDB], dict[str, Any] | None]:
    """Fusiona por fecha las tres consultas del índice de estado.

    Cada posición se guarda solo hasta el último elemento emitido de esa
    secuencia. Si una respuesta contenía elementos que quedaron fuera de la
    página global, la siguiente petición los vuelve a leer desde esa posición.
    """
    if not 1 <= limit <= 100:
        raise ValueError("limit debe estar entre 1 y 100.")

    statuses = ("open", "investigating", "resolved")
    cursor_state = cursor_state or {}
    positions = {
        current_status: cursor_state.get("positions", {}).get(current_status)
        for current_status in statuses
    }
    exhausted = {
        current_status: cursor_state.get("exhausted", {}).get(current_status, False)
        for current_status in statuses
    }
    table = _get_alerts_table()

    candidates: list[tuple[str, AlertInDB]] = []
    page_keys: dict[str, dict[str, Any] | None] = {}
    for current_status in statuses:
        if exhausted.get(current_status, False):
            page_keys[current_status] = None
            continue

        query: dict[str, Any] = {
            "IndexName": "StatusCreatedIndex",
            "KeyConditionExpression": "#partition_key = :partition_value",
            "ExpressionAttributeNames": {"#partition_key": "status"},
            "ExpressionAttributeValues": {":partition_value": current_status},
            "Limit": limit,
            "ScanIndexForward": False,
        }
        if positions.get(current_status) is not None:
            query["ExclusiveStartKey"] = positions[current_status]

        response = table.query(**query)
        current_page = [
            _item_to_alert(item) for item in response.get("Items", [])
        ]
        candidates.extend((current_status, alert) for alert in current_page)
        last_key = response.get("LastEvaluatedKey")
        page_keys[current_status] = dict(last_key) if last_key else None

    # GSI propagation can briefly expose the same alert through two status
    # partitions. Deduplicate within this response while retaining the newest
    # occurrence seen by the merge.
    candidates.sort(key=lambda pair: pair[1].created_at_alert, reverse=True)
    page: list[tuple[str, AlertInDB]] = []
    seen_ids: set[str] = set()
    for source_status, alert in candidates:
        if alert.alert_id in seen_ids:
            continue
        page.append((source_status, alert))
        seen_ids.add(alert.alert_id)
        if len(page) == limit:
            break

    emitted_by_status: dict[str, list[AlertInDB]] = {
        current_status: [] for current_status in statuses
    }
    for source_status, alert in page:
        emitted_by_status[source_status].append(alert)

    next_positions = dict(positions)
    next_exhausted = dict(exhausted)
    for current_status in statuses:
        if next_exhausted.get(current_status, False):
            continue

        emitted = emitted_by_status[current_status]
        # If no matching records were returned, it is safe to advance over the
        # evaluated range, including an empty filtered page with a LEK.
        current_candidates = [
            alert
            for source_status, alert in candidates
            if source_status == current_status
        ]
        if not current_candidates:
            last_key = page_keys[current_status]
            if last_key is None:
                next_exhausted[current_status] = True
            else:
                next_positions[current_status] = last_key
            continue

        if len(emitted) < len(current_candidates):
            # Do not move past matching results that were read but not emitted.
            # They will be returned again on the next page.
            if emitted:
                next_positions[current_status] = _status_start_key(
                    emitted[-1], current_status
                )
            continue

        last_key = page_keys[current_status]
        if last_key is not None:
            # All matching rows from this evaluated page were emitted, so the
            # DynamoDB position is now safe even when the index has more rows.
            next_positions[current_status] = last_key
        else:
            next_exhausted[current_status] = True

    if all(next_exhausted.get(current_status, False) for current_status in statuses):
        next_state = None
    else:
        next_state = {
            "mode": "all_statuses",
            "positions": next_positions,
            "exhausted": {
                current_status: next_exhausted.get(current_status, False)
                for current_status in statuses
            },
        }
    return [alert for _, alert in page], next_state


def _status_start_key(alert: AlertInDB, current_status: str) -> dict[str, Any]:
    """Construye la clave completa de StatusCreatedIndex para una alerta."""
    return {
        "alert_id": alert.alert_id,
        "status": current_status,
        "created_at_alert": alert.created_at_alert,
    }


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
