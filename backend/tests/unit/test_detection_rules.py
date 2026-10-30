"""Pruebas unitarias de las reglas de detección."""

from datetime import datetime, timedelta, timezone

from app.detectors.rules import (
    evaluate_all_rules,
    evaluate_auth_001,
    evaluate_auth_002,
    evaluate_auth_003,
)


UTC = timezone.utc
START = datetime(2026, 10, 29, 10, 0, tzinfo=UTC)


def create_event(
    event_id,
    minutes=0,
    seconds=0,
    username="alice",
    source_ip="192.0.2.10",
    result="failure",
    event_type="login",
):
    return {
        "event_id": event_id,
        "timestamp": START + timedelta(
            minutes=minutes,
            seconds=seconds,
        ),
        "event_type": event_type,
        "result": result,
        "username_key": f"USER#{username}",
        "source_ip": source_ip,
    }


# ============================================================
# AUTH-001: cinco fallos del mismo usuario e IP en cinco minutos
# ============================================================

def test_auth_001_detects_five_failures():
    events = [
        create_event(f"EVT-{i}", minutes=i - 1)
        for i in range(1, 6)
    ]

    detections = evaluate_auth_001(events)

    assert len(detections) == 1
    assert detections[0].rule_id == "AUTH-001"
    assert detections[0].severity == "high"
    assert len(detections[0].related_event_ids) == 5


def test_auth_001_does_not_detect_only_four_failures():
    events = [
        create_event(f"EVT-{i}", minutes=i - 1)
        for i in range(1, 5)
    ]

    assert evaluate_auth_001(events) == []


def test_auth_001_does_not_group_different_users():
    events = [
        create_event(
            f"EVT-{i}",
            username=f"user{i}",
        )
        for i in range(1, 6)
    ]

    assert evaluate_auth_001(events) == []


def test_auth_001_does_not_group_different_ips():
    events = [
        create_event(
            f"EVT-{i}",
            source_ip=f"192.0.2.{i}",
        )
        for i in range(1, 6)
    ]

    assert evaluate_auth_001(events) == []


def test_auth_001_excludes_event_at_five_minute_boundary():
    events = [
        create_event(f"EVT-{i}", minutes=i - 1)
        for i in range(1, 5)
    ]

    events.append(
        create_event("EVT-005", minutes=5)
    )

    assert evaluate_auth_001(events) == []


def test_auth_001_ignores_successful_logins():
    events = [
        create_event(
            f"EVT-{i}",
            minutes=i - 1,
            result="success",
        )
        for i in range(1, 6)
    ]

    assert evaluate_auth_001(events) == []


def test_auth_001_returns_events_in_chronological_order():
    events = [
        create_event("EVT-005", minutes=4),
        create_event("EVT-002", minutes=1),
        create_event("EVT-004", minutes=3),
        create_event("EVT-001", minutes=0),
        create_event("EVT-003", minutes=2),
    ]

    detections = evaluate_auth_001(events)

    assert detections[0].related_event_ids == (
        "EVT-001",
        "EVT-002",
        "EVT-003",
        "EVT-004",
        "EVT-005",
    )

def test_auth_001_detects_two_independent_episodes():
    events = []

    # Primer episodio: 10:00 - 10:04
    for i in range(5):
        events.append(
            create_event(
                f"EVT-{i + 1}",
                minutes=i,
            )
        )

    # Segundo episodio: 10:30 - 10:34
    for i in range(5):
        events.append(
            create_event(
                f"EVT-{i + 6}",
                minutes=30 + i,
            )
        )

    detections = evaluate_auth_001(events)

    assert len(detections) == 2
    assert detections[0].related_event_ids == (
        "EVT-1", "EVT-2", "EVT-3", "EVT-4", "EVT-5"
    )
    assert detections[1].related_event_ids == (
        "EVT-6", "EVT-7", "EVT-8", "EVT-9", "EVT-10"
    )
def test_auth_001_does_not_duplicate_overlapping_windows():
    events = [
        create_event(f"EVT-{i}", minutes=i - 1)
        for i in range(1, 9)
    ]

    detections = evaluate_auth_001(events)

    assert len(detections) == 1


def test_auth_001_detects_independent_episodes_when_events_are_unordered():
    events = [
        create_event("EVT-8", minutes=32),
        create_event("EVT-2", minutes=1),
        create_event("EVT-6", minutes=30),
        create_event("EVT-4", minutes=3),
        create_event("EVT-10", minutes=34),
        create_event("EVT-1", minutes=0),
        create_event("EVT-7", minutes=31),
        create_event("EVT-5", minutes=4),
        create_event("EVT-9", minutes=33),
        create_event("EVT-3", minutes=2),
    ]

    detections = evaluate_auth_001(events)

    assert len(detections) == 2
    assert detections[0].related_event_ids == (
        "EVT-1", "EVT-2", "EVT-3", "EVT-4", "EVT-5"
    )
    assert detections[1].related_event_ids == (
        "EVT-6", "EVT-7", "EVT-8", "EVT-9", "EVT-10"
    )


# ============================================================
# AUTH-002: cinco usuarios diferentes desde una IP en diez minutos
# ============================================================

def test_auth_002_detects_five_different_users():
    events = [
        create_event(
            f"EVT-{i}",
            minutes=i - 1,
            username=f"user{i}",
        )
        for i in range(1, 6)
    ]

    detections = evaluate_auth_002(events)

    assert len(detections) == 1
    assert detections[0].rule_id == "AUTH-002"
    assert detections[0].severity == "high"
    assert len(detections[0].metadata["distinct_usernames"]) == 5


def test_auth_002_does_not_detect_four_different_users():
    events = [
        create_event(
            f"EVT-{i}",
            username=f"user{i}",
        )
        for i in range(1, 5)
    ]

    assert evaluate_auth_002(events) == []


def test_auth_002_does_not_count_repeated_username_twice():
    events = [
        create_event(
            f"EVT-{i}",
            username="alice",
        )
        for i in range(1, 6)
    ]

    assert evaluate_auth_002(events) == []


def test_auth_002_does_not_group_different_ips():
    events = [
        create_event(
            f"EVT-{i}",
            username=f"user{i}",
            source_ip=f"192.0.2.{i}",
        )
        for i in range(1, 6)
    ]

    assert evaluate_auth_002(events) == []


def test_auth_002_excludes_event_at_ten_minute_boundary():
    events = [
        create_event(
            f"EVT-{i}",
            minutes=i - 1,
            username=f"user{i}",
        )
        for i in range(1, 5)
    ]

    events.append(
        create_event(
            "EVT-005",
            minutes=10,
            username="user5",
        )
    )

    assert evaluate_auth_002(events) == []


def test_auth_002_detects_two_independent_episodes():
    events = []

    # Primer episodio: 10:00 - 10:04
    for i in range(5):
        events.append(
            create_event(
                f"EVT-{i + 1}",
                minutes=i,
                username=f"user{i + 1}",
            )
        )

# Segundo episodio: 10:30 - 10:34
    for i in range(5):
        events.append(
            create_event(
                f"EVT-{i + 6}",
                minutes=30 + i,
                username=f"user{i + 6}",
            )
        )

    detections = evaluate_auth_002(events)

    assert len(detections) == 2
    assert detections[0].related_event_ids == (
        "EVT-1", "EVT-2", "EVT-3", "EVT-4", "EVT-5"
    )
    assert detections[1].related_event_ids == (
        "EVT-6", "EVT-7", "EVT-8", "EVT-9", "EVT-10"
    )


def test_auth_002_does_not_duplicate_overlapping_windows():
    events = [
    create_event(
        f"EVT-{i}",
        minutes=i - 1,
        username=f"user{i}",
    )
    for i in range(1, 9)
    ]


    detections = evaluate_auth_002(events)

    assert len(detections) == 1


def test_auth_002_detects_independent_episodes_when_events_are_unordered():
    events = [
        create_event("EVT-8", minutes=32, username="user8"),
        create_event("EVT-2", minutes=1, username="user2"),
        create_event("EVT-6", minutes=30, username="user6"),
        create_event("EVT-4", minutes=3, username="user4"),
        create_event("EVT-10", minutes=34, username="user10"),
        create_event("EVT-1", minutes=0, username="user1"),
        create_event("EVT-7", minutes=31, username="user7"),
        create_event("EVT-5", minutes=4, username="user5"),
        create_event("EVT-9", minutes=33, username="user9"),
        create_event("EVT-3", minutes=2, username="user3"),
    ]


    detections = evaluate_auth_002(events)

    assert len(detections) == 2
    assert detections[0].related_event_ids == (
        "EVT-1", "EVT-2", "EVT-3", "EVT-4", "EVT-5"
    )
    assert detections[1].related_event_ids == (
        "EVT-6", "EVT-7", "EVT-8", "EVT-9", "EVT-10"
    )


# ============================================================
# AUTH-003: éxito después de cinco fallos recientes
# ============================================================

def test_auth_003_detects_success_after_five_failures():
    events = [
        create_event(f"EVT-{i}", minutes=i - 1)
        for i in range(1, 6)
    ]

    events.append(
        create_event(
            "EVT-006",
            minutes=4,
            seconds=30,
            result="success",
        )
    )

    detections = evaluate_auth_003(events)

    assert len(detections) == 1
    assert detections[0].rule_id == "AUTH-003"
    assert detections[0].severity == "medium"
    assert len(detections[0].related_event_ids) == 6
    assert detections[0].related_event_ids[-1] == "EVT-006"


def test_auth_003_does_not_detect_four_previous_failures():
    events = [
        create_event(f"EVT-{i}", minutes=i - 1)
        for i in range(1, 5)
    ]

    events.append(
        create_event(
            "EVT-005",
            minutes=4,
            result="success",
        )
    )

    assert evaluate_auth_003(events) == []


def test_auth_003_requires_successful_login():
    events = [
        create_event(f"EVT-{i}", minutes=i - 1)
        for i in range(1, 6)
    ]

    assert evaluate_auth_003(events) == []


def test_auth_003_requires_same_user_and_ip():
    events = [
        create_event(f"EVT-{i}", minutes=i - 1)
        for i in range(1, 6)
    ]

    events.append(
        create_event(
            "EVT-006",
            minutes=4,
            seconds=30,
            username="bob",
            result="success",
        )
    )

    assert evaluate_auth_003(events) == []


def test_auth_003_excludes_failure_before_five_minute_window():
    events = [
        create_event("EVT-001", minutes=-1),
        create_event("EVT-002", minutes=0),
        create_event("EVT-003", minutes=1),
        create_event("EVT-004", minutes=2),
        create_event("EVT-005", minutes=3),
        create_event(
            "EVT-006",
            minutes=5,
            result="success",
        ),
    ]

    assert evaluate_auth_003(events) == []


def test_auth_003_does_not_duplicate_detection_for_repeated_successes():
    events = [
        create_event(
            event_id=f"fail-{i}",
            minutes=0,
            seconds=i,
            username="cristian",
            source_ip="192.168.1.10",
            result="failure",
        )
        for i in range(5)
    ]

    events.extend([
        create_event(
            event_id="success-1",
            minutes=1,
            username="cristian",
            source_ip="192.168.1.10",
            result="success",
        ),
        create_event(
            event_id="success-2",
            minutes=2,
            username="cristian",
            source_ip="192.168.1.10",
            result="success",
        ),
    ])

    detections = evaluate_auth_003(events)

    assert len(detections) == 1
    assert detections[0].rule_id == "AUTH-003"


def test_auth_003_detects_two_independent_episodes():
    events = []

    # Primer episodio: cinco fallos y un inicio de sesión exitoso.
    for i in range(5):
        events.append(
            create_event(
                event_id=f"fail-1-{i}",
                minutes=0,
                seconds=i,
                username="cristian",
                source_ip="192.168.1.10",
                result="failure",
            )
        )

    events.append(
        create_event(
            event_id="success-1",
            minutes=5,
            username="cristian",
            source_ip="192.168.1.10",
            result="success",
        )
    )

    # Segundo episodio independiente.
    for i in range(5):
        events.append(
            create_event(
                event_id=f"fail-2-{i}",
                minutes=30,
                seconds=i,
                username="cristian",
                source_ip="192.168.1.10",
                result="failure",
            )
        )

    events.append(
        create_event(
            event_id="success-2",
            minutes=35,
            username="cristian",
            source_ip="192.168.1.10",
            result="success",
        )
    )

    detections = evaluate_auth_003(events)

    assert len(detections) == 2
    assert all(d.rule_id == "AUTH-003" for d in detections)


def test_auth_003_detects_pattern_when_events_are_unordered():
    events = [
        create_event(
            event_id="success-1",
            minutes=5,
            username="cristian",
            source_ip="192.168.1.10",
            result="success",
        ),
        create_event(
            event_id="fail-3",
            minutes=0,
            seconds=2,
            username="cristian",
            source_ip="192.168.1.10",
            result="failure",
        ),
        create_event(
            event_id="fail-5",
            minutes=0,
            seconds=4,
            username="cristian",
            source_ip="192.168.1.10",
            result="failure",
        ),
        create_event(
            event_id="fail-1",
            minutes=0,
            username="cristian",
            source_ip="192.168.1.10",
            result="failure",
        ),
        create_event(
            event_id="fail-4",
            minutes=0,
            seconds=3,
            username="cristian",
            source_ip="192.168.1.10",
            result="failure",
        ),
        create_event(
            event_id="fail-2",
            minutes=0,
            seconds=1,
            username="cristian",
            source_ip="192.168.1.10",
            result="failure",
        ),
    ]

    detections = evaluate_auth_003(events)

    assert len(detections) == 1
    assert detections[0].rule_id == "AUTH-003"
    assert detections[0].related_event_ids == (
        "fail-1",
        "fail-2",
        "fail-3",
        "fail-4",
        "fail-5",
        "success-1",
    )

# ============================================================
# Integración entre reglas
# ============================================================

def test_same_events_can_trigger_multiple_rules():
    events = [
        create_event(
            f"EVT-{i}",
            minutes=i - 1,
            username="alice",
        )
        for i in range(1, 6)
    ]

    for i in range(6, 10):
        events.append(
            create_event(
                f"EVT-{i}",
                minutes=4,
                username=f"user{i}",
            )
        )

    events.append(
        create_event(
            "EVT-010",
            minutes=4,
            seconds=30,
            username="alice",
            result="success",
        )
    )

    detections = evaluate_all_rules(events)

    detected_rules = {
        detection.rule_id
        for detection in detections
    }

    assert detected_rules == {
        "AUTH-001",
        "AUTH-002",
        "AUTH-003",
    }