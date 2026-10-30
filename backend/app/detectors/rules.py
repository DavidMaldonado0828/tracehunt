"""Reglas de detección de eventos de autenticación."""

from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime, timedelta, timezone
from typing import Any, Mapping, Sequence

from app.detectors.engine import sort_events


@dataclass(frozen=True)
class DetectionResult:
    """Resultado de evaluar una regla de detección."""

    rule_id: str
    severity: str
    related_event_ids: tuple[str, ...]
    first_event_at: datetime
    last_event_at: datetime
    metadata: Mapping[str, Any] = field(default_factory=dict)


def _timestamp(event: Mapping[str, Any]) -> datetime:
    """Obtiene el timestamp del evento normalizado a UTC."""
    value = event["timestamp"]

    if isinstance(value, str):
        value = datetime.fromisoformat(value.replace("Z", "+00:00"))

    if not isinstance(value, datetime):
        raise ValueError("El timestamp debe ser datetime o ISO-8601.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("El timestamp debe incluir zona horaria.")

    return value.astimezone(timezone.utc)


def _login_failures(
    events: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """Obtiene los eventos de login fallidos ordenados cronológicamente."""
    ordered = sort_events(events)

    return [
        event
        for event in ordered
        if event.get("event_type") == "login"
        and event.get("result") == "failure"
    ]


def evaluate_auth_001(
    events: Sequence[Mapping[str, Any]],
) -> list[DetectionResult]:
    """
    AUTH-001: cinco o más fallos del mismo usuario e IP
    dentro de una ventana de cinco minutos.
    """
    failures = _login_failures(events)

    groups = defaultdict(list)

    for event in failures:
        username_key = event.get("username_key")
        source_ip = event.get("source_ip")

        if not username_key or not source_ip:
            continue

        groups[(username_key, source_ip)].append(event)

    detections = []

    for (username_key, source_ip), group in groups.items():
        index = 0

        while index < len(group):
            first_event = group[index]
            start = _timestamp(first_event)
            end = start + timedelta(minutes=5)

            window = [
                event
                for event in group[index:]
                if start <= _timestamp(event) < end
            ]

            if len(window) >= 5:
                detections.append(
                    DetectionResult(
                        rule_id="AUTH-001",
                        severity="high",
                        related_event_ids=tuple(
                            event["event_id"] for event in window
                        ),
                        first_event_at=_timestamp(window[0]),
                        last_event_at=_timestamp(window[-1]),
                        metadata={
                            "username_key": username_key,
                            "source_ip": source_ip,
                        },
                    )
                )

                index += len(window)
            else:
                index += 1

    return detections


def evaluate_auth_002(
    events: Sequence[Mapping[str, Any]],
) -> list[DetectionResult]:
    """
    AUTH-002: fallos contra cinco o más usuarios diferentes
    desde una misma IP dentro de diez minutos.
    """
    failures = _login_failures(events)

    groups = defaultdict(list)

    for event in failures:
        source_ip = event.get("source_ip")
        username_key = event.get("username_key")

        if not source_ip or not username_key:
            continue

        groups[source_ip].append(event)

    detections = []

    for source_ip, group in groups.items():
        index = 0

        while index < len(group):
            first_event = group[index]
            start = _timestamp(first_event)
            end = start + timedelta(minutes=10)

            window = [
                event
                for event in group[index:]
                if start <= _timestamp(event) < end
            ]

            usernames = {
                event["username_key"]
                for event in window
            }

            if len(usernames) >= 5:
                detections.append(
                    DetectionResult(
                        rule_id="AUTH-002",
                        severity="high",
                        related_event_ids=tuple(
                            event["event_id"] for event in window
                        ),
                        first_event_at=_timestamp(window[0]),
                        last_event_at=_timestamp(window[-1]),
                        metadata={
                            "source_ip": source_ip,
                            "distinct_usernames": sorted(usernames),
                        },
                    )
                )

                index += len(window)
            else:
                index += 1

    return detections


def evaluate_auth_003(
    events: Sequence[Mapping[str, Any]],
) -> list[DetectionResult]:
    """
    AUTH-003: inicio de sesión exitoso precedido por cinco o más
    fallos del mismo usuario e IP en los cinco minutos anteriores.
    """
    ordered = sort_events(events)

    pending_failures = defaultdict(list)
    detections = []

    for event in ordered:
        if event.get("event_type") != "login":
            continue

        username_key = event.get("username_key")
        source_ip = event.get("source_ip")

        if not username_key or not source_ip:
            continue

        key = (username_key, source_ip)

        if event.get("result") == "failure":
            pending_failures[key].append(event)
            continue

        if event.get("result") != "success":
            continue

        success_time = _timestamp(event)
        window_start = success_time - timedelta(minutes=5)

        previous_failures = [
            failure
            for failure in pending_failures[key]
            if window_start <= _timestamp(failure) < success_time
        ]

        pending_failures[key] = previous_failures

        if len(previous_failures) < 5:
            continue

        related_events = previous_failures + [event]

        detections.append(
            DetectionResult(
                rule_id="AUTH-003",
                severity="medium",
                related_event_ids=tuple(
                    related_event["event_id"]
                    for related_event in related_events
                ),
                first_event_at=_timestamp(previous_failures[0]),
                last_event_at=success_time,
                metadata={
                    "username_key": username_key,
                    "source_ip": source_ip,
                    "successful_event_id": event["event_id"],
                },
            )
        )

        # Consumir los fallos utilizados para evitar
        # detecciones repetidas del mismo episodio.
        pending_failures[key] = []

    return detections


def evaluate_all_rules(
    events: Sequence[Mapping[str, Any]],
) -> list[DetectionResult]:
    """Ejecuta todas las reglas de detección disponibles."""
    return (
        evaluate_auth_001(events)
        + evaluate_auth_002(events)
        + evaluate_auth_003(events)
    )