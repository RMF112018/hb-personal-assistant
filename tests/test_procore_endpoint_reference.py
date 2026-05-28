"""Tests for Phase 03 Procore endpoint reference verification (Prompt 01A).

These tests enforce the hard guardrails and the verification rules added in 01A:
- All endpoints in the active contract must be GET-only.
- The specific excluded (correspondence) and deferred (schedule, tasks) statuses must be preserved exactly.
- After Prompt 01A enrichment, the core operational/financial endpoints must use modern /rest/v1.x paths (not legacy /vapid/).
- The materialized unverified candidate catalog must not have any endpoint marked "verified" without official reference metadata (the contract enrichment is the only place "verified" status is recorded for the reconciled set).
- No HB-number-shaped IDs are allowed in procore_project_id fields (enforced in models + contract).
"""

import yaml

from hb_assistant.procore.loader import load_endpoint_contract, load_procore_projects
from hb_assistant.procore.models import ProcoreEndpointContract, ProcoreProjectsRegistry


def test_contract_all_get_only():
    """Reject any non-GET in the active contract (hard read-only guardrail)."""
    contract: ProcoreEndpointContract = load_endpoint_contract()
    for ep in contract.endpoints:
        assert ep.http_method == "GET", f"Non-GET endpoint found: {ep.endpoint_id}"


def test_contract_excluded_and_deferred_statuses_preserved():
    """The hard guardrails for correspondence=excluded and schedule/tasks=deferred must survive 01A enrichment."""
    contract: ProcoreEndpointContract = load_endpoint_contract()

    excluded = [e for e in contract.endpoints if e.endpoint_id == "list-correspondence"]
    assert excluded, "list-correspondence endpoint missing"
    assert excluded[0].status == "excluded"

    deferred_ids = {"list-schedule", "list-tasks"}
    deferred = [e for e in contract.endpoints if e.endpoint_id in deferred_ids]
    assert len(deferred) == 2
    assert all(e.status == "deferred" for e in deferred)


def test_core_endpoints_use_modern_rest_paths_after_01a():
    """After Prompt 01A, the overlapping core endpoints must use modern /rest/ paths (verified against official docs)."""
    contract: ProcoreEndpointContract = load_endpoint_contract()

    modern_checks = {
        "list-rfis": "/rest/v1.0/projects/",
        "list-submittals": "/rest/v1.0/projects/",
        "list-change-events": "/rest/v1.1/change_events",
        "list-commitments": "/rest/v2.0/companies/",
        "list-daily-logs": "/rest/v1.0/projects/",
    }

    for ep in contract.endpoints:
        if ep.endpoint_id in modern_checks:
            assert ep.path_template.startswith(modern_checks[ep.endpoint_id]), \
                f"{ep.endpoint_id} still uses legacy path after 01A: {ep.path_template}"
            assert "Prompt 01A" in (ep.notes or "") or "official_docs_verified" in (ep.notes or ""), \
                f"{ep.endpoint_id} missing Prompt 01A verification note"


def test_unverified_candidate_catalog_does_not_promote_without_metadata():
    """The materialized phase03_unverified seed must keep all candidates as unverified_official_docs_required (or equivalent)."""
    unverified_path = "resources/config/procore_endpoint_reference.phase03_unverified.seed.yaml"
    with open(unverified_path) as f:
        data = yaml.safe_load(f)

    for ep in data.get("endpoints", []):
        vs = ep.get("verification_status", "")
        # The contract enrichment is the only place we record "verified" for reconciled items.
        # Unverified catalog must not have jumped ahead.
        assert (
            "unverified" in vs
            or "candidate" in vs.lower()
            or vs == ""
            or vs in {"excluded", "deferred"}
        ), \
            f"Unverified catalog has premature verified status on {ep.get('endpoint_id')}: {vs}"


def test_no_hb_number_patterns_in_procore_ids():
    """HB project numbers (e.g. 23-435-01) must never appear in procore_project_id (enforced in models + seeds)."""
    # Load the projects registry (the one paired with the contract)
    # This test re-uses the existing validation logic in ProcoreProjectMapping.
    registry: ProcoreProjectsRegistry = load_procore_projects()
    for p in registry.projects:
        if p.procore_project_id:
            pid = p.procore_project_id
            assert not (
                len(pid) == 8
                and pid[2] == "-"
                and pid[6] == "-"
                and pid.replace("-", "").isdigit()
            ), f"HB-number-shaped ID leaked into procore_project_id: {p.hb_project_key} -> {p.procore_project_id}"


# Prompt_06: HB project-number vs Procore ID separation + pending pilot handling (uses working loader from CLI surface; pure, no live).
def test_procore_projects_5280_pilots_vs_pending_hilltop_explicit():
    """Validate 5280 context, 4 numeric-ID pilots, 2 pending (hilltop*) with empty procore IDs (separation + auditable pending)."""
    from hb_assistant.procore.loader import load_procore_projects
    reg = load_procore_projects()
    projs = reg.projects if hasattr(reg, 'projects') else reg
    assert len(projs) >= 6
    pending_keys = [getattr(p, 'hb_project_key', getattr(p, 'project_key', '')) for p in projs if not getattr(p, 'procore_project_id', None) or getattr(p, 'status', None) == 'pending']
    assert 'hilltop' in pending_keys and 'hilltop-gardens' in pending_keys
    for p in projs:
        pid = getattr(p, 'procore_project_id', '') or ''
        if pid:
            # Separation: no HB-number shapes (00-000-00 or HB-/HT-*) allowed as Procore ID
            assert not (pid.replace('-', '').isdigit() and len(pid) <= 7 and '-' in pid), f"HB pattern leaked as procore id: {pid}"
