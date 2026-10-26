"""Router raíz: reúne routers por área, sin contener lógica de negocio."""

from fastapi import APIRouter

from app.api.endpoints.alerts import router as alerts_router
from app.api.endpoints.auth import router as auth_router
from app.api.endpoints.events import router as events_router
from app.api.endpoints.health import router as health_router
from app.api.endpoints.simulations import router as simulations_router
from app.api.endpoints.users import router as users_router

api_router = APIRouter()

# Cada módulo define sus rutas del área; sus operaciones se agregarán al
# implementar las tareas correspondientes del Workplan.
api_router.include_router(auth_router, prefix="/auth", tags=["auth"])
api_router.include_router(users_router, prefix="/users")
api_router.include_router(events_router)
api_router.include_router(alerts_router)
api_router.include_router(simulations_router)
api_router.include_router(health_router)
