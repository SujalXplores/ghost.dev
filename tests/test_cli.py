"""Tests for ghost.dev CLI."""

import pytest
from click.testing import CliRunner
from ghost.cli import (
    main, _extract_repo_name, _is_test_or_lint_step,
    _filter_by_depth, _build_env_dict, _validate_repo_arg,
)
from ghost.models.step import SetupStep, PlanResult


class TestExtractRepoName:
    def test_github_https(self):
        assert _extract_repo_name("https://github.com/user/repo") == "user/repo"

    def test_github_https_with_git(self):
        assert _extract_repo_name("https://github.com/user/repo.git") == "user/repo"

    def test_github_ssh(self):
        assert _extract_repo_name("git@github.com:user/repo") == "user/repo"

    def test_github_ssh_with_git(self):
        assert _extract_repo_name("git@github.com:user/repo.git") == "user/repo"

    def test_gitlab_https(self):
        assert _extract_repo_name("https://gitlab.com/user/repo") == "user/repo"

    def test_local_path(self, tmp_path):
        name = _extract_repo_name(str(tmp_path))
        assert name == tmp_path.name

    def test_trailing_slash(self):
        assert _extract_repo_name("https://github.com/user/repo/") == "user/repo"

    def test_url_with_query_params(self):
        name = _extract_repo_name("https://github.com/user/repo?tab=readme")
        # Should strip query params
        assert "?" not in name

    def test_url_with_fragment(self):
        name = _extract_repo_name("https://github.com/user/repo#setup")
        assert "#" not in name


class TestIsTestOrLintStep:
    def test_npm_test(self):
        assert _is_test_or_lint_step("npm test") is True

    def test_pytest(self):
        assert _is_test_or_lint_step("pytest") is True

    def test_jest(self):
        assert _is_test_or_lint_step("jest --coverage") is True

    def test_npm_run_lint(self):
        assert _is_test_or_lint_step("npm run lint") is True

    def test_eslint(self):
        assert _is_test_or_lint_step("eslint src/") is True

    def test_ruff_check(self):
        assert _is_test_or_lint_step("ruff check .") is True

    def test_npm_install_is_not_test(self):
        assert _is_test_or_lint_step("npm install") is False

    def test_make_build_is_not_test(self):
        assert _is_test_or_lint_step("make build") is False

    def test_bun_test(self):
        assert _is_test_or_lint_step("bun test") is True

    def test_deno_test(self):
        assert _is_test_or_lint_step("deno test") is True

    def test_cargo_test(self):
        assert _is_test_or_lint_step("cargo test") is True

    def test_go_test(self):
        assert _is_test_or_lint_step("go test ./...") is True

    def test_empty_string(self):
        assert _is_test_or_lint_step("") is False


class TestFilterByDepth:
    def test_full_returns_all(self, sample_plan):
        result = _filter_by_depth(sample_plan, "full")
        assert len(result.steps) == len(sample_plan.steps)

    def test_quick_filters_tests(self):
        steps = [
            SetupStep(step_number=1, action="npm install", source="x", confidence=0.9),
            SetupStep(step_number=2, action="npm test", source="x", confidence=0.9),
            SetupStep(step_number=3, action="npm start", source="x", confidence=0.9),
        ]
        plan = PlanResult(steps=steps)
        result = _filter_by_depth(plan, "quick")
        actions = [s.action for s in result.steps]
        assert "npm test" not in actions
        assert "npm install" in actions
        assert "npm start" in actions

    def test_quick_renumbers_steps(self):
        steps = [
            SetupStep(step_number=1, action="npm install", source="x", confidence=0.9),
            SetupStep(step_number=2, action="npm test", source="x", confidence=0.9),
            SetupStep(step_number=3, action="npm start", source="x", confidence=0.9),
        ]
        plan = PlanResult(steps=steps)
        result = _filter_by_depth(plan, "quick")
        assert result.steps[0].step_number == 1
        assert result.steps[1].step_number == 2


class TestBuildEnvDict:
    def test_basic(self):
        result = _build_env_dict(["PORT=3000", "DB_HOST=localhost"])
        assert result == {"PORT": "ghost_placeholder", "DB_HOST": "ghost_placeholder"}

    def test_empty(self):
        assert _build_env_dict([]) == {}

    def test_name_only(self):
        result = _build_env_dict(["API_KEY"])
        assert result == {"API_KEY": "ghost_placeholder"}


class TestCLICommands:
    def test_help(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--help"])
        assert result.exit_code == 0

    def test_version(self):
        runner = CliRunner()
        result = runner.invoke(main, ["--version"])
        assert result.exit_code == 0
        assert "0.1.0" in result.output

    def test_run_no_args(self):
        runner = CliRunner()
        result = runner.invoke(main, ["run"])
        assert result.exit_code != 0  # Missing required argument

    def test_clean_command_exists(self):
        runner = CliRunner()
        result = runner.invoke(main, ["clean"])
        assert result.exit_code == 0
