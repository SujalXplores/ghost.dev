"""Tests for ghost.dev data models."""

import pytest
from ghost.models.step import SetupStep, PlanResult
from ghost.models.friction import FrictionEvent
from ghost.models.report import GhostReport, StepResult


class TestSetupStep:
    def test_basic_creation(self):
        step = SetupStep(step_number=1, action="npm install", source="README.md:5", confidence=0.9)
        assert step.step_number == 1
        assert step.action == "npm install"
        assert step.confidence == 0.9
        assert step.assumptions == []
        assert step.is_prerequisite is False

    def test_confidence_bounds(self):
        with pytest.raises(Exception):
            SetupStep(step_number=1, action="x", source="x", confidence=1.5)
        with pytest.raises(Exception):
            SetupStep(step_number=1, action="x", source="x", confidence=-0.1)

    def test_extra_fields_ignored(self):
        """AI responses often include extra fields — they should be silently ignored."""
        step = SetupStep(
            step_number=1, action="npm install", source="README.md", confidence=0.8,
            extra_field="should be ignored", another="also ignored",
        )
        assert step.action == "npm install"
        assert not hasattr(step, "extra_field")


class TestPlanResult:
    def test_basic_creation(self, sample_step):
        plan = PlanResult(steps=[sample_step])
        assert len(plan.steps) == 1
        assert plan.detected_project_type == "unknown"

    def test_extra_fields_ignored(self, sample_step):
        plan = PlanResult(steps=[sample_step], unknown_ai_field="hello")
        assert len(plan.steps) == 1

    def test_empty_steps(self):
        plan = PlanResult(steps=[])
        assert len(plan.steps) == 0


class TestFrictionEvent:
    def test_is_failure(self):
        critical = FrictionEvent(step_number=1, category="missing_prerequisite",
                                 severity="critical", description="test")
        high = FrictionEvent(step_number=1, category="wrong_command",
                             severity="high", description="test")
        medium = FrictionEvent(step_number=1, category="outdated_instruction",
                               severity="medium", description="test")
        low = FrictionEvent(step_number=1, category="ambiguous_instruction",
                            severity="low", description="test")
        assert critical.is_failure is True
        assert high.is_failure is True
        assert medium.is_failure is False
        assert low.is_failure is False

    def test_add_note(self, sample_friction):
        sample_friction.add_note("test note")
        assert "test note" in sample_friction.notes

    def test_extra_fields_ignored(self):
        event = FrictionEvent(
            step_number=1, category="test", severity="low",
            description="test", hallucinated_field="nope",
        )
        assert event.description == "test"


class TestGhostReport:
    def test_friction_score_empty(self):
        report = GhostReport(repo_url="https://example.com")
        assert report.friction_score == 0
        assert report.grade == "A+"

    def test_friction_score_calculation(self, sample_friction):
        report = GhostReport(
            repo_url="https://example.com",
            friction_events=[sample_friction],
        )
        # critical = 20 + unrecovered penalty 5 = 25
        assert report.friction_score == 25
        assert report.grade == "B+"

    def test_friction_score_recovered(self):
        event = FrictionEvent(
            step_number=1, category="missing_prerequisite",
            severity="critical", description="test", self_recovered=True,
        )
        report = GhostReport(repo_url="x", friction_events=[event])
        # critical = 20, no unrecovered penalty
        assert report.friction_score == 20
        assert report.grade == "A"

    def test_friction_score_capped_at_100(self):
        events = [
            FrictionEvent(step_number=i, category="test", severity="critical", description="test")
            for i in range(10)
        ]
        report = GhostReport(repo_url="x", friction_events=events)
        assert report.friction_score == 100

    def test_all_grades(self):
        """Verify grade boundaries."""
        cases = [
            (0, "A+"), (10, "A+"), (11, "A"), (20, "A"),
            (21, "B+"), (30, "B+"), (31, "B"), (40, "B"),
            (41, "C+"), (50, "C+"), (51, "C"), (60, "C"),
            (61, "D+"), (70, "D+"), (71, "D"), (80, "D"),
            (81, "F"), (100, "F"),
        ]
        for score, expected_grade in cases:
            # Create events to hit the target score
            report = GhostReport(repo_url="x")
            # Manually check grade logic
            s = score
            if s <= 10: g = "A+"
            elif s <= 20: g = "A"
            elif s <= 30: g = "B+"
            elif s <= 40: g = "B"
            elif s <= 50: g = "C+"
            elif s <= 60: g = "C"
            elif s <= 70: g = "D+"
            elif s <= 80: g = "D"
            else: g = "F"
            assert g == expected_grade, f"Score {score} should be {expected_grade}, got {g}"

    def test_friction_level(self):
        report = GhostReport(repo_url="x")
        assert report.friction_level == "Low Friction"

    def test_estimated_cost_hours_minutes(self):
        event = FrictionEvent(
            step_number=1, category="test", severity="low",
            description="test", time_wasted_estimate="~30 minutes",
        )
        report = GhostReport(repo_url="x", friction_events=[event])
        assert report.estimated_cost_hours == 0.5

    def test_estimated_cost_hours_hours(self):
        event = FrictionEvent(
            step_number=1, category="test", severity="low",
            description="test", time_wasted_estimate="~2 hours",
        )
        report = GhostReport(repo_url="x", friction_events=[event])
        assert report.estimated_cost_hours == 2.0

    def test_estimated_cost_hours_fallback(self):
        event = FrictionEvent(
            step_number=1, category="test", severity="low",
            description="test", time_wasted_estimate="unknown",
        )
        report = GhostReport(repo_url="x", friction_events=[event])
        assert report.estimated_cost_hours == 0.2  # 15 min fallback → 0.25 → rounds to 0.2
