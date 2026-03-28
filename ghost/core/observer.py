"""Observes step execution results and classifies friction events."""

from ghost.models.step import SetupStep
from ghost.models.friction import FrictionEvent
from ghost.docker.container import ExecResult
from ghost.core._ai import ai_call
from ghost.core._utils import parse_ai_json

OBSERVER_SYSTEM = """You are analyzing the result of a setup command run by a brand-new developer.

Given the command execution details, classify the result as one of:
- SUCCESS: Step worked as documented
- FAILURE: Step failed entirely
- PARTIAL: Step produced warnings or unexpected output
- AMBIGUITY: Step was unclear, required guessing

If not SUCCESS, provide:
- root_cause: Why did this fail?
- friction_type: One of [missing_prerequisite, wrong_command, outdated_instruction,
  missing_env_var, undocumented_step, version_mismatch, ambiguous_instruction,
  implicit_knowledge, missing_file, port_conflict, permission_error]
- severity: [critical, high, medium, low]
- time_wasted_estimate: How long a real developer would be stuck (e.g. "~15 minutes")
- suggested_fix: What should the docs say instead?
- reality: What the truth actually is

Return ONLY valid JSON, no markdown fences:
{
  "status": "SUCCESS|FAILURE|PARTIAL|AMBIGUITY",
  "root_cause": "...",
  "friction_type": "...",
  "severity": "...",
  "time_wasted_estimate": "...",
  "suggested_fix": "...",
  "reality": "..."
}"""


def observe(step: SetupStep, result: ExecResult) -> tuple[str, FrictionEvent | None]:
    """Analyze a step execution result. Returns (status, optional friction event)."""
    # Quick success heuristic — skip AI call for obvious successes
    if result.exit_code == 0 and not result.timed_out:
        stderr_lower = result.stderr.lower()
        if not any(w in stderr_lower for w in ["error", "warn", "fail", "deprecat"]):
            return "success", None

    user_prompt = (
        f"Command: {step.action}\n"
        f"Exit code: {result.exit_code}\n"
        f"Stdout (last 2000 chars): {result.stdout[-2000:]}\n"
        f"Stderr (last 2000 chars): {result.stderr[-2000:]}\n"
        f"Duration: {result.duration}s\n"
        f"Timed out: {result.timed_out}\n"
        f"Documentation said: {step.source}\n"
        f"Step description: {step.description}"
    )

    try:
        response = ai_call(system=OBSERVER_SYSTEM, user=user_prompt)
        data = parse_ai_json(response)
    except Exception:
        # Fallback heuristic
        data = _heuristic_classify(step, result)

    status = data.get("status", "FAILURE").lower()

    if status == "success":
        return "success", None

    event = FrictionEvent(
        step_number=step.step_number,
        category=data.get("friction_type", "undocumented_step"),
        severity=data.get("severity", "medium"),
        description=data.get("root_cause", f"Step failed with exit code {result.exit_code}"),
        command_attempted=step.action,
        error_output=result.stderr[:2000],
        doc_source=step.source,
        doc_line=step.description,
        reality=data.get("reality", ""),
        time_wasted_estimate=data.get("time_wasted_estimate", "~10 minutes"),
        suggested_fix=data.get("suggested_fix", ""),
    )
    return status, event


def _heuristic_classify(step: SetupStep, result: ExecResult) -> dict:
    """Fallback classification without AI."""
    stderr = result.stderr.lower()

    if result.exit_code == 0:
        if "warn" in stderr or "deprecat" in stderr:
            return {"status": "PARTIAL", "friction_type": "outdated_instruction",
                    "severity": "low", "root_cause": "Warnings in output",
                    "time_wasted_estimate": "~5 minutes", "suggested_fix": "", "reality": ""}
        return {"status": "SUCCESS"}

    if "command not found" in stderr or "not found" in stderr:
        return {"status": "FAILURE", "friction_type": "missing_prerequisite",
                "severity": "critical", "root_cause": "Required tool not installed",
                "time_wasted_estimate": "~15 minutes",
                "suggested_fix": "Add prerequisite to docs", "reality": "Tool not available"}

    if "permission denied" in stderr:
        return {"status": "FAILURE", "friction_type": "permission_error",
                "severity": "high", "root_cause": "Permission denied",
                "time_wasted_estimate": "~10 minutes",
                "suggested_fix": "Document required permissions", "reality": ""}

    return {"status": "FAILURE", "friction_type": "undocumented_step",
            "severity": "high", "root_cause": f"Exit code {result.exit_code}",
            "time_wasted_estimate": "~15 minutes",
            "suggested_fix": "Investigate and document fix", "reality": result.stderr[:200]}
