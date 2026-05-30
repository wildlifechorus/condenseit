"""Shared feed entry date parsing for RSS-style collectors."""

import logging
from datetime import UTC, datetime
from email.utils import parsedate_to_datetime
from typing import Any

logger = logging.getLogger(__name__)


def _from_time_struct(value: Any) -> str | None:
    if not value:
        return None
    try:
        return datetime(*value[:6], tzinfo=UTC).isoformat()
    except (TypeError, ValueError) as exc:
        logger.debug("Could not parse time struct %r: %s", value, exc)
        return None


def _from_rfc2822(value: Any) -> str | None:
    if not value:
        return None
    try:
        return parsedate_to_datetime(value).isoformat()
    except (TypeError, ValueError, OSError) as exc:
        logger.debug("Could not parse RFC2822 date %r: %s", value, exc)
        return None


def parse_feed_entry_date(entry: Any, *, fallback_now: bool = True) -> str:
    """Return an ISO timestamp from a feedparser entry."""
    for candidate in (
        _from_time_struct(entry.get("published_parsed")),
        _from_rfc2822(entry.get("published")),
        _from_time_struct(entry.get("updated_parsed")),
        _from_rfc2822(entry.get("updated")),
    ):
        if candidate:
            return candidate
    if fallback_now:
        return datetime.now(UTC).isoformat()
    return ""


def unix_timestamp_to_iso(ts: Any, *, use_float: bool = False) -> str:
    """Convert a unix epoch value to ISO format, falling back to now()."""
    if not ts:
        return datetime.now(UTC).isoformat()
    try:
        value = float(ts) if use_float else int(ts)
        return datetime.fromtimestamp(value, tz=UTC).isoformat()
    except (TypeError, ValueError, OSError) as exc:
        logger.debug("Could not parse unix timestamp %r: %s", ts, exc)
        return datetime.now(UTC).isoformat()
