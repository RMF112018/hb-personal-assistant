"""Phase 04 Prompt 01 hardening guards on ProcoreSyncCoordinator.

Covers:
- Default sync target excludes any project with ``status == "pending"``.
- An explicit pending key without ``allow_pending=True`` raises
  :class:`ProcorePendingProjectRejected`.
- The same key with ``allow_pending=True`` proceeds.
- The removed ``_load_projects_for_gate`` stub no longer exists; mapping
  loader failures raise :class:`ProcoreMappingUnavailable` rather than
  fabricating project IDs.
"""

from __future__ import annotations

import tempfile
from pathlib import Path
from unittest.mock import patch

import pytest

from hb_assistant.procore.errors import (
    ProcoreMappingUnavailable,
    ProcorePendingProjectRejected,
)
from hb_assistant.procore.loader import ProcoreProjectsError
from hb_assistant.procore.sync import ProcoreSyncCoordinator


def _temp_db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        return Path(tf.name)


def test_default_sync_target_excludes_pending_projects() -> None:
    coord = ProcoreSyncCoordinator(db_path=_temp_db())
    default_keys = coord._resolve_pilot_projects(None)  # noqa: SLF001
    assert default_keys, "default sync target list must not be empty"
    assert "hilltop" not in default_keys
    assert "hilltop-gardens" not in default_keys


def test_pending_project_rejected_in_plan_without_allow_flag() -> None:
    coord = ProcoreSyncCoordinator(db_path=_temp_db())
    with patch.object(coord, "auditor") as mock_auditor:
        mock_auditor.audit_endpoints_for_pilots.return_value = {"rfi": "available"}
        with pytest.raises(ProcorePendingProjectRejected) as exc:
            coord.plan(project_key="hilltop")
    assert "hilltop" in exc.value.pending_keys


def test_pending_project_accepted_with_explicit_allow_pending() -> None:
    coord = ProcoreSyncCoordinator(db_path=_temp_db())
    with patch.object(coord, "auditor") as mock_auditor:
        mock_auditor.audit_endpoints_for_pilots.return_value = {"rfi": "available"}
        plan = coord.plan(project_key="hilltop", allow_pending=True)
    # plan() returns a redacted dict at runtime; the typed return is SyncReceipt.
    assert plan["audit_prerequisite_passed"] is True  # type: ignore[index]


def test_pending_project_rejected_in_apply_without_allow_flag() -> None:
    coord = ProcoreSyncCoordinator(db_path=_temp_db())
    with patch.object(coord, "auditor") as mock_auditor:
        mock_auditor.audit_endpoints_for_pilots.return_value = {"rfi": "available"}
        with pytest.raises(ProcorePendingProjectRejected):
            coord.apply(project_key="hilltop-gardens")


def test_stub_project_loader_no_longer_exists() -> None:
    """The fake ``_load_projects_for_gate`` stub (with hard-coded ID 2525840)
    must be gone from the coordinator surface.
    """
    assert not hasattr(ProcoreSyncCoordinator, "_load_projects_for_gate")


def test_mapping_loader_failure_raises_mapping_unavailable() -> None:
    coord = ProcoreSyncCoordinator(db_path=_temp_db())
    with patch(
        "hb_assistant.procore.sync.load_procore_projects",
        side_effect=ProcoreProjectsError("seed missing for test"),
    ), pytest.raises(ProcoreMappingUnavailable):
        coord._resolve_pilot_projects(None)  # noqa: SLF001
