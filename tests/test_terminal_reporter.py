"""Tests for ghost.dev terminal reporter."""

import pytest
from io import StringIO
from rich.console import Console
from ghost.reporter.terminal import (
    print_header, print_step_start, print_step_result,
    print_final_report, print_no_docker_report,
    _grade_style,
)
from ghost.models.report import GhostReport, StepResult
from ghost.models.step import SetupStep, PlanResult


class TestGradeStyle:
    def test_good(self):
        assert "green" in _grade_style(10)

    def test_mid(self):
        assert "yellow" in _grade_style(50)

    def test_bad(self):
        assert "red" in _grade_style(80)


class TestPrintHeader:
    def test_no_crash(self, capsys):
        """Header should print without errors."""
        print_header("test/repo", ["README.md"], 3, "ghost-test-abc123")


class TestPrintStepResult:
    def test_success(self, capsys):
        result = StepResult(step_number=1, command="npm install", status="success", duration=1.5)
        print_step_result(result)

    def test_failure_with_friction(self, capsys, sample_friction):
        result = StepResult(
            step_number=1, command="npm install", status="failure",
            duration=0.1, friction_event=sample_friction,
        )
        print_step_result(result)


class TestPrintFinalReport:
    def test_no_crash(self, sample_report):
        """Full report should render without errors."""
        print_final_report(sample_report)

    def test_empty_report(self):
        report = GhostReport(repo_url="https://example.com")
        print_final_report(report)


class TestPrintNoDockerReport:
    def test_with_plan(self, sample_report):
        print_no_docker_report(sample_report)

    def test_without_plan(self):
        report = GhostReport(repo_url="https://example.com", docs_found=["README.md"])
        print_no_docker_report(report)
