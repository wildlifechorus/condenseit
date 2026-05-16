from pathlib import Path

import pytest

from condenseit.config import AppConfig, _expand_env, load_config


def test_expand_env_with_default() -> None:
    assert _expand_env("${MISSING_VAR:-http://localhost}") == "http://localhost"


def test_app_config_defaults() -> None:
    cfg = AppConfig()
    assert cfg.model == "llama3.2:3b"
    assert cfg.max_articles_per_digest == 50
    assert cfg.max_article_age_hours == 36
    assert cfg.llm.provider == "openrouter"
    assert cfg.vps.enabled is True
    assert cfg.preferred_languages == []


def test_max_articles_env_override(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cfg_yaml = tmp_path / "cfg.yaml"
    cfg_yaml.write_text("max_articles_per_digest: 10\n", encoding="utf-8")
    monkeypatch.setenv("CONDENSEIT_MAX_ARTICLES_PER_DIGEST", "44")
    cfg = load_config(cfg_yaml)
    assert cfg.max_articles_per_digest == 44


def test_load_config_vps_env_overrides(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path: Path,
) -> None:
    cfg_yaml = tmp_path / "cfg.yaml"
    cfg_yaml.write_text(
        "vps:\n  host: ''\n  path: /old\n  digest_url: ''\n",
        encoding="utf-8",
    )
    monkeypatch.setenv("DIGEST_PWA_SSH_HOST", "deploy@203.0.113.10")
    monkeypatch.setenv("DIGEST_PWA_REMOTE_DIR", "/var/www/digest/")
    monkeypatch.setenv("DIGEST_PWA_LIVE_URL", "https://digest.example.com")
    cfg = load_config(cfg_yaml)
    assert cfg.vps.host == "deploy@203.0.113.10"
    assert cfg.vps.path == "/var/www/digest/"
    assert cfg.vps.digest_url == "https://digest.example.com"


def test_email_section_in_yaml_is_silently_ignored(
    tmp_path: Path,
) -> None:
    """Old YAML files with an email: section should load without error."""
    cfg_yaml = tmp_path / "cfg.yaml"
    cfg_yaml.write_text(
        'email:\n  enabled: true\n  to: "old@example.com"\n',
        encoding="utf-8",
    )
    cfg = load_config(cfg_yaml)
    assert cfg.model == "llama3.2:3b"
