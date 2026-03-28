"""Scans a repository for onboarding-relevant documentation."""

import glob
from pathlib import Path
from dataclasses import dataclass, field
from ghost.config import (
    ONBOARDING_FILES,
    BUILD_FILES,
    PACKAGE_FILES,
    ENV_FILES,
    VERSION_FILES,
    CI_GLOB,
)


@dataclass
class ScanResult:
    """Result of scanning a repository for docs."""

    repo_path: str
    files_found: dict[str, str] = field(default_factory=dict)  # filename -> content
    detected_project_type: str = "unknown"
    has_dockerfile: bool = False
    has_docker_compose: bool = False


def scan_repo(repo_path: str) -> ScanResult:
    """Scan a repository for all onboarding-relevant files."""
    root = Path(repo_path)
    result = ScanResult(repo_path=repo_path)

    all_targets = ONBOARDING_FILES + BUILD_FILES + PACKAGE_FILES + ENV_FILES + VERSION_FILES

    for filename in all_targets:
        filepath = root / filename
        if filepath.is_file():
            try:
                content = filepath.read_text(encoding="utf-8", errors="replace")
                result.files_found[filename] = content[:50000]  # Cap size
            except Exception:
                pass

    # CI workflow files
    ci_pattern = str(root / CI_GLOB)
    for ci_file in glob.glob(ci_pattern):
        rel = str(Path(ci_file).relative_to(root))
        try:
            content = Path(ci_file).read_text(encoding="utf-8", errors="replace")
            result.files_found[rel] = content[:20000]
        except Exception:
            pass

    result.detected_project_type = _detect_project_type(result.files_found)
    result.has_dockerfile = "Dockerfile" in result.files_found
    result.has_docker_compose = any(
        k.startswith("docker-compose") for k in result.files_found
    )

    return result


def _detect_project_type(files: dict[str, str]) -> str:
    """Detect the primary project type from found files."""
    if "package.json" in files:
        return "node"
    if "pyproject.toml" in files or any("requirements" in f for f in files):
        return "python"
    if "Cargo.toml" in files:
        return "rust"
    if "go.mod" in files:
        return "go"
    if "Gemfile" in files:
        return "ruby"
    if "pom.xml" in files or "build.gradle" in files:
        return "java"
    return "unknown"
