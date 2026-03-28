"""Setup step data model."""

from pydantic import BaseModel, ConfigDict, Field


class SetupStep(BaseModel):
    """A single setup step extracted from documentation."""

    model_config = ConfigDict(extra="ignore")

    step_number: int
    action: str = Field(description="Exact command or action to perform")
    source: str = Field(description="Which file and line this came from")
    confidence: float = Field(ge=0, le=1, description="How clear the instruction is")
    assumptions: list[str] = Field(default_factory=list)
    is_prerequisite: bool = False
    description: str = ""


class PlanResult(BaseModel):
    """Full plan extracted from docs."""

    model_config = ConfigDict(extra="ignore")

    steps: list[SetupStep]
    prerequisites: list[str] = Field(default_factory=list)
    environment_variables: list[str] = Field(default_factory=list)
    implicit_requirements: list[str] = Field(default_factory=list)
    detected_project_type: str = "unknown"
