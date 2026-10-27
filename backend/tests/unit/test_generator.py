"""Pruebas unitarias del generador de eventos."""

from datetime import datetime, timedelta, timezone
from ipaddress import ip_address, ip_network
from typing import Any

import pytest
from pydantic import ValidationError

from app.schemas.simulations import SimulationCreate
from app.simulator.generator import generate_events


PERIOD_START = datetime(2026, 1, 1, tzinfo=timezone.utc)
PERIOD_END = PERIOD_START + timedelta(days=1)
INGESTED_AT = datetime(2026, 1, 2, tzinfo=timezone.utc)


def make_request(
    *,
    count: int = 30,
    seed: int | None = 12345,
    start: datetime = PERIOD_START,
    end: datetime = PERIOD_END,
) -> SimulationCreate:
    return SimulationCreate(
        requested_event_count=count,
        period_start=start,
        period_end=end,
        seed=seed,
    )


def parse_timestamp(value: str) -> datetime:
    return datetime.fromisoformat(value.replace("Z", "+00:00"))


def test_generates_exact_count_and_stable_sequential_ids() -> None:
    batch = generate_events(
        "sim-123",
        make_request(count=30),
        ingested_at=INGESTED_AT,
    )

    assert len(batch.events) == 30
    assert [
        event["event_id"] for event in batch.events
    ] == [
        f"SIM-sim-123-EVT-{position:06d}"
        for position in range(1, 31)
    ]


def test_generated_events_match_events_table_fields() -> None:
    batch = generate_events(
        "sim-123",
        make_request(),
        ingested_at=INGESTED_AT,
    )

    required_fields = {
        "event_id",
        "event_type",
        "timestamp",
        "ingested_at",
        "username",
        "username_key",
        "source_ip",
        "result",
        "date_bucket",
        "timestamp_event",
        "simulation_id",
        "data_source",
        "scenario_type",
    }

    for event in batch.events:
        assert set(event) == required_fields
        assert event["event_type"] == "login"
        assert event["data_source"] == "simulator"
        assert event["simulation_id"] == "sim-123"
        assert event["timestamp_event"] == (
            f"{event['timestamp']}#{event['event_id']}"
        )


def test_timestamps_are_inside_requested_half_open_period() -> None:
    batch = generate_events(
        "sim-123",
        make_request(),
        ingested_at=INGESTED_AT,
    )

    timestamps = [parse_timestamp(event["timestamp"]) for event in batch.events]

    assert all(PERIOD_START <= timestamp < PERIOD_END for timestamp in timestamps)
    assert timestamps == sorted(timestamps)


def test_timestamps_and_date_buckets_are_utc_and_consistent() -> None:
    batch = generate_events(
        "sim-123",
        make_request(),
        ingested_at=INGESTED_AT,
    )

    for event in batch.events:
        timestamp = parse_timestamp(event["timestamp"])

        assert timestamp.utcoffset() == timedelta(0)
        assert event["date_bucket"] == f"DATE#{timestamp.date().isoformat()}"
        assert event["ingested_at"] == "2026-01-02T00:00:00.000000Z"


def test_generated_ips_are_reserved_for_documentation() -> None:
    reserved_ranges = (
        ip_network("192.0.2.0/24"),
        ip_network("198.51.100.0/24"),
        ip_network("203.0.113.0/24"),
    )
    batch = generate_events(
        "sim-123",
        make_request(),
        ingested_at=INGESTED_AT,
    )

    for event in batch.events:
        address = ip_address(event["source_ip"])
        assert any(address in network for network in reserved_ranges)


def test_includes_each_active_scenario_and_fills_with_normal_traffic() -> None:
    batch = generate_events(
        "sim-123",
        make_request(count=30),
        ingested_at=INGESTED_AT,
    )
    event_counts: dict[str, int] = {}
    for event in batch.events:
        scenario_type = event["scenario_type"]
        event_counts[scenario_type] = event_counts.get(scenario_type, 0) + 1

    assert event_counts["auth_001_repeated_failures"] == 5
    assert event_counts["auth_002_multiple_accounts"] == 5
    assert event_counts["auth_003_failures_then_success"] == 6
    # 16 eventos de reglas activas; los otros 14 son tráfico normal.
    assert event_counts["normal_traffic"] == 14
    assert "auth_004_disabled" not in event_counts


def test_auth_001_pattern_stays_within_five_minute_window() -> None:
    batch = generate_events(
        "sim-123",
        make_request(),
        ingested_at=INGESTED_AT,
    )
    events = [
        event
        for event in batch.events
        if event["scenario_type"] == "auth_001_repeated_failures"
    ]

    assert len(events) == 5
    assert {event["result"] for event in events} == {"failure"}
    assert len({event["username_key"] for event in events}) == 1
    assert len({event["source_ip"] for event in events}) == 1

    timestamps = [parse_timestamp(event["timestamp"]) for event in events]
    assert max(timestamps) - min(timestamps) < timedelta(minutes=5)


def test_auth_002_pattern_has_five_accounts_within_ten_minutes() -> None:
    batch = generate_events(
        "sim-123",
        make_request(),
        ingested_at=INGESTED_AT,
    )
    events = [
        event
        for event in batch.events
        if event["scenario_type"] == "auth_002_multiple_accounts"
    ]

    assert len(events) == 5
    assert {event["result"] for event in events} == {"failure"}
    assert len({event["username_key"] for event in events}) == 5
    assert len({event["source_ip"] for event in events}) == 1

    timestamps = [parse_timestamp(event["timestamp"]) for event in events]
    assert max(timestamps) - min(timestamps) < timedelta(minutes=10)


def test_auth_003_pattern_has_failures_then_success_within_five_minutes() -> None:
    batch = generate_events(
        "sim-123",
        make_request(),
        ingested_at=INGESTED_AT,
    )
    events = [
        event
        for event in batch.events
        if event["scenario_type"] == "auth_003_failures_then_success"
    ]

    assert [event["result"] for event in events] == [
        "failure",
        "failure",
        "failure",
        "failure",
        "failure",
        "success",
    ]
    assert len({event["username_key"] for event in events}) == 1
    assert len({event["source_ip"] for event in events}) == 1

    timestamps = [parse_timestamp(event["timestamp"]) for event in events]
    assert timestamps[-1] > timestamps[-2]
    assert timestamps[-1] - timestamps[0] < timedelta(minutes=5)


def test_same_seed_and_ingestion_time_reproduce_same_batch() -> None:
    request = make_request(seed=2026)

    first = generate_events(
        "sim-123",
        request,
        ingested_at=INGESTED_AT,
    )
    second = generate_events(
        "sim-123",
        request,
        ingested_at=INGESTED_AT,
    )

    assert first == second
    assert first.effective_seed == 2026


def test_different_seeds_produce_different_normal_traffic() -> None:
    first = generate_events(
        "sim-123",
        make_request(seed=1),
        ingested_at=INGESTED_AT,
    )
    second = generate_events(
        "sim-123",
        make_request(seed=2),
        ingested_at=INGESTED_AT,
    )

    assert first.events != second.events


def test_generated_seed_can_be_reused_to_reproduce_batch() -> None:
    request = make_request(seed=None)

    first = generate_events(
        "sim-123",
        request,
        ingested_at=INGESTED_AT,
    )
    replay = generate_events(
        "sim-123",
        request,
        ingested_at=INGESTED_AT,
        effective_seed=first.effective_seed,
    )

    assert isinstance(first.effective_seed, int)
    assert replay == first


def test_rejects_mismatched_request_and_effective_seeds() -> None:
    with pytest.raises(ValueError, match="no coincide"):
        generate_events(
            "sim-123",
            make_request(seed=1),
            ingested_at=INGESTED_AT,
            effective_seed=2,
        )


def test_rejects_naive_dates() -> None:
    request = make_request(
        start=datetime(2026, 1, 1),
        end=datetime(2026, 1, 2),
    )

    with pytest.raises(ValueError, match="period_start debe incluir"):
        generate_events(
            "sim-123",
            request,
            ingested_at=INGESTED_AT,
        )


def test_rejects_blank_simulation_id() -> None:
    with pytest.raises(ValueError, match="simulation_id"):
        generate_events(
            " ",
            make_request(),
            ingested_at=INGESTED_AT,
        )