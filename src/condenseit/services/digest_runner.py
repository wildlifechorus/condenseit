"""Run the digest pipeline once (shared by CLI and web UI)."""

from __future__ import annotations

import logging
from typing import Any

from condenseit.config import AppConfig, load_config
from condenseit.pipeline.orchestrator import DigestPipeline
from condenseit.services.ollama_lifecycle import OllamaLifecycle

logger = logging.getLogger(__name__)


def execute_digest(
    config_path: str | None = None,
    *,
    dry_run: bool = False,
    skip_email: bool = False,
    skip_deploy: bool = False,
) -> dict[str, Any]:
    """Collect, summarize, save digest; return stats plus optional post-run info."""
    cfg: AppConfig = load_config(config_path)
    pipeline = DigestPipeline(config_path)
    needs_ollama = not dry_run and cfg.llm.provider in ("ollama", "fallback")

    if dry_run:
        stats = pipeline.run(dry_run=True)
    elif needs_ollama:
        with OllamaLifecycle(
            host=cfg.llm.ollama_host,
            manage=cfg.llm.manage_lifecycle,
        ):
            stats = pipeline.run(dry_run=False)
    else:
        stats = pipeline.run(dry_run=False)

    if dry_run:
        post = {
            "email": {"status": "skipped", "reason": "dry run"},
            "deploy": {"status": "skipped", "reason": "dry run"},
        }
    else:
        post = pipeline.post_run(skip_email=skip_email, skip_deploy=skip_deploy)

    latest = pipeline.store.latest_digest()
    digest_id = latest["id"] if latest else None
    logger.info("Digest run finished (id=%s)", digest_id)
    return {"stats": stats, "post": post, "digest_id": digest_id}
