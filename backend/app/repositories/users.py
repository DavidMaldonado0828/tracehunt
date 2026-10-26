"""Operaciones de persistencia para la tabla Users de DynamoDB."""

from datetime import datetime, timezone
from typing import Any

from botocore.exceptions import ClientError

from app.core.config import get_settings
from app.repositories.dynamo_client import get_dynamodb_resource
from app.schemas.users import UserInDB, UserUpdate, normalize_email


class UserAlreadyExistsError(Exception):
    """Señala que ya hay un usuario con la clave primaria solicitada."""


class UserNotFoundError(Exception):
    """Señala que no existe el usuario que se intentó modificar."""


def _get_users_table() -> Any:
    """Resuelve la tabla desde la configuración común para evitar clientes duplicados."""
    return get_dynamodb_resource().Table(get_settings().users_table)


def _utc_now() -> str:
    """Entrega timestamps UTC uniformes y ordenables en la representación acordada."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace("+00:00", "Z")


def _item_to_user(item: dict[str, Any]) -> UserInDB:
    """Valida lo leído de DynamoDB y omite el atributo opcional cuando no existe."""
    return UserInDB.model_validate(item)


def _user_to_item(user: UserInDB) -> dict[str, Any]:
    """Evita persistir last_login_at como NULL cuando nunca hubo inicio de sesión."""
    return user.model_dump(exclude_none=True)


def _is_conditional_failure(error: ClientError) -> bool:
    """Distingue conflictos esperados de fallos de servicio que deben propagarse."""
    return error.response.get("Error", {}).get("Code") == "ConditionalCheckFailedException"


def create_user(user: UserInDB) -> UserInDB:
    """Inserta condicionalmente por PK para que una creación no reemplace otra."""
    try:
        _get_users_table().put_item(
            Item=_user_to_item(user),
            ConditionExpression="attribute_not_exists(#email_key)",
            ExpressionAttributeNames={"#email_key": "email_normalized"},
        )
    except ClientError as error:
        if _is_conditional_failure(error):
            raise UserAlreadyExistsError("El usuario ya existe.") from None
        raise
    return user


def get_by_email(email: str, consistent: bool = False) -> UserInDB | None:
    """Lee por la PK aprobada tras aplicar la misma normalización del schema."""
    response = _get_users_table().get_item(
        Key={"email_normalized": normalize_email(email)},
        ConsistentRead=consistent,
    )
    item = response.get("Item")
    return _item_to_user(item) if item is not None else None


def get_by_user_id(user_id: str) -> UserInDB | None:
    """Consulta el GSI UserIdIndex; su resultado es eventualmente consistente."""
    response = _get_users_table().query(
        IndexName="UserIdIndex",
        KeyConditionExpression="#user_id = :user_id",
        ExpressionAttributeNames={"#user_id": "user_id"},
        ExpressionAttributeValues={":user_id": user_id},
        Limit=1,
    )
    items = response.get("Items", [])
    return _item_to_user(items[0]) if items else None


def list_users() -> list[UserInDB]:
    """Recorre páginas del Scan solicitado para la lista administrativa."""
    table = _get_users_table()
    users: list[UserInDB] = []
    scan_kwargs: dict[str, Any] = {}

    while True:
        response = table.scan(**scan_kwargs)
        users.extend(_item_to_user(item) for item in response.get("Items", []))
        last_key = response.get("LastEvaluatedKey")
        if not last_key:
            return users
        scan_kwargs["ExclusiveStartKey"] = last_key


def update_user(email: str, changes: UserUpdate) -> UserInDB:
    """Actualiza solo campos permitidos y exige que la cuenta exista."""
    values = changes.model_dump(exclude_unset=True)
    names = {"#email_key": "email_normalized", "#updated_at": "updated_at"}
    attribute_values: dict[str, Any] = {":updated_at": _utc_now()}
    assignments = ["#updated_at = :updated_at"]

    for index, (field, value) in enumerate(values.items()):
        # Los alias impiden que nombres reservados, como role o status, alteren la expresión DynamoDB.
        name_token = f"#field_{index}"
        value_token = f":value_{index}"
        names[name_token] = field
        attribute_values[value_token] = value
        assignments.append(f"{name_token} = {value_token}")

    try:
        response = _get_users_table().update_item(
            Key={"email_normalized": normalize_email(email)},
            UpdateExpression="SET " + ", ".join(assignments),
            ConditionExpression="attribute_exists(#email_key)",
            ExpressionAttributeNames=names,
            ExpressionAttributeValues=attribute_values,
            ReturnValues="ALL_NEW",
        )
    except ClientError as error:
        if _is_conditional_failure(error):
            raise UserNotFoundError("El usuario no existe.") from None
        raise
    return _item_to_user(response["Attributes"])


def touch_last_login(email: str) -> None:
    """Registra el acceso y su actualización con una sola escritura condicional."""
    now = _utc_now()
    try:
        _get_users_table().update_item(
            Key={"email_normalized": normalize_email(email)},
            UpdateExpression="SET #last_login_at = :now, #updated_at = :now",
            ConditionExpression="attribute_exists(#email_key)",
            ExpressionAttributeNames={
                "#email_key": "email_normalized",
                "#last_login_at": "last_login_at",
                "#updated_at": "updated_at",
            },
            ExpressionAttributeValues={":now": now},
        )
    except ClientError as error:
        if _is_conditional_failure(error):
            raise UserNotFoundError("El usuario no existe.") from None
        raise
