"""Phase 08D safe MCP resources (Prompt 07).

Five addressable read-only resources, each generated from an **approved workflow/read-model
only** (the Prompt 05 wrappers). Resources are bounded, structured, carry freshness +
policy posture, and fail closed on any unknown URI. Unlike tools, resource reads emit no
per-access receipt (the contract omits one); the resource-registry snapshot is the audit
artifact. Nothing here exposes raw content, SQL, direct APIs, writeback, URLs, or
determinations.
"""

from __future__ import annotations

import json
from datetime import datetime, timezone
from typing import Any, Callable

from ..contracts import load_phase_08d_contract
from ..financial_review_routing import _assert_no_raw
from .policy import _policy_version
from .store import _sha256, write_mcp_resource_registry_snapshot

# Phase 10A P09: raw MCP posture (resources remain no-raw by default; packet tools carry raw when allowed)
try:
    from ..local_ai.contracts import load_raw_content_policy
except Exception:  # pragma: no cover
    load_raw_content_policy = None  # type: ignore
from .wrappers import (
    mcp_get_daily_brief_wrapper,
    mcp_research_packet_wrapper,
    mcp_review_load_status_wrapper,
    mcp_status_wrapper,
    mcp_validation_status_wrapper,
)

# A resource is backed by an approved wrapper; the resolver passes a db_path.
_ResourceFn = Callable[..., dict[str, Any]]

_RESOURCE_POLICY_POSTURE = {
    "advisory_only": True,
    "local_only": True,
    "read_only": True,
    "no_writeback": True,
    "no_raw": True,
    "no_final_determination": True,
}


def _compute_mcp_raw_allowed() -> bool:
    try:
        if load_raw_content_policy is None:
            return False
        rc = load_raw_content_policy()
        rcd = getattr(rc, "raw_content", None)
        downstream = getattr(rcd, "downstream", None) if rcd is not None else None
        flag = (
            bool(getattr(downstream, "mcp_allow_raw_content", False))
            if downstream is not None
            else False
        )
        mode = str(getattr(rcd, "mode", "") or "").lower() if rcd is not None else ""
        permissive = (
            mode in ("", "all_supported", "all_supported_plus_downstream") or "downstream" in mode
        )
        return bool(flag and permissive)
    except Exception:
        return False


# uri -> (resource_name, backing approved-workflow wrapper, source description)
_RESOURCES: dict[str, tuple[str, _ResourceFn, str]] = {
    "hb://status/system": ("mcp_status_resource", mcp_status_wrapper, "safe status workflow"),
    "hb://brief/today": (
        "mcp_today_brief_resource",
        mcp_get_daily_brief_wrapper,
        "daily brief render view",
    ),
    "hb://review/load": (
        "mcp_review_load_resource",
        mcp_review_load_status_wrapper,
        "review triage/load status",
    ),
    "hb://research/latest": (
        "mcp_latest_research_resource",
        mcp_research_packet_wrapper,
        "latest research packet summary",
    ),
    "hb://validation/latest": (
        "mcp_latest_validation_resource",
        mcp_validation_status_wrapper,
        "latest gates/no-writeback proof summaries",
    ),
}


class ResourceUnavailable(RuntimeError):
    """Raised when the resource registry is missing/empty or drifts from the resolvers."""


def load_resources() -> list[dict[str, Any]]:
    """Return the resource registry entries (uri/wrapper/source) from the contract."""
    contract = load_phase_08d_contract("resources_contract")
    resources = contract.get("resources") if isinstance(contract, dict) else None
    if not isinstance(resources, list) or not resources:
        raise ResourceUnavailable("resources registry missing or empty")
    contract_uris = {str(r.get("uri")) for r in resources if isinstance(r, dict)}
    if contract_uris != set(_RESOURCES):
        raise ResourceUnavailable("resource registry drift between contract and resolvers")
    return [
        {"uri": str(r["uri"]), "wrapper": str(r["wrapper"]), "source": r.get("source")}
        for r in resources
        if isinstance(r, dict)
    ]


def _now(now: datetime | None = None) -> str:
    return (now or datetime.now(timezone.utc)).isoformat()


def read_resource(
    uri: str, *, db_path: str | None = None, now: datetime | None = None
) -> dict[str, Any]:
    """Resolve one safe resource URI to a bounded, read-only payload (fail-closed)."""
    entry = _RESOURCES.get(uri)
    if entry is None:
        return {
            "uri": uri,
            "status": "denied",
            "reason_code": "resource_not_allowed",
            "fail_closed": True,
            "policy_posture": {
                **dict(_RESOURCE_POLICY_POSTURE),
                "no_raw": not _compute_mcp_raw_allowed(),
                "mcp_raw_allowed": _compute_mcp_raw_allowed(),
            },
        }

    resource_name, wrapper, source = entry
    payload = wrapper({}, db_path=db_path)
    resource = {
        "uri": uri,
        "resource_name": resource_name,
        "source": source,
        "status": payload.get("status", "ok"),
        "provenance": payload.get("provenance"),
        "content": payload.get("results", []),
        "source_count": payload.get("source_count", 0),
        "output_classification": payload.get("output_classification", "bounded_summary"),
        "freshness": {"generated_utc": _now(now), "basis": "computed_live"},
        "policy_posture": {
            **dict(_RESOURCE_POLICY_POSTURE),
            "no_raw": not _compute_mcp_raw_allowed(),
            "mcp_raw_allowed": _compute_mcp_raw_allowed(),
        },
    }
    _assert_no_raw(json.dumps(resource, default=str), uri)
    return resource


def read_all_resources(*, db_path: str | None = None) -> list[dict[str, Any]]:
    """Resolve every registered resource (read-only)."""
    return [read_resource(uri, db_path=db_path) for uri in _RESOURCES]


def _registry_hash() -> str:
    return _sha256([(uri, entry[0]) for uri, entry in sorted(_RESOURCES.items())])


def snapshot_resource_registry(*, db_path: str | None = None, persist: bool = True) -> str | None:
    """Persist a metadata-only resource-registry snapshot (count + hash). Returns its id."""
    if not persist:
        return None
    return write_mcp_resource_registry_snapshot(
        resource_count=len(_RESOURCES),
        registry_hash=_registry_hash(),
        policy_version=_policy_version(),
        db_path=db_path,
    )
