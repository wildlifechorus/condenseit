"""Shared Jinja2 templates for the web UI."""

from pathlib import Path

from fastapi import Request
from fastapi.templating import Jinja2Templates

_TEMPLATES_DIR = Path(__file__).resolve().parent / "templates"
templates = Jinja2Templates(directory=str(_TEMPLATES_DIR))


def page_context(request: Request, title: str, active: str, **extra: object) -> dict:
    """Standard template context with nav active state."""
    return {
        "request": request,
        "title": title,
        "active": active,
        **extra,
    }
