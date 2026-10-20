"""Router de autenticación; sus rutas esperan la decisión DEC-03 del Workplan."""

from fastapi import APIRouter

router = APIRouter(tags=["auth"])
