"""Shared Jinja2 templates for the web UI."""

from __future__ import annotations

from pathlib import Path

from fastapi.templating import Jinja2Templates
from starlette.requests import Request

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
