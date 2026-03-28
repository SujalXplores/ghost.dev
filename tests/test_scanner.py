"""Tests for ghost.dev scanner."""

import pytest
from ghost.core.scanner import scan_repo, _detect_project_type


class TestDetectProjectType:
    def test_node(self):
        assert _detect_project_type({"package.json": "{}"}) == "node"

    def test_python(self):
        assert _detect_project_type({"pyproject.toml": ""}) == "python"

    def test_rust(self):
        assert _detect_project_type({"Cargo.toml": ""}) == "rust"

    def test_go(self):
        assert _detect_project_type({"go.mod": ""}) == "go"

    def test_ruby(self):
        assert _detect_project_type({"Gemfile": ""}) == "ruby"

    def test_java_maven(self):
        assert _detect_project_type({"pom.xml": ""}) == "java"

    def test_java_gradle(self):
        assert _detect_project_type({"build.gradle": ""}) == "java"

    def test_unknown(self):
        assert _detect_project_type({}) == "unknown"
        assert _detect_project_type({"random.txt": ""}) == "unknown"


class TestScanRepo:
    def test_scan_finds_readme(self, tmp_repo):
        result = scan_repo(str(tmp_repo))
        assert "README.md" in result.files_found
        assert "package.json" in result.files_found
        assert result.detected_project_type == "node"

    def test_scan_empty_dir(self, tmp_path):
        result = scan_repo(str(tmp_path))
        assert len(result.files_found) == 0
        assert result.detected_project_type == "unknown"

    def test_scan_caps_file_size(self, tmp_path):
        readme = tmp_path / "README.md"
        readme.write_text("x" * 60000)
        result = scan_repo(str(tmp_path))
        assert len(result.files_found["README.md"]) == 50000

    def test_scan_detects_dockerfile(self, tmp_path):
        (tmp_path / "Dockerfile").write_text("FROM ubuntu")
        (tmp_path / "README.md").write_text("# test")
        result = scan_repo(str(tmp_path))
        assert result.has_dockerfile is True

    def test_scan_detects_docker_compose(self, tmp_path):
        (tmp_path / "docker-compose.yml").write_text("version: '3'")
        (tmp_path / "README.md").write_text("# test")
        result = scan_repo(str(tmp_path))
        assert result.has_docker_compose is True

    def test_scan_finds_quickstart(self, tmp_path):
        (tmp_path / "QUICKSTART.md").write_text("# Quick Start")
        result = scan_repo(str(tmp_path))
        assert "QUICKSTART.md" in result.files_found

    def test_scan_finds_env_example(self, tmp_path):
        (tmp_path / ".env.example").write_text("API_KEY=xxx")
        result = scan_repo(str(tmp_path))
        assert ".env.example" in result.files_found
