"""Operaciones de persistencia para ejecuciones de simulación."""

from collections.abc import Mapping
from typing import Any

from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.repositories.dynamo_client import get_dynamodb_resource


class SimulationAlreadyExistsError(Exception):
    """Señala que ya existe una ejecución con el identificador solicitado."""


class SimulationNotFoundError(Exception):
    """Señala que no existe la ejecución que se intentó actualizar."""


def _get_simulations_table() -> Any:
    """Resuelve la tabla de simulaciones desde la configuración común."""
    return get_dynamodb_resource().Table(get_settings().simulations_table)


def _is_conditional_failure(error: ClientError) -> bool:
    """Identifica un fallo de condición de DynamoDB."""
    return (
        error.response.get("Error", {}).get("Code")
        == "ConditionalCheckFailedException"
    )


def _validate_identifier(value: str, name: str) -> None:
    """Rechaza identificadores que no sean cadenas no vacías."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{name} es obligatorio y no puede estar vacío.")


def create_simulation(
    simulation: Mapping[str, Any],
) -> dict[str, Any]:
    """Crea una simulación sin reemplazar otra con el mismo ID."""
    item = dict(simulation)
    simulation_id = item.get("simulation_id")
    _validate_identifier(simulation_id, "simulation_id")

    try:
        _get_simulations_table().put_item(
            Item=item,
            ConditionExpression="attribute_not_exists(#simulation_id)",
            ExpressionAttributeNames={
                "#simulation_id": "simulation_id",
            },
        )
    except ClientError as error:
        if _is_conditional_failure(error):
            raise SimulationAlreadyExistsError(
                "La ejecución ya existe."
            ) from None
        raise

    return item


def get_simulation(simulation_id: str) -> dict[str, Any] | None:
    """Consulta una simulación directamente por su clave primaria."""
    _validate_identifier(simulation_id, "simulation_id")

    response = _get_simulations_table().get_item(
        Key={"simulation_id": simulation_id},
    )
    item = response.get("Item")
    return dict(item) if item is not None else None


def update_simulation(
    simulation_id: str,
    changes: Mapping[str, Any],
) -> dict[str, Any]:
    """Actualiza atributos solo si la simulación todavía existe."""
    _validate_identifier(simulation_id, "simulation_id")

    values = dict(changes)
    if not values:
        raise ValueError("Debe indicarse al menos un atributo para actualizar.")
    if "simulation_id" in values:
        raise ValueError("simulation_id no se puede modificar.")

    names = {"#simulation_id": "simulation_id"}
    attribute_values: dict[str, Any] = {}
    assignments: list[str] = []

    for index, (field, value) in enumerate(values.items()):
        name_token = f"#field_{index}"
        value_token = f":value_{index}"
        names[name_token] = field
        attribute_values[value_token] = value
        assignments.append(f"{name_token} = {value_token}")

    try:
        response = _get_simulations_table().update_item(
            Key={"simulation_id": simulation_id},
            UpdateExpression="SET " + ", ".join(assignments),
            ConditionExpression="attribute_exists(#simulation_id)",
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=attribute_values,
            ReturnValues="ALL_NEW",
        )
    except ClientError as error:
        if _is_conditional_failure(error):
            raise SimulationNotFoundError(
                "La ejecución no existe."
            ) from None
        raise

    return dict(response["Attributes"])


def _query_simulations(
    *,
    index_name: str,
    key_name: str,
    key_value: str,
    limit: int,
    exclusive_start_key: Mapping[str, Any] | None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Consulta una página de un GSI y devuelve su clave de continuación."""
    _validate_identifier(key_value, key_name)

    if not 1 <= limit <= 100:
        raise ValueError("limit debe estar entre 1 y 100.")

    query: dict[str, Any] = {
        "IndexName": index_name,
        "KeyConditionExpression": "#partition_key = :partition_value",
        "ExpressionAttributeNames": {
            "#partition_key": key_name,
        },
        "ExpressionAttributeValues": {
            ":partition_value": key_value,
        },
        "Limit": limit,
        "ScanIndexForward": False,
    }
    if exclusive_start_key is not None:
        query["ExclusiveStartKey"] = dict(exclusive_start_key)

    response = _get_simulations_table().query(**query)
    items = [dict(item) for item in response.get("Items", [])]
    last_key = response.get("LastEvaluatedKey")
    return items, dict(last_key) if last_key else None


def list_simulations_by_status(
    status: str,
    *,
    limit: int = 25,
    exclusive_start_key: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Consulta una página por `StatusRequestedIndex`."""
    return _query_simulations(
        index_name="StatusRequestedIndex",
        key_name="status",
        key_value=status,
        limit=limit,
        exclusive_start_key=exclusive_start_key,
    )


def list_simulations_by_user(
    user_id: str,
    *,
    limit: int = 25,
    exclusive_start_key: Mapping[str, Any] | None = None,
) -> tuple[list[dict[str, Any]], dict[str, Any] | None]:
    """Consulta una página por `RequesterRequestedIndex`."""
    return _query_simulations(
        index_name="RequesterRequestedIndex",
        key_name="requested_by_user_id",
        key_value=user_id,
        limit=limit,
        exclusive_start_key=exclusive_start_key,
    )