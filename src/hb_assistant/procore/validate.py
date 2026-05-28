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
