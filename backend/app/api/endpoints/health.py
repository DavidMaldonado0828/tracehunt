"""Comprobación básica de disponibilidad; no consulta dependencias externas."""

from fastapi import APIRouter

router = APIRouter()


@router.get("/health", tags=["health"])
def health_check() -> dict[str, str]:
    """Indica que el proceso HTTP responde."""
    return {"status": "ok"}
