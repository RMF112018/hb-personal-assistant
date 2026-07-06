"""Deny-first broker for NAS MCP tools."""

from __future__ import annotations

import sqlite3
import time
import uuid
from typing import Any

from . import freshness, limits
from .audit import NasMcpAuditWriter
from .config import NasMcpConfig
from .db_allowlist import list_allowlisted_table_keys
from .db_tools import DbSelectError, _ro_uri, hb_db_select
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
from .origin_auth import get_auth_context
from .output_tools import (
    hb_output_create_dir,
    hb_output_list,
    hb_output_read,
    hb_output_stat,
    hb_output_write_file,
)
from .overrides import OverrideStore
from .path_safe import PathAccessError
from .profile import (
    AI_OUTPUTS_WRITE_TOOL,
    assistant_context_packs_enabled,
    assistant_memory_enabled,
    assistant_nav_enabled,
    blocked_write_tools,
    gate_status,
    safe_mode_enabled,
)
from .root_policy import RootPolicyError
from .root_tools import (
    hb_root_list,
    hb_root_read_excerpt,
    hb_root_read_file,
    hb_root_search,
    hb_root_stat,
)

DENIED_TOOL_NAMES = frozenset({"raw_sql", "sql", "shell", "exec", "read_file_absolute", "hb_output_delete"})

# N8C-3 read-only source/card/note navigation tools (reads only; never write). Operator-authorized to
# return complete content; served from a read-only DB snapshot with no live-DB fallback.
ASSISTANT_NAV_TOOLS = (
    "assistant_search_sources",
    "assistant_get_source",
    "assistant_get_card_for_source",
    "assistant_get_source_for_card",
    "assistant_search_cards",
    "assistant_get_card_state",
    "assistant_list_stale_cards",
    "assistant_list_duplicate_cards",
    "assistant_list_ambiguous_card_links",
    "assistant_recent_changes",
    "assistant_get_related_sources",
    "assistant_get_vault_note",
)

# N8C-6 read-only enrichment-review + context-pack tools (reads only; never write — the pack
# BUILD/apply path is CLI-only and never exposed remotely). Served from the same read-only DB
# snapshot as the nav tools. Gated independently by ``assistant_context_packs_enabled()``.
ASSISTANT_CONTEXT_PACK_TOOLS = (
    "assistant_list_context_packs",
    "assistant_get_context_pack",
    "assistant_get_context_pack_items",
    "assistant_list_enrichment_review_items",
)

# N8C-7 read-only memory-compiler tools (reads only; never write — the compile/apply path is
# CLI-only and never exposed remotely). Served from the same read-only DB snapshot as the nav /
# context-pack tools. Gated independently by ``assistant_memory_enabled()``.
ASSISTANT_MEMORY_TOOLS = (
    "assistant_list_memory_nodes",
    "assistant_get_memory_node",
    "assistant_get_memory_mentions",
    "assistant_get_memory_compilations",
)

OBSIDIAN_WRITE_TOOLS = frozenset(
    {
        "create_note",
        "patch_note",
        "vault_update_frontmatter",
        "vault_create_note_from_template",
        "vault_append_to_daily_note",
    }
)

# Read-only freshness/status tools (Tier 0) — always allowed (even in safe mode), never write.
FRESHNESS_TOOLS = frozenset(
    {"hb_data_freshness", "hb_queue_status", "hb_recent_failures", "hb_last_successful_runs", "hb_capability_mode"}
)


def _capability_tier(tool_name: str, write_attempted: bool) -> int:
    if tool_name in DENIED_TOOL_NAMES:
        return 5
    if tool_name in OBSIDIAN_WRITE_TOOLS or tool_name.startswith("hb_output_write") or tool_name == "hb_output_create_dir":
        return 4
    if tool_name == AI_OUTPUTS_WRITE_TOOL:
        return 3
    if tool_name in FRESHNESS_TOOLS or tool_name == "hb_mcp_status":
        return 0
    return 1


class NasMcpBroker:
    def __init__(self, config: NasMcpConfig) -> None:
        self._config = config
        self._audit = NasMcpAuditWriter(config.audit_dir)
        self._concurrency = limits.ConcurrencyLimiter(limits.max_concurrent_calls(config))
        self._override_store: OverrideStore | None = (
            OverrideStore(config.override_store_path) if config.override_store_path else None
        )

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
        auth = get_auth_context()
        client_label = auth.client_label if auth else "any"
        safe_mode = safe_mode_enabled()
        base_audit = {
            "request_id": request_id,
            "tool_name": tool_name,
            # Authenticated actor when a bearer identity is present (defense-in-depth
            # origin auth), else the static config actor (e.g. local trusted profile).
            "actor": auth.actor if auth else self._config.actor,
            "authenticated": auth is not None,
            "client": auth.client if auth else None,
            "client_label": auth.client_label if auth else None,
            "token_id": auth.token_id if auth else None,
            "auth_method": auth.auth_method if auth else None,
            "nas_readonly": True,
            "root_key": root_key or None,
            "relative_path": relative_path,
            "operation": tool_name,
            "write_attempted": write_attempted,
            "safe_mode": safe_mode,
            "capability_tier": _capability_tier(tool_name, write_attempted),
        }
        if tool_name in DENIED_TOOL_NAMES:
            return self._deny(base_audit, "action_denied_by_policy", started)
        # Safe mode: deny every mutation, keep reads/status/freshness. Before the profile
        # gate so an incident lockdown is unconditional.
        if safe_mode and write_attempted:
            return self._deny(base_audit, f"safe_mode_active:{tool_name}", started)
        if tool_name in blocked_write_tools():
            return self._deny(base_audit, f"write_tool_blocked_by_profile:{tool_name}", started)
        # Optional per-token narrowing: a token may carry an allowed_tools allowlist that
        # further restricts (never broadens) what the profile already permits.
        if auth and auth.allowed_tools and tool_name not in auth.allowed_tools:
            return self._deny(base_audit, f"tool_not_in_token_scope:{tool_name}", started)
        # Denylist narrowing (only ever restricts): e.g. a read-scoped OAuth token is barred
        # from the single write tool even though the profile permits it.
        if auth and auth.denied_tools and tool_name in auth.denied_tools:
            return self._deny(base_audit, f"tool_denied_by_token_scope:{tool_name}", started)
        # Per-window AI-Outputs write limiter (override-aware, fail-closed on limit AND on
        # unreadable/corrupt receipt state).
        if tool_name == AI_OUTPUTS_WRITE_TOOL:
            window = limits.check_write_window(self._config, client_label, self._override_store)
            if window["override_id"]:
                base_audit["override_id"] = window["override_id"]
            if not window["allowed"]:
                reason = window["reason"] or limits.DENY_WRITE_RATE
                base_audit["rate_limit_result"] = reason
                return self._deny(base_audit, reason, started)
        # Concurrency cap (best-effort under uvicorn threading).
        if not self._concurrency.try_acquire():
            base_audit["rate_limit_result"] = limits.DENY_CONCURRENCY
            return self._deny(base_audit, limits.DENY_CONCURRENCY, started)
        try:
            # Resolve effective (env + raise-only override) size/row/search/card limits.
            eff_config, override_ids = limits.apply_effective_limits(
                self._config, client_label, self._override_store
            )
            if override_ids:
                base_audit.setdefault("override_id", override_ids[0])
            result = self._invoke(tool_name, arguments, eff_config)
        except (DbSelectError, FsToolError, PathAccessError, RootPolicyError, KeyError, ValueError, TypeError) as exc:
            return self._deny(base_audit, str(exc), started)
        finally:
            self._concurrency.release()
        duration_ms = int((time.perf_counter() - started) * 1000)
        timeout_s = limits.resolve_int_limit(limits.SCOPE_TIMEOUT, self._config)
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
            # Best-effort timeout: flagged post-hoc (hard pre-emption of sync tools is a
            # documented HOLD). Static per-call bounds + concurrency cap bound real work.
            "slow_tool": duration_ms > timeout_s * 1000,
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

    def _invoke(self, tool_name: str, arguments: dict[str, Any], config: NasMcpConfig | None = None) -> dict[str, Any]:
        cfg = config or self._config
        if tool_name == "hb_data_freshness":
            return freshness.data_freshness(cfg)
        if tool_name == "hb_queue_status":
            return freshness.queue_status(cfg)
        if tool_name == "hb_recent_failures":
            return freshness.recent_failures(cfg, limit=int(arguments.get("limit", 10)))
        if tool_name == "hb_last_successful_runs":
            return freshness.last_successful_runs(cfg)
        if tool_name == "hb_capability_mode":
            summary = self._override_store.active_summary() if self._override_store else None
            return freshness.capability_mode(cfg, summary)
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
                "assistant_nav_enabled": assistant_nav_enabled(),
                "assistant_nav_tools": list(ASSISTANT_NAV_TOOLS) if assistant_nav_enabled() else [],
                "assistant_context_packs_enabled": assistant_context_packs_enabled(),
                "assistant_context_pack_tools": (
                    list(ASSISTANT_CONTEXT_PACK_TOOLS) if assistant_context_packs_enabled() else []
                ),
                "assistant_memory_enabled": assistant_memory_enabled(),
                "assistant_memory_tools": (
                    list(ASSISTANT_MEMORY_TOOLS) if assistant_memory_enabled() else []
                ),
                "blocked_write_tools": sorted(profile_blocked),
                "active_override_count": (
                    self._override_store.active_summary()["active_count"] if self._override_store else 0
                ),
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
                domain=str(arguments.get("domain", "unknown")),
            )
        if tool_name in ASSISTANT_CONTEXT_PACK_TOOLS:
            if not assistant_context_packs_enabled():
                raise ValueError("assistant_context_packs_disabled")
            return self._invoke_assistant_context_packs(cfg, tool_name, arguments)
        if tool_name in ASSISTANT_MEMORY_TOOLS:
            if not assistant_memory_enabled():
                raise ValueError("assistant_memory_disabled")
            return self._invoke_assistant_memory(cfg, tool_name, arguments)
        if tool_name.startswith("assistant_"):
            if not assistant_nav_enabled():
                raise ValueError("assistant_nav_disabled")
            return self._invoke_assistant(cfg, tool_name, arguments)
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

    def _invoke_assistant(self, cfg: NasMcpConfig, tool_name: str, arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a read-only ``assistant_*`` navigation tool over a READ-ONLY DB snapshot.

        The snapshot connection is opened ``mode=ro&immutable=1`` + ``PRAGMA query_only=ON`` (the same
        posture the freshness/DB tools use) and threaded via ``conn=`` into the shared
        :mod:`hb_assistant.obsidian_mcp.source_navigation` service — so these tools physically cannot
        write and never fall back to a live/writable DB handle. Bad input raises (``ValueError`` /
        ``KeyError`` / ``ObsidianMcpToolError``), which the caller maps to a deny.
        """
        from hb_assistant.obsidian_mcp import source_navigation as nav
        from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository

        from .obsidian_config import apply_obsidian_support_env, obsidian_config_from_nas

        def _limit(default: int = 25) -> int:
            return int(arguments.get("limit", default) or default)

        conn = sqlite3.connect(_ro_uri(str(cfg.db_path)), uri=True, timeout=5.0)
        conn.execute("PRAGMA query_only=ON")
        try:
            repo = SourceIndexRepository(str(cfg.db_path))
            if tool_name == "assistant_search_sources":
                return nav.search_sources(repo, str(arguments.get("query", "")), limit=_limit(),
                                          project_key=arguments.get("project_key"), conn=conn)
            if tool_name == "assistant_get_source":
                result = nav.get_source(repo, str(arguments["source_id"]), conn=conn)
                if result is None:
                    raise ValueError("source_not_found")
                return result
            if tool_name == "assistant_get_card_for_source":
                return nav.get_card_for_source(repo, str(arguments["source_id"]), conn=conn)
            if tool_name == "assistant_get_source_for_card":
                return nav.get_source_for_card(repo, str(arguments["note_rel_path"]), conn=conn)
            if tool_name == "assistant_search_cards":
                return nav.search_cards(repo, str(arguments.get("query", "")), limit=_limit(),
                                        path_prefix=arguments.get("path_prefix"), conn=conn)
            if tool_name == "assistant_list_stale_cards":
                return nav.list_stale_cards(repo, limit=_limit(), conn=conn)
            if tool_name == "assistant_list_duplicate_cards":
                return nav.list_duplicate_cards(repo, limit=_limit(), conn=conn)
            if tool_name == "assistant_list_ambiguous_card_links":
                return nav.list_ambiguous_card_links(repo, limit=_limit(), conn=conn)
            if tool_name == "assistant_recent_changes":
                ets = arguments.get("event_types")
                types = tuple(str(x) for x in ets) if isinstance(ets, list) and ets else None
                return nav.recent_changes(repo, limit=_limit(), event_types=types, conn=conn)
            if tool_name == "assistant_get_related_sources":
                return nav.get_related_sources(repo, str(arguments["source_id"]), conn=conn)
            if tool_name in ("assistant_get_card_state", "assistant_get_vault_note"):
                apply_obsidian_support_env(cfg)
                obs = obsidian_config_from_nas(cfg)
                if tool_name == "assistant_get_card_state":
                    return nav.get_card_state(repo, obs, str(arguments["source_id"]), conn=conn)
                return nav.get_vault_note(obs, str(arguments.get("note_rel_path", "")),
                                         max_chars=arguments.get("max_chars"))
            raise KeyError(f"tool_not_registered: {tool_name}")
        finally:
            conn.close()

    def _invoke_assistant_context_packs(self, cfg: NasMcpConfig, tool_name: str,
                                        arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a read-only N8C-6 enrichment-review / context-pack tool over a READ-ONLY DB
        snapshot (``mode=ro&immutable=1`` + ``PRAGMA query_only=ON``), threaded via ``conn=`` into the
        derived read model and the context-pack repository — so these tools physically cannot write
        and never fall back to a writable handle. No build/apply path is reachable remotely.
        """
        from hb_assistant.obsidian_mcp import enrichment_review as rv
        from hb_assistant.obsidian_mcp.claim_repository import ClaimRepository
        from hb_assistant.obsidian_mcp.context_pack_repository import ContextPackRepository
        from hb_assistant.obsidian_mcp.enrichment_repository import EnrichmentRepository
        from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository

        def _limit(default: int = 25) -> int:
            return int(arguments.get("limit", default) or default)

        conn = sqlite3.connect(_ro_uri(str(cfg.db_path)), uri=True, timeout=5.0)
        conn.execute("PRAGMA query_only=ON")
        try:
            db = str(cfg.db_path)
            if tool_name == "assistant_list_context_packs":
                repo = ContextPackRepository(db)
                packs = repo.list_packs(pack_type=arguments.get("pack_type"),
                                        status=arguments.get("status"), limit=_limit(), conn=conn)
                return {"context_packs": packs, "count": len(packs)}
            if tool_name == "assistant_get_context_pack":
                pack = ContextPackRepository(db).get_pack(str(arguments["pack_id"]), conn=conn)
                if pack is None:
                    raise ValueError("context_pack_not_found")
                return {"context_pack": pack}
            if tool_name == "assistant_get_context_pack_items":
                items = ContextPackRepository(db).list_items(str(arguments["pack_id"]),
                                                             limit=_limit(200), conn=conn)
                return {"pack_id": str(arguments["pack_id"]), "items": items, "count": len(items)}
            if tool_name == "assistant_list_enrichment_review_items":
                return rv.list_enrichment_review_items(
                    EnrichmentRepository(db), ClaimRepository(db), SourceIndexRepository(db),
                    limit=_limit(), job_type=arguments.get("job_type"),
                    review_tier=arguments.get("review_tier"), conn=conn)
            raise KeyError(f"tool_not_registered: {tool_name}")
        finally:
            conn.close()

    def _invoke_assistant_memory(self, cfg: NasMcpConfig, tool_name: str,
                                 arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a read-only N8C-7 memory-compiler tool over a READ-ONLY DB snapshot
        (``mode=ro&immutable=1`` + ``PRAGMA query_only=ON``), threaded via ``conn=`` into the memory
        repository — physically cannot write, no live-DB fallback. No compile/apply path is reachable
        remotely.
        """
        from hb_assistant.obsidian_mcp.memory_repository import MemoryRepository

        def _limit(default: int = 25) -> int:
            return int(arguments.get("limit", default) or default)

        conn = sqlite3.connect(_ro_uri(str(cfg.db_path)), uri=True, timeout=5.0)
        conn.execute("PRAGMA query_only=ON")
        try:
            repo = MemoryRepository(str(cfg.db_path))
            if tool_name == "assistant_list_memory_nodes":
                nodes = repo.list_nodes(node_type=arguments.get("node_type"),
                                        status=arguments.get("status"),
                                        domain=arguments.get("domain"), limit=_limit(), conn=conn)
                return {"memory_nodes": nodes, "count": len(nodes)}
            if tool_name == "assistant_get_memory_node":
                node = repo.get_node(str(arguments["node_id"]), conn=conn)
                if node is None:
                    raise ValueError("memory_node_not_found")
                return {"memory_node": node}
            if tool_name == "assistant_get_memory_mentions":
                mentions = repo.list_mentions(str(arguments["node_id"]), limit=_limit(200), conn=conn)
                return {"node_id": str(arguments["node_id"]), "mentions": mentions,
                        "count": len(mentions)}
            if tool_name == "assistant_get_memory_compilations":
                comps = repo.list_compilations(str(arguments["node_id"]), limit=_limit(), conn=conn)
                return {"node_id": str(arguments["node_id"]), "compilations": comps,
                        "count": len(comps)}
            raise KeyError(f"tool_not_registered: {tool_name}")
        finally:
            conn.close()
