"""Prompt Preflight — tool-surface freshness guard.

Compares LIVE surface state against an independent stored snapshot when provided.
Never self-compares live gateway to itself and claims current. Failures report
check_failed / indeterminate — never a false current state.
"""

from __future__ import annotations

from typing import Any

from .tool_entry_manifest import build_tool_entry
from .tool_family_manifest import FAMILY_IDS, family_for_tool
from .workflow_recipe_manifest import WORKFLOWS

_ROUTING_LAYER = frozenset({
    "pa_prompt_route", "pa_prompt_route_explain", "pa_tool_family_get",
    "pa_workflow_recipe_get", "pa_tool_surface_freshness_check",
    "pa_tool_surface_runtime_attestation",
})


def _empty_categories() -> dict[str, bool]:
    return {
        "structural_drift": False,
        "semantic_drift": False,
        "workflow_drift": False,
        "exposure_drift": False,
        "gateway_drift": False,
        "schema_drift": False,
        "classification_drift": False,
        "help_coverage_drift": False,
        "alias_drift": False,
        "deployment_runtime_drift": False,
        "manifest_version_drift": False,
        "checksum_drift": False,
        "profile_context_changed": False,
        "execution_attestation": False,
    }


def check_tool_surface(
    live_tools: dict[str, str | None],
    *,
    stored_entries: dict[str, dict[str, Any]] | None = None,
    live_gateway_allowlist: frozenset[str] | set[str] | None = None,
    stored_gateway_allowlist: frozenset[str] | set[str] | None = None,
    check_workflow_coverage: bool = True,
    live_semantic_checksum: str | None = None,
    stored_semantic_checksum: str | None = None,
    live_exposure_checksum: str | None = None,
    stored_exposure_checksum: str | None = None,
    live_runtime_commit: str | None = None,
    stored_runtime_commit: str | None = None,
    live_profile: str | None = None,
    stored_profile: str | None = None,
    help_index: dict[str, Any] | None = None,
    check_error: str | None = None,
    attestation_ok: bool | None = None,
    attestation_failed_count: int | None = None,
    attestation_age_seconds: int | None = None,
) -> dict[str, Any]:
    """Return a freshness report over the live tool surface vs stored snapshot.

    ``live_tools`` maps live tool name -> tool group. When stored baselines are absent,
    structural self-consistency is checked and semantic/gateway categories are
    ``indeterminate`` rather than falsely ``current``.
    """
    categories = _empty_categories()
    warnings: list[str] = []

    if check_error:
        return {
            "stale": True,
            "staleness_state": "check_failed",
            "warnings": [f"freshness_error:{check_error}"],
            "categories": categories,
            "category_status": {"freshness_check": "check_failed"},
            "checked_categories": [],
            "unchecked_categories": ["freshness_check"],
            "review_required": True,
            "check_error": check_error,
            "tool_surface_gateway_current": False,
            "live_tool_count": len(live_tools),
            "unclassified_tools": [],
            "workflow_missing_tools": [],
            "added_tools": [],
            "removed_tools": [],
            "family_changed_tools": [],
            "class_changed_tools": [],
            "gateway_added": [],
            "gateway_removed": [],
        }

    live_names = set(live_tools)

    unclassified = sorted(
        n for n in live_names if family_for_tool(n, live_tools.get(n)) not in FAMILY_IDS
    )
    if unclassified:
        warnings.append(f"tools with no known family: {unclassified}")
        categories["structural_drift"] = True

    workflow_missing_tools: list[str] = []
    if check_workflow_coverage:
        for wf in WORKFLOWS:
            for tool in wf["tool_sequence"]:
                if tool not in live_names and tool not in _ROUTING_LAYER:
                    # profile_conditional tools may be gated off — only flag if present in live map as None group?
                    workflow_missing_tools.append(f"{wf['workflow_id']}:{tool}")
    # Soften: only tools that are in live_tools keys count as "live"; gated-off assistant
    # groups are absent from live_tools, so missing workflow refs against gated tools are
    # exposure, not structural, when the tool is known but disabled.
    if workflow_missing_tools:
        warnings.append(f"workflows reference missing tools: {sorted(set(workflow_missing_tools))}")
        categories["workflow_drift"] = True

    added: list[str] = []
    removed: list[str] = []
    family_changed: list[str] = []
    class_changed: list[str] = []
    if stored_entries is not None:
        stored_names = set(stored_entries)
        added = sorted(live_names - stored_names)
        removed = sorted(stored_names - live_names)
        for name in sorted(live_names & stored_names):
            live_entry = build_tool_entry(name, live_tools.get(name))
            stored = stored_entries[name]
            if live_entry["tool_family"] != stored.get("tool_family"):
                family_changed.append(name)
            if (live_entry["read_write_class"] != stored.get("read_write_class")
                    or live_entry["safety_class"] != stored.get("safety_class")):
                class_changed.append(name)
        if added or removed:
            categories["structural_drift"] = True
            warnings.append(f"tools added since manifest: {added}; removed: {removed}")
        if family_changed or class_changed:
            categories["classification_drift"] = True
            categories["semantic_drift"] = True
            if family_changed:
                warnings.append(f"tools whose family changed: {family_changed}")
            if class_changed:
                warnings.append(f"tools whose read/write or safety class changed: {class_changed}")
    else:
        # No independent stored entries — cannot claim semantic currency.
        categories["semantic_drift"] = False  # unknown, handled via state
        warnings.append("no_stored_entries:semantic_categories_indeterminate")

    gateway_added: list[str] = []
    gateway_removed: list[str] = []
    gateway_current = True
    gateway_checked = False
    if live_gateway_allowlist is not None and stored_gateway_allowlist is not None:
        live_g, stored_g = set(live_gateway_allowlist), set(stored_gateway_allowlist)
        gateway_added = sorted(live_g - stored_g)
        gateway_removed = sorted(stored_g - live_g)
        gateway_current = not (gateway_added or gateway_removed)
        gateway_checked = True
        if not gateway_current:
            categories["gateway_drift"] = True
            warnings.append(
                f"gateway allowlist scope changed (added={gateway_added}, removed={gateway_removed})"
            )
    else:
        # No independent gateway baseline — leave gateway_current True for structural-only
        # checks that omit gateway args; do not invent gateway_drift.
        gateway_current = True
        gateway_checked = False

    semantic_checksum_mismatch = False
    if stored_semantic_checksum is not None and live_semantic_checksum is not None:
        if live_semantic_checksum != stored_semantic_checksum:
            categories["checksum_drift"] = True
            categories["semantic_drift"] = True
            semantic_checksum_mismatch = True
            warnings.append("semantic_surface_checksum_mismatch")
    elif stored_semantic_checksum is not None and live_semantic_checksum is None:
        warnings.append("semantic_checksum_indeterminate")

    exposure_checksum_mismatch = False
    if stored_exposure_checksum is not None and live_exposure_checksum is not None:
        if live_exposure_checksum != stored_exposure_checksum:
            categories["exposure_drift"] = True
            exposure_checksum_mismatch = True
            warnings.append("exposure_checksum_mismatch")
    elif stored_exposure_checksum is not None and live_exposure_checksum is None:
        warnings.append("exposure_checksum_indeterminate")

    if live_profile and stored_profile and live_profile != stored_profile:
        categories["profile_context_changed"] = True
        warnings.append(f"profile_context_changed:{stored_profile}->{live_profile}")

    if live_runtime_commit is not None or stored_runtime_commit is not None:
        live_s = str(live_runtime_commit or "")
        looks_like_sha = bool(live_s) and all(c in "0123456789abcdef" for c in live_s.lower()) and len(live_s) >= 7
        if stored_runtime_commit and looks_like_sha and live_s != str(stored_runtime_commit):
            categories["deployment_runtime_drift"] = True
            warnings.append("deployment_runtime_commit_mismatch")
        elif stored_runtime_commit and looks_like_sha and live_s == str(stored_runtime_commit):
            pass  # exact match
        elif not looks_like_sha:
            # Package-only / unknown is informational unless a stored SHA baseline exists.
            if live_s.startswith("v") or live_s == "unknown" or not live_s:
                warnings.append(
                    "runtime_identity_package_only_fallback"
                    if live_s.startswith("v")
                    else "runtime_identity_unknown"
                )
                if stored_runtime_commit and all(
                    c in "0123456789abcdef" for c in str(stored_runtime_commit).lower()
                ):
                    categories["deployment_runtime_drift"] = True

    if help_index is not None:
        missing_help = sorted(n for n in live_names if n not in help_index or not help_index.get(n))
        if missing_help:
            categories["help_coverage_drift"] = True
            warnings.append(f"help_coverage_missing:{missing_help[:20]}")

    attestation_stale = False
    if attestation_ok is not None:
        if not attestation_ok or (attestation_failed_count or 0) > 0:
            categories["execution_attestation"] = True
            attestation_stale = True
            warnings.append(
                f"execution_attestation_failed:failed_count={attestation_failed_count or 0}"
            )
        elif attestation_age_seconds is not None and attestation_age_seconds > 86_400:
            warnings.append(f"execution_attestation_age:{attestation_age_seconds}s")

    category_status: dict[str, str] = {}
    has_stored_baseline = stored_entries is not None or stored_semantic_checksum is not None

    if stored_entries is None:
        category_status["structural"] = "indeterminate"
    elif added or removed or unclassified or workflow_missing_tools:
        category_status["structural"] = "stale"
    else:
        category_status["structural"] = "current"

    if stored_entries is None:
        category_status["classification"] = "indeterminate"
    elif family_changed or class_changed:
        category_status["classification"] = "stale"
    else:
        category_status["classification"] = "current"

    if stored_semantic_checksum is None:
        category_status["semantic_checksum"] = "indeterminate"
    elif live_semantic_checksum is None:
        category_status["semantic_checksum"] = "indeterminate"
    elif semantic_checksum_mismatch:
        category_status["semantic_checksum"] = "stale"
    else:
        category_status["semantic_checksum"] = "current"

    if stored_exposure_checksum is None:
        category_status["exposure_checksum"] = "indeterminate"
    elif live_exposure_checksum is None:
        category_status["exposure_checksum"] = "indeterminate"
    elif exposure_checksum_mismatch:
        category_status["exposure_checksum"] = "stale"
    else:
        category_status["exposure_checksum"] = "current"

    if stored_gateway_allowlist is None:
        category_status["gateway"] = "indeterminate"
    elif live_gateway_allowlist is None:
        category_status["gateway"] = "indeterminate"
    elif not gateway_current:
        category_status["gateway"] = "stale"
    else:
        category_status["gateway"] = "current"

    if stored_runtime_commit is None:
        category_status["deployment_runtime"] = "indeterminate"
    elif categories.get("deployment_runtime_drift"):
        category_status["deployment_runtime"] = "stale"
    else:
        category_status["deployment_runtime"] = "current"

    if stored_profile is None:
        category_status["profile_context"] = "indeterminate"
    elif categories.get("profile_context_changed"):
        category_status["profile_context"] = "stale"
    else:
        category_status["profile_context"] = "current"

    if attestation_ok is None:
        category_status["execution_attestation"] = "indeterminate"
    elif attestation_stale:
        category_status["execution_attestation"] = "stale"
    else:
        category_status["execution_attestation"] = "current"

    checked_categories = sorted(k for k, v in category_status.items() if v != "indeterminate")
    unchecked_categories = sorted(k for k, v in category_status.items() if v == "indeterminate")
    status_values = [
        v for k, v in category_status.items()
        if v != "indeterminate" or k != "execution_attestation"
    ]

    if attestation_stale:
        stale = True
        staleness_state = "stale"
    elif "stale" in status_values:
        stale = True
        staleness_state = "stale"
    elif has_stored_baseline and "indeterminate" in status_values:
        stale = False
        staleness_state = "indeterminate"
    elif has_stored_baseline and status_values and all(v == "current" for v in status_values):
        stale = False
        staleness_state = "current"
    elif has_stored_baseline:
        stale = False
        staleness_state = "indeterminate"
    else:
        stale = bool(unclassified or workflow_missing_tools)
        staleness_state = "structural_only" if not stale else "stale"

    return {
        "stale": stale,
        "staleness_state": staleness_state,
        "warnings": warnings,
        "categories": categories,
        "category_status": category_status,
        "checked_categories": checked_categories,
        "unchecked_categories": unchecked_categories,
        "unclassified_tools": unclassified,
        "workflow_missing_tools": sorted(set(workflow_missing_tools)),
        "added_tools": added,
        "removed_tools": removed,
        "family_changed_tools": family_changed,
        "class_changed_tools": class_changed,
        "gateway_added": gateway_added,
        "gateway_removed": gateway_removed,
        "tool_surface_gateway_current": gateway_current if gateway_checked else None,
        "live_tool_count": len(live_names),
        "review_required": stale or staleness_state == "indeterminate",
        "independent_baseline": has_stored_baseline,
        "gateway_checked": gateway_checked,
        "execution_attestation_ok": attestation_ok,
        "execution_attestation_failed_count": attestation_failed_count,
        "execution_attestation_age_seconds": attestation_age_seconds,
        "client_writes_must_be_blocked": (
            attestation_stale if attestation_ok is not None else None
        ),
    }
