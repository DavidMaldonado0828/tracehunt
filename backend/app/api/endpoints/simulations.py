"""Endpoints HTTP para iniciar y consultar simulaciones autorizadas."""

import base64
import json
import logging
from typing import Any

from boto3.dynamodb.types import TypeDeserializer, TypeSerializer
from fastapi import APIRouter, Depends, Header, HTTPException, Query, status

from app.api.deps import require_staff
from app.repositories.simulations import list_simulations_by_user
from app.schemas.simulations import SimulationCreate
from app.schemas.users import UserInDB
from app.services.simulation_service import (
    create_simulation_request,
    execute_simulation,
    get_simulation_status,
)

logger = logging.getLogger("uvicorn.error")
router = APIRouter(tags=["simulations"])
_serializer = TypeSerializer()
_deserializer = TypeDeserializer()

# La respuesta se construye por lista permitida para evitar filtrar claves de
# idempotencia, huellas internas u otros atributos persistidos futuros.
_PUBLIC_FIELDS = (
    "simulation_id",
    "status",
    "requested_at",
    "started_at",
    "finished_at",
    "period_start",
    "period_end",
    "requested_event_count",
    "generated_event_count",
    "processed_event_count",
    "created_alert_count",
    "seed",
    "error_summary",
)


def _public_simulation(simulation: dict[str, Any]) -> dict[str, Any]:
    """Limita el contrato de salida a estado, parámetros y resultados útiles."""
    return {field: simulation[field] for field in _PUBLIC_FIELDS if field in simulation}


def _encode_cursor(last_key: dict[str, Any] | None) -> str | None:
    """Codifica la clave DynamoDB para que el cliente solo reciba un cursor opaco."""
    if last_key is None:
        return None
    typed_key = {name: _serializer.serialize(value) for name, value in last_key.items()}
    payload = json.dumps(typed_key, separators=(",", ":")).encode("utf-8")
    return base64.urlsafe_b64encode(payload).decode("ascii").rstrip("=")


def _decode_cursor(cursor: str | None) -> dict[str, Any] | None:
    """Restaura el formato AttributeValue esperado por la clave de continuación."""
    if cursor is None:
        return None
    try:
        padded = cursor + "=" * (-len(cursor) % 4)
        payload = base64.b64decode(padded, altchars=b"-_", validate=True)
        typed_key = json.loads(payload)
        if not isinstance(typed_key, dict) or not all(
            isinstance(value, dict) for value in typed_key.values()
        ):
            raise ValueError("La clave debe ser un objeto.")
        return {name: _deserializer.deserialize(value) for name, value in typed_key.items()}
    except (ValueError, TypeError, json.JSONDecodeError, base64.binascii.Error, KeyError):
        raise HTTPException(status_code=400, detail="Cursor inválido") from None


def _service_unavailable() -> HTTPException:
    """Evita exponer detalles internos cuando falla una dependencia del servicio."""
    return HTTPException(
        status_code=status.HTTP_503_SERVICE_UNAVAILABLE,
        detail="No fue posible procesar la solicitud.",
    )


@router.post("", response_model=dict[str, Any])
def start_simulation(
    payload: SimulationCreate,
    current_user: UserInDB = Depends(require_staff),
    idempotency_key: str = Header(..., alias="Idempotency-Key"),
) -> dict[str, Any]:
    """Registra y ejecuta una solicitud usando identidad del principal autenticado."""
    try:
        simulation = create_simulation_request(
            payload,
            requested_by_user_id=current_user.user_id,
            requested_by_email=current_user.email_normalized,
            idempotency_key=idempotency_key,
        )
    except HTTPException:
        # El servicio ya asigna códigos seguros a conflictos de idempotencia.
        raise
    except ValueError:
        # El schema actual admite fechas sin zona; el servicio detecta ese caso al normalizarlas.
        raise HTTPException(
            status_code=422,
            detail="Los parámetros de simulación no son válidos.",
        ) from None
    except Exception:
        logger.error("No se pudo registrar la solicitud de simulación")
        raise _service_unavailable() from None

    if simulation.get("status") == "pending":
        try:
            simulation = execute_simulation(simulation["simulation_id"])
        except Exception:
            # La ejecución puede haber guardado partial antes de propagar el error.
            try:
                simulation = get_simulation_status(
                    simulation["simulation_id"],
                    requested_by_user_id=current_user.user_id,
                    is_admin=current_user.role == "admin",
                )
            except Exception:
                logger.error("No se pudo recuperar el resultado de la simulación")
                raise _service_unavailable() from None
            if simulation.get("status") not in {"partial", "failed"}:
                logger.error("La ejecución de simulación no pudo completarse")
                raise _service_unavailable() from None

    # El servicio no informa si creó el registro o recuperó uno idempotente;
    # por eso este endpoint mantiene un único código de éxito.
    return _public_simulation(simulation)


@router.get("/{simulation_id}", response_model=dict[str, Any])
def get_simulation(
    simulation_id: str,
    current_user: UserInDB = Depends(require_staff),
) -> dict[str, Any]:
    """Consulta estado y contadores sin revelar existencia ajena al analyst."""
    try:
        simulation = get_simulation_status(
            simulation_id,
            requested_by_user_id=current_user.user_id,
            is_admin=current_user.role == "admin",
        )
    except HTTPException:
        raise
    except Exception:
        logger.error("No se pudo consultar la simulación")
        raise _service_unavailable() from None
    return _public_simulation(simulation)


@router.get("", response_model=dict[str, Any])
def list_my_simulations(
    current_user: UserInDB = Depends(require_staff),
    limit: int = Query(default=25, ge=1, le=100),
    cursor: str | None = Query(default=None),
) -> dict[str, Any]:
    """Pagina las ejecuciones propias en orden reciente usando el GSI existente."""
    exclusive_start_key = _decode_cursor(cursor)
    try:
        items, last_key = list_simulations_by_user(
            current_user.user_id,
            limit=limit,
            exclusive_start_key=exclusive_start_key,
        )
    except Exception:
        logger.error("No se pudo listar las simulaciones del usuario")
        raise _service_unavailable() from None
    return {
        "items": [_public_simulation(item) for item in items],
        "next_cursor": _encode_cursor(last_key),
    }
