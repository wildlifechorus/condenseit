"""Encrypted API key storage."""

from __future__ import annotations

import os
from datetime import UTC, datetime
from pathlib import Path

from cryptography.fernet import Fernet

from condenseit.config import get_data_dir
from condenseit.store.database import ContentStore


class SecureKeyStore:
    def __init__(self, store: ContentStore) -> None:
        self.store = store
        self._fernet = self._get_fernet()

    def _key_path(self) -> Path:
        return get_data_dir() / ".encryption.key"

    def _get_fernet(self) -> Fernet:
        path = self._key_path()
        if path.exists():
            key = path.read_bytes()
        else:
            key = Fernet.generate_key()
            path.write_bytes(key)
            path.chmod(0o600)
        return Fernet(key)

    def store_key(self, service: str, key_value: str, key_name: str = "") -> None:
        encrypted = self._fernet.encrypt(key_value.encode()).decode()
        if len(key_value) > 12:
            preview = f"{key_value[:6]}...{key_value[-4:]}"
        else:
            preview = "***"
        self.store.db["api_keys"].upsert(
            {
                "service": service,
                "key_name": key_name or service,
                "encrypted_value": encrypted,
                "key_preview": preview,
                "updated_at": datetime.now(UTC).isoformat(),
            },
            pk="service",
        )

    def get_key(self, service: str) -> str | None:
        try:
            row = self.store.db["api_keys"].get(service)
            return self._fernet.decrypt(row["encrypted_value"].encode()).decode()
        except Exception:
            return _env_fallback(service)

    def list_keys(self) -> list[dict[str, str]]:
        if "api_keys" not in self.store.db.table_names():
            return []
        return [dict(r) for r in self.store.db["api_keys"].rows]

    def delete_key(self, service: str) -> None:
        self.store.db["api_keys"].delete(service)


def _env_fallback(service: str) -> str | None:
    mapping = {
        "resend": "RESEND_API_KEY",
        "openrouter": "OPENROUTER_API_KEY",
    }
    var = mapping.get(service, f"{service.upper()}_API_KEY")
    return os.environ.get(var)
