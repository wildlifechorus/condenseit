"""Post-run human-readable formatting."""

from __future__ import annotations

from condenseit.services.post_run_format import format_post_run_lines


def test_format_post_run_lines_empty() -> None:
    assert format_post_run_lines(None) == ["Post-run: no details returned."]
    # Empty dict has no deploy step; falls through to the default message.
    result = format_post_run_lines({})
    assert result == ["Post-run: no details returned."]


def test_format_post_run_lines_missing_host() -> None:
    lines = format_post_run_lines(
        {
            "deploy": {"status": "missing_host", "reason": "y"},
        },
    )
    assert len(lines) == 1
    assert "vps.host is empty" in lines[0]


def test_format_post_run_lines_deploy_ok() -> None:
    lines = format_post_run_lines(
        {
            "deploy": {"status": "ok", "destination": "root@myserver:/var/www/"},
        },
    )
    assert len(lines) == 1
    assert "synced" in lines[0]
