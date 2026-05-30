"""Parse admin DB setting strings with explicit invalid-value handling."""

import json
import logging
from typing import Any

logger = logging.getLogger(__name__)


def parse_json_list(raw: str, setting_name: str) -> list[str] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.debug("Ignoring invalid JSON list for %s: %s", setting_name, exc)
        return None
    if isinstance(data, list):
        return [str(item) for item in data]
    logger.debug("Ignoring non-list JSON for %s: %r", setting_name, type(data).__name__)
    return None


def parse_json_dict(raw: str, setting_name: str) -> dict[str, Any] | None:
    if not raw:
        return None
    try:
        data = json.loads(raw)
    except (json.JSONDecodeError, TypeError) as exc:
        logger.debug("Ignoring invalid JSON object for %s: %s", setting_name, exc)
        return None
    if isinstance(data, dict):
        return data
    logger.debug("Ignoring non-dict JSON for %s: %r", setting_name, type(data).__name__)
    return None


def parse_int_in_range(
    raw: str,
    setting_name: str,
    lo: int,
    hi: int,
) -> int | None:
    try:
        val = int(raw)
    except ValueError:
        logger.debug("Ignoring non-integer %s=%r", setting_name, raw)
        return None
    if lo <= val <= hi:
        return val
    logger.debug(
        "Ignoring out-of-range %s=%r (expected %d..%d)",
        setting_name,
        raw,
        lo,
        hi,
    )
    return None


def parse_int_min(raw: str, setting_name: str, min_val: int) -> int | None:
    try:
        val = int(raw)
    except ValueError:
        logger.debug("Ignoring non-integer %s=%r", setting_name, raw)
        return None
    if val >= min_val:
        return val
    logger.debug(
        "Ignoring out-of-range %s=%r (expected >= %d)",
        setting_name,
        raw,
        min_val,
    )
    return None


def parse_float_min(raw: str, setting_name: str, min_val: float) -> float | None:
    try:
        val = float(raw)
    except ValueError:
        logger.debug("Ignoring non-float %s=%r", setting_name, raw)
        return None
    if val >= min_val:
        return val
    logger.debug(
        "Ignoring out-of-range %s=%r (expected >= %s)",
        setting_name,
        raw,
        min_val,
    )
    return None


def parse_float_in_range(
    raw: str,
    setting_name: str,
    lo: float,
    hi: float,
) -> float | None:
    try:
        val = float(raw)
    except ValueError:
        logger.debug("Ignoring non-float %s=%r", setting_name, raw)
        return None
    if lo <= val <= hi:
        return val
    logger.debug(
        "Ignoring out-of-range %s=%r (expected %f..%f)",
        setting_name,
        raw,
        lo,
        hi,
    )
    return None
