"""Pruebas unitarias del esquema de simulaciones."""

from datetime import datetime, timedelta, timezone

import pytest
from pydantic import ValidationError

from app.schemas.simulations import SimulationCreate


@pytest.fixture
def valid_period() -> tuple[datetime, datetime]:
    """Proporciona un periodo válido de un día."""

    start = datetime(2026, 1, 1, tzinfo=timezone.utc)
    end = start + timedelta(days=1)

    return start, end


def test_default_event_count_and_valid_period(
    valid_period: tuple[datetime, datetime],
) -> None:
    """Acepta una solicitud válida con 100 eventos por defecto."""

    start, end = valid_period

    simulation = SimulationCreate(
        period_start=start,
        period_end=end,
    )

    assert simulation.requested_event_count == 100
    assert simulation.period_start == start
    assert simulation.period_end == end
    assert simulation.seed is None


@pytest.mark.parametrize("event_count", [29, 301])
def test_rejects_event_count_out_of_range(
    event_count: int,
    valid_period: tuple[datetime, datetime],
) -> None:
    """Rechaza cantidades inferiores a 30 o superiores a 300."""

    start, end = valid_period

    with pytest.raises(ValidationError):
        SimulationCreate(
            requested_event_count=event_count,
            period_start=start,
            period_end=end,
        )


def test_rejects_inverted_period(
    valid_period: tuple[datetime, datetime],
) -> None:
    """Rechaza un periodo cuya fecha inicial es posterior a la final."""

    start, end = valid_period

    with pytest.raises(ValidationError):
        SimulationCreate(
            period_start=end,
            period_end=start,
        )


def test_rejects_period_longer_than_30_days(
    valid_period: tuple[datetime, datetime],
) -> None:
    """Rechaza periodos que superan los 30 días."""

    start, _ = valid_period
    end = start + timedelta(days=31)

    with pytest.raises(ValidationError):
        SimulationCreate(
            period_start=start,
            period_end=end,
        )