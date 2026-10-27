"""Contratos de entrada y salida para las simulaciones."""

from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator


class SimulationCreate(BaseModel):
    """Datos necesarios para solicitar una simulación."""

    model_config = ConfigDict(extra="forbid")

    requested_event_count: int = Field(default=100, ge=30, le=300)
    period_start: datetime
    period_end: datetime
    seed: int | None = None

    @model_validator(mode="after")
    def validate_period(self) -> "SimulationCreate":
        """Comprueba que el periodo sea válido y no supere 30 días."""

        if self.period_start >= self.period_end:
            raise ValueError(
                "period_start debe ser anterior a period_end."
            )

        duration = self.period_end - self.period_start

        if duration.total_seconds() > 30 * 24 * 60 * 60:
            raise ValueError(
                "El periodo de simulación no puede superar los 30 días."
            )

        return self