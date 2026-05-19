"""Built-in digest scheduler.

The scheduler loop always runs as a background asyncio task when the server
starts. Whether it actually fires digests is controlled by the ``is_enabled``
callable, which checks the DB setting (set via Admin > Schedule) and falls
back to the ``CONDENSEIT_SCHEDULER_ENABLED`` env var. Schedule times are read
from the DB on every loop iteration so admin-panel changes take effect without
a restart.
"""

from __future__ import annotations

import asyncio
import logging
import os
from collections.abc import Callable
from contextlib import suppress
from datetime import UTC, datetime, timedelta
from zoneinfo import ZoneInfo, ZoneInfoNotFoundError

logger = logging.getLogger(__name__)

_SCHEDULER_STATE: dict[str, object] = {
    "enabled": False,
    "next_run_utc": None,
    "schedule_times": [],
}

_RESCHEDULE_EVENT: asyncio.Event | None = None


def _parse_times(times: list[str]) -> list[tuple[int, int]]:
    result: list[tuple[int, int]] = []
    for t in times:
        t = t.strip()
        if not t:
            continue
        try:
            parts = t.split(":")
            h, m = int(parts[0]), int(parts[1])
            if 0 <= h < 24 and 0 <= m < 60:
                result.append((h, m))
            else:
                logger.warning("Skipping invalid schedule time: %r", t)
        except (IndexError, ValueError):
            logger.warning("Could not parse schedule time %r", t)
    return result


def _seconds_until_next(
    parsed_times: list[tuple[int, int]],
    now: datetime,
) -> float:
    if not parsed_times:
        return 3600.0

    today = now.date()
    candidates: list[datetime] = []
    for h, m in parsed_times:
        candidate = datetime(
            today.year, today.month, today.day, h, m,
            tzinfo=now.tzinfo,
        )
        if candidate <= now:
            candidate += timedelta(days=1)
        candidates.append(candidate)

    next_run = min(candidates)
    delta = (next_run - now).total_seconds()
    return max(delta, 1.0)


async def _wait_with_event(seconds: float) -> bool:
    global _RESCHEDULE_EVENT
    if _RESCHEDULE_EVENT is None:
        _RESCHEDULE_EVENT = asyncio.Event()
    _RESCHEDULE_EVENT.clear()

    sleep_task = asyncio.ensure_future(asyncio.sleep(seconds))
    event_task = asyncio.ensure_future(_RESCHEDULE_EVENT.wait())
    try:
        done, pending = await asyncio.wait(
            [sleep_task, event_task],
            return_when=asyncio.FIRST_COMPLETED,
        )
    except asyncio.CancelledError:
        sleep_task.cancel()
        event_task.cancel()
        raise

    for task in pending:
        task.cancel()
        with suppress(asyncio.CancelledError):
            await task

    return event_task in done


async def trigger_reschedule() -> None:
    global _RESCHEDULE_EVENT
    if _RESCHEDULE_EVENT is not None:
        _RESCHEDULE_EVENT.set()


def _resolve_timezone(tz_name: str) -> ZoneInfo:
    """Return a ZoneInfo for *tz_name*, falling back to UTC on invalid names."""
    try:
        return ZoneInfo(tz_name)
    except (ZoneInfoNotFoundError, KeyError):
        logger.warning("Unknown timezone %r; falling back to UTC.", tz_name)
        return ZoneInfo("UTC")


async def scheduler_loop(
    get_times: Callable[[], list[str]],
    job_manager_start: Callable,
    is_enabled: Callable[[], bool] | None = None,
    get_timezone: Callable[[], str] | None = None,
) -> None:
    global _RESCHEDULE_EVENT
    _RESCHEDULE_EVENT = asyncio.Event()

    while True:
        enabled = is_enabled() if is_enabled is not None else True
        _SCHEDULER_STATE["enabled"] = enabled

        if not enabled:
            _SCHEDULER_STATE["next_run_utc"] = None
            try:
                await _wait_with_event(30.0)
            except asyncio.CancelledError:
                return
            continue

        times = get_times()
        parsed = _parse_times(times)
        _SCHEDULER_STATE["schedule_times"] = times

        if not parsed:
            logger.warning(
                "Scheduler enabled but no valid times configured; retrying in 60s."
            )
            _SCHEDULER_STATE["next_run_utc"] = None
            try:
                await _wait_with_event(60.0)
            except asyncio.CancelledError:
                return
            continue

        tz_name = get_timezone() if get_timezone is not None else "UTC"
        tz = _resolve_timezone(tz_name)
        now = datetime.now(tz)
        wait = _seconds_until_next(parsed, now)
        next_utc = (now + timedelta(seconds=wait)).astimezone(UTC)
        next_iso = next_utc.strftime("%Y-%m-%dT%H:%M:%SZ")
        logger.info(
            "Scheduler: next run at %s [%s] (in %.0fs)",
            next_iso,
            tz_name,
            wait,
        )
        _SCHEDULER_STATE["next_run_utc"] = next_iso

        try:
            rescheduled = await _wait_with_event(wait)
        except asyncio.CancelledError:
            _SCHEDULER_STATE["next_run_utc"] = None
            return

        if rescheduled:
            logger.info("Scheduler: rescheduling due to config change.")
            continue

        logger.info("Scheduler: triggering digest run")
        try:
            ok, msg = job_manager_start()
            if not ok:
                logger.warning("Scheduler: digest not started: %s", msg)
            else:
                logger.info("Scheduler: digest run started (%s)", msg)
        except Exception:
            logger.exception("Scheduler: unexpected error starting digest run")


def get_scheduler_status() -> dict[str, object]:
    return dict(_SCHEDULER_STATE)


def is_env_scheduler_enabled() -> bool:
    """Return True if CONDENSEIT_SCHEDULER_ENABLED=1 is set in the environment."""
    return os.environ.get("CONDENSEIT_SCHEDULER_ENABLED", "").strip() == "1"
