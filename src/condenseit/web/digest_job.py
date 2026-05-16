"""Background digest runs triggered from the web UI."""

from __future__ import annotations

import logging
import threading
from dataclasses import asdict, dataclass
from datetime import UTC, datetime
from typing import Any

from condenseit.services.digest_runner import execute_digest
from condenseit.services.post_run_format import format_post_run_lines

logger = logging.getLogger(__name__)


@dataclass
class DigestJobSnapshot:
    state: str = "idle"
    message: str = ""
    started_at: str | None = None
    finished_at: str | None = None
    stats: dict[str, Any] | None = None
    post: dict[str, Any] | None = None
    post_display: str = ""
    digest_id: int | None = None
    error: str | None = None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


class DigestJobManager:
    """Single-flight background digest runner."""

    def __init__(self, config_path: str | None = None) -> None:
        self._config_path = config_path
        self._lock = threading.Lock()
        self._thread: threading.Thread | None = None
        self._snapshot = DigestJobSnapshot()

    def snapshot(self) -> dict[str, Any]:
        with self._lock:
            return self._snapshot.to_dict()

    @property
    def is_running(self) -> bool:
        with self._lock:
            return self._snapshot.state == "running"

    def start(
        self,
        *,
        dry_run: bool = False,
        skip_email: bool = False,
        skip_deploy: bool = False,
    ) -> tuple[bool, str]:
        with self._lock:
            if self._snapshot.state == "running":
                return False, "A digest is already running."
            self._snapshot = DigestJobSnapshot(
                state="running",
                message="Collecting feeds and summarizing…",
                started_at=_now_iso(),
            )
            self._thread = threading.Thread(
                target=self._run,
                kwargs={
                    "dry_run": dry_run,
                    "skip_email": skip_email,
                    "skip_deploy": skip_deploy,
                },
                name="condenseit-digest",
                daemon=True,
            )
            self._thread.start()
        return True, "Digest started."

    def _run(
        self,
        *,
        dry_run: bool,
        skip_email: bool,
        skip_deploy: bool,
    ) -> None:
        try:
            result = execute_digest(
                self._config_path,
                dry_run=dry_run,
                skip_email=skip_email,
                skip_deploy=skip_deploy,
            )
            stats = result["stats"]
            articles = stats.get("articles_count", 0)
            slim_stats = {k: v for k, v in stats.items() if k != "digest_items"}
            raw_post = result.get("post")
            post_display = "\n".join(
                format_post_run_lines(
                    raw_post if isinstance(raw_post, dict) else None,
                ),
            )
            with self._lock:
                self._snapshot = DigestJobSnapshot(
                    state="completed",
                    message=(
                        f"Done: {articles} articles in "
                        f"{stats.get('processing_time', '?')}"
                    ),
                    started_at=self._snapshot.started_at,
                    finished_at=_now_iso(),
                    stats=slim_stats,
                    post=result.get("post"),
                    post_display=post_display,
                    digest_id=result.get("digest_id"),
                )
        except Exception as exc:
            logger.exception("Digest job failed")
            with self._lock:
                self._snapshot = DigestJobSnapshot(
                    state="failed",
                    message="Digest failed.",
                    started_at=self._snapshot.started_at,
                    finished_at=_now_iso(),
                    error=str(exc),
                )

    def dismiss(self) -> None:
        """Clear completed/failed state back to idle."""
        with self._lock:
            if self._snapshot.state == "running":
                return
            self._snapshot = DigestJobSnapshot()


def _now_iso() -> str:
    return datetime.now(UTC).strftime("%Y-%m-%dT%H:%M:%SZ")
