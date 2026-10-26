"""Pruebas API de administración de cuentas y permisos."""

import pytest
from fastapi.testclient import TestClient

from app.api.deps import get_current_user
from app.api.endpoints import users as users_api
from app.main import app
from app.repositories.users import UserAlreadyExistsError, UserNotFoundError
from app.schemas.users import UserInDB, UserPublic
from app.services.user_management import LastActiveAdminError


def _user(role: str = "admin", status: str = "active", email: str = "admin@example.com") -> UserInDB:
    return UserInDB(
        email_normalized=email,
        user_id="user-1",
        display_name="Test User",
        password_hash="never-return-this-hash",
        role=role,
        status=status,
        created_at="2026-10-26T00:00:00Z",
        updated_at="2026-10-26T00:00:00Z",
    )


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    principal = _user()
    app.dependency_overrides[get_current_user] = lambda: principal
    monkeypatch.setattr(users_api, "create_account", lambda *args: _user().to_public())
    monkeypatch.setattr(users_api, "list_accounts", lambda: [_user().to_public()])
    monkeypatch.setattr(users_api, "update_account_role", lambda email, role: _user(role=role).to_public())
    monkeypatch.setattr(users_api, "update_account_status", lambda email, state: _user(status=state).to_public())
    with TestClient(app) as test_client:
        yield test_client
    app.dependency_overrides.clear()


def test_admin_can_create_user_without_exposing_hash(client: TestClient) -> None:
    response = client.post("/users", json={
        "email": "New.User@example.com", "display_name": "New User", "password": "safe-password",
        "role": "analyst",
    })

    assert response.status_code == 201
    assert response.json()["email"] == "admin@example.com"
    assert "password_hash" not in response.json()


def test_duplicate_email_returns_conflict(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def duplicate(*args):
        raise UserAlreadyExistsError()

    monkeypatch.setattr(users_api, "create_account", duplicate)
    response = client.post("/users", json={
        "email": "same@example.com", "display_name": "Same", "password": "safe-password", "role": "analyst",
    })
    assert response.status_code == 409


def test_analyst_cannot_manage_accounts(client: TestClient) -> None:
    app.dependency_overrides[get_current_user] = lambda: _user(role="analyst")
    assert client.get("/users").status_code == 403
    assert client.post("/users", json={}).status_code == 403
    assert client.patch("/users/a@example.com/role", json={"role": "admin"}).status_code == 403


def test_anonymous_user_is_rejected() -> None:
    with TestClient(app) as anonymous_client:
        response = anonymous_client.get("/users")
    assert response.status_code == 401


def test_admin_can_list_without_password_hash(client: TestClient) -> None:
    response = client.get("/users")
    assert response.status_code == 200
    assert "password_hash" not in response.json()[0]


def test_admin_can_change_role_and_status(client: TestClient) -> None:
    assert client.patch("/users/a@example.com/role", json={"role": "analyst"}).json()["role"] == "analyst"
    assert client.patch("/users/a@example.com/status", json={"status": "disabled"}).json()["status"] == "disabled"


@pytest.mark.parametrize(("path", "payload"), [
    ("role", {"role": "owner"}),
    ("status", {"status": "paused"}),
])
def test_invalid_role_and_status_are_rejected(client: TestClient, path: str, payload: dict) -> None:
    response = client.patch(f"/users/a@example.com/{path}", json=payload)
    assert response.status_code == 422


def test_user_not_found_returns_404(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def missing(*args):
        raise UserNotFoundError()

    monkeypatch.setattr(users_api, "update_account_role", missing)
    assert client.patch("/users/missing@example.com/role", json={"role": "analyst"}).status_code == 404


def test_last_active_admin_cannot_be_removed(client: TestClient, monkeypatch: pytest.MonkeyPatch) -> None:
    def protected(*args):
        raise LastActiveAdminError("Debe permanecer al menos un administrador activo.")

    monkeypatch.setattr(users_api, "update_account_status", protected)
    response = client.patch("/users/admin@example.com/status", json={"status": "disabled"})
    assert response.status_code == 409
