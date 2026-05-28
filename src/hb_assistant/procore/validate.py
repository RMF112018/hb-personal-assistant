"""Procore operator validation — read-only stack readiness check (Prompt 11).

Pure, local, GET-free. Surfaces a single structured envelope answering
"is the Procore stack on this machine wired correctly and safe to run?"
by cross-checking the seed configs, mapping, redaction module, Obsidian
templates, vault writer posture, schema migrator state, and auth
credential presence. Every per-check failure is caught locally and
surfaced via `redact_body(..., for_error=True)` so raw exception strings
never reach the envelope.

Hard guardrails honored here:
- No live Procore HTTP call. No network.
- No vault, repo, or SQLite write.
- No token / secret / response-body content in the envelope.
- Auth status is `check_auth_status()` (env-key presence only), never
  the values themselves.
- `strict=True` only tightens pass criteria; it never enables I/O.

CLI wrapper lives at :func:`hb_assistant.cli.procore.validate_cmd`.
"""

from __future__ import annotations

from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

from hb_assistant.procore.auditor import EndpointAuditor
from hb_assistant.procore.auth import check_auth_status
from hb_assistant.procore.config import load_procore_app_profile
from hb_assistant.procore.loader import (
    load_endpoint_contract,
    load_procore_projects,
)
from hb_assistant.procore.obsidian import (
    PROCORE_TEMPLATE_NAMES,
    ProcoreObsidianRenderer,
    reset_procore_obsidian_caches,
)
from hb_assistant.procore.redaction import (
    redact_body,
    redact_headers,
    redact_request,
    redact_response,
)
from hb_assistant.store.connection import get_connection
from hb_assistant.store.migrator import SQLiteMigrator

VALIDATE_GUARDRAILS: dict[str, Any] = {
    "external_systems_called": False,
    "writeback": False,
    "redaction_applied": True,
    "secrets_in_output": False,
    "local_only": True,
    "read_only": True,
}

EXPECTED_SCHEMA_MIN = 5
PROCORE_TABLES = (
    "procore_sync_runs",
    "procore_sync_errors",
    "procore_synced_entities",
    "procore_sync_watermarks",
)
SCHEMA_VERSION = 1


def _now_iso() -> str:
    return datetime.now(timezone.utc).isoformat()


def _safe_check(name: str, fn: Callable[[], dict[str, Any]]) -> dict[str, Any]:
    try:
        result = fn()
        return {"name": name, "ok": bool(result.get("ok", True)), **result}
    except Exception as exc:  # noqa: BLE001 — boundary; redact below
        # Discard the exception message entirely (it may carry token- or path-shaped
        # content that the structural redactor does not regex-scan); preserve only
        # the exception class name so the failure mode is still observable. The key
        # is "error" because `redact_body(for_error=True)` only passes through values
        # whose key is in {"error", "errors", "message", "code", "status", "title"}.
        return {
            "name": name,
            "ok": False,
            "error_redacted": redact_body({"error": type(exc).__name__}, for_error=True),
        }


def _check_seed_endpoint_contract_loadable() -> dict[str, Any]:
    contract = load_endpoint_contract()
    return {
        "ok": True,
        "detail": {
            "company_id": contract.company_id,
            "endpoint_count": len(contract.endpoints),
        },
    }


def _check_seed_projects_loadable() -> dict[str, Any]:
    projects = load_procore_projects()
    return {
        "ok": True,
        "detail": {
            "company_id": projects.company_id,
            "project_count": len(projects.projects),
        },
    }


def _check_mapping_consistent() -> dict[str, Any]:
    contract = load_endpoint_contract()
    projects = load_procore_projects()
    report = EndpointAuditor(contract, projects).validate_mapping()
    return {
        "ok": bool(report.ok),
        "detail": {"by_status": dict(report.by_status), "total": report.total},
    }


def _check_app_profile_loadable() -> dict[str, Any]:
    profile = load_procore_app_profile()
    return {
        "ok": True,
        "detail": {
            "environment": profile.environment,
            "redirect_uri_kind": "oob" if profile.redirect_uri.startswith("urn:") else "localhost",
            "company_id": profile.company_id,
        },
    }


def _check_auth_status_present(*, strict: bool) -> dict[str, Any]:
    report = check_auth_status()
    if report.status == "env_present":
        ok = True
    elif strict:
        ok = False
    else:
        ok = True  # informational: live access is intentionally gated
    return {
        "ok": ok,
        "detail": {
            "status": report.status,
            "env_keys_present_count": len(report.env_keys_present),
            "env_keys_missing_count": len(report.env_keys_missing),
            "token_cache_present": report.token_cache_present,
            "ready_for_live_calls": report.ready_for_live_calls,
        },
    }


def _check_redaction_module_importable() -> dict[str, Any]:
    callables = {
        "redact_headers": callable(redact_headers),
        "redact_body": callable(redact_body),
        "redact_request": callable(redact_request),
        "redact_response": callable(redact_response),
    }
    return {"ok": all(callables.values()), "detail": callables}


def _check_obsidian_templates_resolvable() -> dict[str, Any]:
    renderer = ProcoreObsidianRenderer()
    resolved: dict[str, bool] = {}
    try:
        for short_name in PROCORE_TEMPLATE_NAMES:
            body = renderer._load_procore_template(short_name)  # noqa: SLF001
            resolved[short_name] = bool(body)
    finally:
        reset_procore_obsidian_caches()
    return {"ok": all(resolved.values()), "detail": {"resolved": resolved}}


def _check_obsidian_routing_rules_loadable() -> dict[str, Any]:
    renderer = ProcoreObsidianRenderer()
    rules = renderer._load_procore_routing_rules()  # noqa: SLF001
    return {
        "ok": isinstance(rules, dict),
        "detail": {"rule_groups": sorted(rules.keys())[:10] if isinstance(rules, dict) else []},
    }


def _check_obsidian_renderer_phase_04_register_coverage() -> dict[str, Any]:
    """Phase 04 Prompt 10: assert ProcoreObsidianRenderer exposes a callable
    builder for each per-entity register (RFI, Submittal, Observation,
    Meeting, Daily Log). Surfaces missing builders before apply-time."""
    expected = (
        "build_rfi_register",
        "build_submittal_register",
        "build_observation_register",
        "build_meeting_register",
        "build_daily_log_index",
    )
    present = {name: callable(getattr(ProcoreObsidianRenderer, name, None)) for name in expected}
    return {
        "ok": all(present.values()),
        "detail": {"builders": present},
    }


def _check_sensitive_routing_rules_cover_phase_04_families() -> dict[str, Any]:
    """Phase 04 Prompt 09: declarative parity — each per-entity normalizer
    family must be represented by at least one rule_id in
    procore_sensitive_routing_rules.yaml."""
    renderer = ProcoreObsidianRenderer()
    try:
        rules = renderer._load_procore_routing_rules().get("rules", [])  # noqa: SLF001
    finally:
        renderer._reset_routing_cache()  # noqa: SLF001
    rule_ids = [str(r.get("rule_id", "")) for r in rules if isinstance(r, dict)]
    families = ("rfi", "submittal", "observation", "meeting", "daily-log")
    covered = {fam: any(fam in rid for rid in rule_ids) for fam in families}
    return {
        "ok": all(covered.values()),
        "detail": {
            "rule_ids": rule_ids,
            "families_covered": covered,
        },
    }


def _check_vault_root_configurable() -> dict[str, Any]:
    from hb_assistant.construction.manifests.vault_writer import ConstructionVaultWriter

    writer = ConstructionVaultWriter()
    return {
        "ok": True,
        "detail": {"configured": bool(writer.configured)},
    }


def _check_sqlite_schema_at_expected_version(db_path: Path | None) -> dict[str, Any]:
    version = SQLiteMigrator(str(db_path) if db_path else None).current_version()
    return {
        "ok": version >= EXPECTED_SCHEMA_MIN,
        "detail": {"current_version": version, "expected_minimum": EXPECTED_SCHEMA_MIN},
    }


def _check_http_client_demands_access_token() -> dict[str, Any]:
    """Phase 04: a client built without a usable access token must fail closed
    with :class:`ProcoreAuthRequired` and never reuse ``PROCORE_CLIENT_SECRET``.
    """
    from hb_assistant.procore.errors import ProcoreAuthRequired
    from hb_assistant.procore.http_client import ProcoreHTTPClient

    def _empty_provider() -> str | None:
        return None

    def _stub_transport(method: str, url: str, headers: dict, params: Any) -> Any:  # noqa: ARG001
        raise AssertionError("transport must not be reached when no access token is available")

    client = ProcoreHTTPClient(
        environment="sandbox",
        transport=_stub_transport,
        access_token_provider=_empty_provider,
    )
    try:
        client.get("/rest/v1.1/projects")
    except ProcoreAuthRequired:
        return {"ok": True, "detail": {"fail_closed": True}}
    return {"ok": False, "detail": {"fail_closed": False}}


def _check_sync_pagination_method_aligned() -> dict[str, Any]:
    """Phase 04: the sync coordinator calls ``client.paginate(...)``; the HTTP
    client must expose that name (the prior ``get_paginated`` rename hazard).
    """
    from hb_assistant.procore.http_client import ProcoreHTTPClient

    has_paginate = hasattr(ProcoreHTTPClient, "paginate")
    has_legacy = hasattr(ProcoreHTTPClient, "get_paginated")
    return {
        "ok": bool(has_paginate and not has_legacy),
        "detail": {"paginate": has_paginate, "legacy_get_paginated": has_legacy},
    }


def _check_pending_projects_not_default_target() -> dict[str, Any]:
    """Phase 04: with no explicit ``--project``, the default sync target list
    must contain only ``status == "pilot"`` keys (never pending).
    """
    from hb_assistant.procore.sync import ProcoreSyncCoordinator

    coord = ProcoreSyncCoordinator()
    default_keys = coord._resolve_pilot_projects(None)  # noqa: SLF001
    registry = load_procore_projects()
    pending_by_key = {p.hb_project_key: (p.status == "pending") for p in registry.projects}
    leaked = [k for k in default_keys if pending_by_key.get(k)]
    return {
        "ok": not leaked,
        "detail": {"default_keys": default_keys, "leaked_pending": leaked},
    }


def _check_endpoint_verification_metadata_complete() -> dict[str, Any]:
    """Phase 04 Prompt 03: every included Phase-01 endpoint must declare a
    structured verification status of ``official_docs_verified`` or ``candidate``
    and supply either ``official_reference_url`` or ``verification_reason``.
    """
    contract = load_endpoint_contract()
    incomplete: list[str] = []
    for ep in contract.endpoints:
        if not ep.included_in_phase_01:
            continue
        if ep.status in ("excluded", "deferred"):
            continue
        if ep.verification_status not in ("official_docs_verified", "candidate"):
            incomplete.append(ep.endpoint_id)
            continue
        has_url = bool((ep.official_reference_url or "").strip())
        has_reason = bool((ep.verification_reason or "").strip())
        if not (has_url or has_reason):
            incomplete.append(ep.endpoint_id)
    return {
        "ok": not incomplete,
        "detail": {
            "total_phase_01_included": sum(
                1 for e in contract.endpoints
                if e.included_in_phase_01 and e.status not in ("excluded", "deferred")
            ),
            "incomplete": incomplete,
        },
    }


def _check_live_eligibility_blocks_ineligible() -> dict[str, Any]:
    """Phase 04 Prompt 03: ``is_live_eligible`` must be False for every
    excluded/deferred/non-verified endpoint, and True for at least one
    included Phase-01 endpoint (otherwise the data is malformed).
    """
    contract = load_endpoint_contract()
    leaked: list[str] = []
    eligible: list[str] = []
    for ep in contract.endpoints:
        if ep.is_live_eligible:
            eligible.append(ep.endpoint_id)
            if (
                ep.status in ("excluded", "deferred")
                or ep.verification_status != "official_docs_verified"
                or not ep.included_in_phase_01
            ):
                leaked.append(ep.endpoint_id)
    return {
        "ok": not leaked and bool(eligible),
        "detail": {
            "live_eligible_count": len(eligible),
            "leaked_ineligible": leaked,
        },
    }


def _check_token_provider_default_chain_shape() -> dict[str, Any]:
    """Phase 04 Prompt 02: the default Procore token provider must be a
    composed chain whose providers are, in order: env_or_keychain, oauth_cache,
    missing. This is the fail-closed boundary the HTTP client relies on.
    """
    from hb_assistant.procore.token_provider import default_procore_token_provider

    chain = default_procore_token_provider()
    providers = getattr(chain, "providers", None)
    if not providers:
        return {"ok": False, "detail": {"reason": "no_providers"}}
    actual_kinds = [getattr(p, "kind", type(p).__name__) for p in providers]
    expected_kinds = ["env_or_keychain", "oauth_refreshing", "missing"]
    return {
        "ok": actual_kinds == expected_kinds,
        "detail": {"expected": expected_kinds, "actual": actual_kinds},
    }


def _check_oauth_acquisition_path_present() -> dict[str, Any]:
    """Phase 04 Prompt 02 remediation: the OAuth acquisition module must
    expose the OOB exchange + refresh + authorization-URL surface, and
    ``RefreshingOAuthTokenProvider`` must be importable.
    """
    from hb_assistant.procore.oauth import ProcoreOAuthClient
    from hb_assistant.procore.token_provider import RefreshingOAuthTokenProvider

    methods = {
        "build_authorization_url": hasattr(ProcoreOAuthClient, "build_authorization_url"),
        "exchange_authorization_code": hasattr(ProcoreOAuthClient, "exchange_authorization_code"),
        "refresh_access_token": hasattr(ProcoreOAuthClient, "refresh_access_token"),
        "refreshing_provider_kind": getattr(RefreshingOAuthTokenProvider(), "kind", None)
        == "oauth_refreshing",
    }
    return {"ok": all(methods.values()), "detail": methods}


def _check_rfi_normalizer_dispatch_present() -> dict[str, Any]:
    """Phase 04 Prompt 04: ``list-rfis`` must be wired through the
    endpoint-id-keyed normalizer dispatch (``sync.NORMALIZER_DISPATCH``) so
    the apply path persists RFI replies as separate canonical rows.
    """
    from hb_assistant.procore.normalizers import (
        NORMALIZATION_SCHEMA_VERSION,
        normalize_rfi,
        normalize_rfi_payload_block,
        normalize_rfi_reply,
    )
    from hb_assistant.procore.sync import NORMALIZER_DISPATCH, RFI_ENDPOINT_ID

    dispatched = NORMALIZER_DISPATCH.get(RFI_ENDPOINT_ID)
    return {
        "ok": dispatched is normalize_rfi_payload_block
        and callable(normalize_rfi)
        and callable(normalize_rfi_reply)
        and NORMALIZATION_SCHEMA_VERSION >= 1,
        "detail": {
            "rfi_endpoint_id": RFI_ENDPOINT_ID,
            "dispatch_present": dispatched is not None,
            "schema_version": NORMALIZATION_SCHEMA_VERSION,
        },
    }


def _check_submittal_normalizer_dispatch_present() -> dict[str, Any]:
    """Phase 04 Prompt 05: ``list-submittals`` must be wired through the
    endpoint-id-keyed normalizer dispatch (``sync.NORMALIZER_DISPATCH``) so
    the apply path persists submittal responses and packages as separate
    canonical rows.
    """
    from hb_assistant.procore.normalizers import (
        NORMALIZATION_SCHEMA_VERSION,
        normalize_submittal,
        normalize_submittal_package,
        normalize_submittal_payload_block,
        normalize_submittal_response,
    )
    from hb_assistant.procore.sync import NORMALIZER_DISPATCH, SUBMITTAL_ENDPOINT_ID

    dispatched = NORMALIZER_DISPATCH.get(SUBMITTAL_ENDPOINT_ID)
    return {
        "ok": dispatched is normalize_submittal_payload_block
        and callable(normalize_submittal)
        and callable(normalize_submittal_response)
        and callable(normalize_submittal_package)
        and NORMALIZATION_SCHEMA_VERSION >= 1,
        "detail": {
            "submittal_endpoint_id": SUBMITTAL_ENDPOINT_ID,
            "dispatch_present": dispatched is not None,
            "schema_version": NORMALIZATION_SCHEMA_VERSION,
        },
    }


def _check_observation_normalizer_dispatch_present() -> dict[str, Any]:
    """Phase 04 Prompt 06: ``list-observations`` must be wired through the
    endpoint-id-keyed normalizer dispatch (``sync.NORMALIZER_DISPATCH``) so
    the apply path persists observation comments as separate canonical rows
    with safety-aware routing. The endpoint itself ships as a
    ``verification_status: candidate`` entry so live execution stays blocked
    until docs reconciliation completes.
    """
    from hb_assistant.procore.normalizers import (
        NORMALIZATION_SCHEMA_VERSION,
        normalize_observation,
        normalize_observation_comment,
        normalize_observation_payload_block,
    )
    from hb_assistant.procore.sync import NORMALIZER_DISPATCH, OBSERVATION_ENDPOINT_ID

    dispatched = NORMALIZER_DISPATCH.get(OBSERVATION_ENDPOINT_ID)
    return {
        "ok": dispatched is normalize_observation_payload_block
        and callable(normalize_observation)
        and callable(normalize_observation_comment)
        and NORMALIZATION_SCHEMA_VERSION >= 1,
        "detail": {
            "observation_endpoint_id": OBSERVATION_ENDPOINT_ID,
            "dispatch_present": dispatched is not None,
            "schema_version": NORMALIZATION_SCHEMA_VERSION,
        },
    }


def _check_meeting_normalizer_dispatch_present() -> dict[str, Any]:
    """Phase 04 Prompt 07: both ``list-meetings`` and ``list-meeting-topics``
    must be wired through ``sync.NORMALIZER_DISPATCH``. Meetings are
    metadata-only at the parent level; topics carry safety-aware routing.
    Both endpoints ship as ``verification_status: candidate`` until docs
    reconciliation completes.
    """
    from hb_assistant.procore.normalizers import (
        NORMALIZATION_SCHEMA_VERSION,
        normalize_meeting,
        normalize_meeting_payload_block,
        normalize_meeting_topic,
        normalize_meeting_topic_payload_block,
    )
    from hb_assistant.procore.sync import (
        MEETING_ENDPOINT_ID,
        MEETING_TOPIC_ENDPOINT_ID,
        NORMALIZER_DISPATCH,
    )

    parent_dispatched = NORMALIZER_DISPATCH.get(MEETING_ENDPOINT_ID)
    topic_dispatched = NORMALIZER_DISPATCH.get(MEETING_TOPIC_ENDPOINT_ID)
    return {
        "ok": parent_dispatched is normalize_meeting_payload_block
        and topic_dispatched is normalize_meeting_topic_payload_block
        and callable(normalize_meeting)
        and callable(normalize_meeting_topic)
        and NORMALIZATION_SCHEMA_VERSION >= 1,
        "detail": {
            "meeting_endpoint_id": MEETING_ENDPOINT_ID,
            "meeting_topic_endpoint_id": MEETING_TOPIC_ENDPOINT_ID,
            "meeting_dispatch_present": parent_dispatched is not None,
            "meeting_topic_dispatch_present": topic_dispatched is not None,
            "schema_version": NORMALIZATION_SCHEMA_VERSION,
        },
    }


def _check_daily_log_selection_and_dispatch_present() -> dict[str, Any]:
    """Phase 04 Prompt 08: ``list-daily-logs`` must be wired through the
    normalizer dispatch and the section-selection seed must load with all
    three buckets populated (selected, review_only, routed_to_review).
    Together these enforce: selected sections persist as canonical rows;
    notes are review-only with hash-only bodies; accident / injury / delay /
    safety sections never enter normal rows.
    """
    from hb_assistant.procore.daily_log_selection import load_daily_log_selection
    from hb_assistant.procore.normalizers import normalize_daily_log_payload_block
    from hb_assistant.procore.sync import DAILY_LOG_ENDPOINT_ID, NORMALIZER_DISPATCH

    dispatched = NORMALIZER_DISPATCH.get(DAILY_LOG_ENDPOINT_ID)
    selection = load_daily_log_selection()
    return {
        "ok": dispatched is normalize_daily_log_payload_block
        and bool(selection.selected_sections)
        and bool(selection.review_only_sections)
        and bool(selection.routed_to_review_sections),
        "detail": {
            "daily_log_endpoint_id": DAILY_LOG_ENDPOINT_ID,
            "dispatch_present": dispatched is not None,
            "selected_section_count": len(selection.selected_sections),
            "review_only_section_count": len(selection.review_only_sections),
            "routed_to_review_section_count": len(selection.routed_to_review_sections),
            "selection_version": selection.version,
        },
    }


def _check_procore_init_exports_complete() -> dict[str, Any]:
    """Phase 04: the public ``hb_assistant.procore`` API must re-export the
    sync coordinator, ``run_sync``, ``SyncReceipt``, and the new fail-closed
    exceptions added in this prompt.
    """
    import hb_assistant.procore as procore_pkg

    required = {
        "ProcoreSyncCoordinator",
        "run_sync",
        "SyncReceipt",
        "ProcoreAuthRequired",
        "ProcorePendingProjectRejected",
        "ProcoreMappingUnavailable",
        "ProcoreTokenProvider",
        "MissingTokenProvider",
        "EnvOrKeychainTokenProvider",
        "LocalOAuthCacheTokenProvider",
        "default_procore_token_provider",
        "ProcoreOAuthClient",
        "ProcoreOAuthError",
        "TokenSet",
        "RefreshingOAuthTokenProvider",
        "write_token_cache",
        "clear_token_cache",
    }
    missing = sorted(name for name in required if not hasattr(procore_pkg, name))
    return {
        "ok": not missing,
        "detail": {"required": sorted(required), "missing": missing},
    }


def _check_procore_tables_present(db_path: Path | None, *, strict: bool) -> dict[str, Any]:
    conn = get_connection(str(db_path) if db_path else None)
    present: dict[str, bool] = {}
    for table in PROCORE_TABLES:
        cur = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?",
            (table,),
        )
        present[table] = cur.fetchone() is not None
    all_present = all(present.values())
    if all_present:
        ok = True
    elif strict:
        ok = False
    else:
        ok = True  # informational: tables are created on-demand by first sync
    return {
        "ok": ok,
        "detail": {
            "tables": present,
            "all_present": all_present,
            "note": (
                "Procore tables are created on demand by the sync coordinator; "
                "absence is expected on a fresh checkout."
            ),
        },
    }


def run_procore_validate(
    *,
    strict: bool = False,
    db_path: Path | None = None,
) -> dict[str, Any]:
    """Run the full read-only validation suite. Returns a JSON-serializable envelope."""

    started_at = _now_iso()

    checks: list[dict[str, Any]] = [
        _safe_check("seed_endpoint_contract_loadable", _check_seed_endpoint_contract_loadable),
        _safe_check("seed_projects_loadable", _check_seed_projects_loadable),
        _safe_check("mapping_consistent", _check_mapping_consistent),
        _safe_check("app_profile_loadable", _check_app_profile_loadable),
        _safe_check("auth_status_present", lambda: _check_auth_status_present(strict=strict)),
        _safe_check("redaction_module_importable", _check_redaction_module_importable),
        _safe_check("obsidian_templates_resolvable", _check_obsidian_templates_resolvable),
        _safe_check("obsidian_routing_rules_loadable", _check_obsidian_routing_rules_loadable),
        _safe_check("vault_root_configurable", _check_vault_root_configurable),
        _safe_check("sqlite_schema_at_expected_version", lambda: _check_sqlite_schema_at_expected_version(db_path)),
        _safe_check("procore_tables_present", lambda: _check_procore_tables_present(db_path, strict=strict)),
        _safe_check("http_client_demands_access_token", _check_http_client_demands_access_token),
        _safe_check("sync_pagination_method_aligned", _check_sync_pagination_method_aligned),
        _safe_check("pending_projects_not_default_target", _check_pending_projects_not_default_target),
        _safe_check("token_provider_default_chain_shape", _check_token_provider_default_chain_shape),
        _safe_check("oauth_acquisition_path_present", _check_oauth_acquisition_path_present),
        _safe_check("endpoint_verification_metadata_complete", _check_endpoint_verification_metadata_complete),
        _safe_check("live_eligibility_blocks_ineligible", _check_live_eligibility_blocks_ineligible),
        _safe_check("procore_init_exports_complete", _check_procore_init_exports_complete),
        _safe_check("rfi_normalizer_dispatch_present", _check_rfi_normalizer_dispatch_present),
        _safe_check("submittal_normalizer_dispatch_present", _check_submittal_normalizer_dispatch_present),
        _safe_check("observation_normalizer_dispatch_present", _check_observation_normalizer_dispatch_present),
        _safe_check("meeting_normalizer_dispatch_present", _check_meeting_normalizer_dispatch_present),
        _safe_check("daily_log_selection_and_dispatch_present", _check_daily_log_selection_and_dispatch_present),
        _safe_check(
            "sensitive_routing_rules_cover_phase_04_families",
            _check_sensitive_routing_rules_cover_phase_04_families,
        ),
        _safe_check(
            "obsidian_renderer_phase_04_register_coverage",
            _check_obsidian_renderer_phase_04_register_coverage,
        ),
    ]

    passed = sum(1 for c in checks if c.get("ok"))
    failed = len(checks) - passed
    completed_at = _now_iso()

    return {
        "command": "hb-assistant procore validate",
        "schema_version": SCHEMA_VERSION,
        "started_at": started_at,
        "completed_at": completed_at,
        "strict": strict,
        "ok": failed == 0,
        "summary": {
            "total": len(checks),
            "passed": passed,
            "failed": failed,
        },
        "checks": checks,
        "guardrails": VALIDATE_GUARDRAILS,
    }


__all__ = [
    "VALIDATE_GUARDRAILS",
    "EXPECTED_SCHEMA_MIN",
    "PROCORE_TABLES",
    "run_procore_validate",
]
