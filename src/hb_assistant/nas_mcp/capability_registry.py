"""Canonical, immutable MCP capability registry and startup-static public profiles.

The embedded definitions are a lossless representation of the operator-authorized
Batch 1 normative matrix. Runtime consumers derive membership and policy sets from
this module; enforcement remains in the broker, origin-auth, safe-mode, scope, path,
and feature-gate layers.
"""

from __future__ import annotations

import csv
import hashlib
import io
import os
import re
from collections.abc import Mapping
from dataclasses import dataclass
from enum import StrEnum
from functools import lru_cache
from types import MappingProxyType

from .capability_registry_data import MATRIX_CSV, MATRIX_SHA256

CAPABILITY_PROFILE_ENV = "HB_MCP_CAPABILITY_PROFILE"
HANDLER_SOURCE_DECLARATION = (
    "src/hb_assistant/nas_mcp/tool_registration/register_nas_mcp_tools.py"
)
GENERATED_OBSIDIAN_HANDLER_SYMBOL = "_make_obsidian_tool.<locals>._obsidian_tool"
_PROMPT_PREFLIGHT_COMPATIBILITY_EXCLUSIONS = frozenset(
    {
        "hb_assistant_catalog",
        "hb_assistant_tool_help",
        "hb_capability_mode",
        "hb_data_freshness",
        "hb_mcp_status",
    }
)


class Authorization(StrEnum):
    READ_ONLY = "read_only"
    CONTROLLED_WRITE = "controlled_write"
    CANONICAL_WRITE = "canonical_write"
    ADMINISTRATIVE = "administrative"
    INTERNAL = "internal"
    PROHIBITED = "prohibited"


class SideEffect(StrEnum):
    READ_ONLY = "read_only"
    STAGED_WRITE = "staged_write"
    CANONICAL_WRITE = "canonical_write"
    ADMIN_WRITE = "admin_write"
    WRITE_PROXY = "write_proxy"


class Exposure(StrEnum):
    DIRECT = "direct"
    GATEWAY = "gateway"
    NONE = "none"


class Lifecycle(StrEnum):
    ACTIVE = "active"
    COMPATIBILITY = "compatibility"
    LEGACY = "legacy"
    DEPRECATED_ALIAS = "deprecated_alias"
    INTERNAL = "internal"


class CapabilityProfile(StrEnum):
    FRONTIER_V1 = "frontier-v1"
    LEGACY_V12 = "legacy-v12"
    INTERNAL = "internal"


@dataclass(frozen=True, slots=True)
class CapabilityDefinition:
    registered_name: str
    semantic_capability_id: str
    capability_version: str
    handler_module: str
    handler_symbol: str
    schema_provider: str
    authorization_class: Authorization
    side_effect_class: SideEffect
    direct_exposure: bool
    gateway_exposure: bool
    profile_membership: tuple[CapabilityProfile, ...]
    group: str
    feature_gate: str | None
    lifecycle_status: Lifecycle
    alias_status: str
    alias_target: str | None
    deprecation_status: str
    replacement: str | None
    description_authority: str
    result_bounds: str
    attestation_probes: tuple[str, ...]
    exact_test_node_ids: tuple[str, ...]
    indirect_test_node_ids: tuple[str, ...]
    compatibility_disposition: str
    planning_rationale: str
    source_evidence: tuple[str, ...]

    @property
    def exposures(self) -> frozenset[Exposure]:
        values: set[Exposure] = set()
        if self.direct_exposure:
            values.add(Exposure.DIRECT)
        if self.gateway_exposure:
            values.add(Exposure.GATEWAY)
        return frozenset(values or {Exposure.NONE})

    @property
    def schema_sha256(self) -> str:
        match = re.fullmatch(r"live FastMCP schema hash:([0-9a-f]{64})", self.schema_provider)
        return match.group(1) if match else ""

    @property
    def is_alias(self) -> bool:
        return self.alias_status == "alias"


@dataclass(frozen=True, slots=True)
class CapabilityRegistry:
    definitions: tuple[CapabilityDefinition, ...]

    @property
    def by_name(self) -> Mapping[str, CapabilityDefinition]:
        return MappingProxyType({item.registered_name: item for item in self.definitions})

    def get(self, name: str) -> CapabilityDefinition | None:
        return self.by_name.get(name)


# Generated matrix bytes are imported from a non-authoritative, reviewable module.
def _split(value: str) -> tuple[str, ...]:
    return tuple(item for item in value.split(";") if item)


def _optional(value: str) -> str | None:
    return None if not value or value == "none" else value


def _bool(value: str) -> bool:
    if value not in {"true", "false"}:
        raise ValueError(f"invalid matrix boolean: {value!r}")
    return value == "true"


def _matrix_bytes() -> bytes:
    payload = MATRIX_CSV.encode("utf-8")
    digest = hashlib.sha256(payload).hexdigest()
    if digest != MATRIX_SHA256:
        raise RuntimeError(f"capability matrix identity mismatch: {digest}")
    return payload


def _definition(row: Mapping[str, str]) -> CapabilityDefinition:
    return CapabilityDefinition(
        registered_name=row["registered_name"],
        semantic_capability_id=row["semantic_capability_id"],
        capability_version=row["capability_version"],
        handler_module=row["handler_module"],
        handler_symbol=row["handler_symbol"],
        schema_provider=row["schema_provider"],
        authorization_class=Authorization(row["authorization_class"]),
        side_effect_class=SideEffect(row["side_effect_class"]),
        direct_exposure=_bool(row["direct_exposure"]),
        gateway_exposure=_bool(row["gateway_exposure"]),
        profile_membership=tuple(
            CapabilityProfile(item) for item in _split(row["profile_membership"])
        ),
        group=row["group"],
        feature_gate=_optional(row["feature_gate"]),
        lifecycle_status=Lifecycle(row["lifecycle_status"]),
        alias_status=row["alias_status"],
        alias_target=_optional(row["alias_target"]),
        deprecation_status=row["deprecation_status"],
        replacement=_optional(row["replacement"]),
        description_authority=row["description_authority"],
        result_bounds=row["result_bounds"],
        attestation_probes=_split(row["attestation_probes"]),
        exact_test_node_ids=_split(row["exact_test_node_ids"]),
        indirect_test_node_ids=_split(row["indirect_test_node_ids"]),
        compatibility_disposition=row["compatibility_disposition"],
        planning_rationale=row["planning_rationale"],
        source_evidence=_split(row["source_evidence"]),
    )


@lru_cache(maxsize=1)
def build_capability_registry() -> CapabilityRegistry:
    text = _matrix_bytes().decode("utf-8")
    definitions = tuple(
        sorted(
            (_definition(row) for row in csv.DictReader(io.StringIO(text))),
            key=lambda item: item.registered_name,
        )
    )
    registry = CapabilityRegistry(definitions)
    validate_registry(registry)
    return registry


def resolve_profile(name: str | CapabilityProfile | None = None) -> CapabilityProfile:
    if isinstance(name, CapabilityProfile):
        return name
    selected = (name if name is not None else os.environ.get(CAPABILITY_PROFILE_ENV, "")).strip()
    selected = selected or CapabilityProfile.FRONTIER_V1.value
    try:
        return CapabilityProfile(selected)
    except ValueError as exc:
        raise ValueError(f"invalid MCP capability profile: {selected!r}") from exc


def _gate_enabled(gate: str | None, environment: Mapping[str, bool] | None) -> bool:
    if gate is None:
        return True
    if environment is not None and gate in environment:
        return bool(environment[gate])
    value = os.environ.get(gate)
    return value is None or value.strip() != "0"


def definitions_for_profile(
    profile: str | CapabilityProfile,
    environment: Mapping[str, bool] | None = None,
) -> tuple[CapabilityDefinition, ...]:
    resolved = resolve_profile(profile)
    return tuple(
        item
        for item in build_capability_registry().definitions
        if resolved in item.profile_membership and _gate_enabled(item.feature_gate, environment)
    )


def gateway_names_for_profile(
    profile: str | CapabilityProfile,
    environment: Mapping[str, bool] | None = None,
) -> frozenset[str]:
    return frozenset(
        item.registered_name
        for item in definitions_for_profile(profile, environment)
        if item.gateway_exposure
    )


def prompt_preflight_compatibility_names() -> frozenset[str]:
    """Return the context-free historical tool surface used by prompt preflight.

    This compatibility contract is static registry metadata. It intentionally
    does not consult the selected runtime profile, feature gates, or broker.
    Explicit startup-pinned surface inputs remain authoritative when supplied.
    """
    return frozenset(
        item.registered_name
        for item in build_capability_registry().definitions
        if item.gateway_exposure
        and CapabilityProfile.LEGACY_V12 in item.profile_membership
        and item.registered_name not in _PROMPT_PREFLIGHT_COMPATIBILITY_EXCLUSIONS
    )


def direct_names_for_profile(
    profile: str | CapabilityProfile,
    environment: Mapping[str, bool] | None = None,
) -> frozenset[str]:
    """Exact FastMCP direct set for one profile.

    ``legacy-v12`` intentionally retains every selected member as an explicit
    compatibility exception. Frontier and internal profiles honor the matrix
    ``direct_exposure`` field.
    """
    resolved = resolve_profile(profile)
    definitions = definitions_for_profile(resolved, environment)
    if resolved is CapabilityProfile.LEGACY_V12:
        return frozenset(item.registered_name for item in definitions)
    return frozenset(item.registered_name for item in definitions if item.direct_exposure)


def validate_registry(registry: CapabilityRegistry) -> None:
    definitions = registry.definitions
    names = [item.registered_name for item in definitions]
    if names != sorted(names):
        raise ValueError("capability definitions must be sorted by registered name")
    if len(names) != len(set(names)):
        raise ValueError("duplicate registered capability name")
    by_name = {item.registered_name: item for item in definitions}
    canonical_by_identity: dict[tuple[str, str], CapabilityDefinition] = {}
    for item in definitions:
        if not item.handler_module or not item.handler_symbol:
            raise ValueError(f"missing handler binding: {item.registered_name}")
        if item.handler_module != HANDLER_SOURCE_DECLARATION:
            raise ValueError(f"invalid handler module: {item.registered_name}")
        if item.handler_symbol not in {
            item.registered_name,
            GENERATED_OBSIDIAN_HANDLER_SYMBOL,
        }:
            raise ValueError(f"invalid handler symbol: {item.registered_name}")
        if not item.schema_sha256:
            raise ValueError(f"invalid schema provider: {item.registered_name}")
        if item.authorization_class is Authorization.PROHIBITED and (
            item.direct_exposure or item.gateway_exposure
        ):
            raise ValueError(f"prohibited capability exposed: {item.registered_name}")
        if (
            item.lifecycle_status is Lifecycle.INTERNAL
            and CapabilityProfile.FRONTIER_V1 in item.profile_membership
        ):
            raise ValueError(f"internal capability in frontier-v1: {item.registered_name}")
        if item.feature_gate is not None and not item.feature_gate.startswith("HB_MCP_"):
            raise ValueError(f"invalid feature gate: {item.registered_name}")
        if (
            item.lifecycle_status is Lifecycle.ACTIVE
            and CapabilityProfile.FRONTIER_V1 not in item.profile_membership
        ):
            raise ValueError(f"active capability missing frontier-v1: {item.registered_name}")
        if (
            item.lifecycle_status is Lifecycle.DEPRECATED_ALIAS
            and CapabilityProfile.FRONTIER_V1 in item.profile_membership
        ):
            raise ValueError(f"deprecated alias in frontier-v1: {item.registered_name}")
        identity = (item.semantic_capability_id, item.capability_version)
        if not item.is_alias:
            prior = canonical_by_identity.get(identity)
            if prior is not None:
                raise ValueError(f"duplicate semantic capability identity: {identity}")
            canonical_by_identity[identity] = item
        if item.is_alias:
            if not item.alias_target or item.alias_target not in by_name:
                raise ValueError(f"invalid alias target: {item.registered_name}")
            if item.lifecycle_status is not Lifecycle.DEPRECATED_ALIAS:
                raise ValueError(f"alias lifecycle mismatch: {item.registered_name}")
            if not item.replacement:
                raise ValueError(f"alias missing replacement metadata: {item.registered_name}")
    for item in definitions:
        seen: set[str] = set()
        current = item
        while current.is_alias:
            if current.registered_name in seen:
                raise ValueError(f"alias cycle: {item.registered_name}")
            seen.add(current.registered_name)
            current = by_name[current.alias_target or ""]
    if len(definitions) != 185:
        raise ValueError(f"expected 185 capability definitions, found {len(definitions)}")


__all__ = [
    "Authorization",
    "CapabilityDefinition",
    "CapabilityProfile",
    "CapabilityRegistry",
    "Exposure",
    "Lifecycle",
    "SideEffect",
    "build_capability_registry",
    "definitions_for_profile",
    "direct_names_for_profile",
    "gateway_names_for_profile",
    "prompt_preflight_compatibility_names",
    "resolve_profile",
    "validate_registry",
]
