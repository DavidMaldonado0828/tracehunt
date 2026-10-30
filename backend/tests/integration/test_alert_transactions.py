"""Pruebas de transacciones Alerts/AuditLogs contra DynamoDB Local."""

from __future__ import annotations

from collections.abc import Iterator
from datetime import datetime, timezone
import json
from typing import Any
from uuid import uuid4

import pytest

from app.core.config import get_settings
from app.repositories.alert_transactions import (
    AuditConflictError,
    assign_with_audit,
    update_status_with_audit,
)
from app.repositories.alerts import (
    AlertNotFoundError,
    AlertStateConflictError,
    create_alert,
    get_alert,
)
from app.repositories.audit_logs import append_log, build_change_key, list_logs
from app.repositories.dynamo_client import get_dynamodb_resource
from app.schemas.alerts import AlertInDB, AuditLogRecord


def _now() -> str:
    """Usa un instante UTC válido y único para los contratos de alerta."""
    return datetime.now(timezone.utc).isoformat(timespec="milliseconds").replace(
        "+00:00", "Z"
    )


def _record(
    alert_id: str,
    change_id: str,
    *,
    previous_status: str | None = "open",
    new_status: str | None = "investigating",
    action: str = "status_changed",
    changed_at: str | None = None,
) -> AuditLogRecord:
    timestamp = changed_at or _now()
    return AuditLogRecord(
        alert_id=alert_id,
        change_key=build_change_key(timestamp, change_id),
        change_id=change_id,
        actor_type="user",
        actor_id="integration-user",
        actor_email="integration@example.invalid",
        action=action,
        previous_status=previous_status,
        new_status=new_status,
        changed_at=timestamp,
        comment="integration transaction",
    )


def _delete_owned_data(alert_id: str) -> None:
    """Borra exclusivamente filas bajo el ID aleatorio que creó esta prueba."""
    resource = get_dynamodb_resource()
    audit_table = resource.Table(get_settings().audit_logs_table)
    response = audit_table.query(
        KeyConditionExpression="#alert_id = :alert_id",
        ExpressionAttributeNames={"#alert_id": "alert_id"},
        ExpressionAttributeValues={":alert_id": alert_id},
    )
    for item in response.get("Items", []):
        audit_table.delete_item(
            Key={"alert_id": alert_id, "change_key": item["change_key"]}
        )
    resource.Table(get_settings().alerts_table).delete_item(
        Key={"alert_id": alert_id}
    )


@pytest.fixture
def alert() -> Iterator[AlertInDB]:
    """Crea una alerta aislada y limpia solo sus propias filas al terminar."""
    alert_id = f"IT-ALERT-{uuid4().hex}"
    timestamp = _now()
    item = AlertInDB(
        alert_id=alert_id,
        rule_id="AUTH-001",
        title="Integration alert",
        description="Alert used by transaction integration tests.",
        severity="high",
        status="open",
        created_at=timestamp,
        created_at_alert=f"{timestamp}#{alert_id}",
        first_event_at=timestamp,
        last_event_at=timestamp,
        related_event_ids=["integration-event"],
        simulation_id="integration-simulation",
        owner_user_id="integration-owner",
        updated_at=timestamp,
    )
    create_alert(item)
    try:
        yield item
    finally:
        _delete_owned_data(alert_id)


def _type_summary(value: Any) -> Any:
    """Describe estructura y tipos sin mostrar valores del request."""
    if isinstance(value, dict):
        attribute_value_types = {
            "S", "N", "B", "BOOL", "NULL", "M", "L", "SS", "NS", "BS"
        }
        if len(value) == 1 and next(iter(value)) in attribute_value_types:
            return {"AttributeValue": next(iter(value))}
        return {key: _type_summary(child) for key, child in value.items()}
    if isinstance(value, list):
        return [_type_summary(child) for child in value]
    return type(value).__name__


@pytest.fixture
def transaction_requests() -> Iterator[list[dict[str, Any]]]:
    """Captura el body que Boto3 serializa antes de enviarlo a DynamoDB Local."""
    client = get_dynamodb_resource().meta.client
    captured: list[dict[str, Any]] = []
    event_name = "before-call.dynamodb.TransactWriteItems"
    unique_id = f"alert-transaction-test-{uuid4().hex}"

    def capture_request(**kwargs: Any) -> None:
        body = kwargs["params"].get("body")
        if isinstance(body, bytes):
            body = body.decode("utf-8")
        if isinstance(body, str):
            captured.append(json.loads(body))

    client.meta.events.register(event_name, capture_request, unique_id=unique_id)
    try:
        yield captured
    finally:
        client.meta.events.unregister(event_name, unique_id=unique_id)


def _assert_serialized_request(
    request: dict[str, Any],
    *,
    alert_id: str,
    expected_update: str,
    expected_condition: str,
    value_names: set[str],
) -> None:
    items = request["TransactItems"]
    assert len(items) == 2
    update = items[0]["Update"]
    put = items[1]["Put"]

    assert update["Key"] == {"alert_id": {"S": alert_id}}
    assert update["UpdateExpression"] == expected_update
    assert update["ConditionExpression"] == expected_condition
    assert set(update["ExpressionAttributeValues"]) == value_names
    assert all(
        set(value) == {"S"}
        for value in update["ExpressionAttributeValues"].values()
    )
    assert set(put["Item"]) == {
        "alert_id",
        "change_key",
        "change_id",
        "actor_type",
        "actor_id",
        "actor_email",
        "action",
        "previous_status",
        "new_status",
        "changed_at",
        "comment",
    }
    assert all(set(value) == {"S"} for value in put["Item"].values())
    assert put["ConditionExpression"] == (
        "attribute_not_exists(#a) AND attribute_not_exists(#k)"
    )


def test_status_change_writes_alert_and_one_audit_record(
    alert: AlertInDB,
    transaction_requests: list[dict[str, Any]],
) -> None:
    record = _record(alert.alert_id, f"change-{uuid4().hex}")
    try:
        updated = update_status_with_audit(
            alert.alert_id,
            "investigating",
            expected_status="open",
            updated_at=record.changed_at,
            audit_record=record,
        )
    except Exception:
        if transaction_requests:
            print("Request AV types:", json.dumps(_type_summary(transaction_requests[-1])))
        raise

    assert transaction_requests
    _assert_serialized_request(
        transaction_requests[-1],
        alert_id=alert.alert_id,
        expected_update="SET #s = :n, #u = :t",
        expected_condition="attribute_exists(#p) AND #s = :e",
        value_names={":n", ":e", ":t"},
    )
    assert updated.status == "investigating"
    records, _ = list_logs(alert.alert_id)
    assert len(records) == 1
    assert records[0].change_id == record.change_id


def test_state_conflict_does_not_update_or_append_audit(alert: AlertInDB) -> None:
    first_record = _record(alert.alert_id, f"change-{uuid4().hex}")
    update_status_with_audit(
        alert.alert_id,
        "investigating",
        expected_status="open",
        updated_at=first_record.changed_at,
        audit_record=first_record,
    )
    conflict_record = _record(alert.alert_id, f"change-{uuid4().hex}")

    with pytest.raises(AlertStateConflictError):
        update_status_with_audit(
            alert.alert_id,
            "resolved",
            expected_status="open",
            updated_at=conflict_record.changed_at,
            audit_record=conflict_record,
        )

    assert get_alert(alert.alert_id, consistent=True).status == "investigating"
    records, _ = list_logs(alert.alert_id)
    assert [record.change_id for record in records] == [first_record.change_id]


def test_missing_alert_does_not_write_audit() -> None:
    missing_id = f"IT-MISSING-{uuid4().hex}"
    record = _record(missing_id, f"change-{uuid4().hex}")

    with pytest.raises(AlertNotFoundError):
        update_status_with_audit(
            missing_id,
            "resolved",
            expected_status="open",
            updated_at=record.changed_at,
            audit_record=record,
        )

    records, _ = list_logs(missing_id)
    assert records == []


def test_audit_collision_rolls_back_alert_update(alert: AlertInDB) -> None:
    collision = _record(alert.alert_id, f"change-{uuid4().hex}")
    append_log(collision)

    with pytest.raises(AuditConflictError):
        update_status_with_audit(
            alert.alert_id,
            "investigating",
            expected_status="open",
            updated_at=collision.changed_at,
            audit_record=collision,
        )

    assert get_alert(alert.alert_id, consistent=True).status == "open"
    records, _ = list_logs(alert.alert_id)
    assert [record.change_id for record in records] == [collision.change_id]


def test_assignment_writes_assignee_and_audit(
    alert: AlertInDB,
    transaction_requests: list[dict[str, Any]],
) -> None:
    record = _record(
        alert.alert_id,
        f"change-{uuid4().hex}",
        previous_status=None,
        new_status=None,
        action="alert_assigned",
    )
    assigned_to = f"integration-assignee-{uuid4().hex}"
    updated = assign_with_audit(
        alert.alert_id,
        assigned_to,
        updated_at=record.changed_at,
        audit_record=record,
    )

    assert transaction_requests
    request = transaction_requests[-1]
    items = request["TransactItems"]
    update = items[0]["Update"]
    assert update["Key"] == {"alert_id": {"S": alert.alert_id}}
    assert update["UpdateExpression"] == "SET #a = :v, #u = :t"
    assert update["ConditionExpression"] == "attribute_exists(#p)"
    assert all(
        set(value) == {"S"}
        for value in update["ExpressionAttributeValues"].values()
    )
    assert updated.assigned_to == assigned_to
    records, _ = list_logs(alert.alert_id)
    assert len(records) == 1
    assert records[0].change_id == record.change_id
