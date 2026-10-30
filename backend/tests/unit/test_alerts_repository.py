"""Pruebas unitarias de consulta y paginación del repositorio de alertas."""

from datetime import datetime, timedelta, timezone
from typing import Any
from unittest.mock import Mock

import pytest

from app.repositories import alerts


def _alert_item(
    alert_id: str,
    state: str,
    created_at: datetime,
    *,
    severity: str = "high",
) -> dict[str, Any]:
    timestamp = created_at.astimezone(timezone.utc).isoformat().replace("+00:00", "Z")
    return {
        "alert_id": alert_id,
        "rule_id": "AUTH-001",
        "title": f"Alert {alert_id}",
        "description": "Repository pagination test.",
        "severity": severity,
        "status": state,
        "created_at": timestamp,
        "created_at_alert": f"{timestamp}#{alert_id}",
        "first_event_at": timestamp,
        "last_event_at": timestamp,
        "related_event_ids": [f"event-{alert_id}"],
        "simulation_id": "sim-test",
        "owner_user_id": "owner-test",
        "updated_at": timestamp,
    }


def _position(item: dict[str, Any], state: str) -> dict[str, str]:
    return {
        "alert_id": item["alert_id"],
        "status": state,
        "created_at_alert": item["created_at_alert"],
    }


class QueryTable:
    """Simula Query ordenada y paginada en StatusCreatedIndex."""

    def __init__(self, items: list[dict[str, Any]]) -> None:
        self.items = items
        self.queries: list[dict[str, Any]] = []

    def query(self, **query: Any) -> dict[str, Any]:
        self.queries.append(query)
        state = query["ExpressionAttributeValues"][":partition_value"]
        items = [item for item in self.items if item["status"] == state]
        items.sort(key=lambda item: item["created_at_alert"], reverse=True)
        start_key = query.get("ExclusiveStartKey")
        if start_key is not None:
            start_index = next(
                index
                for index, item in enumerate(items)
                if _position(item, state) == start_key
            )
            items = items[start_index + 1 :]

        page = items[: query["Limit"]]
        response: dict[str, Any] = {"Items": page}
        if len(items) > len(page) and page:
            response["LastEvaluatedKey"] = _position(page[-1], state)
        return response


@pytest.fixture
def query_table(monkeypatch: pytest.MonkeyPatch) -> QueryTable:
    base = datetime(2026, 10, 1, tzinfo=timezone.utc)
    items = [
        _alert_item("open-10", "open", base + timedelta(minutes=10)),
        _alert_item("investigating-09", "investigating", base + timedelta(minutes=9)),
        _alert_item("resolved-08", "resolved", base + timedelta(minutes=8)),
        _alert_item("open-07", "open", base + timedelta(minutes=7)),
        _alert_item("investigating-06", "investigating", base + timedelta(minutes=6)),
        _alert_item("resolved-05", "resolved", base + timedelta(minutes=5)),
        _alert_item("open-04", "open", base + timedelta(minutes=4)),
        _alert_item("investigating-03", "investigating", base + timedelta(minutes=3)),
        _alert_item("resolved-02", "resolved", base + timedelta(minutes=2)),
    ]
    table = QueryTable(items)
    monkeypatch.setattr(alerts, "_get_alerts_table", lambda: table)
    return table


def test_list_all_statuses_queries_each_status_and_merges_descending(
    query_table: QueryTable,
) -> None:
    result, cursor = alerts.list_alerts_all_statuses(limit=4)

    assert [item.alert_id for item in result] == [
        "open-10",
        "investigating-09",
        "resolved-08",
        "open-07",
    ]
    assert [query["ExpressionAttributeValues"][":partition_value"] for query in query_table.queries] == [
        "open",
        "investigating",
        "resolved",
    ]
    assert all(query["IndexName"] == "StatusCreatedIndex" for query in query_table.queries)
    assert cursor is not None


def test_list_all_statuses_pages_without_duplicates_or_omissions(
    query_table: QueryTable,
) -> None:
    cursor = None
    received: list[str] = []
    while True:
        page, cursor = alerts.list_alerts_all_statuses(
            limit=2,
            cursor_state=cursor,
        )
        received.extend(item.alert_id for item in page)
        if cursor is None:
            break

    assert received == [
        "open-10",
        "investigating-09",
        "resolved-08",
        "open-07",
        "investigating-06",
        "resolved-05",
        "open-04",
        "investigating-03",
        "resolved-02",
    ]
    assert len(received) == len(set(received))


def test_list_all_statuses_orders_equal_timestamps_by_composite_key(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    timestamp = datetime(2026, 10, 1, tzinfo=timezone.utc)
    table = QueryTable(
        [
            _alert_item("A-1", "open", timestamp),
            _alert_item("A-3", "investigating", timestamp),
            _alert_item("A-2", "resolved", timestamp),
        ]
    )
    monkeypatch.setattr(alerts, "_get_alerts_table", lambda: table)

    result, cursor = alerts.list_alerts_all_statuses(limit=3)

    assert [item.alert_id for item in result] == ["A-3", "A-2", "A-1"]
    assert cursor is None


def test_status_severity_filter_and_last_key_are_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    table = Mock()
    key = {
        "alert_id": "alert-1",
        "status": "open",
        "created_at_alert": "2026-10-01T00:00:00Z#alert-1",
    }
    table.query.return_value = {"Items": [], "LastEvaluatedKey": key}
    monkeypatch.setattr(alerts, "_get_alerts_table", lambda: table)

    items, cursor = alerts.list_alerts(
        status="open",
        severity="high",
        limit=10,
    )

    assert items == []
    assert cursor == key
    query = table.query.call_args.kwargs
    assert query["IndexName"] == "StatusCreatedIndex"
    assert query["FilterExpression"] == "#filter_severity = :filter_severity"


@pytest.mark.parametrize("limit", [0, 101])
def test_list_all_statuses_rejects_invalid_limit(
    monkeypatch: pytest.MonkeyPatch,
    limit: int,
) -> None:
    table = Mock()
    monkeypatch.setattr(alerts, "_get_alerts_table", lambda: table)

    with pytest.raises(ValueError):
        alerts.list_alerts_all_statuses(limit=limit)

    table.query.assert_not_called()
