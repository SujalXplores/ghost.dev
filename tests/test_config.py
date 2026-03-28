"""Tests for ghost.dev config."""

import os
import pytest
from pathlib import Path
from ghost.config import save_api_key, has_any_api_key, clear_cache, CACHE_DB


class TestHasAnyApiKey:
    def test_no_keys(self, monkeypatch):
        monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
        monkeypatch.delenv("OPENAI_API_KEY", raising=False)
        monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
        assert has_any_api_key() is False

    def test_anthropic_key(self, monkeypatch):
        monkeypatch.setenv("ANTHROPIC_API_KEY", "sk-test")
        assert has_any_api_key() is True

    def test_openai_key(self, monkeypatch):
        monkeypatch.setenv("OPENAI_API_KEY", "sk-test")
        assert has_any_api_key() is True

    def test_openrouter_key(self, monkeypatch):
        monkeypatch.setenv("OPENROUTER_API_KEY", "sk-test")
        assert has_any_api_key() is True


class TestSaveApiKey:
    def test_save_new_key(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        import ghost.config as cfg
        monkeypatch.setattr(cfg, "ENV_FILE", env_file)
        save_api_key("TEST_KEY", "test-value")
        content = env_file.read_text()
        assert "TEST_KEY=test-value" in content
        assert os.environ.get("TEST_KEY") == "test-value"

    def test_replace_existing_key(self, tmp_path, monkeypatch):
        env_file = tmp_path / ".env"
        env_file.write_text("TEST_KEY=old-value\nOTHER=keep\n")
        import ghost.config as cfg
        monkeypatch.setattr(cfg, "ENV_FILE", env_file)
        save_api_key("TEST_KEY", "new-value")
        content = env_file.read_text()
        assert "TEST_KEY=new-value" in content
        assert "TEST_KEY=old-value" not in content
        assert "OTHER=keep" in content


class TestClearCache:
    def test_clear_nonexistent(self):
        # Should not raise
        clear_cache()

    def test_clear_existing(self, tmp_path, monkeypatch):
        import ghost.config as cfg
        cache_file = tmp_path / "cache.db"
        cache_file.write_text("data")
        monkeypatch.setattr(cfg, "CACHE_DB", cache_file)
        clear_cache()
        assert not cache_file.exists()
