from __future__ import annotations

import hashlib
import runpy
from dataclasses import FrozenInstanceError, replace
from pathlib import Path

import pytest

from hb_assistant.nas_mcp.capability_registry import (
    MATRIX_SHA256,
    CapabilityProfile,
    CapabilityRegistry,
    Lifecycle,
    build_capability_registry,
    validate_registry,
)
from hb_assistant.nas_mcp.capability_registry_data import MATRIX_CSV


def _registry_with(*items):
    return CapabilityRegistry(tuple(sorted(items, key=lambda item: item.registered_name)))


def test_authorized_matrix_builds_exact_immutable_registry() -> None:
    registry = build_capability_registry()
    assert MATRIX_SHA256 == "6f758afd1f46c3ef4a5c06763faf21b2e4d8a2c01ed347a52b96a18f6db3c08e"
    assert len(registry.definitions) == 185
    assert tuple(item.registered_name for item in registry.definitions) == tuple(
        sorted(item.registered_name for item in registry.definitions)
    )
    assert len(registry.by_name) == 185
    with pytest.raises(TypeError):
        registry.by_name["new"] = registry.definitions[0]  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        registry.definitions[0].group = "changed"  # type: ignore[misc]


def test_duplicate_registered_name_fails_closed() -> None:
    item = build_capability_registry().definitions[0]
    with pytest.raises(ValueError, match="duplicate registered"):
        validate_registry(CapabilityRegistry((item, item)))


def test_duplicate_non_alias_semantic_identity_fails_closed() -> None:
    a, b = [item for item in build_capability_registry().definitions if not item.is_alias][:2]
    b = replace(
        b, semantic_capability_id=a.semantic_capability_id, capability_version=a.capability_version
    )
    with pytest.raises(ValueError, match="duplicate semantic"):
        validate_registry(_registry_with(a, b))


def test_alias_cannot_hide_second_canonical_semantic_identity() -> None:
    canonical, second = [
        item for item in build_capability_registry().definitions if not item.is_alias
    ][:2]
    alias = next(item for item in build_capability_registry().definitions if item.is_alias)
    identity = (canonical.semantic_capability_id, canonical.capability_version)
    canonical = replace(canonical, registered_name="a_canonical", handler_symbol="a_canonical")
    alias = replace(
        alias,
        registered_name="b_alias",
        handler_symbol="b_alias",
        semantic_capability_id=identity[0],
        capability_version=identity[1],
        alias_target="a_canonical",
        replacement="a_canonical",
    )
    second = replace(
        second,
        registered_name="c_second_canonical",
        handler_symbol="c_second_canonical",
        semantic_capability_id=identity[0],
        capability_version=identity[1],
    )
    with pytest.raises(ValueError, match="duplicate semantic"):
        validate_registry(_registry_with(canonical, alias, second))


@pytest.mark.parametrize("field", ["handler_module", "handler_symbol"])
def test_missing_handler_binding_fails_closed(field: str) -> None:
    item = build_capability_registry().definitions[0]
    with pytest.raises(ValueError, match="missing handler"):
        validate_registry(_registry_with(replace(item, **{field: ""})))


@pytest.mark.parametrize(
    ("field", "value", "match"),
    [
        ("handler_module", "missing.module", "invalid handler module"),
        ("handler_symbol", "missing_symbol", "invalid handler symbol"),
    ],
)
def test_invalid_handler_declaration_fails_closed(field: str, value: str, match: str) -> None:
    item = build_capability_registry().definitions[0]
    with pytest.raises(ValueError, match=match):
        validate_registry(_registry_with(replace(item, **{field: value})))


def test_generated_registry_module_is_byte_identical_to_generator() -> None:
    root = Path(__file__).resolve().parents[1]
    generator = runpy.run_path(str(root / "scripts/generate_batch1_capability_registry.py"))
    expected = generator["render"](MATRIX_CSV.encode("utf-8"))
    generated_path = root / "src/hb_assistant/nas_mcp/capability_registry_data.py"
    assert expected == generated_path.read_bytes()
    assert hashlib.sha256(MATRIX_CSV.encode()).hexdigest() == MATRIX_SHA256


def test_missing_or_incompatible_schema_binding_fails_closed() -> None:
    item = build_capability_registry().definitions[0]
    with pytest.raises(ValueError, match="schema provider"):
        validate_registry(_registry_with(replace(item, schema_provider="missing")))


def test_invalid_alias_target_and_missing_replacement_fail_closed() -> None:
    alias = next(item for item in build_capability_registry().definitions if item.is_alias)
    with pytest.raises(ValueError, match="invalid alias target"):
        validate_registry(_registry_with(replace(alias, alias_target="not_registered")))
    target = build_capability_registry().by_name[alias.alias_target or ""]
    with pytest.raises(ValueError, match="missing replacement"):
        validate_registry(_registry_with(target, replace(alias, replacement=None)))


def test_alias_cycle_fails_closed() -> None:
    alias = next(item for item in build_capability_registry().definitions if item.is_alias)
    target = build_capability_registry().by_name[alias.alias_target or ""]
    target_alias = replace(
        target,
        alias_status="alias",
        alias_target=alias.registered_name,
        lifecycle_status=Lifecycle.DEPRECATED_ALIAS,
        replacement=alias.registered_name,
    )
    with pytest.raises(ValueError, match="alias cycle"):
        validate_registry(_registry_with(alias, target_alias))


def test_invalid_lifecycle_profile_and_feature_gate_fail_closed() -> None:
    item = next(
        item
        for item in build_capability_registry().definitions
        if item.lifecycle_status is Lifecycle.ACTIVE
    )
    with pytest.raises(ValueError, match="missing frontier"):
        validate_registry(
            _registry_with(replace(item, profile_membership=(CapabilityProfile.LEGACY_V12,)))
        )
    with pytest.raises(ValueError, match="invalid feature gate"):
        validate_registry(_registry_with(replace(item, feature_gate="UNSCOPED_GATE")))
