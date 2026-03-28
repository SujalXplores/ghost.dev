"""Friction event data model."""

from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class FrictionEvent(BaseModel):
    """A single friction event encountered during onboarding."""

    model_config = ConfigDict(extra="ignore")

    step_number: int
    timestamp: datetime = Field(default_factory=lambda: datetime.now(tz=None))
    category: str = Field(
        description="missing_prerequisite, wrong_command, outdated_instruction, "
        "missing_env_var, undocumented_step, version_mismatch, "
        "ambiguous_instruction, implicit_knowledge, missing_file, "
        "port_conflict, permission_error"
    )
    severity: str = Field(description="critical, high, medium, low")
    description: str
    command_attempted: str = ""
    error_output: str = ""
    doc_source: str = ""
    doc_line: str = ""
    reality: str = ""
    time_wasted_estimate: str = "~5 minutes"
    suggested_fix: str = ""
    self_recovered: bool = False
    recovery_method: str = ""
    notes: list[str] = Field(default_factory=list)

    @property
    def is_failure(self) -> bool:
        return self.severity in ("critical", "high")

    def add_note(self, note: str) -> None:
        self.notes.append(note)
