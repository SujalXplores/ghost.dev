"""Tests for ghost.dev recoverer."""

import pytest
from ghost.core.recoverer import _heuristic_recovery


class TestHeuristicRecovery:
    def test_node_not_found(self):
        suggestions = _heuristic_recovery("bash: node: command not found")
        assert len(suggestions) >= 1
        assert "nodejs" in suggestions[0]["command"]

    def test_npm_not_found(self):
        suggestions = _heuristic_recovery("bash: npm: command not found")
        assert len(suggestions) >= 1
        assert "nodejs" in suggestions[0]["command"]

    def test_python_not_found(self):
        suggestions = _heuristic_recovery("bash: python: command not found")
        assert len(suggestions) >= 1
        assert "python3" in suggestions[0]["command"]

    def test_pip_not_found(self):
        suggestions = _heuristic_recovery("bash: pip: command not found")
        assert len(suggestions) >= 1
        assert "pip" in suggestions[0]["command"]

    def test_permission_denied(self):
        suggestions = _heuristic_recovery("permission denied: ./start.sh")
        assert len(suggestions) >= 1
        assert "chmod" in suggestions[0]["command"]

    def test_unknown_error(self):
        suggestions = _heuristic_recovery("something completely unknown happened")
        assert suggestions == []
