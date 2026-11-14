"""Shared pytest fixtures for CondenseIt tests."""

from __future__ import annotations

import pytest


@pytest.fixture(autouse=True)
def clear_auth_env(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pin an explicit test password.

    Production does not fall back to this value. Set the env var (not delete)
    so load_dotenv(override=False) in load_config won't re-populate it from
    .env. Tests that cover generation override this with an empty string.
    """
    monkeypatch.setenv("DIGEST_PWA_AUTH_PASSWORD", "")
    monkeypatch.setenv("CONDENSEIT_AUTH_PASSWORD", "condenseit")
    monkeypatch.setenv("DIGEST_PWA_SESSION_SECRET", "")
