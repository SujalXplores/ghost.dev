"""Report data model."""

from datetime import datetime
from pydantic import BaseModel, Field
from ghost.models.friction import FrictionEvent
from ghost.models.step import PlanResult
from ghost.config import SEVERITY_WEIGHTS, UNRECOVERED_PENALTY


class StepResult(BaseModel):
    """Result of executing a single step."""

    step_number: int
    command: str
    status: str = "pending"  # success, failure, partial, ambiguity, skipped
    duration: float = 0.0
    stdout: str = ""
    stderr: str = ""
    exit_code: int = -1
    friction_event: FrictionEvent | None = None


class GhostReport(BaseModel):
    """Complete ghost.dev friction report."""

    repo_url: str
    repo_name: str = ""
    scanner_project_type: str = "unknown"
    scan_date: datetime = Field(default_factory=lambda: datetime.now(tz=None))
    docs_found: list[str] = Field(default_factory=list)
    plan: PlanResult | None = None
    step_results: list[StepResult] = Field(default_factory=list)
    friction_events: list[FrictionEvent] = Field(default_factory=list)
    total_duration: float = 0.0
    time_to_first_build: float | None = None
    time_to_first_test: float | None = None

    fix_suggestions: list[dict] = Field(default_factory=list)

    @property
    def friction_score(self) -> int:
        score = 0
        for event in self.friction_events:
            score += SEVERITY_WEIGHTS.get(event.severity, 2)
            if not event.self_recovered:
                score += UNRECOVERED_PENALTY
        return min(score, 100)

    @property
    def grade(self) -> str:
        s = self.friction_score
        if s <= 10:
            return "A+"
        if s <= 20:
            return "A"
        if s <= 30:
            return "B+"
        if s <= 40:
            return "B"
        if s <= 50:
            return "C+"
        if s <= 60:
            return "C"
        if s <= 70:
            return "D+"
        if s <= 80:
            return "D"
        return "F"

    @property
    def friction_level(self) -> str:
        s = self.friction_score
        if s <= 20:
            return "Low Friction"
        if s <= 50:
            return "Moderate Friction"
        return "High Friction"

    @property
    def estimated_cost_hours(self) -> float:
        """Estimate total hours wasted from friction events."""
        total_minutes = 0.0
        for event in self.friction_events:
            est = event.time_wasted_estimate.lower()
            if "hour" in est:
                try:
                    total_minutes += float("".join(c for c in est if c.isdigit() or c == ".")) * 60
                except ValueError:
                    total_minutes += 60
            elif "minute" in est or "min" in est:
                try:
                    total_minutes += float("".join(c for c in est if c.isdigit() or c == "."))
                except ValueError:
                    total_minutes += 15
            else:
                total_minutes += 15
        return round(total_minutes / 60, 1)
