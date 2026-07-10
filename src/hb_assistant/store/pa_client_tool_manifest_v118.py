"""V118 — expand client tool manifest persistence for independent semantic freshness.

Additive columns on ``pa_client_tool_manifests`` only. Existing rows remain readable
(schema 0 / null payload → indeterminate semantic categories, not false current).
"""

from __future__ import annotations

V118_CLIENT_TOOL_MANIFEST_STATEMENTS: list[str] = [
    # SQLite ADD COLUMN is idempotent-safe when guarded by migrator version row.
    "ALTER TABLE pa_client_tool_manifests ADD COLUMN manifest_schema_version INTEGER NOT NULL DEFAULT 0",
    "ALTER TABLE pa_client_tool_manifests ADD COLUMN manifest_payload_json TEXT",
    "ALTER TABLE pa_client_tool_manifests ADD COLUMN semantic_surface_checksum TEXT",
    "ALTER TABLE pa_client_tool_manifests ADD COLUMN exposure_checksum TEXT",
    "ALTER TABLE pa_client_tool_manifests ADD COLUMN gateway_checksum TEXT",
    "ALTER TABLE pa_client_tool_manifests ADD COLUMN surface_profile TEXT",
    "ALTER TABLE pa_client_tool_manifests ADD COLUMN gate_state_snapshot_json TEXT",
    "ALTER TABLE pa_client_tool_manifests ADD COLUMN generated_from_package_version TEXT",
    "ALTER TABLE pa_client_tool_manifests ADD COLUMN runtime_identity_kind TEXT",
]
