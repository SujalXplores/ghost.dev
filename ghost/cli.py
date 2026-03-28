"""ghost.dev CLI — The Phantom Developer."""

from __future__ import annotations

import atexit
import json
import logging
import re
import shutil
import sys
import time
import tempfile
from pathlib import Path

import click
from rich.console import Console

from ghost.config import MAX_TOTAL_TIMEOUT

console = Console()
logger = logging.getLogger("ghost")

_temp_dirs: list[str] = []


def _cleanup_temp():
    for d in _temp_dirs:
        shutil.rmtree(d, ignore_errors=True)


atexit.register(_cleanup_temp)


BANNER = """[bold cyan]
   ╔══════════════════════════════════════╗
   ║  👻  g h o s t . d e v              ║
   ║     the phantom developer           ║
   ╚══════════════════════════════════════╝[/bold cyan]"""


class GhostGroup(click.Group):
    """Custom Click group with Rich-styled help."""

    def format_help(self, ctx, formatter):
        console.print(BANNER)
        console.print("  [dim]Simulates a brand-new developer onboarding onto any repository.[/dim]")
        console.print("  [dim]Finds every friction point, missing step, and broken instruction.[/dim]")
        console.print()
        console.print("  [bold white]Commands:[/bold white]")
        for name, cmd in self.commands.items():
            short = cmd.get_short_help_str(limit=60)
            console.print(f"    [cyan]{name:<12}[/cyan] {short}")
        console.print()
        console.print("  [bold white]Quick start:[/bold white]")
        console.print("    [green]ghost run[/green] https://github.com/user/repo")
        console.print("    [green]ghost run[/green] ./local-project --no-docker")
        console.print("    [green]ghost setup[/green]")
        console.print()


@click.group(cls=GhostGroup)
@click.version_option(version="0.1.0", prog_name="ghost.dev")
def main():
    """👻 ghost.dev — The Phantom Developer."""
    pass


@main.command()
def setup():
    """Configure API keys for ghost.dev."""
    console.print(BANNER)
    _interactive_key_setup()


@main.command()
def clean():
    """Remove cached plans and orphaned containers."""
    import ghost.config as cfg

    cleaned = []
    if cfg.CACHE_DB.exists():
        cfg.clear_cache()
        cleaned.append("plan cache")

    # Try to remove orphaned ghost containers
    try:
        import docker
        client = docker.from_env()
        containers = client.containers.list(all=True, filters={"name": "ghost-"})
        for c in containers:
            try:
                c.remove(force=True)
                cleaned.append(f"container {c.name}")
            except Exception:
                pass
    except Exception:
        pass

    if cleaned:
        for item in cleaned:
            console.print(f"  [green]✓[/green] Removed {item}")
    else:
        console.print("  [dim]Nothing to clean.[/dim]")
    console.print()


@main.command()
@click.argument("repo")
@click.option("--depth", type=click.Choice(["quick", "full"]), default="quick",
              help="quick = build only, full = build+test+contribute")
@click.option("--timeout", default=5, type=int, help="Max minutes per step")
@click.option("--model", default="", help="AI model (e.g. google/gemini-3.1-pro)")
@click.option("--output", default="", help="HTML report path (auto-named if empty)")
@click.option("--no-docker", is_flag=True, help="Doc analysis only, no execution")
@click.option("--verbose", is_flag=True, help="Show container stdout/stderr")
@click.option("--json-output", "json_out", is_flag=True, help="Output report as JSON")
@click.option("--fail-threshold", type=int, default=None,
              help="Exit code 2 if friction score exceeds this value")
@click.option("--no-cache", is_flag=True, help="Bypass the plan cache")
@click.option("--quiet", is_flag=True, help="Minimal output")
@click.option("--debug", is_flag=True, help="Enable debug logging")
def run(repo, depth, timeout, model, output, no_docker, verbose, json_out, fail_threshold, no_cache, quiet, debug):
    """Run ghost.dev against a repository."""
    if debug:
        logging.basicConfig(level=logging.DEBUG, format="  [%(name)s] %(message)s")
    try:
        _run_impl(repo, depth, timeout, model, output, no_docker, verbose,
                  json_out, fail_threshold, no_cache, quiet)
    except KeyboardInterrupt:
        console.print("\n  [dim]Interrupted.[/dim]")
        sys.exit(130)
    except Exception as e:
        _print_error(e)
        sys.exit(1)


def _print_error(e: Exception):
    msg = str(e)
    console.print()
    if "onnect" in msg or "WinError" in msg or "refused" in msg:
        console.print("  [red]✗ Network error — can't reach the AI provider.[/red]")
        console.print("    Check your connection or run [cyan]ghost setup[/cyan] to switch providers.")
    elif "API" in msg or "key" in msg.lower() or "401" in msg or "auth" in msg.lower():
        console.print(f"  [red]✗ AI provider error:[/red] [dim]{msg[:120]}[/dim]")
        console.print("    Run [cyan]ghost setup[/cyan] to reconfigure.")
    elif "Docker" in msg or "docker" in msg:
        console.print(f"  [red]✗ Docker error:[/red] [dim]{msg[:120]}[/dim]")
        console.print("    Try [cyan]--no-docker[/cyan] for analysis-only mode.")
    else:
        console.print(f"  [red]✗[/red] {msg[:200]}")
    console.print()


def _run_impl(repo, depth, timeout, model, output, no_docker, verbose,
              json_out, fail_threshold, no_cache, quiet):
    from ghost.core.scanner import scan_repo
    from ghost.core.planner import plan_setup
    from ghost.models.report import GhostReport
    from ghost.reporter.terminal import (
        print_header, print_step_start, print_step_result,
        print_final_report, print_no_docker_report,
    )
    from ghost.reporter.html import generate_html_report
    from ghost.fixgen.suggestions import generate_fixes
    from rich.status import Status

    _ensure_api_key()

    # Validate repo argument
    repo_name = _extract_repo_name(repo)
    _validate_repo_arg(repo)

    if not output:
        safe = repo_name.replace("/", "-").replace("\\", "-")
        output = f"ghost-{safe}-report.html"

    run_start = time.time()
    if not quiet:
        console.print()

    # ── Clone ─────────────────────────────────────────────────
    if not quiet:
        with Status(f"[cyan]Resolving {repo_name}...[/cyan]", console=console, spinner="dots"):
            repo_path, clone_err = _resolve_repo(repo)
    else:
        repo_path, clone_err = _resolve_repo(repo)

    if not repo_path:
        console.print(f"  [red]✗[/red] {clone_err or 'Could not clone or find repository.'}")
        sys.exit(1)
    if not quiet:
        console.print(f"  [green]✓[/green] [white]{repo_name}[/white] ready")

    # ── Scan ──────────────────────────────────────────────────
    if not quiet:
        with Status("[cyan]Scanning docs...[/cyan]", console=console, spinner="dots"):
            scan = scan_repo(repo_path)
    else:
        scan = scan_repo(repo_path)

    if not scan.files_found:
        console.print("  [red]✗[/red] No documentation files found.")
        sys.exit(1)
    n = len(scan.files_found)
    if not quiet:
        console.print(f"  [green]✓[/green] {n} docs found [dim]({scan.detected_project_type})[/dim]")

    # ── Plan ──────────────────────────────────────────────────
    if not quiet:
        with Status("[cyan]AI extracting setup steps...[/cyan]", console=console, spinner="dots"):
            plan = plan_setup(scan, model=model, use_cache=not no_cache)
    else:
        plan = plan_setup(scan, model=model, use_cache=not no_cache)

    if not plan.steps:
        console.print("  [yellow]⚠[/yellow] AI couldn't extract setup steps from the docs.")
        console.print("    The docs may be too sparse or the AI response was malformed.")
        console.print("    Try a different [cyan]--model[/cyan] or check the repo's README.\n")
        sys.exit(1)
    plan = _filter_by_depth(plan, depth)
    if not quiet:
        console.print(f"  [green]✓[/green] {len(plan.steps)} steps [dim](depth={depth})[/dim]")
        console.print()

    report = GhostReport(
        repo_url=repo,
        repo_name=repo_name,
        scanner_project_type=scan.detected_project_type,
        docs_found=list(scan.files_found.keys()),
        plan=plan,
    )

    # ── No-docker: analysis only ──────────────────────────────
    if no_docker:
        report.total_duration = time.time() - run_start
        if json_out:
            _print_json_report(report)
        else:
            if not quiet:
                print_no_docker_report(report)
            generate_html_report(report, output)
            if not quiet:
                console.print(f"  📄 Report saved: [cyan]{output}[/cyan]\n")
        _exit_with_threshold(report, fail_threshold)
        return

    # ── Docker execution ──────────────────────────────────────
    from ghost.docker.container import GhostContainer
    from ghost.core.executor import execute_plan

    timeout_secs = timeout * 60
    try:
        if not quiet:
            with Status("[cyan]Starting Docker container...[/cyan]", console=console, spinner="dots"):
                container = GhostContainer(repo_path, timeout=timeout_secs, verbose=verbose)
                container_name = container.start()
        else:
            container = GhostContainer(repo_path, timeout=timeout_secs, verbose=verbose)
            container_name = container.start()
    except RuntimeError as e:
        if not quiet:
            console.print(f"  [yellow]⚠[/yellow] {e}")
            console.print("  [dim]Falling back to doc analysis...[/dim]\n")
        report.total_duration = time.time() - run_start
        if json_out:
            _print_json_report(report)
        else:
            if not quiet:
                print_no_docker_report(report)
            generate_html_report(report, output)
            if not quiet:
                console.print(f"  📄 Report saved: [cyan]{output}[/cyan]\n")
        _exit_with_threshold(report, fail_threshold)
        return

    try:
        if not quiet:
            print_header(repo_name, list(scan.files_found.keys()), len(plan.steps), container_name)

        # Build env dict from detected env vars
        env_dict = _build_env_dict(plan.environment_variables)

        total_steps = len(plan.steps)

        def on_start(step):
            if not quiet:
                print_step_start(step, total_steps)

        def on_end(step, result):
            if not quiet:
                print_step_result(result)
                if verbose and result.stderr:
                    console.print(f"       [dim]{result.stderr[:200]}[/dim]")

        step_results = execute_plan(
            plan=plan,
            container=container,
            on_step_start=on_start,
            on_step_end=on_end,
            max_total_time=MAX_TOTAL_TIMEOUT,
            run_start_time=run_start,
            env=env_dict if env_dict else None,
        )

        report.step_results = step_results
        report.friction_events = [sr.friction_event for sr in step_results if sr.friction_event]
        report.total_duration = time.time() - run_start
        _calculate_milestones(report)

        if report.friction_events and not quiet:
            with Status("[cyan]Generating fix suggestions...[/cyan]", console=console, spinner="dots"):
                report.fix_suggestions = generate_fixes(report.friction_events)
        elif report.friction_events:
            report.fix_suggestions = generate_fixes(report.friction_events)

        if json_out:
            _print_json_report(report)
        else:
            if not quiet:
                print_final_report(report)
            generate_html_report(report, output)
            if not quiet:
                console.print(f"  📄 Report saved: [cyan]{output}[/cyan]\n")

        _exit_with_threshold(report, fail_threshold)

    finally:
        container.destroy()


# ── Helpers ───────────────────────────────────────────────────

def _validate_repo_arg(repo: str):
    """Validate the repo argument and give specific error messages."""
    p = Path(repo)
    if p.exists():
        if not p.is_dir():
            console.print(f"  [red]✗[/red] '{repo}' is a file, not a directory.")
            sys.exit(1)
        return  # Valid local path

    # Check if it looks like a URL or SSH path
    url_pattern = re.compile(
        r"^(https?://|git@|ssh://)"
        r"|^[a-zA-Z0-9_-]+/[a-zA-Z0-9_.-]+$"  # user/repo shorthand
    )
    if url_pattern.match(repo):
        return  # Looks like a valid remote ref

    # Doesn't exist locally and doesn't look like a URL
    console.print(f"  [red]✗[/red] '{repo}' is not a valid path or repository URL.")
    console.print("    Expected: a local directory, a git URL, or owner/repo shorthand.")
    sys.exit(1)


def _extract_repo_name(repo: str) -> str:
    """Extract a clean repo name from a URL or path."""
    r = repo.rstrip("/")
    if r.endswith(".git"):
        r = r[:-4]
    # SSH URLs: git@github.com:user/repo
    ssh_match = re.match(r"git@[^:]+:(.+)", r)
    if ssh_match:
        return ssh_match.group(1)
    for prefix in ["https://github.com/", "git@github.com:", "http://github.com/",
                    "https://gitlab.com/", "https://bitbucket.org/"]:
        if r.startswith(prefix):
            name = r[len(prefix):]
            # Strip query params and fragments
            name = name.split("?")[0].split("#")[0]
            return name
    # Strip query params and fragments from URLs
    r = r.split("?")[0].split("#")[0]
    # Local path — resolve "." and ".." to actual directory name
    p = Path(r).resolve()
    if p.is_dir():
        return p.name
    if "/" in r or "\\" in r:
        parts = r.replace("\\", "/").split("/")
        return "/".join(p for p in parts[-2:] if p)
    return r


def _resolve_repo(repo: str) -> tuple[str | None, str]:
    """Clone a git URL or validate a local path. Returns (path, error_msg)."""
    p = Path(repo)
    if p.is_dir():
        return str(p.resolve()), ""
    try:
        import git
        tmpdir = tempfile.mkdtemp(prefix="ghost-")
        _temp_dirs.append(tmpdir)

        clone_kwargs = dict(depth=1, single_branch=True)
        # kill_after_timeout is not supported on Windows
        if sys.platform != "win32":
            clone_kwargs["kill_after_timeout"] = 120

        git.Repo.clone_from(repo, tmpdir, **clone_kwargs)
        return tmpdir, ""
    except Exception as e:
        err = str(e)
        logger.debug("Clone failed: %s", err)
        if "not found" in err.lower() or "404" in err:
            return None, f"Repository not found: {repo}"
        if "auth" in err.lower() or "403" in err or "could not read" in err.lower():
            return None, "Authentication required — is this a private repo?"
        if "timeout" in err.lower() or "timed out" in err.lower():
            return None, "Clone timed out — the repo may be very large or the network is slow."
        # Include the actual error for debugging
        short_err = err.split("\n")[0][:150]
        return None, f"Clone failed: {short_err}"


def _build_env_dict(env_vars: list[str]) -> dict[str, str]:
    """Build env dict from detected variable names."""
    d = {}
    for var in env_vars:
        name = var.split("=")[0].strip()
        if name:
            d[name] = "ghost_placeholder"
    return d


def _print_json_report(report):
    """Output the report as JSON to stdout."""
    from ghost.models.report import GhostReport
    data = {
        "repo_url": report.repo_url,
        "repo_name": report.repo_name,
        "project_type": report.scanner_project_type,
        "scan_date": report.scan_date.isoformat(),
        "grade": report.grade,
        "friction_score": report.friction_score,
        "friction_level": report.friction_level,
        "total_duration": round(report.total_duration, 2),
        "time_to_first_build": report.time_to_first_build,
        "time_to_first_test": report.time_to_first_test,
        "docs_found": report.docs_found,
        "friction_count": len(report.friction_events),
        "estimated_cost_hours": report.estimated_cost_hours,
        "step_results": [
            {
                "step": sr.step_number,
                "command": sr.command,
                "status": sr.status,
                "duration": sr.duration,
                "exit_code": sr.exit_code,
            }
            for sr in report.step_results
        ],
        "friction_events": [
            {
                "step": e.step_number,
                "category": e.category,
                "severity": e.severity,
                "description": e.description,
                "self_recovered": e.self_recovered,
            }
            for e in report.friction_events
        ],
        "fix_suggestions": report.fix_suggestions,
    }
    click.echo(json.dumps(data, indent=2))


def _exit_with_threshold(report, threshold: int | None):
    """Exit with code 2 if friction score exceeds threshold."""
    if threshold is not None and report.friction_score > threshold:
        sys.exit(2)


# ── Depth filtering ───────────────────────────────────────────

# Test runners (first word of command)
_TEST_RUNNERS = {"pytest", "jest", "mocha", "rspec", "vitest", "phpunit",
                 "cargo-test", "bun", "deno"}
# Subcommands that indicate test/lint/contribute
_TEST_SUBCOMMANDS = {"test", "spec", "check"}
_LINT_SUBCOMMANDS = {"lint", "format", "typecheck"}
# Full command prefixes
_TEST_PREFIXES = ("npm test", "yarn test", "pnpm test", "cargo test", "go test",
                  "mvn test", "gradle test", "make test", "make check",
                  "bun test", "deno test")
_LINT_PREFIXES = ("npm run lint", "yarn lint", "pnpm lint", "pre-commit",
                  "eslint", "flake8", "ruff check", "mypy", "prettier",
                  "black", "isort")


def _is_test_or_lint_step(cmd: str) -> bool:
    """Check if a command is a test/lint step using word-level matching."""
    cmd_lower = cmd.lower().strip()
    for prefix in _TEST_PREFIXES + _LINT_PREFIXES:
        if cmd_lower.startswith(prefix):
            return True
    words = cmd_lower.split()
    if not words:
        return False
    first = words[0]
    if first in _TEST_RUNNERS:
        return True
    if len(words) >= 2 and words[1] in (_TEST_SUBCOMMANDS | _LINT_SUBCOMMANDS):
        return True
    return False


def _filter_by_depth(plan, depth: str):
    """Filter plan steps by depth. quick = build only, full = everything."""
    if depth == "full":
        return plan
    from ghost.models.step import PlanResult
    filtered = [s for s in plan.steps if s.is_prerequisite or not _is_test_or_lint_step(s.action)]
    for i, step in enumerate(filtered, 1):
        step.step_number = i
    return PlanResult(
        steps=filtered,
        prerequisites=plan.prerequisites,
        environment_variables=plan.environment_variables,
        implicit_requirements=plan.implicit_requirements,
        detected_project_type=plan.detected_project_type,
    )


# ── Milestones ────────────────────────────────────────────────

_BUILD_WORDS = {"build", "compile", "install", "setup"}
_TEST_WORDS = {"test", "spec", "check", "pytest", "jest"}


def _calculate_milestones(report):
    cumulative = 0.0
    for sr in report.step_results:
        cumulative += sr.duration
        words = set(sr.command.lower().split())
        if report.time_to_first_build is None and words & _BUILD_WORDS:
            if sr.status in ("success", "recovered"):
                report.time_to_first_build = cumulative
        if report.time_to_first_test is None and words & _TEST_WORDS:
            if sr.status in ("success", "recovered"):
                report.time_to_first_test = cumulative


# ── API key management ────────────────────────────────────────

def _ensure_api_key():
    import ghost.config as cfg

    if not cfg.has_any_api_key():
        console.print(BANNER)
        console.print("  [yellow]👻 No API key found. Let's set one up.[/yellow]\n")
        _prompt_for_key()
        return

    ok, provider, err = _verify_api_connection()
    if ok:
        return

    console.print()
    console.print(f"  [red]✗[/red] {provider} key is invalid: [dim]{err}[/dim]")
    console.print()
    _prompt_for_key()


def _verify_api_connection() -> tuple[bool, str, str]:
    """Quick ping to configured AI providers using their own SDKs."""
    import ghost.config as cfg

    checks: list[tuple[str, str]] = []
    if cfg.ANTHROPIC_API_KEY:
        checks.append(("Anthropic", cfg.ANTHROPIC_API_KEY))
    if cfg.OPENROUTER_API_KEY:
        checks.append(("OpenRouter", cfg.OPENROUTER_API_KEY))
    if cfg.OPENAI_API_KEY:
        checks.append(("OpenAI", cfg.OPENAI_API_KEY))

    if not checks:
        return False, "none", "No API key configured"

    last_provider, last_err = "none", "No API key configured"
    for provider, key in checks:
        try:
            if provider == "Anthropic":
                import anthropic
                client = anthropic.Anthropic(api_key=key, timeout=10.0)
                client.models.list(limit=1)
                return True, provider, ""
            elif provider == "OpenRouter":
                from openai import OpenAI
                client = OpenAI(api_key=key, base_url=cfg.OPENROUTER_BASE_URL, timeout=10.0)
                client.models.list()
                return True, provider, ""
            elif provider == "OpenAI":
                from openai import OpenAI
                client = OpenAI(api_key=key, timeout=10.0)
                client.models.list()
                return True, provider, ""
        except Exception as e:
            last_provider, last_err = provider, str(e)[:100]
            continue

    return False, last_provider, last_err


def _prompt_for_key():
    import ghost.config as cfg

    providers = [
        ("ANTHROPIC_API_KEY", "Anthropic", "https://console.anthropic.com/", "recommended — direct, fastest"),
        ("OPENROUTER_API_KEY", "OpenRouter", "https://openrouter.ai/keys", "any model — Claude, GPT, Gemini, Llama"),
        ("OPENAI_API_KEY", "OpenAI", "https://platform.openai.com/api-keys", "GPT models"),
    ]

    console.print("  Select your AI provider:\n")
    for i, (_, name, _, desc) in enumerate(providers, 1):
        marker = "[cyan]›[/cyan]" if i == 1 else " "
        rec = " [green](recommended)[/green]" if i == 1 else ""
        console.print(f"  {marker} [white]{i}. {name}[/white]{rec}")
        console.print(f"      [dim]{desc}[/dim]")

    console.print()
    choice = click.prompt(
        "  Enter 1, 2, or 3",
        type=click.IntRange(1, 3),
        default=1,
        show_default=True,
    )

    key_name, provider, url, _ = providers[choice - 1]
    console.print(f"\n  Get your key → [link={url}][cyan]{url}[/cyan][/link]")
    console.print()

    key_value = click.prompt(f"  Paste {provider} API key", hide_input=True)
    if not key_value.strip():
        console.print("  [red]No key provided.[/red]")
        sys.exit(1)

    cfg.save_api_key(key_name, key_value.strip())
    console.print(f"\n  [green]✓[/green] {provider} key saved to [dim]{cfg.ENV_FILE}[/dim]")
    console.print("    You won't be asked again.\n")


def _interactive_key_setup():
    import ghost.config as cfg
    keys = [
        ("ANTHROPIC_API_KEY", "Anthropic", cfg.ANTHROPIC_API_KEY),
        ("OPENROUTER_API_KEY", "OpenRouter", cfg.OPENROUTER_API_KEY),
        ("OPENAI_API_KEY", "OpenAI", cfg.OPENAI_API_KEY),
    ]
    console.print()
    for _, provider, current in keys:
        st = "[green]✓[/green]" if current else "[dim]–[/dim]"
        console.print(f"  {st} {provider}")
    console.print()
    for key_name, provider, current in keys:
        if current:
            masked = f"{current[:8]}...{current[-4:]}" if len(current) > 12 else "***"
            console.print(f"  {provider}: [dim]{masked}[/dim]")
            if not click.confirm(f"  Replace?", default=False):
                continue
        value = click.prompt(f"  {provider} key (Enter to skip)", default="", show_default=False, hide_input=True)
        if value.strip():
            cfg.save_api_key(key_name, value.strip())
            console.print(f"  [green]✓[/green] Saved.")
    console.print(f"\n  Keys in: [dim]{cfg.ENV_FILE}[/dim]\n")


if __name__ == "__main__":
    main()
