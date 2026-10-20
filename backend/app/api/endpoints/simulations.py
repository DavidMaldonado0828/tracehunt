"""Router de simulaciones; autenticación, lease e idempotencia no están implementadas."""

from fastapi import APIRouter

router = APIRouter(tags=["simulations"])
