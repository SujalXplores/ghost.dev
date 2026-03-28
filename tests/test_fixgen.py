"""Tests for ghost.dev fix generation."""

import pytest
from unittest.mock import patch
from ghost.fixgen.suggestions import generate_fixes
from ghost.models.friction import FrictionEvent


class TestGenerateFixes:
    def test_empty_events(self):
        assert generate_fixes([]) == []

    def test_fallback_on_ai_failure(self):
        events = [
            FrictionEvent(
                step_number=1,
                category="missing_prerequisite",
                severity="critical",
                description="Node.js not installed",
                command_attempted="npm install",
                error_output="command not found",
                doc_source="README.md",
                doc_line="Run npm install",
                suggested_fix="Add Node.js to prerequisites",
            ),
        ]
        with patch("ghost.fixgen.suggestions.ai_call", side_effect=Exception("no key")):
            fixes = generate_fixes(events)
        assert len(fixes) == 1
        assert fixes[0]["file_to_fix"] == "README.md"
        assert "Node.js" in fixes[0]["suggested_text"]

    def test_fallback_skips_events_without_fix(self):
        events = [
            FrictionEvent(
                step_number=1, category="test", severity="low",
                description="test", suggested_fix="",
            ),
        ]
        with patch("ghost.fixgen.suggestions.ai_call", side_effect=Exception("no key")):
            fixes = generate_fixes(events)
        assert fixes == []
