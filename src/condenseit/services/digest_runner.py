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
    skip_deploy: bool = False,
) -> dict[str, Any]:
    """Collect, summarize, save digest; return stats plus optional post-run info.

    DigestPipeline is used as a context manager so its SQLite connection is
    always closed in the finally block. Without explicit close, the connection
    can survive long after the run completes (GC is unreliable for objects with
    complex references), holding a SQLite writer lock that blocks every write
    on the web server's shared connection (/api/read, /api/dismiss, etc.).
    """
    cfg: AppConfig = load_config(config_path)
    needs_ollama = not dry_run and cfg.llm.provider in ("ollama", "fallback")

    with DigestPipeline(config_path) as pipeline:
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
                "deploy": {"status": "skipped", "reason": "dry run"},
            }
        else:
            post = pipeline.post_run(skip_deploy=skip_deploy)

        latest = pipeline.store.latest_digest()
        digest_id = latest["id"] if latest else None
        logger.info("Digest run finished (id=%s)", digest_id)
        return {"stats": stats, "post": post, "digest_id": digest_id}
