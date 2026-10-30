"""Pruebas unitarias de autenticidad y alcance de cursores de alertas."""

from types import SimpleNamespace

import pytest

from app.schemas.users import UserInDB
from app.services import pagination


def _actor(role: str = "admin", user_id: str = "user-1") -> UserInDB:
    return UserInDB(
        email_normalized="test@example.invalid",
        user_id=user_id,
        display_name="Test User",
        password_hash="not-used",
        role=role,
        status="active",
        created_at="2026-10-01T00:00:00Z",
        updated_at="2026-10-01T00:00:00Z",
    )


@pytest.fixture(autouse=True)
def signing_settings(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        pagination,
        "get_settings",
        lambda: SimpleNamespace(jwt_secret="test-secret-" + "x" * 32),
    )


def _all_statuses_state() -> dict:
    return {
        "mode": "all_statuses",
        "positions": {
            "open": {
                "alert_id": "alert-open",
                "status": "open",
                "created_at_alert": "2026-10-01T00:00:00Z#alert-open",
            },
            "investigating": None,
            "resolved": None,
        },
        "exhausted": {
            "open": False,
            "investigating": False,
            "resolved": False,
        },
    }


def test_signed_all_statuses_cursor_round_trips() -> None:
    actor = _actor()
    token = pagination.encode_alert_cursor(
        _all_statuses_state(),
        actor=actor,
        status=None,
        severity=None,
        limit=25,
    )

    assert token is not None
    decoded = pagination.decode_alert_cursor(
        token,
        actor=actor,
        status=None,
        severity=None,
        limit=25,
    )
    assert decoded == _all_statuses_state()


def test_tampered_cursor_is_rejected() -> None:
    actor = _actor()
    token = pagination.encode_alert_cursor(
        _all_statuses_state(),
        actor=actor,
        status=None,
        severity=None,
        limit=25,
    )
    assert token is not None
    replacement = "A" if token[0] != "A" else "B"

    with pytest.raises(pagination.InvalidAlertCursorError):
        pagination.decode_alert_cursor(
            replacement + token[1:],
            actor=actor,
            status=None,
            severity=None,
            limit=25,
        )


def test_expired_cursor_is_rejected(monkeypatch: pytest.MonkeyPatch) -> None:
    actor = _actor()
    monkeypatch.setattr(pagination, "_now_timestamp", lambda: 100)
    token = pagination.encode_alert_cursor(
        _all_statuses_state(),
        actor=actor,
        status=None,
        severity=None,
        limit=25,
    )
    monkeypatch.setattr(
        pagination,
        "_now_timestamp",
        lambda: 100 + pagination.CURSOR_TTL_SECONDS,
    )

    with pytest.raises(pagination.InvalidAlertCursorError):
        pagination.decode_alert_cursor(
            token,
            actor=actor,
            status=None,
            severity=None,
            limit=25,
        )


@pytest.mark.parametrize(
    "context",
    [
        {"status": "open", "severity": None, "limit": 25, "actor": _actor()},
        {"status": None, "severity": "high", "limit": 25, "actor": _actor()},
        {"status": None, "severity": None, "limit": 10, "actor": _actor()},
        {"status": None, "severity": None, "limit": 25, "actor": _actor(user_id="other")},
    ],
)
def test_cursor_bound_to_filters_limit_and_actor(context: dict) -> None:
    actor = _actor()
    token = pagination.encode_alert_cursor(
        _all_statuses_state(),
        actor=actor,
        status=None,
        severity=None,
        limit=25,
    )

    with pytest.raises(pagination.InvalidAlertCursorError):
        pagination.decode_alert_cursor(
            token,
            actor=context["actor"],
            status=context["status"],
            severity=context["severity"],
            limit=context["limit"],
        )


def test_single_query_cursor_round_trips() -> None:
    actor = _actor(role="analyst")
    state = {
        "mode": "single",
        "exclusive_start_key": {
            "alert_id": "alert-1",
            "owner_user_id": "user-1",
            "created_at_alert": "2026-10-01T00:00:00Z#alert-1",
        },
    }
    token = pagination.encode_alert_cursor(
        state,
        actor=actor,
        status=None,
        severity=None,
        limit=25,
    )

    assert pagination.decode_alert_cursor(
        token,
        actor=actor,
        status=None,
        severity=None,
        limit=25,
    ) == state


def test_invalid_cursor_format_is_rejected() -> None:
    with pytest.raises(pagination.InvalidAlertCursorError):
        pagination.decode_alert_cursor(
            "not-a-signed-token",
            actor=_actor(),
            status=None,
            severity=None,
            limit=25,
        )
