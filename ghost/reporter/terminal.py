"""Rich terminal output for ghost.dev - polished UI/UX."""

from rich.console import Console, Group
from rich.panel import Panel
from rich.table import Table
from rich.text import Text
from rich.columns import Columns
from rich.rule import Rule
from rich import box
from ghost.models.report import GhostReport, StepResult
from ghost.models.step import SetupStep

console = Console()

# ── Status icons ──────────────────────────────────────────────
_ICON = {
    "success": "[green]✓[/green]",
    "recovered": "[yellow]↻[/yellow]",
    "failure": "[red]✗[/red]",
    "partial": "[yellow]![/yellow]",
    "ambiguity": "[blue]?[/blue]",
    "pending": "[dim]…[/dim]",
    "skipped": "[dim]–[/dim]",
}

_SEV_STYLE = {
    "critical": "bold red",
    "high": "red",
    "medium": "yellow",
    "low": "dim",
}


def _grade_style(score: int) -> str:
    if score <= 30:
        return "bold green"
    if score <= 60:
        return "bold yellow"
    return "bold red"


# ── Docker-mode header ────────────────────────────────────────
def print_header(repo_url: str, docs_found: list[str], step_count: int, container_name: str):
    console.print()
    t = Table(show_header=False, box=None, padding=(0, 1), expand=True)
    t.add_column(ratio=1)
    t.add_column(justify="right")
    t.add_row(
        f"[bold cyan]{repo_url}[/bold cyan]",
        f"[dim]{len(docs_found)} docs · {step_count} steps[/dim]",
    )
    if container_name:
        t.add_row(
            f"[dim]container[/dim] [white]{container_name}[/white]",
            "[dim]ubuntu:24.04[/dim]",
        )
    console.print(Panel(
        t,
        title="[bold white]👻 ghost.dev[/bold white]",
        subtitle="[dim]phantom developer simulation[/dim]",
        border_style="bright_cyan",
        padding=(1, 2),
    ))
    console.print()


# ── Step execution (live) ─────────────────────────────────────
def print_step_start(step: SetupStep, total: int):
    pad = len(str(total))
    num = f"[bold white]{step.step_number:>{pad}}[/bold white]"
    of = f"[dim]/{total}[/dim]"
    cmd = f"[white]{step.action[:65]}[/white]"
    conf_pct = int(step.confidence * 100)
    if conf_pct >= 70:
        conf = f"[green]{conf_pct}%[/green]"
    elif conf_pct >= 40:
        conf = f"[yellow]{conf_pct}%[/yellow]"
    else:
        conf = f"[red]{conf_pct}%[/red]"
    console.print(f"  {num}{of}  {cmd}  [dim]{conf}[/dim]", end="")


def print_step_result(result: StepResult):
    icon = _ICON.get(result.status, "?")
    dur = f"[dim]{result.duration:.1f}s[/dim]"
    console.print(f"  {icon} {dur}")
    if result.friction_event:
        e = result.friction_event
        sev = f"[{_SEV_STYLE.get(e.severity, 'dim')}]{e.severity.upper()}[/{_SEV_STYLE.get(e.severity, 'dim')}]"
        console.print(f"       [dim]└[/dim] {sev} {e.description[:75]}")
        if e.self_recovered:
            console.print(f"       [dim]└[/dim] [green]recovered:[/green] [dim]{e.recovery_method[:60]}[/dim]")


# ── Final report (Docker mode) ────────────────────────────────
def print_final_report(report: GhostReport):
    score = report.friction_score
    gs = _grade_style(score)
    console.print()
    console.print(Rule("[bold white]👻 FRICTION REPORT[/bold white]", style="bright_cyan"))
    console.print()

    # Grade + score row
    grade_panel = Panel(
        f"[{gs}]{report.grade}[/{gs}]",
        title="grade", border_style="dim", width=12, padding=(0, 2),
    )
    score_panel = Panel(
        f"[{gs}]{score}[/{gs}][dim]/100[/dim]",
        title="score", border_style="dim", width=14, padding=(0, 2),
    )
    level_panel = Panel(
        f"[{gs}]{report.friction_level}[/{gs}]",
        title="level", border_style="dim", width=22, padding=(0, 2),
    )
    console.print(Columns([grade_panel, score_panel, level_panel], padding=1))
    console.print()

    # Timing table
    tt = Table(box=box.SIMPLE_HEAVY, show_header=False, padding=(0, 2), expand=True)
    tt.add_column("metric", style="dim")
    tt.add_column("value", justify="right", style="white")
    tt.add_row("Total duration", f"{report.total_duration / 60:.1f}m")
    if report.time_to_first_build is not None:
        tt.add_row("Time to first build", f"{report.time_to_first_build / 60:.1f}m")
    if report.time_to_first_test is not None:
        tt.add_row("Time to first test", f"{report.time_to_first_test / 60:.1f}m")
    tt.add_row("Friction events", str(len(report.friction_events)))
    console.print(tt)
    console.print()

    if report.friction_events:
        _print_breakdown(report)
        _print_events(report)
        _print_cost(report)
    if report.fix_suggestions:
        _print_fixes(report)
    console.print()


def _print_breakdown(report: GhostReport):
    cats: dict[str, int] = {}
    for e in report.friction_events:
        cats[e.category] = cats.get(e.category, 0) + 1
    mx = max(cats.values()) if cats else 1

    t = Table(title="Friction Breakdown", box=box.ROUNDED, border_style="dim",
              title_style="bold white", expand=True, padding=(0, 1))
    t.add_column("Category", style="white")
    t.add_column("", ratio=1)
    t.add_column("#", justify="right", style="bold")
    for cat, cnt in sorted(cats.items(), key=lambda x: -x[1]):
        bar_w = max(1, int((cnt / mx) * 25))
        bar = f"[yellow]{'━' * bar_w}[/yellow][dim]{'╌' * (25 - bar_w)}[/dim]"
        t.add_row(cat.replace("_", " ").title(), bar, str(cnt))
    console.print(t)
    console.print()


def _print_events(report: GhostReport):
    sev_order = {"critical": 0, "high": 1, "medium": 2, "low": 3}
    evts = sorted(report.friction_events, key=lambda e: sev_order.get(e.severity, 4))

    t = Table(title="Top Friction Events", box=box.ROUNDED, border_style="dim",
              title_style="bold white", expand=True, padding=(0, 1))
    t.add_column("Sev", width=8, justify="center")
    t.add_column("Description")
    t.add_column("Fix", style="dim", max_width=35)
    for e in evts[:7]:
        sty = _SEV_STYLE.get(e.severity, "dim")
        sev = f"[{sty}]{e.severity.upper()}[/{sty}]"
        rec = " [green]↻[/green]" if e.self_recovered else ""
        t.add_row(sev, f"{e.description[:65]}{rec}", e.suggested_fix[:35] if e.suggested_fix else "")
    console.print(t)
    console.print()


def _print_cost(report: GhostReport):
    h = report.estimated_cost_hours
    if h <= 0:
        return
    cost = h * 100
    t = Table(box=box.SIMPLE_HEAVY, show_header=False, padding=(0, 2), expand=True)
    t.add_column(style="dim")
    t.add_column(justify="right", style="yellow")
    t.add_row("Estimated time wasted per dev", f"~{h}h")
    t.add_row("Cost at $100/hr", f"${cost:,.0f}")
    t.add_row("10 new devs/year", f"${cost * 10:,.0f}/yr")
    console.print(t)
    console.print()


def _print_fixes(report: GhostReport):
    t = Table(title="Suggested Doc Fixes", box=box.ROUNDED, border_style="dim",
              title_style="bold white", expand=True, padding=(0, 1))
    t.add_column("File", style="cyan", max_width=20)
    t.add_column("Current", style="red", max_width=30)
    t.add_column("→", width=2, justify="center", style="dim")
    t.add_column("Suggested", style="green", max_width=30)
    for fix in report.fix_suggestions[:5]:
        t.add_row(
            fix.get("file_to_fix", "?"),
            fix.get("current_text", "")[:30],
            "→",
            fix.get("suggested_text", "")[:30],
        )
    console.print(t)
    console.print()


# ── No-docker report (analysis only) ─────────────────────────
def print_no_docker_report(report: GhostReport):
    plan = report.plan
    console.print()
    console.print(Rule("[bold white]👻 ghost.dev - doc analysis[/bold white]", style="bright_cyan"))
    console.print()

    # Info row
    ptype = plan.detected_project_type if plan else report.scanner_project_type
    if ptype == "unknown":
        ptype = report.scanner_project_type

    info = Table(show_header=False, box=None, padding=(0, 1))
    info.add_column(style="dim", width=14)
    info.add_column(style="white")
    info.add_row("Repository", f"[cyan]{report.repo_name or report.repo_url}[/cyan]")
    info.add_row("Docs scanned", str(len(report.docs_found)))
    info.add_row("Project type", ptype)
    if plan:
        info.add_row("Steps found", str(len(plan.steps)))
    console.print(info)
    console.print()

    if not plan:
        return

    # Prerequisites / implicit reqs
    if plan.prerequisites or plan.implicit_requirements:
        req = Table(box=box.ROUNDED, border_style="dim", expand=True, padding=(0, 1),
                    title="Requirements", title_style="bold white")
        req.add_column("Type", style="dim", width=14)
        req.add_column("Items")
        if plan.prerequisites:
            req.add_row("[green]Prerequisites[/green]", ", ".join(plan.prerequisites))
        if plan.environment_variables:
            req.add_row("[yellow]Env vars[/yellow]", ", ".join(plan.environment_variables))
        if plan.implicit_requirements:
            req.add_row("[red]Implicit[/red]", ", ".join(plan.implicit_requirements))
        console.print(req)
        console.print()

    # Steps table
    st = Table(box=box.ROUNDED, border_style="dim", expand=True, padding=(0, 1),
               title="Extracted Setup Steps", title_style="bold white")
    st.add_column("#", width=3, justify="right", style="bold")
    st.add_column("Command", style="white", ratio=3)
    st.add_column("Conf", width=5, justify="center")
    st.add_column("Source", style="dim", ratio=1)
    st.add_column("Assumptions", style="dim yellow", ratio=2)

    for step in plan.steps:
        pct = int(step.confidence * 100)
        if pct >= 70:
            conf = f"[green]{pct}%[/green]"
        elif pct >= 40:
            conf = f"[yellow]{pct}%[/yellow]"
        else:
            conf = f"[red]{pct}%[/red]"
        assumes = ", ".join(step.assumptions) if step.assumptions else ""
        st.add_row(str(step.step_number), step.action, conf, step.source, assumes)

    console.print(st)

    # Docs found (truncated)
    console.print()
    MAX_DOCS = 6
    docs = report.docs_found
    shown = docs[:MAX_DOCS]
    tags = " ".join(f"[dim]{d}[/dim]" for d in shown)
    extra = f" [dim]and {len(docs) - MAX_DOCS} more[/dim]" if len(docs) > MAX_DOCS else ""
    console.print(f"  [dim]docs:[/dim] {tags}{extra}")
    console.print()
