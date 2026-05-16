"""Tests for background digest job manager."""

from __future__ import annotations

import time
from unittest.mock import patch

from condenseit.web.digest_job import DigestJobManager


def test_job_manager_rejects_concurrent_runs() -> None:
    manager = DigestJobManager()
    with patch("condenseit.web.digest_job.execute_digest") as mock_run:

        def slow_run(*_a: object, **_k: object) -> dict[str, object]:
            time.sleep(0.5)
            return {
                "stats": {"articles_count": 1, "processing_time": "1s"},
                "post": {},
                "digest_id": 1,
            }

        mock_run.side_effect = slow_run
        ok1, _ = manager.start()
        ok2, msg2 = manager.start()
        assert ok1 is True
        assert ok2 is False
        assert "already running" in msg2.lower()
        if manager._thread:
            manager._thread.join(timeout=2)


def test_job_manager_completes() -> None:
    manager = DigestJobManager()
    with patch("condenseit.web.digest_job.execute_digest") as mock_run:
        mock_run.return_value = {
            "stats": {"articles_count": 3, "processing_time": "2s"},
            "post": {},
            "digest_id": 42,
        }
        ok, _ = manager.start()
        assert ok is True
        if manager._thread:
            manager._thread.join(timeout=2)
        snap = manager.snapshot()
        assert snap["state"] == "completed"
        assert snap["digest_id"] == 42
        assert "post_display" in snap
        assert "Post-run: no details returned." in snap["post_display"]
