"""Servicio de aplicación para gestionar ejecuciones de simulación."""

from __future__ import annotations

import hashlib
import json
import secrets
from datetime import datetime, timezone
from typing import Any

from boto3.dynamodb.types import TypeSerializer
from fastapi import HTTPException

from app.core.config import get_settings
from app.repositories.dynamo_client import get_dynamodb_resource
from app.repositories.events import EventsRepository, UnprocessedEventsError
from app.repositories.simulations import (
    SimulationAlreadyExistsError,
    SimulationNotFoundError,
    create_simulation,
    get_simulation,
    update_simulation,
)
from app.schemas.simulations import SimulationCreate
from app.simulator.generator import generate_events


VALID_STATUSES = {
    "pending",
    "running",
    "completed",
    "partial",
    "failed",
}

TERMINAL_STATUSES = {
    "completed",
    "partial",
    "failed",
}

ALLOWED_TRANSITIONS = {
    "pending": {"running", "failed"},
    "running": {"completed", "partial", "failed"},
    "completed": set(),
    "partial": set(),
    "failed": set(),
}

DYNAMODB_BATCH_SIZE = 25
_TYPE_SERIALIZER = TypeSerializer()


def _utc_now() -> datetime:
    """Devuelve la hora actual en UTC."""
    return datetime.now(timezone.utc)


def _utc_iso(value: datetime) -> str:
    """Normaliza una fecha consciente de zona horaria a UTC ISO 8601."""
    if value.tzinfo is None or value.utcoffset() is None:
        raise ValueError("Las fechas deben incluir información de zona horaria.")

    return value.astimezone(timezone.utc).isoformat()


def _validate_identifier(value: str, field: str) -> str:
    """Valida y normaliza un identificador obligatorio."""
    if not isinstance(value, str) or not value.strip():
        raise ValueError(f"{field} es obligatorio.")

    return value.strip()


def _validate_idempotency_key(value: str) -> str:
    """Valida y normaliza la clave de idempotencia."""
    if not isinstance(value, str):
        raise ValueError("La clave de idempotencia debe ser una cadena.")

    key = value.strip()

    if not key:
        raise ValueError("La clave de idempotencia es obligatoria.")

    if len(key) > 200:
        raise ValueError("La clave de idempotencia no puede superar 200 caracteres.")

    return key


def _normalized_request(request: SimulationCreate) -> dict[str, Any]:
    """Construye una representación estable de los parámetros solicitados."""
    return {
        "requested_event_count": request.requested_event_count,
        "period_start": _utc_iso(request.period_start),
        "period_end": _utc_iso(request.period_end),
        "seed": request.seed,
    }


def _request_fingerprint(request: SimulationCreate) -> str:
    """Calcula la huella de los parámetros normalizados."""
    payload = json.dumps(
        _normalized_request(request),
        sort_keys=True,
        separators=(",", ":"),
    )
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _simulation_id(requested_by_user_id: str, idempotency_key: str) -> str:
    """Deriva un ID estable a partir del usuario y la clave."""
    identity = json.dumps(
        [requested_by_user_id, idempotency_key],
        ensure_ascii=False,
        separators=(",", ":"),
    )
    digest = hashlib.sha256(identity.encode("utf-8")).hexdigest()
    return f"SIM-{digest}"


def _safe_error_summary(error: Exception) -> str:
    """Devuelve un resumen que no incluye mensajes potencialmente sensibles."""
    allowed_types = {
        "ValueError",
        "TypeError",
        "TimeoutError",
        "ConnectionError",
        "RuntimeError",
        "UnprocessedEventsError",
    }

    error_type = type(error).__name__
    if error_type not in allowed_types:
        error_type = "ExecutionError"

    return f"La ejecución no pudo completarse. Tipo de error: {error_type}."


def _serialize_event_for_low_level_client(
    event: dict[str, Any],
) -> dict[str, dict[str, Any]]:
    """Convierte un evento Python al formato AttributeValue de boto3 client."""
    return {
        name: _TYPE_SERIALIZER.serialize(value)
        for name, value in event.items()
        if value is not None
    }


def _serialize_events_for_low_level_client(
    events: list[dict[str, Any]],
) -> list[dict[str, dict[str, Any]]]:
    """Serializa todos los eventos para BatchWriteItem."""
    return [_serialize_event_for_low_level_client(event) for event in events]


def _get_events_repository() -> EventsRepository:
    """Construye el repositorio de eventos con la configuración común."""
    settings = get_settings()
    dynamodb = get_dynamodb_resource()

    return EventsRepository(
        client=dynamodb.meta.client,
        table_name=settings.events_table,
    )


def create_simulation_request(
    request: SimulationCreate,
    *,
    requested_by_user_id: str,
    idempotency_key: str,
    requested_by_email: str | None = None,
) -> dict[str, Any]:
    """
    Registra una ejecución o devuelve la existente para el mismo usuario y clave.

    `requested_by_user_id` y `requested_by_email` deben obtenerse del contexto
    autenticado del backend, nunca de datos sin verificar del cliente.
    """
    user_id = _validate_identifier(
        requested_by_user_id,
        "requested_by_user_id",
    )
    key = _validate_idempotency_key(idempotency_key)

    normalized = _normalized_request(request)
    fingerprint = _request_fingerprint(request)
    simulation_id = _simulation_id(user_id, key)

    # La seed efectiva se persiste para que una ejecución pueda reproducirse.
    effective_seed = (
        request.seed
        if request.seed is not None
        else secrets.randbits(64)
    )

    requested_at = _utc_iso(_utc_now())

    item: dict[str, Any] = {
        "simulation_id": simulation_id,
        "status": "pending",
        "requested_at": requested_at,
        "requested_at_sim": f"{requested_at}#{simulation_id}",
        "period_start": normalized["period_start"],
        "period_end": normalized["period_end"],
        "requested_event_count": request.requested_event_count,
        "generated_event_count": 0,
        "processed_event_count": 0,
        "created_alert_count": 0,
        "requested_by_user_id": user_id,
        "idempotency_key": key,
        "request_fingerprint": fingerprint,
        "seed": effective_seed,
    }

    if requested_by_email:
        item["requested_by_email"] = requested_by_email.strip()

    try:
        return create_simulation(item)

    except SimulationAlreadyExistsError:
        # La lectura actual del repositorio no solicita ConsistentRead.
        # Una lectura eventualmente consistente puede devolver None brevemente.
        existing = get_simulation(simulation_id)

        if existing is None:
            raise HTTPException(
                status_code=503,
                detail="No fue posible confirmar el estado de la ejecución.",
            ) from None

        if existing.get("request_fingerprint") != fingerprint:
            raise HTTPException(
                status_code=409,
                detail=(
                    "La clave de idempotencia ya se utilizó con parámetros "
                    "diferentes."
                ),
            ) from None

        return existing


def get_simulation_status(
    simulation_id: str,
    *,
    requested_by_user_id: str,
    is_admin: bool = False,
) -> dict[str, Any]:
    """Obtiene una ejecución y verifica que el solicitante pueda verla."""
    simulation_id = _validate_identifier(simulation_id, "simulation_id")
    user_id = _validate_identifier(
        requested_by_user_id,
        "requested_by_user_id",
    )

    simulation = get_simulation(simulation_id)

    if simulation is None:
        raise HTTPException(
            status_code=404,
            detail="La ejecución no existe.",
        )

    if (
        not is_admin
        and simulation.get("requested_by_user_id") != user_id
    ):
        # No revelar si existe una ejecución perteneciente a otro usuario.
        raise HTTPException(
            status_code=404,
            detail="La ejecución no existe.",
        )

    return simulation


def transition_simulation(
    simulation_id: str,
    *,
    new_status: str,
    changes: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Valida y persiste una transición permitida de estado."""
    simulation_id = _validate_identifier(simulation_id, "simulation_id")

    if new_status not in VALID_STATUSES:
        raise ValueError("El estado solicitado no es válido.")

    current = get_simulation(simulation_id)

    if current is None:
        raise SimulationNotFoundError("La ejecución no existe.")

    current_status = current.get("status")
    allowed = ALLOWED_TRANSITIONS.get(current_status, set())

    if new_status not in allowed:
        raise ValueError(
            f"No se permite cambiar el estado de "
            f"{current_status!r} a {new_status!r}."
        )

    values = dict(changes or {})
    values["status"] = new_status

    if new_status == "running":
        values.setdefault("started_at", _utc_iso(_utc_now()))

    if new_status in TERMINAL_STATUSES:
        values.setdefault("finished_at", _utc_iso(_utc_now()))

    # El repositorio actual solo condiciona a que el elemento exista.
    # Para concurrencia real debe aceptar expected_status y token de lease.
    return update_simulation(simulation_id, values)


def _update_generated_count(
    simulation_id: str,
    generated_count: int,
) -> dict[str, Any]:
    """Guarda el total confirmado por lotes completados."""
    return update_simulation(
        simulation_id,
        {"generated_event_count": generated_count},
    )


def execute_simulation(
    simulation_id: str,
    *,
    events_repository: EventsRepository | None = None,
) -> dict[str, Any]:
    """
    Genera y persiste los eventos de una ejecución pendiente.

    Esta función no implementa recuperación mediante checkpoints ni ejecuta
    el motor de detección. Si BatchWriteItem falla, pueden quedar eventos
    persistidos; el conteo solo incluye los que pudieron confirmarse.
    """
    simulation_id = _validate_identifier(simulation_id, "simulation_id")
    simulation = get_simulation(simulation_id)

    if simulation is None:
        raise SimulationNotFoundError("La ejecución no existe.")

    if simulation.get("status") != "pending":
        raise ValueError(
            "Solo se pueden iniciar ejecuciones en estado 'pending'."
        )

    # Esta transición todavía no es compare-and-set en el repositorio actual.
    running = transition_simulation(simulation_id, new_status="running")
    persisted_count = int(simulation.get("generated_event_count", 0))

    try:
        started_at = running.get("started_at")
        if not isinstance(started_at, str):
            raise RuntimeError(
                "La ejecución no tiene un started_at persistido."
            )

        request = SimulationCreate(
            requested_event_count=simulation["requested_event_count"],
            period_start=datetime.fromisoformat(simulation["period_start"]),
            period_end=datetime.fromisoformat(simulation["period_end"]),
            seed=simulation["seed"],
        )

        # Reutilizar started_at mantiene estable `ingested_at` durante esta
        # ejecución; no constituye por sí solo un protocolo de recuperación.
        generated_batch = generate_events(
            simulation_id,
            request,
            ingested_at=datetime.fromisoformat(started_at),
            effective_seed=simulation["seed"],
        )

        repository = events_repository or _get_events_repository()
        batch_size = getattr(
            repository,
            "MAX_BATCH_SIZE",
            DYNAMODB_BATCH_SIZE,
        )

        if not 1 <= batch_size <= DYNAMODB_BATCH_SIZE:
            raise ValueError("El tamaño de lote debe estar entre 1 y 25.")

        for start in range(0, len(generated_batch.events), batch_size):
            batch = generated_batch.events[start : start + batch_size]
            serialized_batch = _serialize_events_for_low_level_client(batch)

            try:
                repository.save_many(serialized_batch)
            except UnprocessedEventsError as error:
                # save_many reintenta solo los UnprocessedItems. Los demás
                # elementos del lote ya fueron procesados por DynamoDB.
                confirmed_in_batch = max(
                    0,
                    len(batch) - error.pending_count,
                )
                persisted_count += confirmed_in_batch
                _update_generated_count(simulation_id, persisted_count)
                raise

            persisted_count += len(batch)
            _update_generated_count(simulation_id, persisted_count)

        return transition_simulation(
            simulation_id,
            new_status="completed",
            changes={
                "generated_event_count": persisted_count,
                "processed_event_count": 0,
                "created_alert_count": 0,
                "error_summary": "",
            },
        )

    except Exception as error:
        current = get_simulation(simulation_id)

        if current is not None and current.get("status") == "running":
            try:
                transition_simulation(
                    simulation_id,
                    new_status="partial",
                    changes={
                        "generated_event_count": persisted_count,
                        "error_summary": _safe_error_summary(error),
                    },
                )
            except Exception:
                # Conserva el error original si falla también la actualización
                # de estado; el estado persistido podría seguir en running.
                pass

        raise