"""Pruebas unitarias del motor de detección."""

from datetime import datetime, timedelta, timezone

import pytest

from app.detectors.engine import (
    filter_events_by_window,
    sort_events,
)


UTC = timezone.utc

START = datetime(2026, 10, 29, 10, 0, tzinfo=UTC)
END = START + timedelta(minutes=5)


def create_event(event_id, timestamp):
    return {
        "event_id": event_id,
        "timestamp": timestamp,
        "event_type": "login",
        "result": "failure",
    }


def test_sort_events_chronologically():
    events = [
        create_event("EVT-003", START + timedelta(minutes=3)),
        create_event("EVT-001", START),
        create_event("EVT-002", START + timedelta(minutes=1)),
    ]

    result = sort_events(events)

    assert [event["event_id"] for event in result] == [
        "EVT-001",
        "EVT-002",
        "EVT-003",
    ]


def test_sort_events_uses_event_id_as_tiebreaker():
    events = [
        create_event("EVT-003", START),
        create_event("EVT-001", START),
        create_event("EVT-002", START),
    ]

    result = sort_events(events)

    assert [event["event_id"] for event in result] == [
        "EVT-001",
        "EVT-002",
        "EVT-003",
    ]


def test_sort_events_normalizes_different_timezones():
    events = [
        create_event(
            "EVT-002",
            "2026-10-29T07:00:00-05:00",
        ),
        create_event(
            "EVT-001",
            "2026-10-29T11:00:00+00:00",
        ),
    ]

    result = sort_events(events)

    assert [event["event_id"] for event in result] == [
        "EVT-001",
        "EVT-002",
    ]


def test_sort_events_rejects_naive_timestamp():
    events = [
        create_event(
            "EVT-001",
            datetime(2026, 10, 29, 10, 0),
        )
    ]

    with pytest.raises(ValueError, match="zona horaria"):
        sort_events(events)


def test_sort_events_rejects_invalid_timestamp():
    events = [
        create_event("EVT-001", "fecha-invalida")
    ]

    with pytest.raises(ValueError, match="Timestamp inválido"):
        sort_events(events)


def test_sort_events_rejects_missing_event_id():
    events = [
        {"timestamp": START}
    ]

    with pytest.raises(ValueError, match="event_id"):
        sort_events(events)


def test_filter_window_includes_start_boundary():
    events = [
        create_event("EVT-001", START)
    ]

    result = filter_events_by_window(events, START, END)

    assert len(result) == 1


def test_filter_window_excludes_end_boundary():
    events = [
        create_event("EVT-001", END)
    ]

    result = filter_events_by_window(events, START, END)

    assert len(result) == 0


def test_filter_window_includes_events_inside_boundaries():
    events = [
        create_event("EVT-001", START + timedelta(seconds=1)),
        create_event("EVT-002", START + timedelta(minutes=2)),
        create_event("EVT-003", END - timedelta(seconds=1)),
    ]

    result = filter_events_by_window(events, START, END)

    assert len(result) == 3


def test_filter_window_returns_events_in_chronological_order():
    events = [
        create_event("EVT-003", START + timedelta(minutes=3)),
        create_event("EVT-001", START + timedelta(minutes=1)),
        create_event("EVT-002", START + timedelta(minutes=2)),
    ]

    result = filter_events_by_window(events, START, END)

    assert [event["event_id"] for event in result] == [
        "EVT-001",
        "EVT-002",
        "EVT-003",
    ]


def test_filter_window_rejects_invalid_period():
    with pytest.raises(ValueError, match="anterior"):
        filter_events_by_window(events=[], start=END, end=START)


def test_filter_window_rejects_naive_start():
    naive_start = datetime(2026, 10, 29, 10, 0)

    with pytest.raises(ValueError, match="zona horaria"):
        filter_events_by_window([], naive_start, END)


def test_filter_window_accepts_iso_utc_strings():
    events = [
        create_event("EVT-001", "2026-10-29T10:02:00Z")
    ]

    result = filter_events_by_window(
        events,
        "2026-10-29T10:00:00Z",
        "2026-10-29T10:05:00Z",
    )

    assert len(result) == 1