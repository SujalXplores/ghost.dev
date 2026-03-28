"""AI-powered recovery when setup steps fail."""

from ghost.models.step import SetupStep
from ghost.docker.container import GhostContainer
from ghost.core._ai import ai_call
from ghost.core._utils import parse_ai_json, is_command_safe
from dataclasses import dataclass

RECOVERY_SYSTEM = """A setup step failed with an error. As a new developer, you would try to fix this yourself.

Suggest up to 3 recovery commands to try, in order of likelihood.
You CAN interpret error messages (like a dev reading stack traces).
You CAN suggest installing missing tools if the error says "command not found".
You CANNOT use knowledge the documentation didn't provide beyond error interpretation.

Return ONLY valid JSON, no markdown fences:
{
  "recovery_commands": [
    {"command": "...", "reasoning": "..."},
    {"command": "...", "reasoning": "..."}
  ]
}"""


@dataclass
class RecoveryResult:
    succeeded: bool
    fix_applied: str = ""
    commands_tried: list[str] = None

    def __post_init__(self):
        if self.commands_tried is None:
            self.commands_tried = []


def attempt_recovery(
    step: SetupStep,
    error: str,
    container: GhostContainer,
    previous_steps: list[str] | None = None,
) -> RecoveryResult:
    """Attempt to recover from a failed step using AI-suggested fixes."""
    context = "\n".join(previous_steps or [])
    user_prompt = (
        f"Failed command: {step.action}\n"
        f"Error output:\n{error[:3000]}\n"
        f"Previous successful commands:\n{context}\n"
    )

    try:
        response = ai_call(system=RECOVERY_SYSTEM, user=user_prompt)
        data = parse_ai_json(response)
        commands = data.get("recovery_commands", [])
    except Exception:
        commands = _heuristic_recovery(error)

    tried = []
    for cmd_info in commands[:3]:
        cmd = cmd_info.get("command", "") if isinstance(cmd_info, dict) else str(cmd_info)
        if not cmd:
            continue

        # Security: validate command before execution
        if not is_command_safe(cmd):
            tried.append(f"[BLOCKED] {cmd}")
            continue

        tried.append(cmd)

        result = container.exec_command(cmd)
        if result.exit_code == 0:
            # Now retry the original step
            retry = container.exec_command(step.action)
            if retry.exit_code == 0:
                return RecoveryResult(
                    succeeded=True,
                    fix_applied=cmd,
                    commands_tried=tried,
                )

    return RecoveryResult(succeeded=False, commands_tried=tried)


def _heuristic_recovery(error: str) -> list[dict]:
    """Fallback recovery suggestions without AI."""
    error_lower = error.lower()
    suggestions = []

    if "node" in error_lower and "not found" in error_lower:
        suggestions.append({
            "command": "curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs",
            "reasoning": "Node.js not installed",
        })
    elif "npm" in error_lower and "not found" in error_lower:
        suggestions.append({
            "command": "curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash - && sudo apt-get install -y nodejs",
            "reasoning": "npm not installed (comes with Node.js)",
        })
    elif "python" in error_lower and "not found" in error_lower:
        suggestions.append({
            "command": "sudo apt-get update && sudo apt-get install -y python3 python3-pip python3-venv",
            "reasoning": "Python not installed",
        })
    elif "pip" in error_lower and "not found" in error_lower:
        suggestions.append({
            "command": "sudo apt-get update && sudo apt-get install -y python3-pip",
            "reasoning": "pip not installed",
        })
    elif "permission denied" in error_lower:
        suggestions.append({
            "command": "find . -name '*.sh' -exec chmod +x {} +",
            "reasoning": "Shell scripts may not be executable",
        })

    return suggestions
