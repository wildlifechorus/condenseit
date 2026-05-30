"""Deterministic digest markdown with links to every source."""

from datetime import UTC, datetime
from typing import Any


def build_digest_markdown(
    categorized: dict[str, list[dict[str, Any]]],
    changes: list[dict[str, str]] | None = None,
    videos: list[dict[str, Any]] | None = None,
) -> str:
    """Build digest markdown; every article/video includes a clickable link."""
    stamp = datetime.now(UTC).strftime("%Y-%m-%d %H:%M UTC")
    lines: list[str] = [
        "# CondenseIt Digest",
        "",
        f"_{stamp}_",
        "",
    ]

    for category in sorted(categorized.keys()):
        items = categorized[category]
        if not items:
            continue
        lines.append(f"## {category}")
        lines.append("")
        for item in items:
            lines.extend(_format_item(item))
        lines.append("")

    if videos:
        lines.append("## Videos")
        lines.append("")
        for item in videos:
            lines.extend(_format_item(item))
        lines.append("")

    if changes:
        lines.append("## Website changes")
        lines.append("")
        for change in changes:
            url = change.get("url", "")
            status = change.get("status", "updated")
            lines.append(f"- **[{status}]({url})** — {url}")
        lines.append("")

    if len(lines) <= 4:
        lines.append("_No new items in this run._")

    return "\n".join(lines).strip() + "\n"


def _format_item(item: dict[str, Any]) -> list[str]:
    title = (item.get("title") or "Untitled").strip()
    url = (item.get("url") or "").strip()
    summary = (item.get("summary") or "").strip()
    source = (item.get("source") or "").strip()

    if url:
        bullet = f"- **[{title}]({url})**"
    else:
        bullet = f"- **{title}**"

    out = [bullet]
    if summary:
        out.append(f"  {summary}")
    if source:
        out.append(f"  _via {source}_")
    return out
