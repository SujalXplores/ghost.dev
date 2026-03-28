"""Tests for ghost.dev AI call helper."""

import pytest
from unittest.mock import patch, MagicMock
from ghost.core._ai import ai_call, _resolve_openrouter_model


class TestResolveOpenrouterModel:
    def test_full_model_id_passthrough(self):
        assert _resolve_openrouter_model("anthropic/claude-sonnet-4.6") == "anthropic/claude-sonnet-4.6"

    def test_shorthand_claude_sonnet(self):
        result = _resolve_openrouter_model("claude-sonnet")
        assert "anthropic" in result

    def test_shorthand_gpt(self):
        result = _resolve_openrouter_model("gpt-5.4")
        assert "openai" in result

    def test_shorthand_gemini(self):
        result = _resolve_openrouter_model("gemini-pro")
        assert "google" in result

    def test_shorthand_deepseek(self):
        result = _resolve_openrouter_model("deepseek")
        assert "deepseek" in result

    def test_shorthand_llama(self):
        result = _resolve_openrouter_model("llama")
        assert "meta-llama" in result

    def test_unknown_model_passthrough(self):
        assert _resolve_openrouter_model("some-custom-model") == "some-custom-model"


class TestAiCall:
    def test_no_keys_raises(self, monkeypatch):
        import ghost.config as cfg
        monkeypatch.setattr(cfg, "ANTHROPIC_API_KEY", "")
        monkeypatch.setattr(cfg, "OPENROUTER_API_KEY", "")
        monkeypatch.setattr(cfg, "OPENAI_API_KEY", "")
        with pytest.raises(RuntimeError, match="All AI providers failed"):
            ai_call("system", "user")

    def test_anthropic_fallback_to_openrouter(self, monkeypatch):
        import ghost.config as cfg
        monkeypatch.setattr(cfg, "ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setattr(cfg, "OPENROUTER_API_KEY", "or-test")
        monkeypatch.setattr(cfg, "OPENAI_API_KEY", "")

        with patch("ghost.core._ai._call_anthropic", side_effect=Exception("fail")):
            with patch("ghost.core._ai._call_openrouter", return_value="openrouter response"):
                result = ai_call("system", "user")
        assert result == "openrouter response"

    def test_all_fallback_to_openai(self, monkeypatch):
        import ghost.config as cfg
        monkeypatch.setattr(cfg, "ANTHROPIC_API_KEY", "sk-test")
        monkeypatch.setattr(cfg, "OPENROUTER_API_KEY", "or-test")
        monkeypatch.setattr(cfg, "OPENAI_API_KEY", "oa-test")

        with patch("ghost.core._ai._call_anthropic", side_effect=Exception("fail")):
            with patch("ghost.core._ai._call_openrouter", side_effect=Exception("fail")):
                with patch("ghost.core._ai._call_openai", return_value="openai response"):
                    result = ai_call("system", "user")
        assert result == "openai response"
