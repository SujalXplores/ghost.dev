"""Tests for ghost.dev shared utilities."""

import pytest
from ghost.core._utils import parse_ai_json, is_command_safe


class TestParseAiJson:
    def test_plain_json(self):
        result = parse_ai_json('{"key": "value"}')
        assert result == {"key": "value"}

    def test_json_with_markdown_fences(self):
        result = parse_ai_json('```json\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_json_with_plain_fences(self):
        result = parse_ai_json('```\n{"key": "value"}\n```')
        assert result == {"key": "value"}

    def test_invalid_json_raises(self):
        with pytest.raises(Exception):
            parse_ai_json("not json")

    def test_whitespace_handling(self):
        result = parse_ai_json('  \n  {"key": "value"}  \n  ')
        assert result == {"key": "value"}


class TestIsCommandSafe:
    def test_safe_commands(self):
        assert is_command_safe("npm install") is True
        assert is_command_safe("pip install -r requirements.txt") is True
        assert is_command_safe("make build") is True
        assert is_command_safe("cargo build") is True
        assert is_command_safe("sudo apt-get install -y nodejs") is True

    def test_dangerous_rm_rf_root(self):
        assert is_command_safe("rm -rf /") is False
        assert is_command_safe("rm -rf /etc") is False

    def test_dangerous_mkfs(self):
        assert is_command_safe("mkfs.ext4 /dev/sda1") is False

    def test_dangerous_dd(self):
        assert is_command_safe("dd if=/dev/zero of=/dev/sda") is False

    def test_dangerous_fork_bomb(self):
        assert is_command_safe(":(){ :|:& }") is False

    def test_dangerous_shutdown(self):
        assert is_command_safe("shutdown -h now") is False
        assert is_command_safe("reboot") is False

    def test_safe_rm_in_project(self):
        # rm within project dirs should be fine
        assert is_command_safe("rm -rf node_modules") is True
        assert is_command_safe("rm -rf ./dist") is True
