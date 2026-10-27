"""Generación determinista de eventos para una simulación."""

import random
import secrets
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from ipaddress import IPv4Network, ip_address, ip_network
from typing import Any

from app.schemas.simulations import SimulationCreate
from app.simulator.scenarios import SCENARIOS, ScenarioEvent


DOCUMENTATION_IP_NETWORKS: tuple[IPv4Network, ...] = (
    ip_network("192.0.2.0/24"),
    ip_network("198.51.100.0/24"),
    ip_network("203.0.113.0/24"),
)


@dataclass(frozen=True, slots=True)
class GeneratedEventBatch:
    """Eventos generados y seed que permite reproducirlos."""

    events: list[dict[str, Any]]
    effective_seed: int


@dataclass(frozen=True, slots=True)
class _ScheduledEvent:
    """Evento de escenario asociado con su timestamp de ocurrencia."""

    timestamp: datetime
    event: ScenarioEvent
    scenario_type: str


def _normalize_utc(value: datetime, field_name: str) -> datetime:
    """Requiere una fecha con zona horaria y la normaliza a UTC."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError(f"{field_name} debe incluir una zona horaria.")

    return value.astimezone(timezone.utc)


def _timedelta_microseconds(value: timedelta) -> int:
    """Convierte un timedelta a microsegundos enteros."""
    return (
        (value.days * 24 * 60 * 60 + value.seconds) * 1_000_000
        + value.microseconds
    )


def _format_utc(value: datetime) -> str:
    """Serializa UTC con precisión fija para mantener claves ordenables."""
    return value.astimezone(timezone.utc).isoformat(
        timespec="microseconds"
    ).replace("+00:00", "Z")


def _schedule_scenario(
    scenario_type: str,
    events: tuple[ScenarioEvent, ...],
    period_start: datetime,
    period_duration_microseconds: int,
    rng: random.Random,
) -> list[_ScheduledEvent]:
    """Ubica un escenario dentro del periodo conservando el orden de eventos."""
    if not events:
        return []

    offsets = [_timedelta_microseconds(event.offset) for event in events]
    if any(offset < 0 for offset in offsets):
        raise ValueError("Los offsets de escenario no pueden ser negativos.")

    maximum_offset = max(offsets)
    latest_allowed_offset = period_duration_microseconds - 1
    scenario_span = min(maximum_offset, latest_allowed_offset)

    latest_start = period_duration_microseconds - 1 - scenario_span
    start_offset = rng.randrange(latest_start + 1)

    scheduled: list[_ScheduledEvent] = []
    for event, offset in zip(events, offsets, strict=True):
        if maximum_offset == 0:
            relative_offset = 0
        else:
            relative_offset = (offset * scenario_span) // maximum_offset

        timestamp = period_start + timedelta(
            microseconds=start_offset + relative_offset
        )
        scheduled.append(
            _ScheduledEvent(
                timestamp=timestamp,
                event=event,
                scenario_type=scenario_type,
            )
        )

    return scheduled


def _random_documentation_ip(
    rng: random.Random,
    used_ips: set[str],
) -> str:
    """Elige una IP aún no usada de los rangos reservados para documentación."""
    while True:
        network = rng.choice(DOCUMENTATION_IP_NETWORKS)
        address_number = int(network.network_address) + rng.randrange(
            1,
            network.num_addresses - 1,
        )
        address = str(ip_address(address_number))
        if address not in used_ips:
            used_ips.add(address)
            return address


def _make_normal_event(
    index: int,
    period_start: datetime,
    period_duration_microseconds: int,
    rng: random.Random,
    used_ips: set[str],
) -> _ScheduledEvent:
    """Crea tráfico normal con cuenta e IP únicas para evitar patrones extra."""
    username = f"normal-{index:03d}-{rng.getrandbits(32):08x}"
    event = ScenarioEvent(
        offset=timedelta(0),
        username=username,
        username_key=f"USER#{username.casefold()}",
        source_ip=_random_documentation_ip(rng, used_ips),
        result=rng.choice(("success", "failure")),
    )
    timestamp_offset = rng.randrange(period_duration_microseconds)

    return _ScheduledEvent(
        timestamp=period_start + timedelta(microseconds=timestamp_offset),
        event=event,
        scenario_type="normal_traffic",
    )


def generate_events(
    simulation_id: str,
    request: SimulationCreate,
    *,
    ingested_at: datetime,
    effective_seed: int | None = None,
) -> GeneratedEventBatch:
    """Genera los eventos de la ejecución en el intervalo semiabierto [inicio, fin).

    `effective_seed` permite recuperar una ejecución cuya seed generada ya fue
    persistida. Para reproducir exactamente los elementos también se debe
    reutilizar `ingested_at` de la ejecución original.
    """
    if not simulation_id or simulation_id.strip() != simulation_id:
        raise ValueError("simulation_id es obligatorio y no puede tener espacios.")

    if not 30 <= request.requested_event_count <= 300:
        raise ValueError("requested_event_count debe estar entre 30 y 300.")

    period_start = _normalize_utc(request.period_start, "period_start")
    period_end = _normalize_utc(request.period_end, "period_end")
    ingested_at_utc = _normalize_utc(ingested_at, "ingested_at")

    if period_start >= period_end:
        raise ValueError("period_start debe ser anterior a period_end.")

    duration_microseconds = _timedelta_microseconds(period_end - period_start)
    if duration_microseconds <= 0:
        raise ValueError("El periodo debe durar al menos un microsegundo.")

    if (
        request.seed is not None
        and effective_seed is not None
        and request.seed != effective_seed
    ):
        raise ValueError("effective_seed no coincide con la seed de la solicitud.")

    selected_seed = (
        request.seed
        if request.seed is not None
        else effective_seed
    )
    if selected_seed is None:
        selected_seed = secrets.randbits(64)

    if not isinstance(selected_seed, int) or isinstance(selected_seed, bool):
        raise ValueError("La seed efectiva debe ser un entero.")

    rng = random.Random(selected_seed)
    scheduled_events: list[_ScheduledEvent] = []

    # SCENARIOS contiene AUTH-004 desactivada y sin eventos, por lo que se omite.
    for scenario in SCENARIOS:
        if not scenario.enabled or not scenario.events:
            continue
        scheduled_events.extend(
            _schedule_scenario(
                scenario.scenario_type,
                scenario.events,
                period_start,
                duration_microseconds,
                rng,
            )
        )

    requested_count = request.requested_event_count
    if len(scheduled_events) > requested_count:
        raise ValueError(
            "La cantidad solicitada no permite incluir todos los escenarios activos."
        )

    used_ips = {
        scheduled.event.source_ip
        for scheduled in scheduled_events
    }

    normal_event_count = requested_count - len(scheduled_events)
    for index in range(normal_event_count):
        scheduled_events.append(
            _make_normal_event(
                index=index,
                period_start=period_start,
                period_duration_microseconds=duration_microseconds,
                rng=rng,
                used_ips=used_ips,
            )
        )

    # El orden estable determina el número de secuencia de cada ID.
    scheduled_events.sort(key=lambda scheduled: scheduled.timestamp)

    generated: list[dict[str, Any]] = []
    for position, scheduled in enumerate(scheduled_events, start=1):
        event_id = f"SIM-{simulation_id}-EVT-{position:06d}"
        timestamp = _format_utc(scheduled.timestamp)

        generated.append(
            {
                "event_id": event_id,
                "event_type": "login",
                "timestamp": timestamp,
                "ingested_at": _format_utc(ingested_at_utc),
                "username": scheduled.event.username,
                "username_key": scheduled.event.username_key,
                "source_ip": scheduled.event.source_ip,
                "result": scheduled.event.result,
                "date_bucket": (
                    f"DATE#{scheduled.timestamp.date().isoformat()}"
                ),
                "timestamp_event": f"{timestamp}#{event_id}",
                "simulation_id": simulation_id,
                "data_source": "simulator",
                "scenario_type": scheduled.scenario_type,
            }
        )

    if len(generated) != requested_count:
        raise RuntimeError("El generador no produjo la cantidad solicitada.")

    return GeneratedEventBatch(
        events=generated,
        effective_seed=selected_seed,
    )