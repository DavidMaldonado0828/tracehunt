"""Limitador local concurrente para fallos de inicio de sesión."""

from collections import deque
from hashlib import sha256
from math import ceil
from threading import Lock
from time import monotonic

from app.core.config import get_settings
from app.schemas.users import normalize_email

_failures: dict[str, deque[float]] = {}
_lock = Lock()


def _key(email: str, client_ip: str) -> str:
    normalized_pair = f"{normalize_email(email)}\0{client_ip}"
    return sha256(normalized_pair.encode("utf-8")).hexdigest()


def reserve_attempt(email: str, client_ip: str) -> int | None:
    """Reserva atómicamente un intento o retorna los segundos de espera."""
    now = monotonic()
    settings = get_settings()
    cutoff = now - settings.login_rate_limit_window_seconds
    key = _key(email, client_ip)
    with _lock:
        for stale_key, stale_attempts in list(_failures.items()):
            while stale_attempts and stale_attempts[0] <= cutoff:
                stale_attempts.popleft()
            if not stale_attempts:
                _failures.pop(stale_key, None)
        attempts = _failures.setdefault(key, deque())
        if len(attempts) < settings.login_rate_limit_attempts:
            attempts.append(now)
            return None
        return max(1, ceil(attempts[0] + settings.login_rate_limit_window_seconds - now))


def clear_failures(email: str, client_ip: str) -> None:
    with _lock:
        _failures.pop(_key(email, client_ip), None)


def reset_for_tests() -> None:
    """Limpia contadores para aislar pruebas."""
    with _lock:
        _failures.clear()
