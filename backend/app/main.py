"""Punto de entrada de FastAPI para el backend de TraceHunt."""

from collections.abc import AsyncIterator
from contextlib import asynccontextmanager

from fastapi import FastAPI

from app.api.router import api_router
from app.services.bootstrap import ensure_initial_admin


@asynccontextmanager
async def lifespan(_: FastAPI) -> AsyncIterator[None]:
    """Prepara la cuenta semilla antes de aceptar solicitudes HTTP."""
    ensure_initial_admin()
    yield


app = FastAPI(title="TraceHunt API", version="0.1.0", lifespan=lifespan)
app.include_router(api_router)
