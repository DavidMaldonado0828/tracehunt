"""Pruebas unitarias del servicio de simulaciones."""

from datetime import datetime, timezone
from unittest.mock import Mock

import pytest
from fastapi import HTTPException

from app.repositories.events import UnprocessedEventsError
from app.repositories.simulations import (
    SimulationAlreadyExistsError,
    SimulationNotFoundError,
)
from app.schemas.simulations import SimulationCreate
from app.services import simulation_service

from typing import Any

@pytest.fixture
def request_data() -> SimulationCreate:
    """Solicitud válida para las pruebas."""
    return SimulationCreate(
        requested_event_count=30,
        period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 1, 2, tzinfo=timezone.utc),
        seed=123,
    )


@pytest.fixture
def simulation_item() -> dict[str, object]:
    """Elemento básico persistido en Simulations."""
    return {
        "simulation_id": "SIM-test",
        "status": "pending",
        "requested_at": "2026-01-01T00:00:00+00:00",
        "requested_at_sim": "2026-01-01T00:00:00+00:00#SIM-test",
        "period_start": "2026-01-01T00:00:00+00:00",
        "period_end": "2026-01-02T00:00:00+00:00",
        "requested_event_count": 30,
        "generated_event_count": 0,
        "processed_event_count": 0,
        "created_alert_count": 0,
        "requested_by_user_id": "user-1",
        "idempotency_key": "request-1",
        "request_fingerprint": "fingerprint-1",
        "seed": 123,
    }


def test_create_simulation_request_persists_normalized_item(
    request_data: SimulationCreate,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_mock = Mock(side_effect=lambda item: item)
    monkeypatch.setattr(
        simulation_service,
        "create_simulation",
        create_mock,
    )

    result = simulation_service.create_simulation_request(
        request_data,
        requested_by_user_id=" user-1 ",
        idempotency_key=" request-1 ",
        requested_by_email=" analyst@example.com ",
    )

    create_mock.assert_called_once()
    persisted = create_mock.call_args.args[0]

    assert result == persisted
    assert persisted["requested_by_user_id"] == "user-1"
    assert persisted["idempotency_key"] == "request-1"
    assert persisted["requested_by_email"] == "analyst@example.com"
    assert persisted["requested_event_count"] == 30
    assert persisted["seed"] == 123
    assert persisted["period_start"] == "2026-01-01T00:00:00+00:00"
    assert persisted["period_end"] == "2026-01-02T00:00:00+00:00"
    assert persisted["request_fingerprint"]


def test_create_simulation_request_generates_seed_when_absent(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = SimulationCreate(
        requested_event_count=30,
        period_start=datetime(2026, 1, 1, tzinfo=timezone.utc),
        period_end=datetime(2026, 1, 2, tzinfo=timezone.utc),
        seed=None,
    )
    create_mock = Mock(side_effect=lambda item: item)
    monkeypatch.setattr(
        simulation_service,
        "create_simulation",
        create_mock,
    )
    monkeypatch.setattr(
        simulation_service.secrets,
        "randbits",
        lambda _: 987654,
    )

    result = simulation_service.create_simulation_request(
        request,
        requested_by_user_id="user-1",
        idempotency_key="request-1",
    )

    assert result["seed"] == 987654


@pytest.mark.parametrize(
    ("user_id", "key"),
    [
        (" ", "request-1"),
        ("user-1", " "),
        ("user-1", "x" * 201),
    ],
)
def test_create_simulation_request_rejects_invalid_identifiers(
    request_data: SimulationCreate,
    user_id: str,
    key: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_mock = Mock()
    monkeypatch.setattr(
        simulation_service,
        "create_simulation",
        create_mock,
    )

    with pytest.raises(ValueError):
        simulation_service.create_simulation_request(
            request_data,
            requested_by_user_id=user_id,
            idempotency_key=key,
        )

    create_mock.assert_not_called()


def test_create_simulation_request_rejects_non_string_key(
    request_data: SimulationCreate,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    create_mock = Mock()
    monkeypatch.setattr(
        simulation_service,
        "create_simulation",
        create_mock,
    )

    with pytest.raises(ValueError):
        simulation_service.create_simulation_request(
            request_data,
            requested_by_user_id="user-1",
            idempotency_key=None,  # type: ignore[arg-type]
        )

    create_mock.assert_not_called()


def test_same_idempotency_key_returns_existing_simulation(
    request_data: SimulationCreate,
    simulation_item: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    fingerprint = simulation_service._request_fingerprint(request_data)
    existing = {
        **simulation_item,
        "request_fingerprint": fingerprint,
    }

    monkeypatch.setattr(
        simulation_service,
        "create_simulation",
        Mock(side_effect=SimulationAlreadyExistsError()),
    )
    get_mock = Mock(return_value=existing)
    monkeypatch.setattr(simulation_service, "get_simulation", get_mock)

    result = simulation_service.create_simulation_request(
        request_data,
        requested_by_user_id="user-1",
        idempotency_key="request-1",
    )

    assert result == existing
    get_mock.assert_called_once_with(
        simulation_service._simulation_id("user-1", "request-1")
    )


def test_same_key_with_different_parameters_returns_conflict(
    request_data: SimulationCreate,
    simulation_item: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        simulation_service,
        "create_simulation",
        Mock(side_effect=SimulationAlreadyExistsError()),
    )
    monkeypatch.setattr(
        simulation_service,
        "get_simulation",
        Mock(return_value=simulation_item),
    )

    with pytest.raises(HTTPException) as error:
        simulation_service.create_simulation_request(
            request_data,
            requested_by_user_id="user-1",
            idempotency_key="request-1",
        )

    assert error.value.status_code == 409


def test_duplicate_without_readable_record_returns_service_unavailable(
    request_data: SimulationCreate,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        simulation_service,
        "create_simulation",
        Mock(side_effect=SimulationAlreadyExistsError()),
    )
    monkeypatch.setattr(
        simulation_service,
        "get_simulation",
        Mock(return_value=None),
    )

    with pytest.raises(HTTPException) as error:
        simulation_service.create_simulation_request(
            request_data,
            requested_by_user_id="user-1",
            idempotency_key="request-1",
        )

    assert error.value.status_code == 503


def test_get_simulation_status_returns_owned_simulation(
    simulation_item: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        simulation_service,
        "get_simulation",
        Mock(return_value=simulation_item),
    )

    result = simulation_service.get_simulation_status(
        "SIM-test",
        requested_by_user_id="user-1",
    )

    assert result == simulation_item


def test_get_simulation_status_hides_other_users_simulation(
    simulation_item: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        simulation_service,
        "get_simulation",
        Mock(return_value=simulation_item),
    )

    with pytest.raises(HTTPException) as error:
        simulation_service.get_simulation_status(
            "SIM-test",
            requested_by_user_id="user-2",
        )

    assert error.value.status_code == 404


def test_admin_can_read_another_users_simulation(
    simulation_item: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        simulation_service,
        "get_simulation",
        Mock(return_value=simulation_item),
    )

    result = simulation_service.get_simulation_status(
        "SIM-test",
        requested_by_user_id="admin-1",
        is_admin=True,
    )

    assert result == simulation_item


def test_get_simulation_status_returns_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        simulation_service,
        "get_simulation",
        Mock(return_value=None),
    )

    with pytest.raises(HTTPException) as error:
        simulation_service.get_simulation_status(
            "missing",
            requested_by_user_id="user-1",
        )

    assert error.value.status_code == 404


def test_transition_pending_to_running_sets_started_at(
    simulation_item: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        simulation_service,
        "get_simulation",
        Mock(return_value=simulation_item),
    )
    update_mock = Mock(return_value={"status": "running"})
    monkeypatch.setattr(
        simulation_service,
        "update_simulation",
        update_mock,
    )

    result = simulation_service.transition_simulation(
        "SIM-test",
        new_status="running",
    )

    assert result == {"status": "running"}
    changes = update_mock.call_args.args[1]
    assert changes["status"] == "running"
    assert datetime.fromisoformat(changes["started_at"]).tzinfo is not None


def test_transition_to_terminal_state_sets_finished_at(
    simulation_item: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    running = {**simulation_item, "status": "running"}
    monkeypatch.setattr(
        simulation_service,
        "get_simulation",
        Mock(return_value=running),
    )
    update_mock = Mock(return_value={"status": "completed"})
    monkeypatch.setattr(
        simulation_service,
        "update_simulation",
        update_mock,
    )

    simulation_service.transition_simulation(
        "SIM-test",
        new_status="completed",
        changes={"generated_event_count": 30},
    )

    changes = update_mock.call_args.args[1]
    assert changes["status"] == "completed"
    assert changes["generated_event_count"] == 30
    assert datetime.fromisoformat(changes["finished_at"]).tzinfo is not None


def test_transition_rejects_unknown_status(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    get_mock = Mock()
    update_mock = Mock()
    monkeypatch.setattr(simulation_service, "get_simulation", get_mock)
    monkeypatch.setattr(simulation_service, "update_simulation", update_mock)

    with pytest.raises(ValueError):
        simulation_service.transition_simulation(
            "SIM-test",
            new_status="unknown",
        )

    get_mock.assert_not_called()
    update_mock.assert_not_called()


def test_transition_rejects_invalid_state_change(
    simulation_item: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        simulation_service,
        "get_simulation",
        Mock(return_value=simulation_item),
    )
    update_mock = Mock()
    monkeypatch.setattr(
        simulation_service,
        "update_simulation",
        update_mock,
    )

    with pytest.raises(ValueError):
        simulation_service.transition_simulation(
            "SIM-test",
            new_status="completed",
        )

    update_mock.assert_not_called()


def test_transition_missing_simulation_raises_not_found(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setattr(
        simulation_service,
        "get_simulation",
        Mock(return_value=None),
    )

    with pytest.raises(SimulationNotFoundError):
        simulation_service.transition_simulation(
            "missing",
            new_status="running",
        )


class FakeEventsRepository:
    """Repositorio falso que registra las llamadas de escritura."""

    MAX_BATCH_SIZE = 25

    def __init__(self) -> None:
        self.batches: list[list[dict[str, Any]]] = []

    def save_many(self, events: list[dict[str, Any]]) -> None:
        self.batches.append(events)


def _generated_events(count: int) -> list[dict[str, Any]]:
    return [
        {"event_id": f"event-{index}", "sequence": index}
        for index in range(count)
    ]


def test_execute_simulation_writes_batches_of_at_most_25(
    simulation_item: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    running = {
        **simulation_item,
        "status": "running",
        "started_at": "2026-01-01T00:00:00+00:00",
    }
    completed = {
        **running,
        "status": "completed",
        "generated_event_count": 30,
    }

    monkeypatch.setattr(
        simulation_service,
        "get_simulation",
        Mock(return_value=simulation_item),
    )
    monkeypatch.setattr(
        simulation_service,
        "transition_simulation",
        Mock(
            side_effect=[
                running,
                completed,
            ]
        ),
    )
    monkeypatch.setattr(
        simulation_service,
        "generate_events",
        Mock(
            return_value=Mock(
                events=_generated_events(30),
                effective_seed=123,
            )
        ),
    )
    update_count_mock = Mock()
    monkeypatch.setattr(
        simulation_service,
        "_update_generated_count",
        update_count_mock,
    )

    repository = FakeEventsRepository()

    result = simulation_service.execute_simulation(
        "SIM-test",
        events_repository=repository,  # type: ignore[arg-type]
    )

    assert result["status"] == "completed"
    assert [len(batch) for batch in repository.batches] == [25, 5]
    assert repository.batches[0][0] == {
        "event_id": {"S": "event-0"},
        "sequence": {"N": "0"},
    }
    assert update_count_mock.call_count == 2


def test_execute_simulation_rejects_non_pending_record(
    simulation_item: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    completed = {**simulation_item, "status": "completed"}
    monkeypatch.setattr(
        simulation_service,
        "get_simulation",
        Mock(return_value=completed),
    )
    transition_mock = Mock()
    monkeypatch.setattr(
        simulation_service,
        "transition_simulation",
        transition_mock,
    )

    with pytest.raises(ValueError):
        simulation_service.execute_simulation("SIM-test")

    transition_mock.assert_not_called()


def test_execute_simulation_records_confirmed_items_on_partial_write(
    simulation_item: dict[str, object],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    running = {
        **simulation_item,
        "status": "running",
        "started_at": "2026-01-01T00:00:00+00:00",
    }

    monkeypatch.setattr(
        simulation_service,
        "get_simulation",
        Mock(
            side_effect=[
                simulation_item,
                running,
            ]
        ),
    )
    transition_mock = Mock(return_value=running)
    monkeypatch.setattr(
        simulation_service,
        "transition_simulation",
        transition_mock,
    )
    monkeypatch.setattr(
        simulation_service,
        "generate_events",
        Mock(
            return_value=Mock(
                events=_generated_events(3),
                effective_seed=123,
            )
        ),
    )

    repository = FakeEventsRepository()
    repository.save_many = Mock(
        side_effect=UnprocessedEventsError(
            pending_count=1,
            attempts=6,
        )
    )

    update_count_mock = Mock()
    monkeypatch.setattr(
        simulation_service,
        "_update_generated_count",
        update_count_mock,
    )

    with pytest.raises(UnprocessedEventsError):
        simulation_service.execute_simulation(
            "SIM-test",
            events_repository=repository,  # type: ignore[arg-type]
        )

    update_count_mock.assert_called_once_with("SIM-test", 2)
    assert transition_mock.call_args.kwargs["new_status"] == "partial"
    assert transition_mock.call_args.kwargs["changes"]["generated_event_count"] == 2
    assert (
        transition_mock.call_args.kwargs["changes"]["error_summary"]
        == "La ejecución no pudo completarse. "
        "Tipo de error: UnprocessedEventsError."
    )