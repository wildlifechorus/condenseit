"""Resolve the admin password without a shared public default."""

from __future__ import annotations

import logging
import os
import secrets

from condenseit.store.database import ContentStore

logger = logging.getLogger(__name__)

# Historical public fallback. Accepted only when set explicitly, and never
# on a non-loopback bind. Not used when the password is unset.
INSECURE_PUBLIC_PASSWORD = "condenseit"

_PASSWORD_KEY = "auth_password"
_GENERATED_FLAG = "auth_password_generated"
_LOOPBACK_HOSTS = frozenset({"127.0.0.1", "::1", "localhost"})


class InsecureBindError(Exception):
    """Refusing to listen because the admin password is public."""


def env_auth_password() -> str:
    """Password from the environment, ignoring blank values."""
    return (
        os.environ.get("CONDENSEIT_AUTH_PASSWORD", "").strip()
        or os.environ.get("DIGEST_PWA_AUTH_PASSWORD", "").strip()
    )


def is_loopback_host(host: str) -> bool:
    """True for the loopback names `serve` treats as local-only."""
    normalized = host.strip().lower().strip("[]")
    return normalized in _LOOPBACK_HOSTS


def configured_auth_password(store: ContentStore) -> str:
    """DB password, otherwise the env password. Empty when neither is set."""
    db_pw = store.get_setting(_PASSWORD_KEY, "").strip()
    if db_pw:
        return db_pw
    return env_auth_password()


def ensure_auth_password(store: ContentStore) -> str:
    """Return the effective password, generating one unique value if needed.

    The generated password is stored and logged once. Later calls return the
    stored value without printing it again.
    """
    existing = configured_auth_password(store)
    if existing:
        return existing

    generated = secrets.token_urlsafe(18)
    store.set_setting(_PASSWORD_KEY, generated)
    store.set_setting(_GENERATED_FLAG, "1")
    logger.warning(
        "No admin password was configured. Generated a random password "
        "and saved it to the database. It will not be printed again. "
        "Admin password: %s. Change it in Admin > Security or set "
        "CONDENSEIT_AUTH_PASSWORD. If you lose it, run "
        "`condenseit reset-admin-password`. The old public default "
        "no longer works.",
        generated,
    )
    return generated


def password_was_generated(store: ContentStore) -> bool:
    """True until an operator replaces a generated password."""
    return store.get_setting(_GENERATED_FLAG, "").strip() == "1"


def password_info(store: ContentStore) -> dict[str, str | bool]:
    """Source label and whether the UI should nag for a password change."""
    db_pw = store.get_setting(_PASSWORD_KEY, "").strip()
    if db_pw:
        source = "db"
    elif env_auth_password():
        source = "env"
    else:
        source = "generated"
    return {
        "source": source,
        "using_default": password_was_generated(store),
    }


def clear_generated_password_flag(store: ContentStore) -> None:
    """Stop treating the current password as an unreviewed generated value."""
    if store.get_setting(_GENERATED_FLAG, "").strip():
        store.set_setting(_GENERATED_FLAG, "0")


def reset_admin_password(store: ContentStore) -> str:
    """Replace the stored password and mark it as still needing a change."""
    generated = secrets.token_urlsafe(18)
    store.set_setting(_PASSWORD_KEY, generated)
    store.set_setting(_GENERATED_FLAG, "1")
    return generated


def warn_if_public_password(password: str) -> None:
    """Log when the effective password is the retired public value."""
    if password != INSECURE_PUBLIC_PASSWORD:
        return
    logger.warning(
        "The admin password is the public value %r. `condenseit serve` "
        "refuses to listen on a non-loopback address until a unique "
        "CONDENSEIT_AUTH_PASSWORD is set.",
        INSECURE_PUBLIC_PASSWORD,
    )


def assert_bind_allowed(host: str, password: str) -> None:
    """Refuse a network bind that would expose the public admin password."""
    if password != INSECURE_PUBLIC_PASSWORD or is_loopback_host(host):
        return
    raise InsecureBindError(
        f"Refusing to listen on {host}: the admin password is the public "
        "default. Set CONDENSEIT_AUTH_PASSWORD to a unique value."
    )
