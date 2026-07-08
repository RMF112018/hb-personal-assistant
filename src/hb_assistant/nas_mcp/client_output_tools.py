"""N8C-24 MCP handler surface for the connected-client generated-output workspace.

Ten ``pa_output_*`` tools: three controlled writes (stage/commit/archive_commit) behind the
``client_output_write_enabled()`` gate + server-minted approval + idempotency, and seven bounded reads.
None of the names contain a write-verb or finality substring; none joins ``ALL_ASSISTANT_TOOLS``. They are
gateway-reachable (via ``GATEWAY_ALLOWLIST``) but every write still passes the full broker gate chain.
"""

from __future__ import annotations

from typing import Any

from .client_output_workspace import ClientOutputError, ClientOutputWorkspaceRepository
from .config import NasMcpConfig

# Controlled writes (gated by client_output_write_enabled()); mirrors profile.CLIENT_OUTPUT_WRITE_TOOLS.
PA_OUTPUT_WRITE_TOOLS: tuple[str, ...] = ("pa_output_stage", "pa_output_commit", "pa_output_archive_commit")
# Bounded reads / advisory (never write the workspace).
PA_OUTPUT_READ_TOOLS: tuple[str, ...] = (
    "pa_output_list", "pa_output_metadata", "pa_output_read_excerpt", "pa_output_receipt_get",
    "pa_output_manifest_get", "pa_output_archive_plan", "pa_output_zip_inspect",
)
ALL_PA_OUTPUT_TOOLS: tuple[str, ...] = PA_OUTPUT_WRITE_TOOLS + PA_OUTPUT_READ_TOOLS
# The gateway-reachable non-canonical output section (operator-authorized gateway expansion).
CLIENT_OUTPUT_GATEWAY_TOOLS: frozenset[str] = frozenset(ALL_PA_OUTPUT_TOOLS)


def _require(a: dict[str, Any], key: str) -> Any:
    v = a.get(key)
    if v in (None, ""):
        raise ClientOutputError(f"missing_required_arg:{key}")
    return v


def dispatch_client_output_tool(config: NasMcpConfig, tool_name: str, arguments: dict[str, Any], *,
                                runtime_commit: str = "unknown") -> dict[str, Any]:
    repo = ClientOutputWorkspaceRepository(config, str(config.db_path))
    a = arguments or {}

    if tool_name == "pa_output_stage":
        return repo.stage_output_file(a)
    if tool_name == "pa_output_commit":
        return repo.commit_output_file(
            output_id=str(_require(a, "output_id")),
            operator_approval_id=str(_require(a, "operator_approval_id")),
            idempotency_key=a.get("idempotency_key"), operator_id=a.get("operator_id"))
    if tool_name == "pa_output_archive_commit":
        return repo.commit_archive_output(
            output_id=str(_require(a, "output_id")),
            operator_approval_id=str(_require(a, "operator_approval_id")))
    if tool_name == "pa_output_archive_plan":
        return repo.plan_archive_output(str(_require(a, "output_id")))
    if tool_name == "pa_output_list":
        return repo.list_output_files(status=a.get("status"), file_type=a.get("file_type"),
                                      source_session_id=a.get("source_session_id"),
                                      limit=int(a.get("limit", 50)))
    if tool_name == "pa_output_metadata":
        return repo.get_output_metadata(str(_require(a, "output_id")))
    if tool_name == "pa_output_read_excerpt":
        return repo.read_output_excerpt(str(_require(a, "output_id")), max_chars=int(a.get("max_chars", 4000)))
    if tool_name == "pa_output_receipt_get":
        r = repo.get_output_receipt(str(_require(a, "receipt_id")))
        if not r:
            raise ClientOutputError("receipt_not_found")
        return r
    if tool_name == "pa_output_manifest_get":
        return repo.get_output_manifest()
    if tool_name == "pa_output_zip_inspect":
        return repo.read_output_excerpt(str(_require(a, "output_id")))
    raise ClientOutputError(f"unknown_pa_output_tool:{tool_name}")


def client_output_status(config: NasMcpConfig) -> dict[str, Any]:
    """Status fields for hb_mcp_status. Never raises — reports missing/empty safely."""
    from .profile import client_output_write_enabled, safe_mode_enabled  # noqa: PLC0415

    root = config.roots.get("outputs") if config.roots else None
    md_rel, _ = ("99 Manifests/client-output-manifest.md", "")
    out = {
        "client_output_workspace_enabled": True,
        "client_output_write_enabled": client_output_write_enabled(),
        "client_output_root_configured": root is not None and root.mode == "read_write",
        "client_output_root_key": "outputs",
        "client_output_allowed_extensions": sorted(config.client_output_extensions),
        "client_output_max_file_bytes": config.max_client_output_file_bytes,
        "client_output_max_zip_members": config.max_client_output_zip_members,
        "client_output_max_zip_uncompressed_bytes": config.max_client_output_zip_uncompressed_bytes,
        "client_output_manifest_path": md_rel,
        "client_output_receipts_path": "99 Receipts",
        "client_output_pending_count": 0,
        "client_output_committed_count": 0,
        "client_output_last_write_at": None,
        "client_output_last_receipt_id": None,
        "client_output_safe_mode_blocked": safe_mode_enabled(),
    }
    try:
        counts = ClientOutputWorkspaceRepository(config, str(config.db_path)).status_counts()
        out.update({
            "client_output_pending_count": counts["pending_count"],
            "client_output_committed_count": counts["committed_count"],
            "client_output_last_write_at": counts["last_write_at"],
            "client_output_last_receipt_id": counts["last_receipt_id"],
        })
    except Exception:  # noqa: BLE001 — status must never crash if the table is absent/empty
        pass
    return out
