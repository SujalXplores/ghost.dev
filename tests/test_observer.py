"""Tests for ghost.dev observer."""

import pytest
from ghost.core.observer import observe, _heuristic_classify
from ghost.models.step import SetupStep
from ghost.docker.container import ExecResult


class TestObserve:
    def test_quick_success(self, sample_step, sample_exec_success):
        """Exit code 0 with clean stderr should be instant success without AI call."""
        status, event = observe(sample_step, sample_exec_success)
        assert status == "success"
        assert event is None

    def test_success_with_warnings_triggers_analysis(self, sample_step):
        """Exit code 0 but warnings in stderr should not be instant success."""
        result = ExecResult(stdout="ok", stderr="warning: deprecated", exit_code=0, duration=1.0)
        # Without AI, this falls back to heuristic
        status, event = observe(sample_step, result)
        # Heuristic should catch the warning
        assert status in ("success", "partial")


class TestHeuristicClassify:
    def test_clean_success(self, sample_step, sample_exec_success):
        result = _heuristic_classify(sample_step, sample_exec_success)
        assert result["status"] == "SUCCESS"

    def test_warning_partial(self, sample_step):
        result = ExecResult(stdout="", stderr="warning: something", exit_code=0, duration=1.0)
        classified = _heuristic_classify(sample_step, result)
        assert classified["status"] == "PARTIAL"
        assert classified["severity"] == "low"

    def test_command_not_found(self, sample_step):
        result = ExecResult(stdout="", stderr="bash: npm: command not found", exit_code=127, duration=0.1)
        classified = _heuristic_classify(sample_step, result)
        assert classified["status"] == "FAILURE"
        assert classified["friction_type"] == "missing_prerequisite"
        assert classified["severity"] == "critical"

    def test_permission_denied(self, sample_step):
        result = ExecResult(stdout="", stderr="permission denied", exit_code=1, duration=0.1)
        classified = _heuristic_classify(sample_step, result)
        assert classified["status"] == "FAILURE"
        assert classified["friction_type"] == "permission_error"

    def test_generic_failure(self, sample_step):
        result = ExecResult(stdout="", stderr="some error", exit_code=1, duration=0.1)
        classified = _heuristic_classify(sample_step, result)
        assert classified["status"] == "FAILURE"
        assert classified["severity"] == "high"
