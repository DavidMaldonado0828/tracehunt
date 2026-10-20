"""Punto de entrada de FastAPI para el backend de TraceHunt."""

from fastapi import FastAPI

from app.api.router import api_router

app = FastAPI(title="TraceHunt API", version="0.1.0")
app.include_router(api_router)
