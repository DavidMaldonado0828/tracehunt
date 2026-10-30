"""Codificación y validación de cursores de listas de alertas."""

from __future__ import annotations

import base64
import binascii
from datetime import datetime, timezone
import hashlib
import hmac
import json
from typing import Any

from boto3.dynamodb.types import TypeDeserializer, TypeSerializer

from app.core.config import get_settings
from app.schemas.users import UserInDB

CURSOR_VERSION = 1
CURSOR_PURPOSE = "alerts.list"
CURSOR_TTL_SECONDS = 900
MAX_CURSOR_LENGTH = 16_384
ALERT_STATUSES = ("open", "investigating", "resolved")

_serializer = TypeSerializer()
_deserializer = TypeDeserializer()


class InvalidAlertCursorError(ValueError):
    """El cursor está alterado, vencido o no corresponde a la consulta."""


def _now_timestamp() -> int:
    return int(datetime.now(timezone.utc).timestamp())


def _cursor_signing_key() -> bytes:
    """Deriva una clave de cursor separada criptográficamente del uso JWT."""
    secret = get_settings().jwt_secret
    if secret is None or not secret.strip() or len(secret) < 32:
        raise RuntimeError("JWT_SECRET no está configurado para firmar cursores.")
    return hmac.new(
        secret.encode("utf-8"),
        b"TraceHunt/alerts/list-cursor/v1",
        hashlib.sha256,
    ).digest()


def _context(
    *,
    actor: UserInDB,
    status: str | None,
    severity: str | None,
    limit: int,
) -> dict[str, Any]:
    return {
        "actor_id": actor.user_id,
        "role": actor.role,
        "status": status,
        "severity": severity,
        "limit": limit,
    }


def _expected_mode(
    actor: UserInDB,
    status: str | None,
    severity: str | None,
) -> str:
    return (
        "all_statuses"
        if actor.role == "admin" and status is None and severity is None
        else "single"
    )


def _encode_key(key: dict[str, Any]) -> dict[str, Any]:
    return {name: _serializer.serialize(value) for name, value in key.items()}


def _decode_key(value: Any) -> dict[str, Any]:
    if not isinstance(value, dict) or not value:
        raise InvalidAlertCursorError("Cursor inválido.")
    if all(isinstance(item, (str, int, float, bytes)) for item in value.values()):
        return dict(value)
    if not all(
        isinstance(name, str)
        and isinstance(attribute_value, dict)
        and len(attribute_value) == 1
        for name, attribute_value in value.items()
    ):
        raise InvalidAlertCursorError("Cursor inválido.")
    try:
        decoded = {
            name: _deserializer.deserialize(attribute_value)
            for name, attribute_value in value.items()
        }
    except (TypeError, ValueError, KeyError):
        raise InvalidAlertCursorError("Cursor inválido.") from None
    if not all(isinstance(item, (str, int, float, bytes)) for item in decoded.values()):
        raise InvalidAlertCursorError("Cursor inválido.")
    return decoded


def _expected_key_names(
    actor: UserInDB,
    status: str | None,
    severity: str | None,
) -> set[str]:
    if actor.role == "analyst":
        partition_name = "owner_user_id"
    elif status is not None:
        partition_name = "status"
    else:
        partition_name = "severity"
    return {"alert_id", partition_name, "created_at_alert"}


def _validate_state(
    state: Any,
    *,
    expected_mode: str,
    actor: UserInDB,
    status: str | None,
    severity: str | None,
) -> dict[str, Any]:
    if not isinstance(state, dict) or state.get("mode") != expected_mode:
        raise InvalidAlertCursorError("Cursor incompatible con esta consulta.")

    if expected_mode == "single":
        key = _decode_key(state.get("exclusive_start_key"))
        if set(key) != _expected_key_names(actor, status, severity):
            raise InvalidAlertCursorError("Cursor inválido.")
        return {"mode": "single", "exclusive_start_key": key}

    positions = state.get("positions")
    exhausted = state.get("exhausted")
    if (
        not isinstance(positions, dict)
        or not isinstance(exhausted, dict)
        or set(positions) != set(ALERT_STATUSES)
        or set(exhausted) != set(ALERT_STATUSES)
        or not all(isinstance(value, bool) for value in exhausted.values())
    ):
        raise InvalidAlertCursorError("Cursor inválido.")

    decoded_positions: dict[str, dict[str, Any] | None] = {}
    expected_names = {"alert_id", "status", "created_at_alert"}
    for current_status in ALERT_STATUSES:
        position = positions[current_status]
        if position is None:
            decoded_positions[current_status] = None
            continue
        key = _decode_key(position)
        if set(key) != expected_names or key.get("status") != current_status:
            raise InvalidAlertCursorError("Cursor inválido.")
        decoded_positions[current_status] = key

    return {
        "mode": "all_statuses",
        "positions": decoded_positions,
        "exhausted": dict(exhausted),
    }


def encode_alert_cursor(
    state: dict[str, Any] | None,
    *,
    actor: UserInDB,
    status: str | None,
    severity: str | None,
    limit: int,
) -> str | None:
    """Firma el estado de continuación; el token no incluye datos de alertas."""
    if state is None:
        return None

    mode = _expected_mode(actor, status, severity)
    validated_state = _validate_state(
        state,
        expected_mode=mode,
        actor=actor,
        status=status,
        severity=severity,
    )
    if mode == "single":
        wire_state = {
            "mode": mode,
            "exclusive_start_key": _encode_key(
                validated_state["exclusive_start_key"]
            ),
        }
    else:
        wire_state = {
            "mode": mode,
            "positions": {
                current_status: (
                    _encode_key(position) if position is not None else None
                )
                for current_status, position in validated_state["positions"].items()
            },
            "exhausted": validated_state["exhausted"],
        }

    now = _now_timestamp()
    payload = {
        "version": CURSOR_VERSION,
        "purpose": CURSOR_PURPOSE,
        "issued_at": now,
        "expires_at": now + CURSOR_TTL_SECONDS,
        "context": _context(
            actor=actor,
            status=status,
            severity=severity,
            limit=limit,
        ),
        "state": wire_state,
    }
    raw = json.dumps(
        payload,
        sort_keys=True,
        separators=(",", ":"),
    ).encode("utf-8")
    encoded_payload = base64.urlsafe_b64encode(raw).rstrip(b"=")
    signature = hmac.new(_cursor_signing_key(), encoded_payload, hashlib.sha256).digest()
    encoded_signature = base64.urlsafe_b64encode(signature).rstrip(b"=")
    return encoded_payload.decode("ascii") + "." + encoded_signature.decode("ascii")


def decode_alert_cursor(
    token: str | None,
    *,
    actor: UserInDB,
    status: str | None,
    severity: str | None,
    limit: int,
) -> dict[str, Any] | None:
    """Verifica firma, vencimiento, contexto y claves antes de consultar DynamoDB."""
    if token is None:
        return None
    if not token or len(token) > MAX_CURSOR_LENGTH:
        raise InvalidAlertCursorError("Cursor inválido.")

    try:
        encoded_payload, encoded_signature = token.split(".", maxsplit=1)
        padding = b"=" * (-len(encoded_payload) % 4)
        signature_padding = b"=" * (-len(encoded_signature) % 4)
        raw = base64.b64decode(
            encoded_payload + padding.decode("ascii"),
            altchars=b"-_",
            validate=True,
        )
        supplied_signature = base64.b64decode(
            encoded_signature + signature_padding.decode("ascii"),
            altchars=b"-_",
            validate=True,
        )
    except (ValueError, UnicodeDecodeError, binascii.Error):
        raise InvalidAlertCursorError("Cursor inválido.") from None

    expected_signature = hmac.new(
        _cursor_signing_key(), encoded_payload.encode("ascii"), hashlib.sha256
    ).digest()
    if not hmac.compare_digest(supplied_signature, expected_signature):
        raise InvalidAlertCursorError("Cursor inválido.")

    try:
        payload = json.loads(raw)
    except (json.JSONDecodeError, UnicodeDecodeError):
        raise InvalidAlertCursorError("Cursor inválido.") from None

    now = _now_timestamp()
    if (
        not isinstance(payload, dict)
        or payload.get("version") != CURSOR_VERSION
        or payload.get("purpose") != CURSOR_PURPOSE
        or not isinstance(payload.get("issued_at"), int)
        or not isinstance(payload.get("expires_at"), int)
        or payload["issued_at"] > now
        or payload["expires_at"] <= now
        or payload["expires_at"] - payload["issued_at"] != CURSOR_TTL_SECONDS
    ):
        raise InvalidAlertCursorError("Cursor inválido o expirado.")

    expected_context = _context(
        actor=actor,
        status=status,
        severity=severity,
        limit=limit,
    )
    if payload.get("context") != expected_context:
        raise InvalidAlertCursorError("Cursor incompatible con esta consulta.")

    mode = _expected_mode(actor, status, severity)
    return _validate_state(
        payload.get("state"),
        expected_mode=mode,
        actor=actor,
        status=status,
        severity=severity,
    )
