"""AI-generated fix suggestions for friction events."""

import json
from ghost.models.friction import FrictionEvent
from ghost.core._ai import ai_call

FIXGEN_SYSTEM = """For each friction event in a developer onboarding process, generate a concrete documentation fix.

Return ONLY valid JSON array, no markdown fences:
[
  {
    "file_to_fix": "README.md",
    "section": "Getting Started",
    "current_text": "what the docs currently say",
    "suggested_text": "what the docs should say instead",
    "reasoning": "why this change is needed"
  }
]"""


def generate_fixes(events: list[FrictionEvent]) -> list[dict]:
    """Generate fix suggestions for all friction events."""
    if not events:
        return []

    descriptions = []
    for e in events:
        descriptions.append(
            f"- Step {e.step_number}: {e.description}\n"
            f"  Command: {e.command_attempted}\n"
            f"  Error: {e.error_output[:500]}\n"
            f"  Doc source: {e.doc_source}\n"
            f"  Doc said: {e.doc_line}\n"
            f"  Reality: {e.reality}\n"
            f"  Category: {e.category}"
        )

    user_prompt = (
        "Here are the friction events found during onboarding:\n\n"
        + "\n\n".join(descriptions)
    )

    try:
        response = ai_call(system=FIXGEN_SYSTEM, user=user_prompt)
        text = response.strip()
        if text.startswith("```"):
            text = text.split("\n", 1)[1]
            text = text.rsplit("```", 1)[0]
        return json.loads(text)
    except Exception:
        # Fallback: generate basic suggestions from events
        return [
            {
                "file_to_fix": e.doc_source or "README.md",
                "section": "Setup",
                "current_text": e.doc_line,
                "suggested_text": e.suggested_fix,
                "reasoning": e.description,
            }
            for e in events
            if e.suggested_fix
        ]
