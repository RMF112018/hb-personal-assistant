"""F-017 — disambiguating tool help for audit-called tools and manifest rendering."""

from __future__ import annotations

import os
import tempfile

import pytest

from hb_assistant.obsidian_mcp.canonical_tool_specs import (
    AUDIT_HELP_TOOL_NAMES,
    GENERIC_FAMILY_PURPOSES,
    MANIFEST_PURPOSE_MAX_LEN,
    normalize_manifest_purpose,
    purpose_is_complete,
    resolve_tool_spec,
    tool_spec_public_entry,
)
from hb_assistant.nas_mcp.tool_registration import _TOOL_TO_GROUP
from hb_assistant.nas_mcp.config import NasMcpConfig
from hb_assistant.nas_mcp.live_tool_surface import build_tool_index
from hb_assistant.nas_mcp.tool_registration import _assistant_tool_meta
from hb_assistant.store.migrator import SQLiteMigrator


def _test_config() -> NasMcpConfig:
    d = tempfile.mkdtemp()
    db = os.path.join(d, "t.db")
    SQLiteMigrator(db_path=db).apply()
    return NasMcpConfig.from_mapping({"db_path": db, "roots": {"outputs": {"path": d, "mode": "read_write"}}})


@pytest.mark.parametrize("tool_name", sorted(AUDIT_HELP_TOOL_NAMES))
def test_audit_tools_have_complete_non_generic_purpose(tool_name: str) -> None:
    spec = resolve_tool_spec(tool_name, _TOOL_TO_GROUP.get(tool_name))
    purpose = str(spec.purpose or "").strip()
    assert purpose, tool_name
    assert purpose_is_complete(purpose), (tool_name, purpose)
    assert purpose not in GENERIC_FAMILY_PURPOSES, (tool_name, purpose)


@pytest.mark.parametrize("tool_name", sorted(AUDIT_HELP_TOOL_NAMES - {"hb_assistant_tool_help"}))
def test_audit_tools_have_at_least_one_example(tool_name: str) -> None:
    group = _TOOL_TO_GROUP.get(tool_name)
    entry = tool_spec_public_entry(tool_name, group)
    examples = list(entry.get("examples") or entry.get("preferred_for") or [])
    assert examples, tool_name


def test_normalize_manifest_purpose_caps_at_sentence_boundary() -> None:
    long = "Search indexed NAS source files by name or topic before reading file bodies. " * 5
    capped = normalize_manifest_purpose(long)
    assert len(capped) <= MANIFEST_PURPOSE_MAX_LEN
    assert purpose_is_complete(capped)
    assert "…" not in capped and "[truncated]" not in capped.lower()


def test_manifest_audit_tools_have_bounded_complete_purposes_and_examples() -> None:
    from hb_assistant.obsidian_mcp.client_tool_manifest import build_manifest

    cfg = _test_config()
    idx = build_tool_index(cfg, for_manifest=True)
    manifest = build_manifest(idx, runtime_commit="vT", now="2026-07-10T00:00:00+00:00")
    by_name = {e["tool_name"]: e for e in manifest["entries"]}
    for tool_name in sorted(AUDIT_HELP_TOOL_NAMES - {"hb_assistant_tool_help"}):
        entry = by_name.get(tool_name)
        assert entry is not None, tool_name
        purpose = str(entry.get("purpose") or "").strip()
        assert purpose_is_complete(purpose), (tool_name, purpose)
        assert len(purpose) <= MANIFEST_PURPOSE_MAX_LEN
        examples = list(entry.get("examples") or entry.get("preferred_for") or [])
        assert examples, tool_name


def test_hb_assistant_tool_help_exposes_example_prompts_for_audit_tool() -> None:
    meta = _assistant_tool_meta("assistant_source_file_search", {})
    assert meta.get("examples") or meta.get("example_prompts")
    assert purpose_is_complete(str(meta.get("purpose") or ""))