"""Shared utilities for ghost.dev core modules."""

import json
import logging
import re

logger = logging.getLogger("ghost")

# Patterns that should never be executed — even inside Docker
_DANGEROUS_PATTERNS = [
    re.compile(r"\brm\s+-rf\s+/\s*$"),          # rm -rf /
    re.compile(r"\brm\s+-rf\s+/[^h]"),           # rm -rf /anything (except /home)
    re.compile(r"\bmkfs\b"),                       # format filesystem
    re.compile(r"\bdd\s+.*of=/dev/"),              # raw disk write
    re.compile(r"curl\s+.*\|\s*(?:sudo\s+)?bash"), # curl | bash from unknown
    re.compile(r"wget\s+.*\|\s*(?:sudo\s+)?bash"),
    re.compile(r":\(\)\s*\{\s*:\|:\s*&\s*\}"),    # fork bomb
    re.compile(r"\bshutdown\b"),
    re.compile(r"\breboot\b"),
    re.compile(r"\binit\s+0\b"),
]


def parse_ai_json(text: str) -> dict:
    """Parse JSON from an AI response, stripping markdown fences if present."""
    text = text.strip()
    if text.startswith("```"):
        text = text.split("\n", 1)[1]
        text = text.rsplit("```", 1)[0]
    return json.loads(text)


def is_command_safe(command: str) -> bool:
    """Check if a command is safe to execute inside the container."""
    cmd = command.strip()
    for pattern in _DANGEROUS_PATTERNS:
        if pattern.search(cmd):
            logger.warning("Blocked dangerous command: %s", cmd[:80])
            return False
    return True
