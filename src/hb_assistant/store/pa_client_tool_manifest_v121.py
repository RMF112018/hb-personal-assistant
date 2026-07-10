"""V121 — persist normalized gateway allowlist on promoted manifests.

Enables independent gateway-scope freshness checks (not checksum-only).
"""

from __future__ import annotations

V121_CLIENT_TOOL_MANIFEST_STATEMENTS: list[str] = [
    "ALTER TABLE pa_client_tool_manifests ADD COLUMN gateway_allowlist_json TEXT",
]