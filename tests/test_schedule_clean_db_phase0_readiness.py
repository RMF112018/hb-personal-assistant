"""Phase 0 readiness wrapper tests."""

from __future__ import annotations

from scripts.dev_schedule_clean_db_phase0_readiness import run_readiness_checks


def test_readiness_checks_include_core_scripts() -> None:
    report = run_readiness_checks()
    ids = {c["id"] for c in report["checks"]}
    assert "gitignore_local_sensitive" in ids
    assert "loaded_state_helper" in ids
    assert "schema_audit_fixture" in ids
