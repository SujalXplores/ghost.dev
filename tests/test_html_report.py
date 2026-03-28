"""Tests for ghost.dev HTML report generation."""

import pytest
from pathlib import Path
from ghost.reporter.html import generate_html_report


class TestHtmlReport:
    def test_generates_file(self, sample_report, tmp_path):
        output = str(tmp_path / "report.html")
        generate_html_report(sample_report, output)
        assert Path(output).exists()
        content = Path(output).read_text(encoding="utf-8")
        assert "ghost.dev" in content
        assert "test/repo" in content

    def test_contains_grade(self, sample_report, tmp_path):
        output = str(tmp_path / "report.html")
        generate_html_report(sample_report, output)
        content = Path(output).read_text(encoding="utf-8")
        assert sample_report.grade in content

    def test_contains_friction_events(self, sample_report, tmp_path):
        output = str(tmp_path / "report.html")
        generate_html_report(sample_report, output)
        content = Path(output).read_text(encoding="utf-8")
        assert "Node.js not installed" in content

    def test_has_accessibility_features(self, sample_report, tmp_path):
        output = str(tmp_path / "report.html")
        generate_html_report(sample_report, output)
        content = Path(output).read_text(encoding="utf-8")
        assert 'role="main"' in content
        assert 'skip-link' in content.lower() or 'Skip to content' in content
        assert 'lang="en"' in content

    def test_has_print_stylesheet(self, sample_report, tmp_path):
        output = str(tmp_path / "report.html")
        generate_html_report(sample_report, output)
        content = Path(output).read_text(encoding="utf-8")
        assert "@media print" in content

    def test_has_favicon(self, sample_report, tmp_path):
        output = str(tmp_path / "report.html")
        generate_html_report(sample_report, output)
        content = Path(output).read_text(encoding="utf-8")
        assert 'rel="icon"' in content

    def test_empty_report(self, tmp_path):
        from ghost.models.report import GhostReport
        report = GhostReport(repo_url="https://example.com", repo_name="example")
        output = str(tmp_path / "report.html")
        generate_html_report(report, output)
        assert Path(output).exists()
