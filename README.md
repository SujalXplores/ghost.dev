<p align="center">
  <img src="https://em-content.zobj.net/source/apple/391/ghost_1f47b.png" width="80" />
</p>

<h1 align="center">ghost.dev</h1>

<p align="center">
  <strong>The Phantom Developer</strong><br>
  <em>Every repo claims easy setup. ghost.dev proves them wrong — or right.</em>
</p>

<p align="center">
  <img src="https://img.shields.io/badge/python-3.11+-blue?style=flat-square" />
  <img src="https://img.shields.io/badge/tests-141_passed-brightgreen?style=flat-square" />
  <img src="https://img.shields.io/badge/license-MIT-gray?style=flat-square" />
  <img src="https://img.shields.io/badge/hackathon-DX--RAY_2026-orange?style=flat-square" />
</p>

---

An AI agent that simulates a **brand-new developer** onboarding onto any GitHub repository from absolute zero. It reads the docs, follows setup instructions step-by-step inside a fresh Docker container, and logs every failure, ambiguity, and undocumented assumption as a **friction event**.

The ghost doesn't know your framework. It doesn't know your conventions. If the README doesn't say "install Node," it won't install Node. It's the most literal, naive developer possible — and that's the point.

```
ghost run https://github.com/fastapi/fastapi --no-docker
```

```
  ✓ fastapi/fastapi ready
  ✓ 23 docs found (python)
  ✓ 4 steps (depth=quick)

──────────── 👻 ghost.dev — doc analysis ────────────

 Repository      fastapi/fastapi
 Docs scanned    23
 Project type    python
 Steps found     4
```

## How It Works

```
Scanner ──▶ Planner ──▶ Executor ──▶ Observer ──▶ Reporter
reads docs   AI gets    runs in     classifies    terminal +
& configs    steps      Docker      friction      HTML report
                │              │
                ▼              ▼
           Recoverer      Fix Gen
           AI fixes       suggests
           failures       doc edits
```

Six-stage pipeline. Each stage does one thing well:

1. **Scanner** — Finds README, CONTRIBUTING, Makefile, package.json, CI workflows, env templates, version files. 23+ file patterns.
2. **Planner** — AI extracts ordered setup steps from docs. Nothing else. Confidence scores, assumptions, prerequisites — all tracked.
3. **Executor** — Runs each step in a bare `ubuntu:24.04` Docker container. Sandboxed. Resource-limited. Timed.
4. **Observer** — Classifies each result: success, failure, ambiguity, partial. AI-powered with heuristic fallback.
5. **Recoverer** — On failure, AI diagnoses the error and attempts self-recovery. Like a real dev reading stack traces.
6. **Reporter** — Friction score, letter grade, cost estimate, timeline, fix suggestions. Terminal + self-contained HTML.

## Quick Start

Zero-install — run it directly (like `npx`):

```bash
# Using uvx (recommended — fastest, no install)
uvx ghost-dev run https://github.com/user/repo

# Using pipx
pipx run ghost-dev run https://github.com/user/repo
```

Or install it permanently:

```bash
pip install ghost-dev
ghost run https://github.com/user/repo
```

First run prompts for an API key:

```
👻 No API key found. Let's set one up.

  › 1. Anthropic  (recommended)
    2. OpenRouter  (any model — Claude, GPT, Gemini, Llama)
    3. OpenAI      (GPT models)
```

Or run `ghost setup` anytime to add or change keys.

## Usage

```
ghost run <repo_url_or_local_path> [options]
```

| Flag | Description |
|------|-------------|
| `--depth [quick\|full]` | `quick` = build only, `full` = build + test + lint |
| `--timeout <minutes>` | Max time per step (default: 5) |
| `--model <name>` | AI model (default: claude-sonnet) |
| `--output <path>` | HTML report path |
| `--no-docker` | Doc analysis only — no execution |
| `--json-output` | Machine-readable JSON to stdout |
| `--fail-threshold <n>` | Exit code 2 if friction score > n (CI mode) |
| `--no-cache` | Bypass plan cache |
| `--quiet` | Minimal output |
| `--debug` | Debug logging |
| `--verbose` | Show container stdout/stderr |

```bash
# Analyze any repo's docs without Docker
ghost run ./my-project --no-docker

# Full pipeline in Docker
ghost run https://github.com/user/repo --depth full

# CI gate — fail if friction is too high
ghost run . --json-output --fail-threshold 40

# Use any model via OpenRouter
ghost run <url> --model google/gemini-3.1-pro
ghost run <url> --model deepseek/deepseek-v3.2
ghost run <url> --model meta-llama/llama-4-maverick
```

## Other Commands

```bash
ghost setup          # Configure API keys interactively
ghost clean          # Remove cached plans + orphaned containers
ghost --version      # Print version
```

## Output

ghost.dev produces a **friction report** with:

- **Friction Score** (0–100) and letter grade (A+ to F)
- **Execution timeline** — every step with pass/fail, duration, exit code
- **Friction events** — severity, root cause, category, suggested fix
- **Self-recovery log** — what the ghost tried, what worked
- **Cost estimate** — developer hours wasted × $100/hr × team size
- **Fix suggestions** — concrete doc edits with before/after diffs
- **HTML report** — self-contained, dark theme, print-ready, accessible

A sample report from running against FastAPI is included in [`demo/fastapi-report.html`](demo/fastapi-report.html).

## The Ghost Philosophy

The agent behaves like a **literal, naive first-day intern**:

- It ONLY knows what the docs tell it
- It does NOT use prior knowledge about frameworks
- If the README doesn't say "install Node," it won't install Node
- If something fails, it attempts self-recovery (like a real dev Googling)
- Every assumption the docs make is logged as implicit knowledge

## Architecture

```
ghost/
├── cli.py              # Click CLI with Rich-styled help
├── config.py           # Config, API key management, cache
├── core/
│   ├── _ai.py          # Multi-provider AI (Anthropic → OpenRouter → OpenAI)
│   ├── _utils.py       # Shared JSON parsing, command safety validation
│   ├── scanner.py      # Repo doc scanner (23+ file patterns)
│   ├── planner.py      # AI step extraction with SQLite caching
│   ├── executor.py     # Docker execution engine with env injection
│   ├── observer.py     # Result classification (AI + heuristic fallback)
│   └── recoverer.py    # AI-powered self-recovery with safety checks
├── docker/
│   ├── container.py    # Container lifecycle, exec, resource limits
│   └── Dockerfile.ghost
├── models/
│   ├── step.py         # SetupStep, PlanResult (Pydantic)
│   ├── friction.py     # FrictionEvent model
│   └── report.py       # GhostReport with scoring, grading, cost estimation
├── reporter/
│   ├── terminal.py     # Rich terminal UI — panels, tables, progress
│   ├── html.py         # Jinja2 HTML report generator
│   └── templates/
│       └── report.html # Self-contained dark-theme HTML template
└── fixgen/
    └── suggestions.py  # AI-generated documentation fix suggestions
```

## Engineering Highlights

**Multi-provider AI with automatic fallback**
Anthropic → OpenRouter → OpenAI. If one fails, the next picks up. OpenRouter gives access to any model — Claude, GPT, Gemini, Llama, DeepSeek — through a single key.

**Security-first execution**
- Docker containers are sandboxed with 2GB RAM / 2 CPU limits
- AI-generated recovery commands are validated against a dangerous-pattern blocklist before execution
- No `curl | bash`, no `rm -rf /`, no fork bombs — even inside the container
- `shlex.quote` for all shell arguments

**Intelligent caching**
Plans are cached in SQLite with a 24-hour TTL. Same repo + same model = instant results on re-run. `--no-cache` to bypass.

**Graceful degradation**
No Docker? `--no-docker` gives full doc analysis. No API key? Interactive setup on first run. AI returns garbage JSON? Heuristic fallback classifies results without AI.

**CI/CD ready**
`--json-output` for machine-readable reports. `--fail-threshold 40` exits with code 2 if friction is too high. Gate your PRs on documentation quality.

**141 tests, zero warnings**
Unit tests for every model, every heuristic, every parser. Integration tests for the CLI. Mocked AI calls for the execution pipeline. All passing.

## Tech Stack

`click` · `rich` · `docker` · `anthropic` · `openai` · `gitpython` · `jinja2` · `pydantic` · `python-dotenv`

Dev: `pytest` · `pytest-cov` · `ruff`

## Requirements

- Python 3.11+
- Docker (or `--no-docker` for analysis-only)
- API key: Anthropic, OpenRouter, or OpenAI (prompted on first run)

## License

MIT

---

<p align="center">
  <em>Built for DX-RAY 2026</em> 👻
</p>
