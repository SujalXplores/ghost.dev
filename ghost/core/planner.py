"""AI-powered planner that extracts setup steps from documentation."""

import json
import hashlib
import sqlite3
from ghost.core.scanner import ScanResult
from ghost.models.step import PlanResult, SetupStep
from ghost.config import CACHE_DB
from ghost.core._ai import ai_call
from ghost.core._utils import parse_ai_json

PLANNER_SYSTEM = """You are simulating a brand-new developer who has NEVER seen this project.
You can ONLY use information explicitly stated in the provided documentation.
DO NOT use any prior knowledge about frameworks, tools, or conventions.

From the documentation provided, extract an ordered list of setup steps.
Each step must include:
- step_number: int
- action: str (the exact command or action to perform)
- source: str (which file and line this instruction came from)
- confidence: float (0-1, how clear/unambiguous this instruction is)
- assumptions: list[str] (any implicit knowledge required that isn't stated)
- description: str (brief human-readable description of what this step does)

If the docs are vague (e.g., "set up the database"), mark confidence as low and list what's missing.

Also identify:
- prerequisites: what must be installed BEFORE the documented steps
- environment_variables: all env vars mentioned anywhere
- implicit_requirements: things the docs assume you know but don't state
- detected_project_type: node, python, rust, go, ruby, java, or unknown

Return ONLY valid JSON matching this schema, no markdown fences:
{
  "steps": [...],
  "prerequisites": [...],
  "environment_variables": [...],
  "implicit_requirements": [...],
  "detected_project_type": "..."
}"""


def plan_setup(scan: ScanResult, model: str = "", use_cache: bool = True) -> PlanResult:
    """Use AI to extract ordered setup steps from scanned docs."""
    from ghost.config import _ensure_cache_dir
    _ensure_cache_dir()

    doc_context = _build_doc_context(scan.files_found)
    cache_key = _cache_key(doc_context + "|model=" + (model or "default"))

    if use_cache:
        cached = _get_cached(cache_key)
        if cached:
            return cached

    user_msg = f"Here are all the documentation files from the repository:\n{doc_context}"

    # Try up to 2 times - AI sometimes returns malformed JSON on first attempt
    last_error = None
    for attempt in range(2):
        try:
            response = ai_call(system=PLANNER_SYSTEM, user=user_msg, model=model)
            plan = _parse_plan_strict(response, scan.detected_project_type)
            _set_cached(cache_key, plan)
            return plan
        except (json.JSONDecodeError, ValueError, KeyError) as e:
            last_error = e
            continue
        except Exception as e:
            # AI call itself failed (network, auth, etc.) - don't retry
            raise

    # Both attempts failed to parse - return empty plan, don't cache it
    return PlanResult(
        steps=[],
        detected_project_type=scan.detected_project_type,
    )


def _build_doc_context(files: dict[str, str], max_chars: int = 100_000) -> str:
    """Build doc context string, prioritizing onboarding files and capping size."""
    # Priority order: README > CONTRIBUTING > SETUP/INSTALL > package files > CI
    priority = ["README", "CONTRIBUTING", "SETUP", "INSTALL", "DEVELOPMENT",
                "Makefile", "Justfile", "package.json", "pyproject.toml",
                "Cargo.toml", "go.mod", "Gemfile", "pom.xml",
                ".env.example", ".env.sample"]

    def sort_key(name: str) -> int:
        for i, p in enumerate(priority):
            if p.lower() in name.lower():
                return i
        return 100  # CI and other files last

    sorted_files = sorted(files.keys(), key=sort_key)
    context = ""
    for filename in sorted_files:
        entry = f"\n\n--- FILE: {filename} ---\n{files[filename]}"
        if len(context) + len(entry) > max_chars:
            break
        context += entry
    return context


def _parse_plan_strict(response: str, scanner_project_type: str = "unknown") -> PlanResult:
    """Parse AI response into a PlanResult. Raises on failure so caller can retry."""
    data = parse_ai_json(response)  # Raises JSONDecodeError if malformed
    if "steps" not in data or not data["steps"]:
        raise ValueError("No steps found in AI response")
    if data.get("detected_project_type", "unknown") == "unknown":
        data["detected_project_type"] = scanner_project_type
    return PlanResult(**data)


def _cache_key(content: str) -> str:
    return hashlib.sha256(content.encode()).hexdigest()


def _get_cached(key: str) -> PlanResult | None:
    try:
        with sqlite3.connect(str(CACHE_DB)) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS plan_cache "
                "(key TEXT PRIMARY KEY, data TEXT, created_at REAL DEFAULT (strftime('%s','now')))"
            )
            # TTL: ignore entries older than 24 hours
            row = conn.execute(
                "SELECT data FROM plan_cache WHERE key = ? "
                "AND (created_at IS NULL OR created_at > strftime('%s','now') - 86400)",
                (key,),
            ).fetchone()
            if row:
                return PlanResult(**json.loads(row[0]))
    except Exception:
        pass
    return None


def _set_cached(key: str, plan: PlanResult) -> None:
    try:
        with sqlite3.connect(str(CACHE_DB)) as conn:
            conn.execute(
                "CREATE TABLE IF NOT EXISTS plan_cache "
                "(key TEXT PRIMARY KEY, data TEXT, created_at REAL DEFAULT (strftime('%s','now')))"
            )
            conn.execute(
                "INSERT OR REPLACE INTO plan_cache (key, data, created_at) VALUES (?, ?, strftime('%s','now'))",
                (key, plan.model_dump_json()),
            )
    except Exception:
        pass
