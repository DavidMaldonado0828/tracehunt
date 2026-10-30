"""Motor de procesamiento temporal de eventos de seguridad."""

from collections.abc import Mapping, Sequence
from datetime import datetime, timezone
from typing import Any


def _normalize_utc(value: datetime | str) -> datetime:
    """Convierte un timestamp con zona horaria a UTC."""

    if isinstance(value, str):
        try:
            value = datetime.fromisoformat(
                value.replace("Z", "+00:00")
            )
        except ValueError as error:
            raise ValueError("Timestamp inválido.") from error

    if not isinstance(value, datetime):
        raise ValueError("El timestamp debe ser datetime o ISO-8601.")

    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("El timestamp debe incluir zona horaria.")

    return value.astimezone(timezone.utc)


def sort_events(
    events: Sequence[Mapping[str, Any]],
) -> list[Mapping[str, Any]]:
    """Ordena eventos cronológicamente y desempata mediante event_id."""

    normalized_events = []

    for event in events:
        if "timestamp" not in event:
            raise ValueError("El evento debe contener timestamp.")

        event_id = event.get("event_id")

        if not isinstance(event_id, str) or not event_id:
            raise ValueError("El evento debe contener un event_id válido.")

        timestamp = _normalize_utc(event["timestamp"])

        normalized_events.append(
            (timestamp, event_id, event)
        )

    normalized_events.sort(
        key=lambda item: (item[0], item[1])
    )

    return [item[2] for item in normalized_events]


def filter_events_by_window(
    events: Sequence[Mapping[str, Any]],
    start: datetime | str,
    end: datetime | str,
) -> list[Mapping[str, Any]]:
    """Filtra eventos dentro de una ventana temporal [inicio, fin)."""

    start_utc = _normalize_utc(start)
    end_utc = _normalize_utc(end)

    if start_utc >= end_utc:
        raise ValueError("El inicio debe ser anterior al final.")

    ordered_events = sort_events(events)

    return [
        event
        for event in ordered_events
        if start_utc <= _normalize_utc(event["timestamp"]) < end_utc
    ]