"""Human-readable lines for digest post-run (email + VPS deploy)."""

from __future__ import annotations

from collections.abc import Mapping
from typing import Any


def line_for_email(step: Mapping[str, Any]) -> str:
    """One line describing the email notification outcome."""
    status = step.get("status", "?")
    if status == "sent":
        rid = str(step.get("id", "")).strip()
        return f"Email: sent (id {rid})" if rid else "Email: sent"
    if status == "error":
        return f"Email: failed ({step.get('error', 'unknown')})"
    if status == "disabled_in_config":
        return (
            "Email: not run (email.enabled is false in config; "
            "set true and configure Resend)"
        )
    if status == "missing_credentials":
        return (
            "Email: not run (no Resend API key; set RESEND_API_KEY "
            "or add resend in Admin / API keys)"
        )
    if status == "skipped":
        return f"Email: not run ({step.get('reason', 'skipped')})"
    return f"Email: {status}"


def line_for_deploy(step: Mapping[str, Any]) -> str:
    """One line describing the VPS rsync outcome."""
    status = step.get("status", "?")
    if status == "ok":
        dest = step.get("destination", "?")
        return f"VPS deploy: synced to {dest}"
    if status == "error":
        return f"VPS deploy: failed ({step.get('error', 'unknown')})"
    if status == "disabled_in_config":
        return (
            "VPS deploy: not run (vps.enabled is false in config; set true when ready)"
        )
    if status == "missing_host":
        return "VPS deploy: not run (vps.host is empty; set user@host for rsync target)"
    if status == "skipped":
        return f"VPS deploy: not run ({step.get('reason', 'skipped')})"
    return f"VPS deploy: {status}"


def format_post_run_lines(post: dict[str, Any] | None) -> list[str]:
    """Return one line per post-run step for CLI or UI."""
    if not post:
        return ["Post-run: no details returned."]
    lines: list[str] = []
    if "email" in post:
        lines.append(line_for_email(post["email"]))
    if "deploy" in post:
        lines.append(line_for_deploy(post["deploy"]))
    return lines if lines else ["Post-run: no email or deploy steps returned."]
