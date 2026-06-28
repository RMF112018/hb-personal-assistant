"""Backend-managed service facade for the UI Obsidian MCP surface."""

from __future__ import annotations

import importlib.util
import socket
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from .config import ObsidianMcpConfig, ObsidianMcpConfigPatch, apply_patch, load_config
from .mutations import (
    create_note,
    patch_note,
    recent_mutations,
    write_readiness,
)
from .tools import (
    ObsidianMcpToolError,
    list_directory,
    read_file,
    resolve_safe_path,
    search_vault,
    tool_registry,
)

_LAST_HEALTH: dict[str, Any] | None = None


def _now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


class ObsidianMcpService:
    """Application-backend service used by FastAPI routes and MCP handlers."""

    def get_config(self) -> ObsidianMcpConfig:
        return load_config()

    def update_config(self, patch: ObsidianMcpConfigPatch) -> dict[str, Any]:
        config, one_time_token = apply_patch(patch)
        payload = {"config": config.redacted(), "one_time_token": one_time_token}
        if one_time_token is None:
            payload.pop("one_time_token")
        return payload

    def status(self) -> dict[str, Any]:
        config = self.get_config()
        health = _LAST_HEALTH or self.health_check(persist=False)
        blocking = list(health.get("blocking_issues", []))
        sdk_ready = not any(issue.get("code") == "mcp_sdk_missing" for issue in blocking)
        running = bool(config.enabled and sdk_ready and not blocking)
        return {
            "surface": "settings.obsidian_mcp.status",
            "enabled": config.enabled,
            "service_state": "running" if running else ("stopped" if not config.enabled else "unavailable"),
            "mode": config.mode,
            "vault_root": config.vault_root,
            "endpoint_url": config.endpoint_url,
            "token_configured": config.token_configured,
            "tools_registered": len(tool_registry()),
            "writes_enabled": config.writes_enabled,
            "vault_markdown_write_enabled": config.vault_markdown_write_enabled,
            "write_policy": self.write_policy_summary(config),
            "recent_mutations": recent_mutations(5),
            "last_mutation": (recent_mutations(1) or [None])[-1],
            "last_health_check_at": health.get("checked_at"),
            "blocking_issues": blocking,
            "warnings": health.get("warnings", []),
            "guardrails": self.guardrails(),
        }

    def guardrails(self) -> dict[str, Any]:
        return {
            "ui_managed": True,
            "no_user_cli_required": True,
            "local_first": True,
            "filesystem_mode_default": True,
            "no_source_file_writes": True,
            "autonomous_markdown_writes_policy_gated": True,
            "no_per_write_approval": True,
            "tokens_redacted": True,
            "raw_note_content_redacted": True,
            "path_traversal_blocked": True,
        }

    def write_policy_summary(self, config: ObsidianMcpConfig | None = None) -> dict[str, Any]:
        cfg = config or self.get_config()
        return {
            "writes_enabled": cfg.writes_enabled,
            "vault_markdown_write_enabled": cfg.vault_markdown_write_enabled,
            "max_write_chars": cfg.max_write_chars,
            "write_requires_expected_sha256": cfg.write_requires_expected_sha256,
            "backup_before_replace": cfg.backup_before_replace,
            "create_parent_dirs_enabled": cfg.create_parent_dirs_enabled,
            "allow_full_vault_markdown_writes": cfg.allow_full_vault_markdown_writes,
            "protected_paths": cfg.protected_paths,
            "blocked_hidden_paths": cfg.blocked_hidden_paths,
            "allowed_write_file_types": cfg.allowed_write_file_types,
        }

    def health_check(self, *, persist: bool = True) -> dict[str, Any]:
        global _LAST_HEALTH

        config = self.get_config()
        blocking: list[dict[str, str]] = []
        warnings: list[dict[str, str]] = []
        checks: list[dict[str, Any]] = []

        def add(name: str, ok: bool, detail: str, *, blocker: str | None = None, warning: str | None = None) -> None:
            checks.append({"name": name, "status": "pass" if ok else "fail", "detail": detail})
            if not ok and blocker:
                blocking.append({"code": blocker, "detail": detail})
            if not ok and warning:
                warnings.append({"code": warning, "detail": detail})

        root = Path(config.vault_root).expanduser()
        add("vault_root_exists", root.exists(), "vault root exists" if root.exists() else "vault root not found", blocker="vault_root_missing")
        add("vault_root_readable", root.is_dir() and root.exists(), "vault root is readable" if root.is_dir() else "vault root is not a directory", blocker="vault_root_unreadable")
        try:
            resolve_safe_path(config, config.default_scope or "", must_exist=False)
            add("configured_scope_safe", True, "configured scope stays inside vault root")
        except ObsidianMcpToolError as exc:
            add("configured_scope_safe", False, exc.code, blocker=exc.code)

        add("pdf_dependency", importlib.util.find_spec("pdfplumber") is not None or importlib.util.find_spec("pypdf") is not None, "PDF extraction dependency available", blocker="pdf_dependency_missing")
        add("docx_dependency", importlib.util.find_spec("docx") is not None, "DOCX extraction dependency available", blocker="docx_dependency_missing")
        mcp_sdk_available = importlib.util.find_spec("mcp") is not None
        add("mcp_sdk", mcp_sdk_available, "MCP SDK available", blocker="mcp_sdk_missing")
        streamable_http_ready = False
        streamable_http_detail = "Streamable HTTP app can be initialized"
        if mcp_sdk_available:
            try:
                from .mcp_app import build_streamable_http_app

                build_streamable_http_app(self)
                streamable_http_ready = True
            except Exception as exc:
                streamable_http_detail = f"Streamable HTTP app unavailable: {type(exc).__name__}"
        add(
            "streamable_http_app",
            streamable_http_ready,
            streamable_http_detail,
            blocker="mcp_http_unavailable",
        )
        add("caps_configured", config.max_file_mb > 0 and config.max_result_chars > 0, "file/result caps configured", blocker="caps_invalid")
        add("tool_registry", len(tool_registry()) == 20, "twenty Obsidian MCP tools registered", blocker="tool_registry_invalid")
        add("http_port", self._port_available_or_self(config), "HTTP port is available or owned by backend", warning="port_unavailable")
        readiness = write_readiness(config)
        add("vault_writable", bool(readiness["vault_writable"]), "vault root is writable", warning="vault_not_writable")
        add("backup_writable", bool(readiness["backup_writable"]), "backup root is writable", warning="backup_root_not_writable")
        add(
            "write_policy_configured",
            config.max_write_chars > 0 and config.allowed_write_file_types == ["md"],
            "Markdown write policy configured",
            blocker="write_policy_invalid",
        )

        payload = {
            "surface": "settings.obsidian_mcp.health",
            "checked_at": _now(),
            "ok": not blocking,
            "checks": checks,
            "blocking_issues": blocking,
            "warnings": warnings,
            "config": config.redacted(),
            "write_policy": self.write_policy_summary(config),
            "write_readiness": readiness,
            "recent_mutations": recent_mutations(5),
            "guardrails": self.guardrails(),
        }
        if persist:
            _LAST_HEALTH = payload
        return payload

    def _port_available_or_self(self, config: ObsidianMcpConfig) -> bool:
        with socket.socket(socket.AF_INET, socket.SOCK_STREAM) as sock:
            sock.settimeout(0.2)
            return sock.connect_ex((config.host, config.port)) != 0

    def tools(self) -> dict[str, Any]:
        health = _LAST_HEALTH or self.health_check(persist=False)
        by_name = {
            check["name"]: check["status"]
            for check in health.get("checks", [])
            if str(check.get("name")).startswith(("tool", "streamable"))
        }
        entries = []
        for tool in tool_registry():
            entry = dict(tool)
            entry["last_validation_status"] = by_name.get("tool_registry", "not_run")
            entries.append(entry)
        return {"surface": "settings.obsidian_mcp.tools", "tools": entries, "guardrails": self.guardrails()}

    def lifecycle(self, action: str) -> dict[str, Any]:
        if action == "enable":
            config, _ = apply_patch(ObsidianMcpConfigPatch(enabled=True))
        elif action == "disable":
            config, _ = apply_patch(ObsidianMcpConfigPatch(enabled=False))
        elif action == "restart":
            config = self.get_config()
        else:
            raise ObsidianMcpToolError("unknown_lifecycle_action")
        health = self.health_check()
        return {
            "surface": f"settings.obsidian_mcp.{action}",
            "action": action,
            "config": config.redacted(),
            "status": self.status(),
            "health": health,
            "guardrails": self.guardrails(),
        }

    def grok_config(self) -> dict[str, Any]:
        config = self.get_config()
        headers = {"Authorization": "Bearer <configured-token>"} if config.token_configured else {}
        return {
            "surface": "settings.obsidian_mcp.grok_config",
            "server_name": "hb-obsidian-hybrid",
            "mcp_config": {
                "mcpServers": {
                    "hb-obsidian-hybrid": {
                        "type": "streamable-http",
                        "url": config.endpoint_url,
                        "headers": headers,
                    }
                }
            },
            "token_configured": config.token_configured,
            "token_value_returned": False,
            "guardrails": self.guardrails(),
        }

    def oauth_status(self, request_base: str | None = None) -> dict[str, Any]:
        from .oauth_store import (
            CLIENT_ID,
            SUPPORTED_SCOPES,
            TOKEN_AUTH_METHOD,
            grok_setup_values,
            recent_events,
        )

        config = self.get_config()
        base = (config.public_base_url or request_base or "").rstrip("/")
        endpoints = {
            "authorization_endpoint": f"{base}/oauth/authorize" if base else None,
            "token_endpoint": f"{base}/oauth/token" if base else None,
            "metadata_endpoint": f"{base}/.well-known/oauth-authorization-server" if base else None,
            "mcp_url": f"{base}/mcp" if base else None,
        }
        return {
            "surface": "settings.obsidian_mcp.oauth",
            "oauth_enabled": config.oauth_enabled,
            "public_base_url": config.public_base_url,
            "client_id": CLIENT_ID,
            "scopes_supported": list(SUPPORTED_SCOPES),
            "token_auth_method": TOKEN_AUTH_METHOD,
            "endpoints": endpoints,
            "grok_setup": grok_setup_values(base) if base else None,
            "recent_events": recent_events(20),
            "guardrails": self.guardrails(),
        }

    def list_directory(self, args: dict[str, Any]) -> dict[str, Any]:
        return list_directory(self.get_config(), **args)

    def search_vault(self, args: dict[str, Any]) -> dict[str, Any]:
        return search_vault(self.get_config(), **args)

    def read_file(self, args: dict[str, Any]) -> dict[str, Any]:
        return read_file(self.get_config(), **args)

    def create_note(self, args: dict[str, Any]) -> dict[str, Any]:
        return create_note(self.get_config(), **args)

    def patch_note(self, args: dict[str, Any]) -> dict[str, Any]:
        return patch_note(self.get_config(), **args)

    def vault_map(self, args: dict[str, Any]) -> dict[str, Any]:
        from .curation import vault_map

        return vault_map(self.get_config(), **args)

    def vault_summarize_note(self, args: dict[str, Any]) -> dict[str, Any]:
        from .summarize import summarize_note

        return summarize_note(self.get_config(), **args)

    def vault_summarize_folder(self, args: dict[str, Any]) -> dict[str, Any]:
        from .summarize import summarize_folder

        return summarize_folder(self.get_config(), **args)

    def vault_read_eml(self, args: dict[str, Any]) -> dict[str, Any]:
        from .eml import read_eml

        return read_eml(self.get_config(), **args)

    def vault_email_inventory(self, args: dict[str, Any]) -> dict[str, Any]:
        from .eml import email_inventory

        return email_inventory(self.get_config(), **args)

    def vault_parse_email(self, args: dict[str, Any]) -> dict[str, Any]:
        from .eml import parse_email

        return parse_email(self.get_config(), **args)

    def vault_read_frontmatter(self, args: dict[str, Any]) -> dict[str, Any]:
        from .frontmatter import read_frontmatter

        return read_frontmatter(self.get_config(), **args)

    def vault_update_frontmatter(self, args: dict[str, Any]) -> dict[str, Any]:
        from .frontmatter import update_frontmatter

        return update_frontmatter(self.get_config(), **args)

    def vault_search_by_properties(self, args: dict[str, Any]) -> dict[str, Any]:
        from .frontmatter import search_by_properties

        return search_by_properties(self.get_config(), **args)

    def vault_dataview_query(self, args: dict[str, Any]) -> dict[str, Any]:
        from .frontmatter import dataview_query

        return dataview_query(self.get_config(), **args)

    def vault_get_backlinks(self, args: dict[str, Any]) -> dict[str, Any]:
        from .graph import get_backlinks

        return get_backlinks(self.get_config(), **args)

    def vault_get_unlinked_mentions(self, args: dict[str, Any]) -> dict[str, Any]:
        from .graph import get_unlinked_mentions

        return get_unlinked_mentions(self.get_config(), **args)

    def vault_get_note_graph(self, args: dict[str, Any]) -> dict[str, Any]:
        from .graph import get_note_graph

        return get_note_graph(self.get_config(), **args)

    def vault_curation_plan(self, args: dict[str, Any]) -> dict[str, Any]:
        from .curation import build_curation_plan

        return build_curation_plan(self.get_config(), **args)

    def vault_curation_apply(self, args: dict[str, Any]) -> dict[str, Any]:
        from .curation import apply_curation_plan

        return apply_curation_plan(self.get_config(), **args)

    def curation_receipt(self, plan_id: str) -> dict[str, Any]:
        from . import plan_store

        return {
            "surface": "settings.obsidian_mcp.curation_receipt",
            "plan_id": plan_id,
            "receipt": plan_store.load_receipt(plan_id),
            "guardrails": self.guardrails(),
        }

    def mutations(self, limit: int = 20) -> dict[str, Any]:
        return {
            "surface": "settings.obsidian_mcp.mutations",
            "mutations": recent_mutations(limit),
            "guardrails": self.guardrails(),
        }

    def write_readiness(self) -> dict[str, Any]:
        payload = write_readiness(self.get_config())
        payload["guardrails"] = self.guardrails()
        return payload

    def write_smoke_test(self) -> dict[str, Any]:
        cfg = self.get_config()
        path = "MCP Write Smoke/hb-mcp-write-smoke.md"
        content = "# HB MCP Write Smoke\n\nThis managed note proves autonomous Markdown writes are configured.\n"
        result = create_note(
            cfg,
            path=path,
            content=content,
            overwrite=True,
            expected_sha256=_current_sha_or_empty(cfg, path),
            caller_surface="ui_test",
        )
        return {
            "surface": "settings.obsidian_mcp.write_smoke",
            "ok": True,
            "result": {k: v for k, v in result.items() if k != "event"} | {"event": result["event"]},
            "guardrails": self.guardrails(),
        }


def safe_tool_response(func: Any, args: dict[str, Any]) -> dict[str, Any]:
    try:
        return {"ok": True, "result": func(args)}
    except ObsidianMcpToolError as exc:
        return {"ok": False, "error_code": exc.code, "message": str(exc)}


def _current_sha_or_empty(config: ObsidianMcpConfig, path: str) -> str | None:
    from .mutations import sha256_file

    try:
        resolved = resolve_safe_path(config, path, must_exist=True)
    except ObsidianMcpToolError:
        return None
    return sha256_file(resolved.path) if resolved.path.is_file() else None
