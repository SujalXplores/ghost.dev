"""Executes planned setup steps inside a Docker container."""

import time
from ghost.models.step import PlanResult
from ghost.models.report import StepResult
from ghost.models.friction import FrictionEvent
from ghost.docker.container import GhostContainer
from ghost.core.observer import observe
from ghost.core.recoverer import attempt_recovery
from ghost.core._utils import is_command_safe
from typing import Callable


def execute_plan(
    plan: PlanResult,
    container: GhostContainer,
    on_step_start: Callable | None = None,
    on_step_end: Callable | None = None,
    max_total_time: int = 1800,
    run_start_time: float | None = None,
    env: dict[str, str] | None = None,
) -> list[StepResult]:
    """Execute all planned steps and return results.

    Args:
        max_total_time: Hard cap on total execution time in seconds.
        run_start_time: When the overall run started (time.time()).
        env: Environment variables to inject into each command.
    """
    results: list[StepResult] = []
    successful_commands: list[str] = []
    start = run_start_time or time.time()

    for step in plan.steps:
        # Enforce total timeout
        elapsed = time.time() - start
        if elapsed > max_total_time:
            results.append(StepResult(
                step_number=step.step_number,
                command=step.action,
                status="skipped",
                friction_event=FrictionEvent(
                    step_number=step.step_number,
                    category="undocumented_step",
                    severity="medium",
                    description=f"Skipped: total run exceeded {max_total_time // 60}m limit",
                    command_attempted=step.action,
                ),
            ))
            continue

        if on_step_start:
            on_step_start(step)

        exec_result = container.exec_command(step.action, env=env)
        status, friction_event = observe(step, exec_result)

        # Attempt recovery on failure
        if friction_event and friction_event.is_failure:
            recovery = attempt_recovery(
                step=step,
                error=exec_result.stderr,
                container=container,
                previous_steps=successful_commands,
            )
            if recovery.succeeded:
                friction_event.self_recovered = True
                friction_event.recovery_method = recovery.fix_applied
                friction_event.add_note(f"Self-recovered: {recovery.fix_applied}")
                status = "recovered"
                exec_result = container.exec_command(step.action, env=env)
            else:
                friction_event.severity = "critical"

        step_result = StepResult(
            step_number=step.step_number,
            command=step.action,
            status=status,
            duration=exec_result.duration,
            stdout=exec_result.stdout,
            stderr=exec_result.stderr,
            exit_code=exec_result.exit_code,
            friction_event=friction_event,
        )
        results.append(step_result)

        if status in ("success", "recovered"):
            successful_commands.append(step.action)

        if on_step_end:
            on_step_end(step, step_result)

    return results
