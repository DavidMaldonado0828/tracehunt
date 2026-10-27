"""Pruebas API del límite de intentos de inicio de sesión."""

import pytest
from fastapi.testclient import TestClient

from app.api.endpoints import auth as auth_api
from app.core.config import Settings
from app.main import app
from app.services import login_rate_limit


@pytest.fixture
def login_client(monkeypatch: pytest.MonkeyPatch):
    login_rate_limit.reset_for_tests()
    monkeypatch.setattr(login_rate_limit, "get_settings", lambda: Settings(
        jwt_secret="x" * 32, login_rate_limit_attempts=5, login_rate_limit_window_seconds=900,
    ))
    monkeypatch.setattr(auth_api, "authenticate_user", lambda email, password: None)
    with TestClient(app) as client:
        yield client
    login_rate_limit.reset_for_tests()


def _login(client: TestClient, email: str = "unknown@example.com"):
    return client.post("/auth/login", json={"email": email, "password": "wrong-password"})


def test_five_invalid_attempts_use_generic_error_and_sixth_is_limited(login_client: TestClient) -> None:
    responses = [_login(login_client) for _ in range(5)]
    assert all(response.status_code == 401 for response in responses)
    assert responses[-1].json()["detail"] == "Credenciales inválidas"

    limited = _login(login_client)
    assert limited.status_code == 429
    assert int(limited.headers["Retry-After"]) > 0


def test_normalized_email_shares_attempt_budget(login_client: TestClient) -> None:
    for _ in range(5):
        assert _login(login_client).status_code == 401
    assert _login(login_client, "UNKNOWN@example.com").status_code == 429


def test_success_resets_the_attempt_budget(login_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    for _ in range(4):
        assert _login(login_client).status_code == 401
    monkeypatch.setattr(auth_api, "authenticate_user", lambda email, password: object())
    monkeypatch.setattr(auth_api, "create_token_for", lambda user: ("token", 3600))
    success = login_client.post("/auth/login", json={"email": "unknown@example.com", "password": "correct"})
    assert success.status_code == 200

    monkeypatch.setattr(auth_api, "authenticate_user", lambda email, password: None)
    assert _login(login_client).status_code == 401


def test_concurrent_reservations_do_not_exceed_configured_limit(login_client: TestClient) -> None:
    from concurrent.futures import ThreadPoolExecutor

    def reserve(_):
        return login_rate_limit.reserve_attempt("race@example.com", "127.0.0.1")

    with ThreadPoolExecutor(max_workers=12) as executor:
        results = list(executor.map(reserve, range(12)))
    assert sum(result is None for result in results) == 5
    assert all(result is None or result > 0 for result in results)


def test_attempt_budget_expires_after_configured_window(login_client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    now = [1000.0]
    monkeypatch.setattr(login_rate_limit, "monotonic", lambda: now[0])
    for _ in range(5):
        assert login_rate_limit.reserve_attempt("window@example.com", "127.0.0.1") is None
    assert login_rate_limit.reserve_attempt("window@example.com", "127.0.0.1") is not None

    now[0] += 901
    assert login_rate_limit.reserve_attempt("window@example.com", "127.0.0.1") is None
