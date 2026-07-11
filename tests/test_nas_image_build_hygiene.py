"""NAS image build hygiene — RT-01 clean context + .dockerignore guards."""

from __future__ import annotations

import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parents[1]
DOCKERIGNORE = REPO_ROOT / ".dockerignore"
BUILD_SCRIPT = REPO_ROOT / "scripts" / "build-nas-image.sh"


def _active_dockerignore_lines() -> list[str]:
    lines: list[str] = []
    for raw in DOCKERIGNORE.read_text(encoding="utf-8").splitlines():
        line = raw.split("#", 1)[0].strip()
        if line:
            lines.append(line)
    return lines


def test_dockerignore_blocks_agent_and_audit_artifacts() -> None:
    lines = _active_dockerignore_lines()
    for needed in (
        ".claude",
        ".code-graph",
        "local_audit_outputs",
        "frontend",
        "docs/planning",
        "subrepos",
    ):
        assert needed in lines, f".dockerignore missing hygiene exclusion: {needed}"


def test_forbidden_paths_not_in_git_archive() -> None:
    proc = subprocess.run(
        ["git", "archive", "--format=tar", "HEAD"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
    )
    listing = subprocess.run(
        ["tar", "-tf", "-"],
        input=proc.stdout,
        check=True,
        capture_output=True,
        text=False,
    )
    names = listing.stdout.decode("utf-8", errors="replace")
    assert ".claude/" not in names
    assert "local_audit_outputs/" not in names


def test_build_script_exists_and_is_executable() -> None:
    assert BUILD_SCRIPT.is_file()
    assert BUILD_SCRIPT.stat().st_mode & 0o111


def test_build_script_requires_clean_tree() -> None:
    """Script must refuse dirty index (integration: only run when tree is clean)."""
    status = subprocess.run(
        ["git", "status", "--porcelain"],
        cwd=REPO_ROOT,
        check=True,
        capture_output=True,
        text=True,
    )
    if status.stdout.strip():
        pytest.skip("working tree dirty — clean-tree refusal test skipped")
    proc = subprocess.run(
        [str(BUILD_SCRIPT), "--check-only"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert proc.returncode == 0, proc.stderr or proc.stdout