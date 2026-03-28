"""HTML report generator using Jinja2."""

from pathlib import Path
from jinja2 import Template
from ghost.models.report import GhostReport

TEMPLATE_DIR = Path(__file__).parent / "templates"


def generate_html_report(report: GhostReport, output_path: str) -> str:
    """Generate a self-contained HTML friction report."""
    template_file = TEMPLATE_DIR / "report.html"
    template = Template(template_file.read_text(encoding="utf-8"))

    plan = report.plan
    data = {
        "repo_name": report.repo_name or report.repo_url,
        "repo_url": report.repo_url,
        "scan_date": report.scan_date.strftime("%Y-%m-%d %H:%M UTC"),
        "grade": report.grade,
        "friction_score": report.friction_score,
        "friction_level": report.friction_level,
        "total_duration_min": round(report.total_duration / 60, 1),
        "total_duration_sec": round(report.total_duration, 1),
        "time_to_build_min": round(report.time_to_first_build / 60, 1) if report.time_to_first_build else None,
        "time_to_test_min": round(report.time_to_first_test / 60, 1) if report.time_to_first_test else None,
        "docs_found": report.docs_found,
        "docs_count": len(report.docs_found),
        # Plan data
        "has_plan": plan is not None,
        "steps": [s.model_dump() for s in plan.steps] if plan else [],
        "step_count": len(plan.steps) if plan else 0,
        "prerequisites": plan.prerequisites if plan else [],
        "env_vars": plan.environment_variables if plan else [],
        "implicit_reqs": plan.implicit_requirements if plan else [],
        "project_type": (plan.detected_project_type if plan and plan.detected_project_type != "unknown"
                        else report.scanner_project_type),
        # Execution data
        "step_results": [_sr_to_dict(sr) for sr in report.step_results],
        "has_execution": len(report.step_results) > 0,
        # Friction data
        "friction_events": [_fe_to_dict(e) for e in report.friction_events],
        "friction_count": len(report.friction_events),
        "fix_suggestions": report.fix_suggestions,
        "cost_hours": report.estimated_cost_hours,
        "cost_dollars": report.estimated_cost_hours * 100,
        "categories": _count_categories(report),
    }

    html = template.render(**data)
    Path(output_path).write_text(html, encoding="utf-8")
    return output_path


def _sr_to_dict(sr) -> dict:
    """Convert StepResult to a plain dict for Jinja2."""
    d = {
        "step_number": sr.step_number,
        "command": sr.command,
        "status": sr.status,
        "duration": sr.duration,
        "exit_code": sr.exit_code,
        "stdout": sr.stdout[:2000] if sr.stdout else "",
        "stderr": sr.stderr[:2000] if sr.stderr else "",
    }
    if sr.friction_event:
        d["friction"] = _fe_to_dict(sr.friction_event)
    else:
        d["friction"] = None
    return d


def _fe_to_dict(e) -> dict:
    """Convert FrictionEvent to a plain dict for Jinja2."""
    return {
        "step_number": e.step_number,
        "category": e.category,
        "severity": e.severity,
        "description": e.description,
        "command": e.command_attempted,
        "error_output": e.error_output[:1000] if e.error_output else "",
        "doc_source": e.doc_source,
        "doc_line": e.doc_line,
        "reality": e.reality,
        "time_wasted": e.time_wasted_estimate,
        "suggested_fix": e.suggested_fix,
        "self_recovered": e.self_recovered,
        "recovery_method": e.recovery_method,
    }


def _count_categories(report: GhostReport) -> list[dict]:
    counts: dict[str, int] = {}
    for e in report.friction_events:
        counts[e.category] = counts.get(e.category, 0) + 1
    max_c = max(counts.values()) if counts else 1
    return [
        {"name": k.replace("_", " ").title(), "count": v, "pct": int(v / max_c * 100)}
        for k, v in sorted(counts.items(), key=lambda x: -x[1])
    ]
