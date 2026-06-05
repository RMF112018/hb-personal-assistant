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
from hb_assistant.procore.models import ProcoreProjectsRegistry
from hb_assistant.procore.sync import ProcoreSyncCoordinator


# Synthetic registry used by the tests that must exercise pending-handling
# semantics. The live seed no longer carries any pending row (hilltop /
# hilltop-gardens were retired into alton-hilltop-pbg on 2026-05-29), so
# the pending project_keys are injected via a patch on the loader.
def _registry_with_pending() -> ProcoreProjectsRegistry:
    return ProcoreProjectsRegistry.model_validate(
        {
            "company_id": "5280",
            "projects": [
                {
                    "hb_project_key": "tropical",
                    "procore_project_id": "2525840",
                    "procore_project_name": "Tropical - S L",
                    "status": "pilot",
                },
                {
                    "hb_project_key": "hilltop",
                    "procore_project_id": "",
                    "procore_project_name": "",
                    "status": "pending",
                },
                {
                    "hb_project_key": "hilltop-gardens",
                    "procore_project_id": "",
                    "procore_project_name": "",
                    "status": "pending",
                },
            ],
        }
    )


def _temp_db() -> Path:
    with tempfile.NamedTemporaryFile(suffix=".sqlite", delete=False) as tf:
        return Path(tf.name)


def test_default_sync_target_excludes_pending_projects() -> None:
    coord = ProcoreSyncCoordinator(db_path=_temp_db())
    with patch(
        "hb_assistant.procore.sync.load_procore_projects",
        return_value=_registry_with_pending(),
    ):
        default_keys = coord._resolve_pilot_projects(None)  # noqa: SLF001
    assert default_keys, "default sync target list must not be empty"
    assert "hilltop" not in default_keys
    assert "hilltop-gardens" not in default_keys
    # The pilot from the synthetic registry must be present.
    assert "tropical" in default_keys


def test_pending_project_rejected_in_plan_without_allow_flag() -> None:
    coord = ProcoreSyncCoordinator(db_path=_temp_db())
    with (
        patch(
            "hb_assistant.procore.sync.load_procore_projects",
            return_value=_registry_with_pending(),
        ),
        patch.object(coord, "auditor") as mock_auditor,
    ):
        mock_auditor.audit_endpoints_for_pilots.return_value = {"rfi": "available"}
        with pytest.raises(ProcorePendingProjectRejected) as exc:
            coord.plan(project_key="hilltop")
    assert "hilltop" in exc.value.pending_keys


def test_pending_project_accepted_with_explicit_allow_pending() -> None:
    coord = ProcoreSyncCoordinator(db_path=_temp_db())
    with (
        patch(
            "hb_assistant.procore.sync.load_procore_projects",
            return_value=_registry_with_pending(),
        ),
        patch.object(coord, "auditor") as mock_auditor,
    ):
        mock_auditor.audit_endpoints_for_pilots.return_value = {"rfi": "available"}
        plan = coord.plan(project_key="hilltop", allow_pending=True)
    # plan() returns a redacted dict at runtime; the typed return is SyncReceipt.
    assert plan["audit_prerequisite_passed"] is True  # type: ignore[index]


def test_pending_project_rejected_in_apply_without_allow_flag() -> None:
    coord = ProcoreSyncCoordinator(db_path=_temp_db())
    with (
        patch(
            "hb_assistant.procore.sync.load_procore_projects",
            return_value=_registry_with_pending(),
        ),
        patch.object(coord, "auditor") as mock_auditor,
    ):
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
    with (
        patch(
            "hb_assistant.procore.sync.load_procore_projects",
            side_effect=ProcoreProjectsError("seed missing for test"),
        ),
        pytest.raises(ProcoreMappingUnavailable),
    ):
        coord._resolve_pilot_projects(None)  # noqa: SLF001
