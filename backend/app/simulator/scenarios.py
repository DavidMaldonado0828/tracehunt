"""Plantillas deterministas de escenarios para el simulador."""

from dataclasses import dataclass
from datetime import timedelta
from typing import Literal


EventResult = Literal["success", "failure"]


@dataclass(frozen=True, slots=True)
class ScenarioEvent:
    """Evento de autenticación relativo al inicio de un escenario."""

    offset: timedelta
    username: str
    username_key: str
    source_ip: str
    result: EventResult


@dataclass(frozen=True, slots=True)
class ScenarioDefinition:
    """Grupo de eventos que representa un patrón de simulación."""

    scenario_type: str
    rule_id: str | None
    events: tuple[ScenarioEvent, ...]
    enabled: bool = True


AUTH_001 = ScenarioDefinition(
    scenario_type="auth_001_repeated_failures",
    rule_id="AUTH-001",
    events=tuple(
        ScenarioEvent(
            offset=timedelta(minutes=minute),
            username="alice",
            username_key="USER#alice",
            source_ip="192.0.2.10",
            result="failure",
        )
        for minute in range(5)
    ),
)

AUTH_002 = ScenarioDefinition(
    scenario_type="auth_002_multiple_accounts",
    rule_id="AUTH-002",
    events=tuple(
        ScenarioEvent(
            offset=timedelta(minutes=minute),
            username=f"user{minute + 1}",
            username_key=f"USER#user{minute + 1}",
            source_ip="198.51.100.20",
            result="failure",
        )
        for minute in range(5)
    ),
)

AUTH_003 = ScenarioDefinition(
    scenario_type="auth_003_failures_then_success",
    rule_id="AUTH-003",
    events=(
        ScenarioEvent(
            offset=timedelta(seconds=0),
            username="carol",
            username_key="USER#carol",
            source_ip="203.0.113.30",
            result="failure",
        ),
        ScenarioEvent(
            offset=timedelta(seconds=30),
            username="carol",
            username_key="USER#carol",
            source_ip="203.0.113.30",
            result="failure",
        ),
        ScenarioEvent(
            offset=timedelta(seconds=60),
            username="carol",
            username_key="USER#carol",
            source_ip="203.0.113.30",
            result="failure",
        ),
        ScenarioEvent(
            offset=timedelta(seconds=90),
            username="carol",
            username_key="USER#carol",
            source_ip="203.0.113.30",
            result="failure",
        ),
        ScenarioEvent(
            offset=timedelta(seconds=120),
            username="carol",
            username_key="USER#carol",
            source_ip="203.0.113.30",
            result="failure",
        ),
        ScenarioEvent(
            offset=timedelta(seconds=150),
            username="carol",
            username_key="USER#carol",
            source_ip="203.0.113.30",
            result="success",
        ),
    ),
)

# AUTH-004 sigue desactivada hasta aprobar un horario de referencia.
# No se inventa una hora para crear un caso activador.
AUTH_004 = ScenarioDefinition(
    scenario_type="auth_004_disabled",
    rule_id="AUTH-004",
    events=(),
    enabled=False,
)

NORMAL_TRAFFIC = ScenarioDefinition(
    scenario_type="normal_traffic",
    rule_id=None,
    events=(
        ScenarioEvent(
            offset=timedelta(seconds=0),
            username="dana",
            username_key="USER#dana",
            source_ip="192.0.2.40",
            result="success",
        ),
        ScenarioEvent(
            offset=timedelta(minutes=2),
            username="erin",
            username_key="USER#erin",
            source_ip="198.51.100.50",
            result="success",
        ),
        ScenarioEvent(
            offset=timedelta(minutes=4),
            username="frank",
            username_key="USER#frank",
            source_ip="203.0.113.60",
            result="failure",
        ),
    ),
)

SCENARIOS: tuple[ScenarioDefinition, ...] = (
    AUTH_001,
    AUTH_002,
    AUTH_003,
    AUTH_004,
    NORMAL_TRAFFIC,
)