"""Pruebas unitarias de las plantillas de escenarios del simulador."""

from datetime import timedelta
from ipaddress import ip_address, ip_network

from app.simulator.scenarios import (
    AUTH_001,
    AUTH_002,
    AUTH_003,
    AUTH_004,
    NORMAL_TRAFFIC,
    SCENARIOS,
)


def test_catalog_contains_each_rule_and_normal_traffic() -> None:
    assert {scenario.rule_id for scenario in SCENARIOS} == {
        "AUTH-001",
        "AUTH-002",
        "AUTH-003",
        "AUTH-004",
        None,
    }
    assert NORMAL_TRAFFIC in SCENARIOS


def test_auth_001_has_five_failures_for_same_user_and_ip() -> None:
    events = AUTH_001.events

    assert len(events) == 5
    assert all(event.result == "failure" for event in events)
    assert len({event.username_key for event in events}) == 1
    assert len({event.source_ip for event in events}) == 1
    assert max(event.offset for event in events) - min(
        event.offset for event in events
    ) < timedelta(minutes=5)


def test_auth_002_has_five_distinct_users_from_same_ip() -> None:
    events = AUTH_002.events

    assert len(events) == 5
    assert all(event.result == "failure" for event in events)
    assert len({event.username_key for event in events}) == 5
    assert len({event.source_ip for event in events}) == 1
    assert max(event.offset for event in events) - min(
        event.offset for event in events
    ) < timedelta(minutes=10)


def test_auth_003_has_failures_followed_by_success_within_five_minutes() -> None:
    events = AUTH_003.events

    assert [event.result for event in events] == [
        "failure",
        "failure",
        "failure",
        "failure",
        "failure",
        "success",
    ]
    assert len({event.username_key for event in events}) == 1
    assert len({event.source_ip for event in events}) == 1
    assert events[-1].offset > events[-2].offset
    assert events[-1].offset - events[0].offset < timedelta(minutes=5)


def test_auth_004_is_disabled_without_invented_schedule() -> None:
    assert AUTH_004.enabled is False
    assert AUTH_004.events == ()


def test_normal_traffic_does_not_meet_auth_001_or_auth_002_thresholds() -> None:
    events = NORMAL_TRAFFIC.events

    assert all(event.result == "success" for event in events[:-1])
    assert len(events) < 5
    assert len({event.username_key for event in events}) < 5


def test_scenario_ips_use_documentation_ranges() -> None:
    documentation_ranges = (
        ip_network("192.0.2.0/24"),
        ip_network("198.51.100.0/24"),
        ip_network("203.0.113.0/24"),
    )

    for scenario in SCENARIOS:
        for event in scenario.events:
            address = ip_address(event.source_ip)
            assert any(address in network for network in documentation_ranges)