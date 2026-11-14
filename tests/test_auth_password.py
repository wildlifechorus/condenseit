"""Admin password generation and the non-loopback bind guard."""

from __future__ import annotations

import logging
from pathlib import Path

import pytest
import uvicorn
from click.testing import CliRunner
from fastapi.testclient import TestClient

from condenseit.auth_password import InsecureBindError, assert_bind_allowed
from condenseit.cli import cli
from condenseit.store.database import ContentStore
from condenseit.web.app import create_app


def _blank_auth(monkeypatch: pytest.MonkeyPatch, data_dir: Path) -> None:
    """Point tests at a temp DB and leave both auth env vars unset."""
    monkeypatch.setenv("CONDENSEIT_DATA_DIR", str(data_dir))
    monkeypatch.setenv("CONDENSEIT_AUTH_PASSWORD", "")
    monkeypatch.setenv("DIGEST_PWA_AUTH_PASSWORD", "")
    monkeypatch.setenv("CONDENSEIT_DEFAULT_PASSWORD", "should-be-ignored")


def test_bind_guard_refuses_public_password_off_loopback() -> None:
    """The retired public password cannot be served on a network bind."""
    assert_bind_allowed("127.0.0.1", "condenseit")
    assert_bind_allowed("localhost", "condenseit")
    assert_bind_allowed("::1", "condenseit")
    assert_bind_allowed("0.0.0.0", "unique-secret")
    with pytest.raises(InsecureBindError):
        assert_bind_allowed("0.0.0.0", "condenseit")


def test_unset_password_is_generated_and_rejects_public_default(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """A blank password becomes a stored secret, not the old public value."""
    _blank_auth(monkeypatch, tmp_path / "data")
    client = TestClient(create_app())

    rejected = client.post("/api/auth/login", json={"password": "condenseit"})
    assert rejected.status_code == 401

    store = ContentStore()
    try:
        generated = store.get_setting("auth_password", "")
        assert generated
        assert generated != "condenseit"
        assert store.get_setting("auth_password_generated", "") == "1"
    finally:
        store.close()

    ok = client.post("/api/auth/login", json={"password": generated})
    assert ok.status_code == 200
    info = client.get("/api/config/password-info")
    assert info.status_code == 200
    assert info.json()["using_default"] is True


def test_generated_password_is_logged_once(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
    caplog: pytest.LogCaptureFixture,
) -> None:
    """The generated password is printed on the first start only."""
    _blank_auth(monkeypatch, tmp_path / "data")
    with caplog.at_level(logging.WARNING):
        create_app()
    store = ContentStore()
    try:
        generated = store.get_setting("auth_password", "")
    finally:
        store.close()
    assert generated in caplog.text

    caplog.clear()
    with caplog.at_level(logging.WARNING):
        create_app()
    assert generated not in caplog.text


def test_password_change_clears_generated_flag(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Replacing the generated password stops the first-run warning."""
    _blank_auth(monkeypatch, tmp_path / "data")
    client = TestClient(create_app())
    store = ContentStore()
    try:
        generated = store.get_setting("auth_password", "")
    finally:
        store.close()

    login = client.post("/api/auth/login", json={"password": generated})
    assert login.status_code == 200
    changed = client.put(
        "/api/config/password",
        json={
            "current_password": generated,
            "new_password": "new-password-1",
        },
    )
    assert changed.status_code == 200

    store = ContentStore()
    try:
        assert store.get_setting("auth_password", "") == "new-password-1"
        assert store.get_setting("auth_password_generated", "") == "0"
    finally:
        store.close()

    info = client.get("/api/config/password-info")
    assert info.json()["using_default"] is False
    client.post("/api/auth/logout")
    assert (
        client.post("/api/auth/login", json={"password": generated}).status_code
        == 401
    )
    assert (
        client.post(
            "/api/auth/login",
            json={"password": "new-password-1"},
        ).status_code
        == 200
    )


def test_serve_refuses_public_password_on_all_interfaces(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """`condenseit serve --host 0.0.0.0` exits when the password is public."""
    monkeypatch.setenv("CONDENSEIT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CONDENSEIT_AUTH_PASSWORD", "condenseit")
    called: dict[str, bool] = {}

    def fake_run(*_args: object, **_kwargs: object) -> None:
        called["ran"] = True

    monkeypatch.setattr(uvicorn, "run", fake_run)
    result = CliRunner().invoke(cli, ["serve", "--host", "0.0.0.0", "--port", "0"])
    assert result.exit_code != 0
    assert "public default" in result.output
    assert "ran" not in called


def test_serve_allows_public_password_on_loopback(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """Loopback still starts, with a warning, when the password is public."""
    monkeypatch.setenv("CONDENSEIT_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("CONDENSEIT_AUTH_PASSWORD", "condenseit")
    called: dict[str, bool] = {}

    def fake_run(*_args: object, **_kwargs: object) -> None:
        called["ran"] = True

    monkeypatch.setattr(uvicorn, "run", fake_run)
    result = CliRunner().invoke(
        cli,
        ["serve", "--host", "127.0.0.1", "--port", "9"],
    )
    assert result.exit_code == 0, result.output
    assert called.get("ran") is True
    assert "public default" in result.output


def test_reset_admin_password_prints_new_value(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    """The reset command stores a new password and prints it once."""
    _blank_auth(monkeypatch, tmp_path)
    create_app()
    result = CliRunner().invoke(cli, ["reset-admin-password"])
    assert result.exit_code == 0, result.output
    store = ContentStore()
    try:
        current = store.get_setting("auth_password", "")
        assert store.get_setting("auth_password_generated", "") == "1"
    finally:
        store.close()
    assert current
    assert current != "condenseit"
    assert current in result.output
