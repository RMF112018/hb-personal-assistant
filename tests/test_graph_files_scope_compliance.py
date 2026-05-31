"""Phase 07C Prompt 03 — `graph files scope-compliance` CLI command."""

from __future__ import annotations

import json

from typer.testing import CliRunner

from hb_assistant.cli.graph import app

runner = CliRunner()


def test_scope_compliance_reports_and_blocks_root_wide_onedrive() -> None:
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

    # The live registry's root-wide OneDrive sources are blocked fail-closed; the
    # SharePoint approved-project-drive folders are compliant.
    onedrive = [s for s in payload["sources"] if s["system"] == "onedrive"]
    sharepoint = [s for s in payload["sources"] if s["system"] == "sharepoint"]
    assert onedrive, "expected OneDrive sources in the registry"
    assert sharepoint, "expected SharePoint sources in the registry"

    blocked = [s for s in onedrive if s["compliance_status"] == "non_compliant"]
    assert blocked, "expected at least one blocked root-wide OneDrive source"
    for s in blocked:
        assert s["action"] == "block_document_card_promotion"
        assert s["source_key"] in payload["blocked_sources"]

    assert any(
        s["kind"] == "sharepoint_project_drive_folder" and s["compliance_status"] == "compliant"
        for s in sharepoint
    )
    # all_compliant reflects the presence of blocked OneDrive roots.
    assert payload["all_compliant"] is (len(payload["blocked_sources"]) == 0)
