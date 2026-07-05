"""Deny-first broker for NAS MCP tools."""

from __future__ import annotations

import time
import uuid
from typing import Any

from .audit import NasMcpAuditWriter
from .config import NasMcpConfig
from .db_allowlist import list_allowlisted_table_keys
from .db_tools import DbSelectError, hb_db_select
from .fs_tools import (
    FsToolError,
    hb_secure_list,
    hb_secure_read_excerpt,
    hb_secure_stat,
    hb_vault_read_excerpt,
    hb_vault_search,
)
from .obsidian_adapter import (
    NAS_OBSIDIAN_BLOCKED,
    dispatch_obsidian_tool,
    list_nas_obsidian_tool_names,
)
from .output_tools import (
    hb_output_create_dir,
    hb_output_list,
    hb_output_read,
    hb_output_stat,
    hb_output_write_file,
)
from .path_safe import PathAccessError
from .profile import AI_OUTPUTS_WRITE_TOOL, blocked_write_tools, gate_status
from .root_policy import RootPolicyError
from .root_tools import (
    hb_root_list,
    hb_root_read_excerpt,
    hb_root_read_file,
    hb_root_search,
    hb_root_stat,
)

DENIED_TOOL_NAMES = frozenset({"raw_sql", "sql", "shell", "exec", "read_file_absolute", "hb_output_delete"})

OBSIDIAN_WRITE_TOOLS = frozenset(
    {
        "create_note",
        "patch_note",
        "vault_update_frontmatter",
        "vault_create_note_from_template",
        "vault_append_to_daily_note",
    }
)


class NasMcpBroker:
    def __init__(self, config: NasMcpConfig) -> None:
        self._config = config
        self._audit = NasMcpAuditWriter(config.audit_dir)

    def dispatch(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        request_id = uuid.uuid4().hex
        root_key = str(arguments.get("root_key") or ("vault" if tool_name in list_nas_obsidian_tool_names() else ""))
        relative_path = str(arguments.get("relative_path") or arguments.get("path") or ".")
        write_attempted = (
            tool_name in OBSIDIAN_WRITE_TOOLS
            or tool_name.startswith("hb_output_")
            or tool_name == AI_OUTPUTS_WRITE_TOOL
        )
        base_audit = {
            "request_id": request_id,
            "tool_name": tool_name,
            "actor": self._config.actor,
            "nas_readonly": True,
            "root_key": root_key or None,
            "relative_path": relative_path,
            "operation": tool_name,
            "write_attempted": write_attempted,
        }
        if tool_name in DENIED_TOOL_NAMES:
            return self._deny(base_audit, "action_denied_by_policy", started)
        if tool_name in blocked_write_tools():
            return self._deny(base_audit, f"write_tool_blocked_by_profile:{tool_name}", started)
        try:
            result = self._invoke(tool_name, arguments)
        except (DbSelectError, FsToolError, PathAccessError, RootPolicyError, KeyError, ValueError, TypeError) as exc:
            return self._deny(base_audit, str(exc), started)
        duration_ms = int((time.perf_counter() - started) * 1000)
        audit = {
            **base_audit,
            "decision": "allow",
            "duration_ms": duration_ms,
            "access_mode": self._access_mode(tool_name),
            "write_allowed": write_attempted,
            "rows_returned": result.get("row_count", result.get("entry_count", result.get("match_count"))),
            "bytes_returned": result.get("bytes_returned", result.get("bytes_written")),
            "redaction_applied": result.get("redaction_applied", False),
            "limit_applied": result.get("limit_applied"),
            "file_type": result.get("file_type"),
            "overwrite_requested": arguments.get("overwrite"),
            "overwrite_applied": result.get("overwrite_applied"),
            "created_dirs": result.get("created"),
            "sha256_prefix": result.get("sha256_prefix"),
        }
        self._audit.write(audit)
        return {"ok": True, "tool": tool_name, "result": result, "request_id": request_id}

    @staticmethod
    def _access_mode(tool_name: str) -> str:
        if (
            tool_name in OBSIDIAN_WRITE_TOOLS
            or tool_name.startswith("hb_output_write")
            or tool_name == "hb_output_create_dir"
            or tool_name == AI_OUTPUTS_WRITE_TOOL
        ):
            return "write"
        return "read"

    def _deny(self, base: dict[str, Any], reason: str, started: float) -> dict[str, Any]:
        duration_ms = int((time.perf_counter() - started) * 1000)
        event = {
            **base,
            "decision": "deny",
            "deny_reason": reason,
            "duration_ms": duration_ms,
            "write_allowed": False,
        }
        self._audit.write(event)
        return {"ok": False, "tool": base["tool_name"], "error": reason, "request_id": base["request_id"]}

    def _invoke(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        cfg = self._config
        if tool_name == "hb_mcp_status":
            obsidian_names = set(list_nas_obsidian_tool_names())
            profile_blocked = blocked_write_tools()
            enabled = sorted((obsidian_names - set(NAS_OBSIDIAN_BLOCKED.keys())) - profile_blocked)
            blocked = sorted(set(NAS_OBSIDIAN_BLOCKED.keys()) | (profile_blocked & obsidian_names))
            return {
                "mode": "nas_mcp_surface",
                "allowlisted_table_keys": list_allowlisted_table_keys(),
                "configured_roots": {k: v.mode for k, v in cfg.roots.items()},
                "obsidian_tools_enabled": enabled,
                "obsidian_tools_blocked": blocked,
                "exposure_profile": gate_status(),
                "blocked_write_tools": sorted(profile_blocked),
                "port_policy": "127.0.0.1:8765 host publish only",
            }
        if tool_name == AI_OUTPUTS_WRITE_TOOL:
            from .ai_outputs import ai_outputs_card_upsert  # noqa: PLC0415

            return ai_outputs_card_upsert(
                config=cfg,
                title=str(arguments.get("title", "")),
                body_markdown=str(arguments.get("body_markdown", "")),
                tags=list(arguments.get("tags") or []),
                source_client=str(arguments.get("source_client", "unknown")),
                expected_sha=arguments.get("expected_sha"),
                mode=str(arguments.get("mode", "create")),
            )
        if tool_name == "hb_db_select":
            return hb_db_select(
                config=cfg,
                table_key=str(arguments["table_key"]),
                columns=list(arguments["columns"]),
                filters=arguments.get("filters") or {},
                order_by=arguments.get("order_by"),
                limit=arguments.get("limit"),
            )
        if tool_name == "hb_secure_list":
            return hb_secure_list(
                config=cfg,
                root_key=str(arguments["root_key"]),
                relative_path=str(arguments.get("relative_path", ".")),
                max_entries=arguments.get("max_entries"),
            )
        if tool_name == "hb_secure_stat":
            return hb_secure_stat(config=cfg, root_key=str(arguments["root_key"]), relative_path=str(arguments["relative_path"]))
        if tool_name == "hb_secure_read_excerpt":
            return hb_secure_read_excerpt(
                config=cfg,
                root_key=str(arguments["root_key"]),
                relative_path=str(arguments["relative_path"]),
                max_bytes=arguments.get("max_bytes"),
            )
        if tool_name == "hb_vault_search":
            return hb_vault_search(
                config=cfg,
                query=str(arguments["query"]),
                relative_path=str(arguments.get("relative_path", ".")),
                limit=int(arguments.get("limit", 25)),
            )
        if tool_name == "hb_vault_read_excerpt":
            return hb_vault_read_excerpt(
                config=cfg,
                relative_path=str(arguments["relative_path"]),
                max_bytes=arguments.get("max_bytes"),
            )
        if tool_name == "hb_root_list":
            return hb_root_list(
                config=cfg,
                root_key=str(arguments["root_key"]),
                relative_path=str(arguments.get("relative_path", ".")),
                max_entries=arguments.get("max_entries"),
            )
        if tool_name == "hb_root_stat":
            return hb_root_stat(config=cfg, root_key=str(arguments["root_key"]), relative_path=str(arguments["relative_path"]))
        if tool_name == "hb_root_search":
            return hb_root_search(
                config=cfg,
                root_key=str(arguments["root_key"]),
                query=str(arguments["query"]),
                relative_path=str(arguments.get("relative_path", ".")),
                limit=int(arguments.get("limit", 25)),
            )
        if tool_name == "hb_root_read_excerpt":
            return hb_root_read_excerpt(
                config=cfg,
                root_key=str(arguments["root_key"]),
                relative_path=str(arguments["relative_path"]),
                max_bytes=arguments.get("max_bytes"),
            )
        if tool_name == "hb_root_read_file":
            return hb_root_read_file(
                config=cfg,
                root_key=str(arguments["root_key"]),
                relative_path=str(arguments["relative_path"]),
                max_chars=arguments.get("max_chars"),
            )
        if tool_name == "hb_output_list":
            return hb_output_list(config=cfg, relative_path=str(arguments.get("relative_path", ".")), max_entries=arguments.get("max_entries"))
        if tool_name == "hb_output_stat":
            return hb_output_stat(config=cfg, relative_path=str(arguments["relative_path"]))
        if tool_name == "hb_output_read":
            return hb_output_read(config=cfg, relative_path=str(arguments["relative_path"]), max_chars=arguments.get("max_chars"))
        if tool_name == "hb_output_write_file":
            return hb_output_write_file(
                config=cfg,
                relative_path=str(arguments["relative_path"]),
                content=str(arguments["content"]),
                overwrite=bool(arguments.get("overwrite", False)),
            )
        if tool_name == "hb_output_create_dir":
            return hb_output_create_dir(config=cfg, relative_path=str(arguments["relative_path"]))
        if tool_name in list_nas_obsidian_tool_names() or tool_name in NAS_OBSIDIAN_BLOCKED:
            return dispatch_obsidian_tool(cfg, tool_name, arguments)
        raise KeyError(f"tool_not_registered: {tool_name}")
