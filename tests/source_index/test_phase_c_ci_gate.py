"""PC-WI-05 — Phase C CI gate + runbook guard (PC-AC-046, PC-AC-047).

Guards the Phase C CI wiring so it stays deterministic and does not silently drift:

- the Phase C gate script exists, is valid bash, and runs the Phase C suite (`tests/source_index/`);
- it selects a deterministic interpreter (never a bare ambient `pytest`) — the interpreter-trap guard;
- it is SEPARATE from the Phase A/B gate (`scripts/ci_source_index_gate.sh`), which stays green (PC-AC-046);
- the Phase C suite is CI-safe (no integration/live/manual markers) — PC-AC-047 determinism;
- the deferred `sqlite_backup` mypy-strict override landed in `pyproject.toml`;
- the migration/rollback runbook exists and states the restore-based rollback + no-downgrade contract.
"""

from __future__ import annotations

import subprocess
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[2]
_PHASE_C_GATE = _REPO_ROOT / "scripts/ci_source_index_phase_c_gate.sh"
_AB_GATE = _REPO_ROOT / "scripts/ci_source_index_gate.sh"
_RUNBOOK = _REPO_ROOT / "docs/runbooks/source-index-phase-c-migration-rollback.md"
_PYPROJECT = _REPO_ROOT / "pyproject.toml"
_SUITE_DIR = _REPO_ROOT / "tests/source_index"


def test_phase_c_gate_exists_and_is_valid_bash() -> None:  # PC-AC-047
    assert _PHASE_C_GATE.is_file()
    proc = subprocess.run(["bash", "-n", str(_PHASE_C_GATE)], capture_output=True, text=True)
    assert proc.returncode == 0, proc.stderr


def test_phase_c_gate_runs_the_phase_c_suite() -> None:  # PC-AC-047
    body = _PHASE_C_GATE.read_text(encoding="utf-8")
    assert "pytest" in body and "tests/source_index/" in body
    assert "ruff check" in body and "mypy --strict" in body


def test_phase_c_gate_uses_a_deterministic_interpreter() -> None:  # PC-AC-047 (interpreter-trap guard)
    body = _PHASE_C_GATE.read_text(encoding="utf-8")
    # It must resolve a pinned interpreter (venv / $PYTHON) and invoke tools via `-m`, never a bare
    # ambient `pytest`/`ruff`/`mypy` that could pick a system interpreter with the wrong dependencies.
    assert ".venv/bin/python" in body
    assert '"$PYTHON_BIN" -m pytest' in body
    assert '"$PYTHON_BIN" -m ruff' in body
    assert '"$PYTHON_BIN" -m mypy' in body


def test_phase_c_gate_is_separate_from_phase_ab_gate() -> None:  # PC-AC-046
    # The Phase A/B gate remains present and is not *executed* by the Phase C gate (kept green,
    # independent). A comment may name it; no runnable line may invoke it.
    assert _AB_GATE.is_file()
    for line in _PHASE_C_GATE.read_text(encoding="utf-8").splitlines():
        code = line.split("#", 1)[0]
        assert "ci_source_index_gate.sh" not in code, f"Phase C gate invokes the A/B gate: {line}"


def test_phase_c_suite_is_ci_safe() -> None:  # PC-AC-047
    # No opt-in external markers anywhere in the Phase C suite — it runs deterministically in CI.
    # (This guard file itself is excluded: it names the markers as data to scan for.)
    this_file = Path(__file__).name
    for path in sorted(_SUITE_DIR.glob("test_*.py")):
        if path.name == this_file:
            continue
        text = path.read_text(encoding="utf-8")
        for marker in ("@pytest.mark.integration", "@pytest.mark.live", "@pytest.mark.manual"):
            assert marker not in text, f"{path.name} carries {marker}"


def test_pyproject_strict_override_covers_phase_c_source() -> None:  # deferred PC-WI-02 override landed
    body = _PYPROJECT.read_text(encoding="utf-8")
    assert '"hb_assistant.store.source_index_migration_assurance"' in body
    assert '"hb_assistant.store.sqlite_backup"' in body


def test_runbook_states_restore_based_rollback_and_no_downgrade() -> None:  # PC-AC-042 continuity
    assert _RUNBOOK.is_file()
    text = _RUNBOOK.read_text(encoding="utf-8").lower()
    assert "restore + prior executable" in text
    assert "no in-place schema downgrade" in text or "schema downgrade is unsupported" in text
