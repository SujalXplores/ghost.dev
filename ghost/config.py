"""Configuration and settings for ghost.dev."""

import os
from pathlib import Path
from dotenv import load_dotenv

# User-level config directory
CONFIG_DIR = Path.home() / ".ghost-dev"
CONFIG_DIR.mkdir(parents=True, exist_ok=True)
ENV_FILE = CONFIG_DIR / ".env"

# Load from user config first, then project-local .env
if ENV_FILE.exists():
    load_dotenv(ENV_FILE)
load_dotenv()  # also load .env in cwd if present


# AI Configuration
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
OPENROUTER_API_KEY = os.getenv("OPENROUTER_API_KEY", "")
OPENROUTER_BASE_URL = "https://openrouter.ai/api/v1"
DEFAULT_MODEL = "claude-sonnet-4-6"

# Docker Configuration
DOCKER_BASE_IMAGE = "ubuntu:24.04"
DOCKER_CONTAINER_PREFIX = "ghost"
DOCKER_NETWORK_NAME = "ghost-net"
DEFAULT_COMMAND_TIMEOUT = 300  # 5 minutes per command
MAX_TOTAL_TIMEOUT = 1800  # 30 minutes total

# Scanner Configuration
ONBOARDING_FILES = [
    "README.md", "README.rst", "README.txt", "README",
    "CONTRIBUTING.md", "CONTRIBUTING.rst",
    "SETUP.md", "INSTALL.md", "DEVELOPMENT.md",
    "QUICKSTART.md",
]

BUILD_FILES = [
    "Makefile", "Justfile",
    "docker-compose.yml", "docker-compose.yaml",
    "Dockerfile",
]

PACKAGE_FILES = [
    "package.json", "pyproject.toml", "Cargo.toml",
    "go.mod", "Gemfile", "pom.xml", "build.gradle",
]

ENV_FILES = [
    ".env.example", ".env.sample", ".env.template",
]

VERSION_FILES = [
    ".nvmrc", ".python-version", ".tool-versions", ".ruby-version",
]

CI_GLOB = ".github/workflows/*.yml"

# Grading
SEVERITY_WEIGHTS = {
    "critical": 20,
    "high": 12,
    "medium": 6,
    "low": 2,
}
UNRECOVERED_PENALTY = 5

# Cache (lazy — created on first use, not at import)
CACHE_DIR = Path.home() / ".ghost-dev" / "cache"
CACHE_DB = CACHE_DIR / "ghost_cache.db"


def _ensure_cache_dir():
    CACHE_DIR.mkdir(parents=True, exist_ok=True)


def save_api_key(key_name: str, key_value: str) -> None:
    """Save an API key to the user-level .env file (~/.ghost-dev/.env)."""
    lines = []
    replaced = False
    if ENV_FILE.exists():
        for line in ENV_FILE.read_text(encoding="utf-8").splitlines():
            if line.startswith(f"{key_name}="):
                lines.append(f"{key_name}={key_value}")
                replaced = True
            else:
                lines.append(line)
    if not replaced:
        lines.append(f"{key_name}={key_value}")
    ENV_FILE.write_text("\n".join(lines) + "\n", encoding="utf-8")

    # Update the running process environment
    os.environ[key_name] = key_value
    # Update module-level vars so current session picks up the change
    import ghost.config as _self
    setattr(_self, key_name, key_value)


def reload_keys() -> None:
    """Reload API keys from environment after save."""
    import ghost.config as _self
    for key in ("ANTHROPIC_API_KEY", "OPENAI_API_KEY", "OPENROUTER_API_KEY"):
        setattr(_self, key, os.getenv(key, ""))


def has_any_api_key() -> bool:
    """Check if at least one AI provider key is configured."""
    return bool(
        os.getenv("ANTHROPIC_API_KEY")
        or os.getenv("OPENROUTER_API_KEY")
        or os.getenv("OPENAI_API_KEY")
    )


def clear_cache() -> None:
    """Remove the plan cache database."""
    if CACHE_DB.exists():
        CACHE_DB.unlink()
