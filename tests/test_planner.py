"""Tests for ghost.dev planner."""

import json
import pytest
from ghost.core.planner import _parse_plan_strict, _build_doc_context
from ghost.models.step import PlanResult


class TestParsePlanStrict:
    def test_valid_json(self):
        response = json.dumps({
            "steps": [
                {"step_number": 1, "action": "npm install", "source": "README.md:5",
                 "confidence": 0.9, "description": "Install deps"}
            ],
            "prerequisites": ["Node.js"],
            "environment_variables": [],
            "implicit_requirements": [],
            "detected_project_type": "node",
        })
        plan = _parse_plan_strict(response)
        assert len(plan.steps) == 1
        assert plan.steps[0].action == "npm install"
        assert plan.detected_project_type == "node"

    def test_json_with_markdown_fences(self):
        inner = json.dumps({
            "steps": [{"step_number": 1, "action": "make", "source": "Makefile", "confidence": 0.7}],
        })
        response = f"```json\n{inner}\n```"
        plan = _parse_plan_strict(response)
        assert len(plan.steps) == 1

    def test_empty_steps_raises(self):
        response = json.dumps({"steps": []})
        with pytest.raises(ValueError, match="No steps"):
            _parse_plan_strict(response)

    def test_malformed_json_raises(self):
        with pytest.raises(json.JSONDecodeError):
            _parse_plan_strict("not json at all")

    def test_extra_fields_ignored(self):
        response = json.dumps({
            "steps": [{"step_number": 1, "action": "x", "source": "x", "confidence": 0.5}],
            "extra_ai_field": "should not crash",
            "another_field": 42,
        })
        plan = _parse_plan_strict(response)
        assert len(plan.steps) == 1

    def test_unknown_project_type_uses_scanner(self):
        response = json.dumps({
            "steps": [{"step_number": 1, "action": "x", "source": "x", "confidence": 0.5}],
            "detected_project_type": "unknown",
        })
        plan = _parse_plan_strict(response, scanner_project_type="python")
        assert plan.detected_project_type == "python"


class TestBuildDocContext:
    def test_priority_ordering(self):
        files = {
            ".github/workflows/ci.yml": "ci stuff",
            "README.md": "# Project",
            "package.json": '{"name": "test"}',
        }
        context = _build_doc_context(files)
        readme_pos = context.find("README.md")
        pkg_pos = context.find("package.json")
        ci_pos = context.find("ci.yml")
        assert readme_pos < pkg_pos < ci_pos

    def test_max_chars_limit(self):
        files = {"README.md": "x" * 200_000}
        context = _build_doc_context(files, max_chars=1000)
        assert len(context) <= 1100  # Some overhead for the header
