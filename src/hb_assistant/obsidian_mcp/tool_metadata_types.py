"""Pure typed contracts for prompt-preflight / tool-routing metadata.

No nas_mcp imports. No I/O. Used by canonical specs, live surface, freshness, and manifests.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
from typing import Any


class AvailabilityKind(str, Enum):
    REQUIRED = "required"
    PROFILE_CONDITIONAL = "profile_conditional"
    FEATURE_FLAGGED = "feature_flagged"
    OPTIONAL_DEPENDENCY = "optional_dependency"
    DEPRECATED = "deprecated"
    REMOVED = "removed"


class RuntimeIdentityKind(str, Enum):
    EXACT_COMMIT = "exact_commit"
    PACKAGE_ONLY_FALLBACK = "package_only_fallback"
    UNKNOWN = "unknown"


class PluginFailureStage(str, Enum):
    """Plugin-authoritative failure stages only (request reached plugin infrastructure)."""

    GATEWAY_ALLOWLIST = "gateway_allowlist"
    SCHEMA_VALIDATION = "schema_validation"
    BROKER_POLICY = "broker_policy"
    BROKER_DISPATCH = "broker_dispatch"
    HANDLER = "handler"
    BACKEND_DEPENDENCY = "backend_dependency"
    SERIALIZATION = "serialization"
    SURFACE_STALE = "surface_stale"
    UNKNOWN_INTERNAL = "unknown_internal"


# Unobserved external possibilities — documentation / diagnostics only, never authoritative envelopes.
UNOBSERVED_EXTERNAL = frozenset({
    "client_did_not_emit_call",
    "connector_or_platform_failure_unverified",
})

ROUTE_SCHEMA_VERSION = 2
MANIFEST_SCHEMA_VERSION = 1  # expanded semantic payload; legacy rows are schema 0

# Capability tokens used by scoped negation / authorization.
CAPABILITY_PROMOTE = "promote"
CAPABILITY_WRITE = "write"
CAPABILITY_STAGE = "stage"
CAPABILITY_EXECUTE = "execute"
CAPABILITY_ARCHIVE = "archive"
CAPABILITY_INDEX = "index"
CAPABILITY_DEPLOY = "deploy"
CAPABILITY_EXTERNAL = "external_action"
CAPABILITY_READ = "read"


@dataclass(frozen=True)
class LifecycleSpec:
    state: str = "active"  # active | deprecated | removed
    replaced_by: tuple[str, ...] = ()
    deprecated: bool = False


@dataclass(frozen=True)
class ExposureDeclaration:
    """Declared design intent (not live observation)."""

    direct_by_design: bool = True
    gateway_by_design: bool = True
    availability: AvailabilityKind = AvailabilityKind.REQUIRED
    profile_gate: str | None = None  # e.g. HB_MCP_PROMPT_PREFLIGHT


@dataclass(frozen=True)
class ToolSpec:
    name: str
    family: str
    group: str | None
    purpose: str = ""
    required_args: tuple[str, ...] = ()
    optional_args: tuple[str, ...] = ()
    limits: dict[str, Any] = field(default_factory=dict)
    read_write_class: str = "read_only"
    safety_class: str = "bounded_read"
    tool_class: str = "read_only_retrieval"
    authorization_capabilities: tuple[str, ...] = (CAPABILITY_READ,)
    aliases: tuple[str, ...] = ()
    exposure: ExposureDeclaration = field(default_factory=ExposureDeclaration)
    lifecycle: LifecycleSpec = field(default_factory=LifecycleSpec)
    use_when: str = ""
    do_not_use_when: str = ""
    workflow_roles: tuple[str, ...] = ()
    examples: tuple[str, ...] = ()
    common_failure_modes: tuple[str, ...] = ()

    def to_public_dict(self) -> dict[str, Any]:
        d = asdict(self)
        d["exposure"]["availability"] = self.exposure.availability.value
        return d


@dataclass(frozen=True)
class WorkflowSpec:
    workflow_id: str
    family_id: str
    trigger_phrases: tuple[str, ...]
    intent_classes: tuple[str, ...]
    tool_sequence: tuple[str, ...]
    when_to_use: str = ""
    when_not_to_use: str = ""
    required_inputs: tuple[str, ...] = ()
    optional_inputs: tuple[str, ...] = ()
    operator_authorization_policy: str = "read"
    additional_approval_points: tuple[str, ...] = ()
    write_risk: str = "none"
    default_retrieval_layer: str = "route_only"
    max_default_candidates: int = 10
    max_default_chars: int = 4000
    expected_outputs: tuple[str, ...] = ()
    required_provenance: tuple[str, ...] = ()
    must_not_use: tuple[str, ...] = ()
    fallback_rules: tuple[str, ...] = ()
    failure_recovery: str = ""
    prohibited_capabilities: tuple[str, ...] = ()  # capabilities this workflow exercises
    source_of_truth: str = ""

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(frozen=True)
class FamilySpec:
    family_id: str
    purpose: str
    read_write_class: str = "read_only"
    safety_class: str = "bounded_read"
    use_when: tuple[str, ...] = ()
    do_not_use_when: tuple[str, ...] = ()
    common_trigger_phrases: tuple[str, ...] = ()
    primary_workflows: tuple[str, ...] = ()
    preferred_before: tuple[str, ...] = ()
    fallback_after: tuple[str, ...] = ()
    family_level_negative_instructions: tuple[str, ...] = ()

    def to_dict(self) -> dict[str, Any]:
        d = asdict(self)
        # Compatibility with existing family_record shape (lists).
        return {
            "family_id": d["family_id"],
            "purpose": d["purpose"],
            "use_when": list(d["use_when"]),
            "do_not_use_when": list(d["do_not_use_when"]),
            "read_write_class": d["read_write_class"],
            "safety_class": d["safety_class"],
            "common_trigger_phrases": list(d["common_trigger_phrases"]),
            "primary_workflows": list(d["primary_workflows"]),
            "preferred_before": list(d["preferred_before"]),
            "fallback_after": list(d["fallback_after"]),
            "family_level_negative_instructions": list(d["family_level_negative_instructions"]),
        }


@dataclass(frozen=True)
class SurfaceToolState:
    """Surface-level only — never request-specific approval/token/path state."""

    name: str
    installed: bool
    profile_enabled: bool
    directly_exposed: bool
    gateway_allowlisted: bool
    server_policy_available: bool
    surface_blocked_reason: str | None
    group: str | None
    family: str
    read_write_class: str
    safety_class: str
    tool_class: str
    purpose: str = ""
    required_args: tuple[str, ...] = ()
    optional_args: tuple[str, ...] = ()
    limits: dict[str, Any] = field(default_factory=dict)


@dataclass(frozen=True)
class RuntimeIdentity:
    runtime_commit: str | None
    package_version: str | None
    runtime_identity_kind: RuntimeIdentityKind

    def as_legacy_string(self) -> str:
        if self.runtime_identity_kind == RuntimeIdentityKind.EXACT_COMMIT and self.runtime_commit:
            return self.runtime_commit
        if self.package_version:
            return f"v{self.package_version.lstrip('v')}"
        return "unknown"

    def to_dict(self) -> dict[str, Any]:
        return {
            "generated_from_runtime_commit": self.runtime_commit,
            "generated_from_package_version": self.package_version,
            "runtime_identity_kind": self.runtime_identity_kind.value,
        }
