"""Helpers for per-source collector health reporting."""

import logging
from collections.abc import Callable
from typing import TypeVar

logger = logging.getLogger(__name__)

T = TypeVar("T")
HealthEntry = tuple[str, str | None, int]


def collect_with_health(
    url: str,
    collect_fn: Callable[[], list[T]],
    *,
    log_label: str,
) -> tuple[list[T], HealthEntry]:
    """Run a collector callback and return items plus a health entry."""
    try:
        items = collect_fn()
    except Exception as exc:
        logger.exception("%s", log_label)
        return [], (url, str(exc), 0)
    return items, (url, None, len(items))
