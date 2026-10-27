"""Pruebas unitarias del repositorio de simulaciones."""

from unittest.mock import Mock

import pytest
from botocore.exceptions import ClientError

from app.repositories import simulations


@pytest.fixture
def table(monkeypatch: pytest.MonkeyPatch) -> Mock:
    """Sustituye la tabla DynamoDB por un mock."""
    mocked_table = Mock()
    monkeypatch.setattr(
        simulations,
        "_get_simulations_table",
        lambda: mocked_table,
    )
    return mocked_table


def conditional_failure() -> ClientError:
    """Crea el error de condición que devuelve DynamoDB."""
    return ClientError(
        {"Error": {"Code": "ConditionalCheckFailedException"}},
        "PutItem",
    )


def test_create_simulation_puts_item_conditionally(table: Mock) -> None:
    item = {"simulation_id": "sim-1", "status": "pending"}

    result = simulations.create_simulation(item)

    assert result == item
    table.put_item.assert_called_once_with(
        Item=item,
        ConditionExpression="attribute_not_exists(#simulation_id)",
        ExpressionAttributeNames={"#simulation_id": "simulation_id"},
    )


@pytest.mark.parametrize(
    "item",
    [{}, {"simulation_id": ""}, {"simulation_id": 1}],
)
def test_create_simulation_rejects_invalid_id(
    table: Mock,
    item: dict[str, object],
) -> None:
    with pytest.raises(ValueError):
        simulations.create_simulation(item)

    table.put_item.assert_not_called()


def test_create_simulation_translates_duplicate_id(table: Mock) -> None:
    table.put_item.side_effect = conditional_failure()

    with pytest.raises(simulations.SimulationAlreadyExistsError):
        simulations.create_simulation({"simulation_id": "sim-1"})


def test_create_simulation_propagates_unexpected_client_error(
    table: Mock,
) -> None:
    table.put_item.side_effect = ClientError(
        {"Error": {"Code": "InternalServerError"}},
        "PutItem",
    )

    with pytest.raises(ClientError):
        simulations.create_simulation({"simulation_id": "sim-1"})


def test_get_simulation_returns_existing_item(table: Mock) -> None:
    item = {"simulation_id": "sim-1", "status": "pending"}
    table.get_item.return_value = {"Item": item}

    assert simulations.get_simulation("sim-1") == item
    table.get_item.assert_called_once_with(
        Key={"simulation_id": "sim-1"},
    )


def test_get_simulation_returns_none_when_missing(table: Mock) -> None:
    table.get_item.return_value = {}

    assert simulations.get_simulation("missing") is None


def test_get_simulation_rejects_empty_id(table: Mock) -> None:
    with pytest.raises(ValueError):
        simulations.get_simulation(" ")

    table.get_item.assert_not_called()


def test_update_simulation_uses_atomic_existence_condition(
    table: Mock,
) -> None:
    updated = {"simulation_id": "sim-1", "status": "running"}
    table.update_item.return_value = {"Attributes": updated}

    result = simulations.update_simulation(
        "sim-1",
        {"status": "running"},
    )

    assert result == updated
    table.update_item.assert_called_once_with(
        Key={"simulation_id": "sim-1"},
        UpdateExpression="SET #field_0 = :value_0",
        ConditionExpression="attribute_exists(#simulation_id)",
        ExpressionAttributeNames={
            "#simulation_id": "simulation_id",
            "#field_0": "status",
        },
        ExpressionAttributeValues={":value_0": "running"},
        ReturnValues="ALL_NEW",
    )


def test_update_simulation_translates_missing_record(table: Mock) -> None:
    table.update_item.side_effect = conditional_failure()

    with pytest.raises(simulations.SimulationNotFoundError):
        simulations.update_simulation(
            "missing",
            {"status": "running"},
        )


@pytest.mark.parametrize(
    "changes",
    [{}, {"simulation_id": "sim-2"}],
)
def test_update_simulation_rejects_invalid_changes(
    table: Mock,
    changes: dict[str, str],
) -> None:
    with pytest.raises(ValueError):
        simulations.update_simulation("sim-1", changes)

    table.update_item.assert_not_called()


@pytest.mark.parametrize("limit", [0, 101])
def test_queries_reject_invalid_limit(
    table: Mock,
    limit: int,
) -> None:
    with pytest.raises(ValueError):
        simulations.list_simulations_by_status("pending", limit=limit)

    with pytest.raises(ValueError):
        simulations.list_simulations_by_user("user-1", limit=limit)

    table.query.assert_not_called()


def test_list_simulations_by_status_uses_index_and_returns_cursor(
    table: Mock,
) -> None:
    items = [{"simulation_id": "sim-1", "status": "pending"}]
    next_key = {
        "simulation_id": "sim-1",
        "status": "pending",
        "requested_at_sim": "2026-01-01T00:00:00Z#sim-1",
    }
    table.query.return_value = {
        "Items": items,
        "LastEvaluatedKey": next_key,
    }

    result_items, cursor = simulations.list_simulations_by_status(
        "pending",
        limit=10,
    )

    assert result_items == items
    assert cursor == next_key
    table.query.assert_called_once_with(
        IndexName="StatusRequestedIndex",
        KeyConditionExpression="#partition_key = :partition_value",
        ExpressionAttributeNames={"#partition_key": "status"},
        ExpressionAttributeValues={":partition_value": "pending"},
        Limit=10,
        ScanIndexForward=False,
    )


def test_list_simulations_by_user_uses_index_and_cursor(
    table: Mock,
) -> None:
    items = [
        {
            "simulation_id": "sim-1",
            "requested_by_user_id": "user-1",
        }
    ]
    next_key = {
        "simulation_id": "sim-1",
        "requested_by_user_id": "user-1",
        "requested_at_sim": "2026-01-01T00:00:00Z#sim-1",
    }
    start_key = {
        "simulation_id": "sim-0",
        "requested_by_user_id": "user-1",
        "requested_at_sim": "2025-12-31T00:00:00Z#sim-0",
    }
    table.query.return_value = {
        "Items": items,
        "LastEvaluatedKey": next_key,
    }

    result_items, cursor = simulations.list_simulations_by_user(
        "user-1",
        limit=10,
        exclusive_start_key=start_key,
    )

    assert result_items == items
    assert cursor == next_key
    table.query.assert_called_once_with(
        IndexName="RequesterRequestedIndex",
        KeyConditionExpression="#partition_key = :partition_value",
        ExpressionAttributeNames={
            "#partition_key": "requested_by_user_id",
        },
        ExpressionAttributeValues={":partition_value": "user-1"},
        Limit=10,
        ScanIndexForward=False,
        ExclusiveStartKey=start_key,
    )


def test_query_returns_none_cursor_when_there_are_no_more_pages(
    table: Mock,
) -> None:
    table.query.return_value = {"Items": []}

    items, cursor = simulations.list_simulations_by_status("failed")

    assert items == []
    assert cursor is None