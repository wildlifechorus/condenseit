"""Tests for the OpenAI-compatible provider and related config / factory wiring."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any
from unittest.mock import MagicMock, patch

import pytest

from condenseit.config import AppConfig, LlmConfig, load_config
from condenseit.providers.base import (
    CHAT_SYSTEM_PROMPT,
    SummarizerProvider,
    build_chat_user_prompt,
)
from condenseit.providers.openai_provider import OpenAISummarizer

# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _make_httpx_response(body: dict[str, Any], status_code: int = 200) -> MagicMock:
    resp = MagicMock()
    resp.status_code = status_code
    resp.json.return_value = body
    resp.headers = {}
    resp.raise_for_status = MagicMock()
    return resp


def _chat_response(content: str) -> dict[str, Any]:
    return {
        "choices": [{"message": {"content": content}}],
    }


# ---------------------------------------------------------------------------
# Shared helpers in base.py
# ---------------------------------------------------------------------------

class TestSharedPromptHelpers:
    def test_chat_system_prompt_is_exported(self) -> None:
        assert isinstance(CHAT_SYSTEM_PROMPT, str)
        assert "JSON" in CHAT_SYSTEM_PROMPT
        assert len(CHAT_SYSTEM_PROMPT) > 20

    def test_build_chat_user_prompt_contains_title_and_content(self) -> None:
        prompt = build_chat_user_prompt("My Title", "Some content here")
        assert "My Title" in prompt
        assert "Some content here" in prompt

    def test_build_chat_user_prompt_default_takeaways(self) -> None:
        prompt = build_chat_user_prompt("T", "C")
        for i in range(1, 6):
            assert f"<takeaway {i}>" in prompt

    def test_build_chat_user_prompt_custom_takeaways(self) -> None:
        prompt = build_chat_user_prompt("T", "C", max_key_takeaways=3)
        assert "<takeaway 3>" in prompt
        assert "<takeaway 4>" not in prompt

    def test_build_chat_user_prompt_paragraph_singular(self) -> None:
        prompt = build_chat_user_prompt("T", "C", max_summary_paragraphs=1)
        assert "1 paragraph" in prompt
        assert "paragraphs" not in prompt

    def test_build_chat_user_prompt_paragraph_plural(self) -> None:
        prompt = build_chat_user_prompt("T", "C", max_summary_paragraphs=3)
        assert "3 paragraphs" in prompt

    def test_openrouter_provider_uses_shared_helpers(self) -> None:
        """OpenRouterSummarizer must import from base, not define locally."""
        import inspect

        import condenseit.providers.openrouter_provider as orp
        source = inspect.getsource(orp)
        # The old local definitions should be gone (check for assignment, not substring)
        assert "_SYSTEM_PROMPT =" not in source
        assert "def _build_user_prompt" not in source
        # And the shared helpers should be imported and used (build_chat_system_prompt
        # replaced the static CHAT_SYSTEM_PROMPT constant to support dynamic language).
        assert "build_chat_system_prompt" in source
        assert "build_chat_user_prompt" in source


# ---------------------------------------------------------------------------
# OpenAISummarizer unit tests
# ---------------------------------------------------------------------------

class TestOpenAISummarizerInit:
    def test_model_name_property(self) -> None:
        s = OpenAISummarizer("gpt-4o", "http://localhost:1234/v1")
        assert s.model_name == "gpt-4o"

    def test_trailing_slash_stripped_from_base_url(self) -> None:
        s = OpenAISummarizer("m", "http://localhost:8000/v1/")
        assert s.base_url == "http://localhost:8000/v1"

    def test_empty_api_key_allowed(self) -> None:
        s = OpenAISummarizer("m", "http://localhost:8000/v1", api_key="")
        assert s.api_key == ""

    def test_is_summarizer_provider(self) -> None:
        s = OpenAISummarizer("m", "http://localhost:8000/v1")
        assert isinstance(s, SummarizerProvider)


_HTTPX_CLIENT = "condenseit.providers.openai_provider.httpx.Client"


class TestOpenAISummarizerChat:
    def _make_summarizer(self) -> OpenAISummarizer:
        return OpenAISummarizer(
            model="test-model",
            base_url="http://localhost:1234/v1",
            api_key="sk-test",
        )

    def test_posts_to_chat_completions_endpoint(self) -> None:
        summarizer = self._make_summarizer()
        fake_resp = _make_httpx_response(_chat_response("hello"))
        with patch(_HTTPX_CLIENT) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = fake_resp
            mock_client_cls.return_value = mock_client

            result = summarizer._chat([{"role": "user", "content": "hi"}])

        call_args = mock_client.post.call_args
        assert call_args[0][0] == "http://localhost:1234/v1/chat/completions"
        assert result == "hello"

    def test_sends_bearer_auth_header(self) -> None:
        summarizer = self._make_summarizer()
        fake_resp = _make_httpx_response(_chat_response("ok"))
        with patch(_HTTPX_CLIENT) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = fake_resp
            mock_client_cls.return_value = mock_client

            summarizer._chat([{"role": "user", "content": "hi"}])

        _, kwargs = mock_client.post.call_args
        assert kwargs["headers"]["Authorization"] == "Bearer sk-test"

    def test_no_auth_header_when_api_key_empty(self) -> None:
        summarizer = OpenAISummarizer("m", "http://localhost:1234/v1", api_key="")
        fake_resp = _make_httpx_response(_chat_response("ok"))
        with patch(_HTTPX_CLIENT) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = fake_resp
            mock_client_cls.return_value = mock_client

            summarizer._chat([{"role": "user", "content": "hi"}])

        _, kwargs = mock_client.post.call_args
        assert "Authorization" not in kwargs["headers"]

    def test_sends_model_in_payload(self) -> None:
        summarizer = self._make_summarizer()
        fake_resp = _make_httpx_response(_chat_response("ok"))
        with patch(_HTTPX_CLIENT) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = fake_resp
            mock_client_cls.return_value = mock_client

            summarizer._chat([{"role": "user", "content": "hi"}])

        _, kwargs = mock_client.post.call_args
        assert kwargs["json"]["model"] == "test-model"

    def test_empty_choices_returns_empty_string(self) -> None:
        summarizer = self._make_summarizer()
        fake_resp = _make_httpx_response({"choices": []})
        with patch(_HTTPX_CLIENT) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.return_value = fake_resp
            mock_client_cls.return_value = mock_client

            result = summarizer._chat([{"role": "user", "content": "hi"}])

        assert result == ""

    def test_retries_on_429(self) -> None:
        summarizer = self._make_summarizer()
        rate_limited = _make_httpx_response({}, status_code=429)
        rate_limited.raise_for_status = MagicMock(side_effect=Exception("429"))
        rate_limited.headers = {"Retry-After": "0"}
        ok_resp = _make_httpx_response(_chat_response("done"))

        with patch(_HTTPX_CLIENT) as mock_client_cls:
            mock_client = MagicMock()
            mock_client.__enter__ = MagicMock(return_value=mock_client)
            mock_client.__exit__ = MagicMock(return_value=False)
            mock_client.post.side_effect = [rate_limited, ok_resp]
            mock_client_cls.return_value = mock_client
            with patch("condenseit.providers.openai_provider.time.sleep"):
                result = summarizer._chat([{"role": "user", "content": "hi"}])

        assert result == "done"
        assert mock_client.post.call_count == 2


class TestOpenAISummarizerSummarize:
    _GOOD_JSON = json.dumps({
        "tldr": "Quick summary.",
        "key_takeaways": ["Point A", "Point B"],
        "summary": "Detailed text here.",
        "topics": ["ai", "news"],
        "entities": ["OpenAI"],
        "novelty": 3,
    })

    def _make_summarizer(self) -> OpenAISummarizer:
        return OpenAISummarizer(
            model="test-model",
            base_url="http://localhost:1234/v1",
            api_key="sk-test",
        )

    def _patch_chat(self, summarizer: OpenAISummarizer, content: str) -> Any:
        return patch.object(summarizer, "_chat", return_value=content)

    def test_summarize_article_returns_article_summary(self) -> None:
        summarizer = self._make_summarizer()
        with self._patch_chat(summarizer, self._GOOD_JSON):
            result = summarizer.summarize_article(
                {"title": "Test Article", "content": "Some content."}
            )
        assert result["tldr"] == "Quick summary."
        assert result["key_takeaways"] == ["Point A", "Point B"]
        assert result["summary"] == "Detailed text here."
        assert result["topics"] == ["ai", "news"]
        assert result["novelty"] == 3

    def test_summarize_article_sends_system_prompt(self) -> None:
        summarizer = self._make_summarizer()
        captured: list[Any] = []
        def capture(messages: list[Any], **kw: Any) -> str:
            captured.extend(messages)
            return self._GOOD_JSON
        with patch.object(summarizer, "_chat", side_effect=capture):
            summarizer.summarize_article({"title": "T", "content": "C"})
        assert captured[0]["role"] == "system"
        assert captured[0]["content"] == CHAT_SYSTEM_PROMPT

    def test_summarize_article_truncates_content_to_4000_chars(self) -> None:
        summarizer = self._make_summarizer()
        long_content = "x" * 10_000
        sent_content: list[str] = []
        def capture(messages: list[Any], **kw: Any) -> str:
            sent_content.append(messages[1]["content"])
            return self._GOOD_JSON
        with patch.object(summarizer, "_chat", side_effect=capture):
            summarizer.summarize_article({"title": "T", "content": long_content})
        assert "x" * 4001 not in sent_content[0]
        assert "x" * 4000 in sent_content[0]

    def test_summarize_article_handles_empty_llm_response(self) -> None:
        summarizer = self._make_summarizer()
        with self._patch_chat(summarizer, ""):
            result = summarizer.summarize_article({"title": "T", "content": "C"})
        assert result["tldr"] == ""
        assert result["summary"] == ""
        assert result["key_takeaways"] == []

    def test_summarize_article_uses_untitled_fallback(self) -> None:
        summarizer = self._make_summarizer()
        sent: list[Any] = []
        def capture(messages: list[Any], **kw: Any) -> str:
            sent.extend(messages)
            return self._GOOD_JSON
        with patch.object(summarizer, "_chat", side_effect=capture):
            summarizer.summarize_article({"content": "C"})
        assert "Untitled" in sent[1]["content"]

    def test_generate_digest_returns_string(self) -> None:
        summarizer = self._make_summarizer()
        result = summarizer.generate_digest(
            {"General": [{"title": "X", "url": "https://x.com", "summary": "s",
                          "tldr": "t", "key_takeaways": [], "source": "src",
                          "published_at": None, "novelty": 0,
                          "relevance_to_you": "", "topics": [], "entities": []}]}
        )
        assert isinstance(result, str)
        assert len(result) > 0


# ---------------------------------------------------------------------------
# Config: new LlmConfig fields
# ---------------------------------------------------------------------------

class TestLlmConfigDefaults:
    def test_openai_fields_default_empty(self) -> None:
        cfg = LlmConfig()
        assert cfg.openai_base_url == ""
        assert cfg.openai_api_key == ""
        assert cfg.openai_model == ""

    def test_openai_fields_set_from_yaml(self) -> None:
        cfg = LlmConfig(
            openai_base_url="http://localhost:8080/v1",
            openai_model="llama4",
            openai_api_key="sk-x",
        )
        assert cfg.openai_base_url == "http://localhost:8080/v1"
        assert cfg.openai_model == "llama4"
        assert cfg.openai_api_key == "sk-x"


class TestLoadConfigOpenAIEnvOverrides:
    def test_openai_base_url_from_env(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        cfg_yaml = tmp_path / "cfg.yaml"
        cfg_yaml.write_text("llm:\n  provider: openai\n", encoding="utf-8")
        monkeypatch.setenv("OPENAI_API_BASE_URL", "http://remote:9000/v1")
        cfg = load_config(cfg_yaml)
        assert cfg.llm.openai_base_url == "http://remote:9000/v1"

    def test_openai_api_key_from_env(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        cfg_yaml = tmp_path / "cfg.yaml"
        cfg_yaml.write_text("llm:\n  provider: openai\n", encoding="utf-8")
        monkeypatch.setenv("OPENAI_API_KEY", "sk-from-env")
        cfg = load_config(cfg_yaml)
        assert cfg.llm.openai_api_key == "sk-from-env"

    def test_openai_model_from_env(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        cfg_yaml = tmp_path / "cfg.yaml"
        cfg_yaml.write_text("llm:\n  provider: openai\n", encoding="utf-8")
        monkeypatch.setenv("OPENAI_MODEL", "gpt-4o-mini")
        cfg = load_config(cfg_yaml)
        assert cfg.llm.openai_model == "gpt-4o-mini"

    def test_env_overrides_yaml_value(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        cfg_yaml = tmp_path / "cfg.yaml"
        cfg_yaml.write_text(
            "llm:\n  provider: openai\n  openai_base_url: http://yaml:1111/v1\n",
            encoding="utf-8",
        )
        monkeypatch.setenv("OPENAI_API_BASE_URL", "http://env:2222/v1")
        cfg = load_config(cfg_yaml)
        assert cfg.llm.openai_base_url == "http://env:2222/v1"

    def test_missing_openai_env_vars_leave_defaults(
        self, monkeypatch: pytest.MonkeyPatch, tmp_path: Path
    ) -> None:
        cfg_yaml = tmp_path / "cfg.yaml"
        cfg_yaml.write_text("llm:\n  provider: openai\n", encoding="utf-8")
        monkeypatch.delenv("OPENAI_API_BASE_URL", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_MODEL", raising=False)
        cfg = load_config(cfg_yaml)
        assert cfg.llm.openai_base_url == ""
        assert cfg.llm.openai_api_key == ""
        assert cfg.llm.openai_model == ""


# ---------------------------------------------------------------------------
# Factory: build_summarizer returns correct provider
# ---------------------------------------------------------------------------

class TestBuildSummarizerOpenAI:
    def _make_store(self) -> MagicMock:
        store = MagicMock()
        store.get_setting.return_value = ""
        return store

    def _make_config(self, **llm_kwargs: Any) -> AppConfig:
        cfg = AppConfig()
        for k, v in llm_kwargs.items():
            setattr(cfg.llm, k, v)
        return cfg

    def test_returns_openai_summarizer(self) -> None:
        from condenseit.providers.factory import build_summarizer

        cfg = self._make_config(
            provider="openai",
            openai_base_url="http://localhost:1234/v1",
            openai_api_key="sk-x",
            openai_model="my-model",
        )
        with patch("condenseit.providers.factory.SecureKeyStore") as mock_ks:
            mock_ks.return_value.get_key.return_value = ""
            summarizer = build_summarizer(cfg, self._make_store())

        assert isinstance(summarizer, OpenAISummarizer)

    def test_openai_summarizer_model_set(self) -> None:
        from condenseit.providers.factory import build_summarizer

        cfg = self._make_config(
            provider="openai",
            openai_base_url="http://localhost:1234/v1",
            openai_api_key="sk-x",
            openai_model="custom-llm",
        )
        with patch("condenseit.providers.factory.SecureKeyStore") as mock_ks:
            mock_ks.return_value.get_key.return_value = ""
            summarizer = build_summarizer(cfg, self._make_store())

        assert summarizer.model_name == "custom-llm"

    def test_openai_summarizer_falls_back_to_top_level_model(self) -> None:
        from condenseit.providers.factory import build_summarizer

        cfg = self._make_config(
            provider="openai",
            openai_base_url="http://localhost:1234/v1",
            openai_api_key="sk-x",
            openai_model="",  # not set
        )
        cfg.model = "fallback-model"
        with patch("condenseit.providers.factory.SecureKeyStore") as mock_ks:
            mock_ks.return_value.get_key.return_value = ""
            summarizer = build_summarizer(cfg, self._make_store())

        assert summarizer.model_name == "fallback-model"

    def test_missing_base_url_raises(self) -> None:
        from condenseit.providers.factory import build_summarizer

        cfg = self._make_config(
            provider="openai",
            openai_base_url="",  # missing
            openai_api_key="sk-x",
        )
        with patch("condenseit.providers.factory.SecureKeyStore") as mock_ks:
            mock_ks.return_value.get_key.return_value = ""
            with pytest.raises(ValueError, match="base URL required"):
                build_summarizer(cfg, self._make_store())

    def test_api_key_from_secure_store_takes_precedence(self) -> None:
        from condenseit.providers.factory import build_summarizer

        cfg = self._make_config(
            provider="openai",
            openai_base_url="http://localhost:1234/v1",
            openai_api_key="sk-from-config",
        )
        with patch("condenseit.providers.factory.SecureKeyStore") as mock_ks:
            mock_ks.return_value.get_key.return_value = "sk-from-store"
            summarizer = build_summarizer(cfg, self._make_store())

        assert isinstance(summarizer, OpenAISummarizer)
        assert summarizer.api_key == "sk-from-store"

    def test_unknown_provider_still_raises(self) -> None:
        from condenseit.providers.factory import build_summarizer

        cfg = self._make_config(provider="nonexistent")
        # Provide a fake OR key so the factory gets past the key check and reaches
        # the "Unknown llm.provider" raise at the end of the function.
        cfg.llm.openrouter_api_key = "fake-or-key"
        with patch("condenseit.providers.factory.SecureKeyStore") as mock_ks:
            mock_ks.return_value.get_key.return_value = ""
            with patch("condenseit.providers.factory.BudgetTracker"):
                with pytest.raises(ValueError, match="Unknown llm.provider"):
                    build_summarizer(cfg, self._make_store())


# ---------------------------------------------------------------------------
# Settings overlay: DB overrides
# ---------------------------------------------------------------------------

class TestSettingsOverlayOpenAI:
    def _make_store(self, settings: dict[str, str]) -> MagicMock:
        store = MagicMock()
        store.get_setting.side_effect = (
            lambda key, default="": settings.get(key, default)
        )
        return store

    def test_openai_base_url_applied_from_db(self) -> None:
        from condenseit.settings_overlay import apply_db_settings

        cfg = AppConfig()
        store = self._make_store({"openai_base_url": "http://db:5000/v1"})
        result = apply_db_settings(cfg, store)
        assert result.llm.openai_base_url == "http://db:5000/v1"

    def test_openai_model_applied_from_db(self) -> None:
        from condenseit.settings_overlay import apply_db_settings

        cfg = AppConfig()
        store = self._make_store({"openai_model": "db-model"})
        result = apply_db_settings(cfg, store)
        assert result.llm.openai_model == "db-model"

    def test_empty_db_value_does_not_override(self) -> None:
        from condenseit.settings_overlay import apply_db_settings

        cfg = AppConfig()
        cfg.llm.openai_base_url = "http://yaml:1234/v1"
        store = self._make_store({})  # no DB value
        result = apply_db_settings(cfg, store)
        assert result.llm.openai_base_url == "http://yaml:1234/v1"
