"""Deny-first broker for NAS MCP tools."""

from __future__ import annotations

import time
import uuid
from typing import Any, Callable

from .audit import NasMcpAuditWriter
from .config import NasMcpConfig
from .db_allowlist import list_allowlisted_table_keys
from .db_tools import DbSelectError, hb_db_select
from .fs_tools import (
    FsToolError,
    hb_secure_list,
    hb_secure_read_excerpt,
    hb_secure_stat,
    hb_source_root_read_excerpt,
    hb_source_root_search,
    hb_vault_read_excerpt,
    hb_vault_search,
)
from .path_safe import PathAccessError

ToolFn = Callable[..., dict[str, Any]]

DENIED_TOOL_NAMES = frozenset({"raw_sql", "sql", "shell", "exec", "read_file_absolute"})


class NasMcpBroker:
    def __init__(self, config: NasMcpConfig) -> None:
        self._config = config
        self._audit = NasMcpAuditWriter(config.audit_dir)

    def dispatch(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        started = time.perf_counter()
        request_id = uuid.uuid4().hex
        base_audit = {
            "request_id": request_id,
            "tool_name": tool_name,
            "actor": self._config.actor,
            "nas_readonly": True,
        }
        if tool_name in DENIED_TOOL_NAMES:
            return self._deny(base_audit, "action_denied_by_policy", started)
        try:
            result = self._invoke(tool_name, arguments)
        except (DbSelectError, FsToolError, PathAccessError, KeyError, ValueError, TypeError) as exc:
            return self._deny(base_audit, str(exc), started)
        duration_ms = int((time.perf_counter() - started) * 1000)
        audit = {
            **base_audit,
            "decision": "allow",
            "duration_ms": duration_ms,
            "rows_returned": result.get("row_count", result.get("entry_count", result.get("match_count"))),
            "bytes_returned": result.get("bytes_returned"),
            "redaction_applied": result.get("redaction_applied", False),
            "limit_applied": result.get("limit_applied"),
        }
        self._audit.write(audit)
        return {"ok": True, "tool": tool_name, "result": result, "request_id": request_id}

    def _deny(self, base: dict[str, Any], reason: str, started: float) -> dict[str, Any]:
        duration_ms = int((time.perf_counter() - started) * 1000)
        event = {**base, "decision": "deny", "deny_reason": reason, "duration_ms": duration_ms}
        self._audit.write(event)
        return {"ok": False, "tool": base["tool_name"], "error": reason, "request_id": base["request_id"]}

    def _invoke(self, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        cfg = self._config
        if tool_name == "hb_mcp_status":
            return {
                "mode": "nas_readonly",
                "allowlisted_table_keys": list_allowlisted_table_keys(),
                "configured_roots": sorted(cfg.roots.keys()),
                "port_policy": "127.0.0.1:8765 host publish only",
            }
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
        if tool_name == "hb_source_root_search":
            return hb_source_root_search(
                config=cfg,
                query=str(arguments["query"]),
                root_key=str(arguments.get("root_key", "syn-work")),
                relative_path=str(arguments.get("relative_path", ".")),
                limit=int(arguments.get("limit", 25)),
            )
        if tool_name == "hb_source_root_read_excerpt":
            return hb_source_root_read_excerpt(
                config=cfg,
                relative_path=str(arguments["relative_path"]),
                root_key=str(arguments.get("root_key", "syn-work")),
                max_bytes=arguments.get("max_bytes"),
            )
        raise KeyError(f"tool_not_registered: {tool_name}")
