"""Post-run human-readable formatting."""

from __future__ import annotations

from condenseit.services.post_run_format import format_post_run_lines


def test_format_post_run_lines_empty() -> None:
    assert format_post_run_lines(None) == ["Post-run: no details returned."]
    assert format_post_run_lines({}) == ["Post-run: no details returned."]


def test_format_post_run_lines_disabled_and_missing_host() -> None:
    lines = format_post_run_lines(
        {
            "email": {"status": "disabled_in_config", "reason": "x"},
            "deploy": {"status": "missing_host", "reason": "y"},
        },
    )
    assert len(lines) == 2
    assert "email.enabled is false" in lines[0]
    assert "vps.host is empty" in lines[1]
