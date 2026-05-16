"""Shared pytest fixtures for CondenseIt tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def clear_auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Ensure no auth password is active during tests so API endpoints are open.

    Set to empty string (not delete) so load_dotenv(override=False) in
    load_config won't re-populate the vars from .env.
    """
    monkeypatch.setenv("DIGEST_PWA_AUTH_PASSWORD", "")
    monkeypatch.setenv("CONDENSEIT_AUTH_PASSWORD", "")
    monkeypatch.setenv("DIGEST_PWA_SESSION_SECRET", "")
