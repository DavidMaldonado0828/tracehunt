"""Pruebas unitarias para EventsRepository."""

from unittest.mock import Mock

import pytest

from app.repositories.events import (
    EventsRepository,
    UnprocessedEventsError,
)


@pytest.fixture
def dynamodb_client():
    """Crea un cliente DynamoDB simulado."""
    return Mock()


@pytest.fixture
def repository(dynamodb_client):
    """Crea el repositorio sin realizar esperas reales."""
    return EventsRepository(
        client=dynamodb_client,
        table_name="Events",
        max_retries=5,
        initial_backoff_seconds=0.5,
        max_backoff_seconds=8.0,
        sleep=Mock(),
    )


def create_events(quantity):
    """Genera eventos ficticios para las pruebas."""
    return [
        {
            "event_id": f"event-{index}",
            "event_type": "login",
            "result": "success",
        }
        for index in range(quantity)
    ]


def test_save_many_with_one_event(repository, dynamodb_client):
    events = create_events(1)

    dynamodb_client.batch_write_item.return_value = {}

    repository.save_many(events)

    dynamodb_client.batch_write_item.assert_called_once()

    request = dynamodb_client.batch_write_item.call_args.kwargs[
        "RequestItems"
    ]

    assert len(request["Events"]) == 1


def test_save_many_with_25_events(repository, dynamodb_client):
    events = create_events(25)

    dynamodb_client.batch_write_item.return_value = {}

    repository.save_many(events)

    dynamodb_client.batch_write_item.assert_called_once()

    request = dynamodb_client.batch_write_item.call_args.kwargs[
        "RequestItems"
    ]

    assert len(request["Events"]) == 25


def test_save_many_splits_batches_over_25(
    repository,
    dynamodb_client,
):
    events = create_events(63)

    dynamodb_client.batch_write_item.return_value = {}

    repository.save_many(events)

    assert dynamodb_client.batch_write_item.call_count == 3

    batch_sizes = [
        len(call.kwargs["RequestItems"]["Events"])
        for call in dynamodb_client.batch_write_item.call_args_list
    ]

    assert batch_sizes == [25, 25, 13]


def test_retries_only_unprocessed_items(
    repository,
    dynamodb_client,
):
    events = create_events(3)

    first_pending_item = {
        "PutRequest": {
            "Item": events[1],
        }
    }

    dynamodb_client.batch_write_item.side_effect = [
        {
            "UnprocessedItems": {
                "Events": [first_pending_item],
            }
        },
        {},
    ]

    repository.save_many(events)

    assert dynamodb_client.batch_write_item.call_count == 2

    first_request = (
        dynamodb_client.batch_write_item.call_args_list[0]
        .kwargs["RequestItems"]["Events"]
    )

    second_request = (
        dynamodb_client.batch_write_item.call_args_list[1]
        .kwargs["RequestItems"]["Events"]
    )

    assert len(first_request) == 3
    assert second_request == [first_pending_item]


def test_raises_error_when_retries_are_exhausted(
    dynamodb_client,
):
    sleep = Mock()

    repository = EventsRepository(
        client=dynamodb_client,
        table_name="Events",
        max_retries=2,
        initial_backoff_seconds=0.5,
        max_backoff_seconds=8.0,
        sleep=sleep,
    )

    events = create_events(1)

    pending_item = {
        "PutRequest": {
            "Item": events[0],
        }
    }

    dynamodb_client.batch_write_item.return_value = {
        "UnprocessedItems": {
            "Events": [pending_item],
        }
    }

    with pytest.raises(UnprocessedEventsError) as error:
        repository.save_many(events)

    assert error.value.pending_count == 1
    assert error.value.attempts == 3
    assert dynamodb_client.batch_write_item.call_count == 3
    assert sleep.call_count == 2


def test_save_many_with_empty_list_does_not_call_dynamodb(
    repository,
    dynamodb_client,
):
    repository.save_many([])

    dynamodb_client.batch_write_item.assert_not_called()