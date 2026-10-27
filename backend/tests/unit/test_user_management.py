"""Pruebas unitarias del servicio administrativo de usuarios."""

import pytest

from app.schemas.users import UserInDB
from app.services import user_management


def _admin(email: str = "admin@example.com") -> UserInDB:
    return UserInDB(
        email_normalized=email,
        user_id="user-1",
        display_name="Administrator",
        password_hash="hash-only",
        role="admin",
        status="active",
        created_at="2026-10-26T00:00:00Z",
        updated_at="2026-10-26T00:00:00Z",
    )


def test_create_account_normalizes_email_hashes_password_and_returns_public(monkeypatch: pytest.MonkeyPatch) -> None:
    captured: list[UserInDB] = []
    monkeypatch.setattr(user_management, "hash_password", lambda password: f"argon:{password}")
    monkeypatch.setattr(user_management, "persist_user", lambda user: captured.append(user) or user)

    result = user_management.create_account(" New.User@Example.com ", "New User", "secret-password", "analyst")

    assert captured[0].email_normalized == "new.user@example.com"
    assert captured[0].password_hash == "argon:secret-password"
    assert "password_hash" not in result.model_dump()


def test_last_active_admin_cannot_be_demoted(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(user_management, "load_users", lambda: [_admin()])

    with pytest.raises(user_management.LastActiveAdminError):
        user_management.update_account_role("admin@example.com", "analyst")


def test_admin_can_be_demoted_when_another_active_admin_remains(monkeypatch: pytest.MonkeyPatch) -> None:
    second_admin = _admin("other@example.com").model_copy(update={"user_id": "user-2"})
    monkeypatch.setattr(user_management, "load_users", lambda: [_admin(), second_admin])
    monkeypatch.setattr(user_management, "persist_user_update", lambda email, changes: _admin().model_copy(update={"role": "analyst"}))

    assert user_management.update_account_role("admin@example.com", "analyst").role == "analyst"
