"""Shared fixtures for ghost.dev tests."""

import os
import pytest
import tempfile
from pathlib import Path
from unittest.mock import MagicMock
from ghost.models.step import SetupStep, PlanResult
from ghost.models.friction import FrictionEvent
from ghost.models.report import GhostReport, StepResult
from ghost.core.scanner import ScanResult
from ghost.docker.container import ExecResult


@pytest.fixture
def tmp_repo(tmp_path):
    """Create a temporary repo directory with a README."""
    readme = tmp_path / "README.md"
    readme.write_text("# Test Project\n\n## Setup\n\n```bash\nnpm install\nnpm start\n```\n")
    pkg = tmp_path / "package.json"
    pkg.write_text('{"name": "test", "version": "1.0.0"}')
    return tmp_path


@pytest.fixture
def sample_scan():
    """A sample ScanResult."""
    return ScanResult(
        repo_path="/tmp/test-repo",
        files_found={
            "README.md": "# Test\n\n## Setup\n\n```bash\nnpm install\n```\n",
            "package.json": '{"name": "test", "version": "1.0.0"}',
        },
        detected_project_type="node",
    )


@pytest.fixture
def sample_step():
    """A sample SetupStep."""
    return SetupStep(
        step_number=1,
        action="npm install",
        source="README.md:5",
        confidence=0.9,
        assumptions=[],
        description="Install dependencies",
    )


@pytest.fixture
def sample_plan(sample_step):
    """A sample PlanResult."""
    return PlanResult(
        steps=[
            sample_step,
            SetupStep(
                step_number=2,
                action="npm start",
                source="README.md:6",
                confidence=0.8,
                assumptions=["Node.js installed"],
                description="Start the application",
            ),
        ],
        prerequisites=["Node.js"],
        environment_variables=["PORT=3000"],
        implicit_requirements=["npm knowledge"],
        detected_project_type="node",
    )


@pytest.fixture
def sample_friction():
    """A sample FrictionEvent."""
    return FrictionEvent(
        step_number=1,
        category="missing_prerequisite",
        severity="critical",
        description="Node.js not installed",
        command_attempted="npm install",
        error_output="bash: npm: command not found",
        doc_source="README.md:5",
        doc_line="npm install",
        reality="Node.js is not pre-installed",
        time_wasted_estimate="~15 minutes",
        suggested_fix="Add: 'Requires Node.js 20+' to prerequisites",
    )


@pytest.fixture
def sample_exec_success():
    """A successful ExecResult."""
    return ExecResult(
        stdout="added 150 packages",
        stderr="",
        exit_code=0,
        duration=5.2,
        timed_out=False,
    )


@pytest.fixture
def sample_exec_failure():
    """A failed ExecResult."""
    return ExecResult(
        stdout="",
        stderr="bash: npm: command not found",
        exit_code=127,
        duration=0.1,
        timed_out=False,
    )


@pytest.fixture
def sample_report(sample_plan, sample_friction):
    """A sample GhostReport with friction events."""
    return GhostReport(
        repo_url="https://github.com/test/repo",
        repo_name="test/repo",
        scanner_project_type="node",
        docs_found=["README.md", "package.json"],
        plan=sample_plan,
        step_results=[
            StepResult(
                step_number=1,
                command="npm install",
                status="failure",
                duration=0.1,
                exit_code=127,
                friction_event=sample_friction,
            ),
            StepResult(
                step_number=2,
                command="npm start",
                status="skipped",
                duration=0.0,
                exit_code=-1,
            ),
        ],
        friction_events=[sample_friction],
        total_duration=12.5,
    )


@pytest.fixture(autouse=True)
def clean_env(monkeypatch):
    """Ensure tests don't use real API keys."""
    monkeypatch.delenv("ANTHROPIC_API_KEY", raising=False)
    monkeypatch.delenv("OPENAI_API_KEY", raising=False)
    monkeypatch.delenv("OPENROUTER_API_KEY", raising=False)
