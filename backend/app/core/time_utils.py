"""Utilidades de tiempo compartidas por los servicios de aplicación."""

from datetime import datetime, timezone


def utc_now_iso() -> str:
    """Devuelve el instante actual en UTC como ISO-8601 terminado en Z."""
    return datetime.now(timezone.utc).isoformat(timespec="seconds").replace(
        "+00:00", "Z"
    )
