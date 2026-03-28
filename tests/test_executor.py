"""Tests for ghost.dev executor."""

import time
import pytest
from unittest.mock import MagicMock, patch
from ghost.core.executor import execute_plan
from ghost.models.step import SetupStep, PlanResult
from ghost.docker.container import ExecResult


def _make_container(exit_code=0, stdout="ok", stderr=""):
    """Create a mock container that returns a fixed ExecResult."""
    container = MagicMock()
    container.exec_command.return_value = ExecResult(
        stdout=stdout, stderr=stderr, exit_code=exit_code, duration=0.5, timed_out=False,
    )
    return container


class TestExecutePlan:
    def test_all_steps_succeed(self):
        steps = [
            SetupStep(step_number=1, action="npm install", source="x", confidence=0.9),
            SetupStep(step_number=2, action="npm start", source="x", confidence=0.8),
        ]
        plan = PlanResult(steps=steps)
        container = _make_container()

        results = execute_plan(plan, container)
        assert len(results) == 2
        assert all(r.status == "success" for r in results)
        assert container.exec_command.call_count == 2

    def test_timeout_skips_remaining(self):
        steps = [
            SetupStep(step_number=1, action="npm install", source="x", confidence=0.9),
            SetupStep(step_number=2, action="npm start", source="x", confidence=0.8),
        ]
        plan = PlanResult(steps=steps)
        container = _make_container()

        # Set run_start_time far in the past so timeout triggers immediately
        results = execute_plan(plan, container, max_total_time=0, run_start_time=time.time() - 100)
        assert all(r.status == "skipped" for r in results)
        assert container.exec_command.call_count == 0

    def test_env_vars_passed_to_container(self):
        steps = [SetupStep(step_number=1, action="echo test", source="x", confidence=0.9)]
        plan = PlanResult(steps=steps)
        container = _make_container()

        env = {"PORT": "3000", "DB_HOST": "localhost"}
        execute_plan(plan, container, env=env)
        container.exec_command.assert_called_with("echo test", env=env)

    def test_callbacks_called(self):
        steps = [SetupStep(step_number=1, action="npm install", source="x", confidence=0.9)]
        plan = PlanResult(steps=steps)
        container = _make_container()

        on_start = MagicMock()
        on_end = MagicMock()
        execute_plan(plan, container, on_step_start=on_start, on_step_end=on_end)
        on_start.assert_called_once()
        on_end.assert_called_once()

    def test_failure_triggers_recovery(self):
        steps = [SetupStep(step_number=1, action="npm install", source="x", confidence=0.9)]
        plan = PlanResult(steps=steps)

        container = MagicMock()
        # First call fails, recovery succeeds, retry succeeds
        container.exec_command.side_effect = [
            ExecResult(stdout="", stderr="npm: command not found", exit_code=127, duration=0.1),
            ExecResult(stdout="ok", stderr="", exit_code=0, duration=1.0),  # recovery cmd
            ExecResult(stdout="ok", stderr="", exit_code=0, duration=2.0),  # retry
        ]

        with patch("ghost.core.executor.attempt_recovery") as mock_recovery:
            from ghost.core.recoverer import RecoveryResult
            mock_recovery.return_value = RecoveryResult(succeeded=True, fix_applied="apt install nodejs")
            results = execute_plan(plan, container)

        assert len(results) == 1
        assert results[0].status == "recovered"
