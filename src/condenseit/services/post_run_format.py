"""Human-readable lines for digest post-run (VPS deploy)."""

from collections.abc import Callable, Mapping
from typing import Any

_DEPLOY_LINE_HANDLERS: dict[str, Callable[[Mapping[str, Any]], str]] = {
    "ok": lambda step: f"VPS deploy: synced to {step.get('destination', '?')}",
    "error": lambda step: f"VPS deploy: failed ({step.get('error', 'unknown')})",
    "disabled_in_config": lambda _step: (
        "VPS deploy: not run (vps.enabled is false in config; set true when ready)"
    ),
    "missing_host": lambda _step: (
        "VPS deploy: not configured (set DIGEST_PWA_SSH_HOST to enable rsync)"
    ),
    "skipped": lambda step: f"VPS deploy: not run ({step.get('reason', 'skipped')})",
}


def line_for_deploy(step: Mapping[str, Any]) -> str:
    """One line describing the VPS rsync outcome."""
    status = str(step.get("status", "?"))
    handler = _DEPLOY_LINE_HANDLERS.get(status)
    if handler is not None:
        return handler(step)
    return f"VPS deploy: {status}"


def format_post_run_lines(post: dict[str, Any] | None) -> list[str]:
    """Return one line per post-run step for CLI or UI."""
    if not post:
        return ["Post-run: no details returned."]
    lines: list[str] = []
    if "deploy" in post:
        lines.append(line_for_deploy(post["deploy"]))
    return lines if lines else ["Post-run: no deploy step returned."]
