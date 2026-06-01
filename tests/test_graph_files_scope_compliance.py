"""Phase 07C Prompt 03 — `graph files scope-compliance` CLI command."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from hb_assistant.cli.graph import app

runner = CliRunner()


def test_scope_compliance_reports_explicit_all_folders_onedrive() -> None:
    """Phase 07D — the live registry's OneDrive roots carry an explicit operator
    all-folders opt-in, so they are compliant (not implicit root-wide); SharePoint
    approved project-drive folders remain compliant."""
    result = runner.invoke(app, ["files", "scope-compliance", "--json"])
    assert result.exit_code == 0, result.output
    payload = json.loads(result.output)

    assert payload["command"] == "graph files scope-compliance"
    assert payload["ok"] is True
    assert payload["policy_version"] == "phase07c-document-source-policy-v1"

    # Read-only / no-writeback posture is documented and the command takes no token.
    g = payload["guardrails"]
    assert g["external_systems"] == "read_only"
    assert g["writeback"] == "none"
    assert g["graph_calls"] == "none"
    assert g["token_acquisition"] == "none"
    assert g["microsoft_365_writeback_enabled"] is False
    # Implicit root-wide is still forbidden; only the explicit opt-in is allowed.
    assert g["onedrive_root_wide_allowed"] is False
    assert g["onedrive_explicit_all_folders_allowed"] is True

    onedrive = [s for s in payload["sources"] if s["system"] == "onedrive"]
    sharepoint = [s for s in payload["sources"] if s["system"] == "sharepoint"]
    assert onedrive, "expected OneDrive sources in the registry"
    assert sharepoint, "expected SharePoint sources in the registry"

    # Every live OneDrive root is compliant via the explicit all-folders allowlist.
    assert all(s["compliance_status"] == "compliant" for s in onedrive)
    assert all(s["scope_type"] == "all_folders_explicit" for s in onedrive)
    assert payload["blocked_sources"] == []
    assert payload["all_compliant"] is True

    # The explicit-vs-implicit distinction is surfaced and shows no implicit blocks.
    breakdown = payload["onedrive_scope_breakdown"]
    assert breakdown["all_folders_explicit_compliant"] == len(onedrive)
    assert breakdown["implicit_root_blocked"] == 0

    assert any(
        s["kind"] == "sharepoint_project_drive_folder" and s["compliance_status"] == "compliant"
        for s in sharepoint
    )
