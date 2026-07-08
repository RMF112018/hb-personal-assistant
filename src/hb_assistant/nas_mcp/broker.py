"""Deny-first broker for NAS MCP tools."""

from __future__ import annotations

import os
import sqlite3
import time
import uuid
from typing import Any

from . import freshness, limits
from .artifact_tools import (
    ALL_PA_TOOLS,
    PA_CANONICAL_WRITE_TOOLS,
    PA_MANIFEST_TOOLS,
    artifact_workspace_status,
    dispatch_artifact_tool,
)
from .audit import NasMcpAuditWriter
from .client_output_tools import (
    ALL_PA_OUTPUT_TOOLS,
    client_output_status,
    dispatch_client_output_tool,
)
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
    CLIENT_OUTPUT_WRITE_TOOLS,
    artifact_workspace_enabled,
    assistant_action_stages_enabled,
    assistant_answer_drafts_enabled,
    assistant_context_packs_enabled,
    assistant_decision_memory_enabled,
    assistant_feedback_enabled,
    assistant_intelligence_enabled,
    assistant_memory_enabled,
    assistant_nav_enabled,
    assistant_quality_enabled,
    assistant_research_packets_enabled,
    assistant_review_enabled,
    assistant_source_connector_enabled,
    assistant_workflows_enabled,
    blocked_write_tools,
    client_tool_manifest_enabled,
    gate_status,
    prompt_preflight_enabled,
    safe_mode_enabled,
)
from .prompt_routing_tools import (
    PROMPT_ROUTING_TOOLS,
    dispatch_prompt_routing_tool,
    prompt_preflight_status,
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

# N8C-8 read-only decision/preference/open-loop tools (reads only; never write — the extract/apply
# path is CLI-only and never exposed remotely). Served from the same read-only DB snapshot. Gated
# independently by ``assistant_decision_memory_enabled()``.
ASSISTANT_DECISION_MEMORY_TOOLS = (
    "assistant_list_decisions",
    "assistant_get_decision",
    "assistant_list_preferences",
    "assistant_get_preference",
    "assistant_list_open_loops",
    "assistant_get_open_loop",
)

# N8C-9 read-only review-overlay tools (reads only; never write — the build/apply and disposition/apply
# writers are CLI-only and never exposed remotely). Served from the same read-only DB snapshot. Gated
# independently by ``assistant_review_enabled()``.
ASSISTANT_REVIEW_TOOLS = (
    "assistant_list_review_items",
    "assistant_get_review_item",
    "assistant_get_review_dispositions",
    "assistant_get_effective_review_state",
    "assistant_get_review_summary",
)

# N8C-10 read-only review-aware intelligence-projection tools (reads only; never write — the build/apply
# writer is CLI-only and never exposed remotely). Served from the same read-only DB snapshot. Gated
# independently by ``assistant_intelligence_enabled()``.
ASSISTANT_INTELLIGENCE_TOOLS = (
    "assistant_list_intelligence_projections",
    "assistant_get_intelligence_projection",
    "assistant_get_intelligence_projection_items",
    "assistant_get_intelligence_projection_export",
    "assistant_get_intelligence_summary",
)

# N8C-11 read-only review-aware research-packet + citation tools (reads only; never write — the build/apply
# writer is CLI-only and never exposed remotely; there is NO answer-generation or action tool). Served from
# the same read-only DB snapshot. Gated independently by ``assistant_research_packets_enabled()``.
ASSISTANT_RESEARCH_PACKET_TOOLS = (
    "assistant_list_research_packets",
    "assistant_get_research_packet",
    "assistant_get_research_packet_items",
    "assistant_get_research_packet_citations",
    "assistant_get_research_packet_export",
    "assistant_get_research_packet_summary",
)

# N8C-12 read-only NAS source-root file connector tools (reads only; never write). Indexed original
# SOURCE FILES — searchable/listable/inspectable + bounded single-file reads — distinct from vault notes
# and generated source cards. No scan/reindex/card-generation/answer/action tool is exposed. Served from
# the same read-only DB snapshot; the bounded read opens exactly one configured file. Gated independently
# by ``assistant_source_connector_enabled()``.
ASSISTANT_SOURCE_CONNECTOR_TOOLS = (
    "assistant_source_status",
    "assistant_source_roots_list",
    "assistant_source_files_list",
    "assistant_source_file_search",
    "assistant_source_file_metadata",
    "assistant_source_file_read",
)

# N8C-14 read-only citation-safe answer-draft tools (reads only; never write). They retrieve bounded,
# citation-safe DRAFT artifacts built from N8C-11 research packets — never a final/authoritative answer, no
# build/apply, no answer-generation, no action. Served from the same read-only DB snapshot. Gated
# independently by ``assistant_answer_drafts_enabled()``. Tool names deliberately use ``draft`` (not
# ``answer``) so the remote surface carries no answer-generation verb — the finality guard in the
# tool-registration tests forbids the substring ``answer`` (as well as build/generate/send) in any tool name.
ASSISTANT_ANSWER_DRAFT_TOOLS = (
    "assistant_list_drafts",
    "assistant_get_draft",
    "assistant_get_draft_sections",
    "assistant_get_draft_citations",
    "assistant_get_draft_export",
    "assistant_get_draft_summary",
)

# N8C-16 read-only LIVE workflow-consumption tools. They expose the N8C-15 deterministic workflow ROUTER to
# MCP clients: resolve a bounded workflow request to EXISTING N8C read surfaces and return a bounded,
# whitelisted routing/context envelope. Served from the same read-only DB snapshot (mode=ro&immutable=1 +
# PRAGMA query_only=ON). They never write, build/apply, persist a run, generate a final answer, execute an
# action, or read a live source file. Gated independently by ``assistant_workflows_enabled()``. The names
# use route/context/policy/artifacts/summary verbs — none is a forbidden finality/action substring, so the
# tool-registration finality guards keep passing unchanged.
ASSISTANT_WORKFLOW_TOOLS = (
    "assistant_list_workflows",
    "assistant_route_workflow",
    "assistant_get_workflow_context",
    "assistant_get_workflow_artifacts",
    "assistant_get_workflow_policy",
    "assistant_get_workflow_summary",
)

# N8C-18 read-only feedback / review-loop inspection tools (reads only; never write). They retrieve bounded
# operator feedback records + ADVISORY review-loop recommendations from the five N8C-18 feedback tables —
# never a review disposition, no write/build/apply, no action. Served from the same read-only DB snapshot
# (mode=ro&immutable=1 + PRAGMA query_only=ON). Gated independently by ``assistant_feedback_enabled()``. The
# names use list/get/targets/recommendations/summary/export verbs — none is a forbidden finality/action
# substring (``export`` is not ``extract``), so the tool-registration finality guards keep passing unchanged.
ASSISTANT_FEEDBACK_TOOLS = (
    "assistant_list_feedback",
    "assistant_get_feedback",
    "assistant_get_feedback_targets",
    "assistant_get_feedback_recommendations",
    "assistant_get_feedback_summary",
    "assistant_get_feedback_export",
)

# N8C-19 read-only action-stage inspection tools: retrieve bounded staged follow-up CANDIDATES (every item
# pinned to not_executed / external_system=none / requires_operator_review=1) + their provenance citations
# from the five N8C-19 stage tables — never executes, never contacts an external system, no write/build/apply.
# Served from the same read-only DB snapshot (mode=ro&immutable=1 + PRAGMA query_only=ON). Gated independently
# by ``assistant_action_stages_enabled()``. The names use list/get/items/citations/summary/export verbs — none
# is a forbidden finality/action substring, so the tool-registration finality guards keep passing unchanged.
ASSISTANT_ACTION_STAGE_TOOLS = (
    "assistant_list_action_stages",
    "assistant_get_action_stage",
    "assistant_get_action_stage_items",
    "assistant_get_action_stage_citations",
    "assistant_get_action_stage_summary",
    "assistant_get_action_stage_export",
)

# N8C-20 read-only quality/evaluation inspection tools: retrieve bounded ADVISORY quality findings over
# existing N8C records (freshness / citation coverage / review-state consistency / source-ref validity /
# policy compliance / duplication / boundedness) from the five N8C-20 ``assistant_quality_*`` tables — never
# repairs, never executes, never accepts/rejects/defers a review disposition, never contacts an external
# system, no write/build/apply/evaluate. Served from the same read-only DB snapshot (mode=ro&immutable=1 +
# PRAGMA query_only=ON). Gated independently by ``assistant_quality_enabled()``. The names use list/get/
# findings/targets/summary/export verbs — none is a forbidden finality/action substring, so the
# tool-registration finality guards keep passing unchanged.
ASSISTANT_QUALITY_TOOLS = (
    "assistant_list_quality",
    "assistant_get_quality",
    "assistant_get_quality_findings",
    "assistant_get_quality_targets",
    "assistant_get_quality_summary",
    "assistant_get_quality_export",
)

# N8C-22 — canonical aggregate registry: the single source of truth for the 13 read-only assistant
# groups / 78 tools. The client-exposure bridge (catalog / help / gateway helper tools) and the
# hb_mcp_status exposure fields derive from these — do NOT hand-maintain a second list. This does not
# add any tool; it only names the union that already existed implicitly across the 13 group tuples.
ASSISTANT_TOOL_GROUPS: dict[str, tuple[str, ...]] = {
    "nav": ASSISTANT_NAV_TOOLS,
    "context_packs": ASSISTANT_CONTEXT_PACK_TOOLS,
    "memory": ASSISTANT_MEMORY_TOOLS,
    "decision_memory": ASSISTANT_DECISION_MEMORY_TOOLS,
    "review": ASSISTANT_REVIEW_TOOLS,
    "intelligence": ASSISTANT_INTELLIGENCE_TOOLS,
    "research_packets": ASSISTANT_RESEARCH_PACKET_TOOLS,
    "source_connector": ASSISTANT_SOURCE_CONNECTOR_TOOLS,
    "answer_drafts": ASSISTANT_ANSWER_DRAFT_TOOLS,
    "workflows": ASSISTANT_WORKFLOW_TOOLS,
    "feedback": ASSISTANT_FEEDBACK_TOOLS,
    "action_stages": ASSISTANT_ACTION_STAGE_TOOLS,
    "quality": ASSISTANT_QUALITY_TOOLS,
}

# Group label -> kill-switch-aware gate predicate. Mirrors the same gates applied at registration
# (tool_registration.py) and dispatch (_invoke), so the exposure view never diverges from reality.
ASSISTANT_GROUP_GATES = {
    "nav": assistant_nav_enabled,
    "context_packs": assistant_context_packs_enabled,
    "memory": assistant_memory_enabled,
    "decision_memory": assistant_decision_memory_enabled,
    "review": assistant_review_enabled,
    "intelligence": assistant_intelligence_enabled,
    "research_packets": assistant_research_packets_enabled,
    "source_connector": assistant_source_connector_enabled,
    "answer_drafts": assistant_answer_drafts_enabled,
    "workflows": assistant_workflows_enabled,
    "feedback": assistant_feedback_enabled,
    "action_stages": assistant_action_stages_enabled,
    "quality": assistant_quality_enabled,
}

# The 78 canonical assistant tools, deduped + sorted. This is the canonical read-only navigation set and
# the catalog's canonical universe. NOTE: the 3 N8C-22 client-bridge helper tools (hb_assistant_catalog /
# _tool_help / _tool_query) are deliberately NOT in here — they are helpers, not canonical assistant tools.
ALL_ASSISTANT_TOOLS: tuple[str, ...] = tuple(
    sorted({tool for tools in ASSISTANT_TOOL_GROUPS.values() for tool in tools})
)

# GATEWAY_ALLOWLIST — the set of tools reachable via the N8C-22 helper gateway (hb_assistant_tool_query /
# _tool_help). Deliberately DECOUPLED from ALL_ASSISTANT_TOOLS and expanded (operator-authorized, N8C-24):
# the canonical 78 PLUS every structured-intelligence + output + AI-output WRITE surface. Denied tools,
# root/db tools, legacy hb_output_* and any non-allowlisted name stay rejected, and every gateway-routed
# write still passes the full broker gate chain (safe-mode, per-tool gate, approval, idempotency, path).
GATEWAY_ALLOWLIST: frozenset[str] = frozenset(
    set(ALL_ASSISTANT_TOOLS)
    | set(ALL_PA_TOOLS)
    | set(ALL_PA_OUTPUT_TOOLS)
    | set(PROMPT_ROUTING_TOOLS)
    | {AI_OUTPUTS_WRITE_TOOL}
)


def runtime_commit() -> str:
    """Best-effort runtime build identity for status (never raises).

    Prefers an explicit build stamp injected at deploy time (the MCP process runs in a container
    without the git repo, so env is the authoritative source); falls back to the package version.
    """
    for var in ("HB_RUNTIME_COMMIT", "HB_BUILD_SHA"):
        val = os.environ.get(var)
        if val:
            return val
    try:
        from hb_assistant import __version__  # noqa: PLC0415

        return f"v{__version__}"
    except Exception:
        return "unknown"


def assistant_client_exposure_status() -> dict[str, Any]:
    """N8C-22 client-exposure summary for hb_mcp_status.

    Reports how many of the 78 canonical assistant tools are currently exposed to connected clients.
    Exposure follows the per-group kill switches: a group turned off by ``HB_MCP_ASSISTANT_*=0`` is
    neither registered nor dispatchable, so its tools count as *missing* here. ``direct+gateway`` means
    both the direct per-tool client wrappers and the fallback catalog/help/query gateway are present.
    """
    groups_enabled = {label: gate() for label, gate in ASSISTANT_GROUP_GATES.items()}
    exposed = sorted(
        tool
        for label, tools in ASSISTANT_TOOL_GROUPS.items()
        if groups_enabled[label]
        for tool in tools
    )
    canonical = len(ALL_ASSISTANT_TOOLS)
    return {
        "assistant_client_exposure_enabled": True,
        "assistant_client_exposure_mode": "direct+gateway",
        "assistant_client_exposed_tool_count": len(exposed),
        "assistant_client_missing_tool_count": canonical - len(exposed),
        "assistant_client_exposure_groups": sorted(
            label for label, on in groups_enabled.items() if on
        ),
        "runtime_commit": runtime_commit(),
    }


# The five fixed no-execution policy fields carried by every N8C-15 workflow envelope.
_WORKFLOW_POLICY_KEYS = (
    "action_policy", "execution_policy", "review_policy", "citation_policy", "source_policy",
)


def _workflow_context_view(env: dict[str, Any]) -> dict[str, Any]:
    """Bounded context slice of an already-bounded workflow envelope — SELECT only, no logic, no reads."""
    keys = ("workflow_id", "workflow_type", "status", "selected_artifacts", "citations", "source_refs",
            "review_labels", "open_questions", "risks_or_caveats", "deferred_capabilities",
            "requires_operator_review", "advisory_next_steps", "warnings",
            # N8C-17 additive (read-only SELECT): bounded per-workflow context sections + the context-only
            # policy marker. Pass-through of already-bounded envelope fields — no new logic, no reads.
            "workflow_sections", "workflow_policy", *_WORKFLOW_POLICY_KEYS)
    return {k: env[k] for k in keys if k in env}


def _workflow_artifacts_view(env: dict[str, Any]) -> dict[str, Any]:
    """Selected artifact REFERENCES only (ids/kinds/status/bounded metadata) — never full upstream payloads."""
    artifacts = env.get("selected_artifacts", [])
    keys = ("workflow_id", "workflow_type", "status", *_WORKFLOW_POLICY_KEYS)
    out = {k: env[k] for k in keys if k in env}
    out["selected_artifacts"] = artifacts
    out["count"] = len(artifacts)
    out["warnings"] = env.get("warnings", [])
    return out


def _workflow_policy_view(env: dict[str, Any]) -> dict[str, Any]:
    """The fixed no-execution policy envelope + the bounded request echo — no artifact contents."""
    keys = ("workflow_id", "workflow_type", "status", "request", *_WORKFLOW_POLICY_KEYS)
    return {k: env[k] for k in keys if k in env}


def _workflow_summary_view(env: dict[str, Any]) -> dict[str, Any]:
    """Bounded, NON-FINAL route-metadata summary — counts + decision + policy only, no artifact/source/draft
    contents and no answer-like prose."""
    keys = ("workflow_id", "workflow_type", "status", "routing_decision", "deferred_capabilities",
            "warnings", *_WORKFLOW_POLICY_KEYS)
    out = {k: env[k] for k in keys if k in env}
    out["counts"] = {name: len(env.get(name, [])) for name in (
        "selected_artifacts", "citations", "source_refs", "review_labels", "open_questions",
        "deferred_capabilities", "warnings")}
    return out

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
    if tool_name == AI_OUTPUTS_WRITE_TOOL or tool_name in PA_CANONICAL_WRITE_TOOLS or tool_name in CLIENT_OUTPUT_WRITE_TOOLS:
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
            or tool_name in PA_CANONICAL_WRITE_TOOLS
            or tool_name in CLIENT_OUTPUT_WRITE_TOOLS
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
                "assistant_decision_memory_enabled": assistant_decision_memory_enabled(),
                "assistant_decision_memory_tools": (
                    list(ASSISTANT_DECISION_MEMORY_TOOLS) if assistant_decision_memory_enabled() else []
                ),
                "assistant_review_enabled": assistant_review_enabled(),
                "assistant_review_tools": (
                    list(ASSISTANT_REVIEW_TOOLS) if assistant_review_enabled() else []
                ),
                "assistant_intelligence_enabled": assistant_intelligence_enabled(),
                "assistant_intelligence_tools": (
                    list(ASSISTANT_INTELLIGENCE_TOOLS) if assistant_intelligence_enabled() else []
                ),
                "assistant_research_packets_enabled": assistant_research_packets_enabled(),
                "assistant_research_packet_tools": (
                    list(ASSISTANT_RESEARCH_PACKET_TOOLS) if assistant_research_packets_enabled() else []
                ),
                "assistant_source_connector_enabled": assistant_source_connector_enabled(),
                "assistant_source_connector_tools": (
                    list(ASSISTANT_SOURCE_CONNECTOR_TOOLS) if assistant_source_connector_enabled() else []
                ),
                "assistant_answer_drafts_enabled": assistant_answer_drafts_enabled(),
                "assistant_answer_draft_tools": (
                    list(ASSISTANT_ANSWER_DRAFT_TOOLS) if assistant_answer_drafts_enabled() else []
                ),
                "assistant_workflows_enabled": assistant_workflows_enabled(),
                "assistant_workflow_tools": (
                    list(ASSISTANT_WORKFLOW_TOOLS) if assistant_workflows_enabled() else []
                ),
                "assistant_feedback_enabled": assistant_feedback_enabled(),
                "assistant_feedback_tools": (
                    list(ASSISTANT_FEEDBACK_TOOLS) if assistant_feedback_enabled() else []
                ),
                "assistant_action_stages_enabled": assistant_action_stages_enabled(),
                "assistant_action_stage_tools": (
                    list(ASSISTANT_ACTION_STAGE_TOOLS) if assistant_action_stages_enabled() else []
                ),
                "assistant_quality_enabled": assistant_quality_enabled(),
                "assistant_quality_tools": (
                    list(ASSISTANT_QUALITY_TOOLS) if assistant_quality_enabled() else []
                ),
                "blocked_write_tools": sorted(profile_blocked),
                "active_override_count": (
                    self._override_store.active_summary()["active_count"] if self._override_store else 0
                ),
                "port_policy": "127.0.0.1:8765 host publish only",
                # N8C-22 client-exposure summary (canonical 78 + per-group kill-switch aware).
                **assistant_client_exposure_status(),
                # N8C-23 artifact workspace + client tool operating manifest (fail-safe if empty/absent).
                **artifact_workspace_status(cfg),
                **client_output_status(cfg),
                # Prompt Preflight & Tool Routing status + tool-surface freshness (fail-safe).
                **prompt_preflight_status(cfg),
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
        if tool_name in ASSISTANT_DECISION_MEMORY_TOOLS:
            if not assistant_decision_memory_enabled():
                raise ValueError("assistant_decision_memory_disabled")
            return self._invoke_assistant_decision_memory(cfg, tool_name, arguments)
        if tool_name in ASSISTANT_REVIEW_TOOLS:
            if not assistant_review_enabled():
                raise ValueError("assistant_review_disabled")
            return self._invoke_assistant_review(cfg, tool_name, arguments)
        if tool_name in ASSISTANT_INTELLIGENCE_TOOLS:
            if not assistant_intelligence_enabled():
                raise ValueError("assistant_intelligence_disabled")
            return self._invoke_assistant_intelligence(cfg, tool_name, arguments)
        if tool_name in ASSISTANT_RESEARCH_PACKET_TOOLS:
            if not assistant_research_packets_enabled():
                raise ValueError("assistant_research_packets_disabled")
            return self._invoke_assistant_research_packets(cfg, tool_name, arguments)
        if tool_name in ASSISTANT_SOURCE_CONNECTOR_TOOLS:
            if not assistant_source_connector_enabled():
                raise ValueError("assistant_source_connector_disabled")
            return self._invoke_assistant_source_connector(cfg, tool_name, arguments)
        if tool_name in ASSISTANT_ANSWER_DRAFT_TOOLS:
            if not assistant_answer_drafts_enabled():
                raise ValueError("assistant_answer_drafts_disabled")
            return self._invoke_assistant_answer_drafts(cfg, tool_name, arguments)
        if tool_name in ASSISTANT_WORKFLOW_TOOLS:
            if not assistant_workflows_enabled():
                raise ValueError("assistant_workflows_disabled")
            return self._invoke_assistant_workflows(cfg, tool_name, arguments)
        if tool_name in ASSISTANT_FEEDBACK_TOOLS:
            if not assistant_feedback_enabled():
                raise ValueError("assistant_feedback_disabled")
            return self._invoke_assistant_feedback(cfg, tool_name, arguments)
        if tool_name in ASSISTANT_ACTION_STAGE_TOOLS:
            if not assistant_action_stages_enabled():
                raise ValueError("assistant_action_stages_disabled")
            return self._invoke_assistant_action_stages(cfg, tool_name, arguments)
        if tool_name in ASSISTANT_QUALITY_TOOLS:
            if not assistant_quality_enabled():
                raise ValueError("assistant_quality_disabled")
            return self._invoke_assistant_quality(cfg, tool_name, arguments)
        if tool_name.startswith("assistant_"):
            if not assistant_nav_enabled():
                raise ValueError("assistant_nav_disabled")
            return self._invoke_assistant(cfg, tool_name, arguments)
        if tool_name in ALL_PA_TOOLS:
            # N8C-23 artifact workspace + client tool operating manifest. Gated by their own kill switches;
            # canonical writes additionally pass through the dispatch write gates + server-side
            # approval/validation/idempotency inside the handler.
            if tool_name in PA_MANIFEST_TOOLS and not client_tool_manifest_enabled():
                raise ValueError("client_tool_manifest_disabled")
            if tool_name not in PA_MANIFEST_TOOLS and not artifact_workspace_enabled():
                raise ValueError("artifact_workspace_disabled")
            return dispatch_artifact_tool(cfg, tool_name, arguments, runtime_commit=runtime_commit())
        if tool_name in ALL_PA_OUTPUT_TOOLS:
            # N8C-24 client generated-output workspace. Controlled writes (stage/commit/archive_commit) are in
            # CLIENT_OUTPUT_WRITE_TOOLS, so they already passed the dispatch write-gate chain (safe-mode +
            # blocked_write_tools when client_output_write_enabled() is off) above; server-side approval +
            # idempotency + path safety are enforced inside the handler. Reads are bounded.
            return dispatch_client_output_tool(cfg, tool_name, arguments, runtime_commit=runtime_commit())
        if tool_name in PROMPT_ROUTING_TOOLS:
            # Prompt Preflight & Tool Routing. Read-only routing layer — never writes/stages/promotes/reads
            # source content. Gated by its own kill switch; gateway-reachable via GATEWAY_ALLOWLIST.
            if not prompt_preflight_enabled():
                raise ValueError("prompt_preflight_disabled")
            return dispatch_prompt_routing_tool(cfg, tool_name, arguments, runtime_commit=runtime_commit())
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

    def _invoke_assistant_decision_memory(self, cfg: NasMcpConfig, tool_name: str,
                                          arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a read-only N8C-8 decision/preference/open-loop tool over a READ-ONLY DB snapshot
        (``mode=ro&immutable=1`` + ``PRAGMA query_only=ON``), threaded via ``conn=`` into the
        decision-memory repository — physically cannot write, no live-DB fallback. No extract/apply
        path is reachable remotely.
        """
        from hb_assistant.obsidian_mcp.decision_memory_repository import DecisionMemoryRepository

        def _limit(default: int = 25) -> int:
            return int(arguments.get("limit", default) or default)

        conn = sqlite3.connect(_ro_uri(str(cfg.db_path)), uri=True, timeout=5.0)
        conn.execute("PRAGMA query_only=ON")
        try:
            repo = DecisionMemoryRepository(str(cfg.db_path))
            if tool_name == "assistant_list_decisions":
                recs = repo.list_decisions(decision_type=arguments.get("decision_type"),
                                           status=arguments.get("status"), limit=_limit(), conn=conn)
                return {"decisions": recs, "count": len(recs)}
            if tool_name == "assistant_get_decision":
                rec = repo.get_decision(str(arguments["decision_id"]), conn=conn)
                if rec is None:
                    raise ValueError("decision_not_found")
                return {"decision": rec}
            if tool_name == "assistant_list_preferences":
                recs = repo.list_preferences(preference_type=arguments.get("preference_type"),
                                             status=arguments.get("status"), limit=_limit(), conn=conn)
                return {"preferences": recs, "count": len(recs)}
            if tool_name == "assistant_get_preference":
                rec = repo.get_preference(str(arguments["preference_id"]), conn=conn)
                if rec is None:
                    raise ValueError("preference_not_found")
                return {"preference": rec}
            if tool_name == "assistant_list_open_loops":
                recs = repo.list_open_loops(open_loop_type=arguments.get("open_loop_type"),
                                            status=arguments.get("status"), limit=_limit(), conn=conn)
                return {"open_loops": recs, "count": len(recs)}
            if tool_name == "assistant_get_open_loop":
                rec = repo.get_open_loop(str(arguments["open_loop_id"]), conn=conn)
                if rec is None:
                    raise ValueError("open_loop_not_found")
                return {"open_loop": rec}
            raise KeyError(f"tool_not_registered: {tool_name}")
        finally:
            conn.close()

    def _invoke_assistant_review(self, cfg: NasMcpConfig, tool_name: str,
                                 arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a read-only N8C-9 review-overlay tool over a READ-ONLY DB snapshot
        (``mode=ro&immutable=1`` + ``PRAGMA query_only=ON``), threaded via ``conn=`` into the review
        repository — physically cannot write, no live-DB fallback. No build/apply or disposition/apply
        path is reachable remotely.
        """
        from hb_assistant.obsidian_mcp.review_repository import ReviewRepository

        def _limit(default: int = 25) -> int:
            return int(arguments.get("limit", default) or default)

        conn = sqlite3.connect(_ro_uri(str(cfg.db_path)), uri=True, timeout=5.0)
        conn.execute("PRAGMA query_only=ON")
        try:
            repo = ReviewRepository(str(cfg.db_path))
            if tool_name == "assistant_list_review_items":
                recs = repo.list_review_items(
                    target_kind=arguments.get("target_kind"), review_type=arguments.get("review_type"),
                    review_state=arguments.get("review_state"),
                    effective_state=arguments.get("effective_state"),
                    include_superseded=bool(arguments.get("include_superseded", False)),
                    limit=_limit(), conn=conn)
                return {"review_items": recs, "count": len(recs)}
            if tool_name == "assistant_get_review_item":
                rec = repo.get_review_item(str(arguments["review_item_id"]), conn=conn)
                if rec is None:
                    raise ValueError("review_item_not_found")
                return {"review_item": rec}
            if tool_name == "assistant_get_review_dispositions":
                recs = repo.list_dispositions(str(arguments["review_item_id"]), limit=_limit(),
                                              conn=conn)
                return {"review_item_id": str(arguments["review_item_id"]), "dispositions": recs,
                        "count": len(recs)}
            if tool_name == "assistant_get_effective_review_state":
                states = repo.effective_state_for_target(
                    str(arguments["target_kind"]), str(arguments["target_id"]), limit=_limit(),
                    conn=conn)
                return {"target_kind": str(arguments["target_kind"]),
                        "target_id": str(arguments["target_id"]), "effective_states": states,
                        "count": len(states)}
            if tool_name == "assistant_get_review_summary":
                return {"summary": repo.summary(conn=conn)}
            raise KeyError(f"tool_not_registered: {tool_name}")
        finally:
            conn.close()

    def _invoke_assistant_intelligence(self, cfg: NasMcpConfig, tool_name: str,
                                       arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a read-only N8C-10 intelligence-projection tool over a READ-ONLY DB snapshot
        (``mode=ro&immutable=1`` + ``PRAGMA query_only=ON``), threaded via ``conn=`` into the projection
        repository — physically cannot write, no live-DB fallback. No build/apply path is reachable
        remotely.
        """
        from hb_assistant.obsidian_mcp import intelligence_projection_builder as IB
        from hb_assistant.obsidian_mcp.intelligence_projection_models import (
            ProjectionValidationError,
        )
        from hb_assistant.obsidian_mcp.intelligence_projection_repository import (
            IntelligenceProjectionRepository,
        )

        def _limit(default: int = 25) -> int:
            return int(arguments.get("limit", default) or default)

        conn = sqlite3.connect(_ro_uri(str(cfg.db_path)), uri=True, timeout=5.0)
        conn.execute("PRAGMA query_only=ON")
        try:
            repo = IntelligenceProjectionRepository(str(cfg.db_path))
            if tool_name == "assistant_list_intelligence_projections":
                recs = repo.list_projections(projection_type=arguments.get("projection_type"),
                                             status=arguments.get("status"), limit=_limit(), conn=conn)
                return {"projections": recs, "count": len(recs)}
            if tool_name == "assistant_get_intelligence_projection":
                rec = repo.get_projection(str(arguments["projection_id"]), conn=conn)
                if rec is None:
                    raise ValueError("projection_not_found")
                return {"projection": rec}
            if tool_name == "assistant_get_intelligence_projection_items":
                recs = repo.list_projection_items(
                    str(arguments["projection_id"]), inclusion_state=arguments.get("inclusion_state"),
                    included_only=bool(arguments.get("included_only", False)), limit=_limit(), conn=conn)
                return {"projection_id": str(arguments["projection_id"]), "items": recs,
                        "count": len(recs)}
            if tool_name == "assistant_get_intelligence_projection_export":
                try:
                    return IB.export_intelligence_projection(
                        repo, projection_id=str(arguments["projection_id"]),
                        included_only=bool(arguments.get("included_only", True)), limit=_limit(200),
                        conn=conn)
                except ProjectionValidationError as e:
                    raise ValueError(str(e)) from None
            if tool_name == "assistant_get_intelligence_summary":
                return {"summary": repo.summary(conn=conn)}
            raise KeyError(f"tool_not_registered: {tool_name}")
        finally:
            conn.close()

    def _invoke_assistant_research_packets(self, cfg: NasMcpConfig, tool_name: str,
                                           arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a read-only N8C-11 research-packet/citation tool over a READ-ONLY DB snapshot
        (``mode=ro&immutable=1`` + ``PRAGMA query_only=ON``), threaded via ``conn=`` into the packet
        repository — physically cannot write, no live-DB fallback. No build/apply, answer-generation, or
        action path is reachable remotely.
        """
        from hb_assistant.obsidian_mcp import research_packet_builder as PB
        from hb_assistant.obsidian_mcp.research_packet_models import ResearchPacketValidationError
        from hb_assistant.obsidian_mcp.research_packet_repository import ResearchPacketRepository

        def _limit(default: int = 25) -> int:
            return int(arguments.get("limit", default) or default)

        conn = sqlite3.connect(_ro_uri(str(cfg.db_path)), uri=True, timeout=5.0)
        conn.execute("PRAGMA query_only=ON")
        try:
            repo = ResearchPacketRepository(str(cfg.db_path))
            if tool_name == "assistant_list_research_packets":
                recs = repo.list_research_packets(packet_type=arguments.get("packet_type"),
                                                  status=arguments.get("status"), limit=_limit(), conn=conn)
                return {"packets": recs, "count": len(recs)}
            if tool_name == "assistant_get_research_packet":
                rec = repo.get_research_packet(str(arguments["packet_id"]), conn=conn)
                if rec is None:
                    raise ValueError("packet_not_found")
                return {"packet": rec}
            if tool_name == "assistant_get_research_packet_items":
                recs = repo.list_research_packet_items(
                    str(arguments["packet_id"]), answer_role=arguments.get("answer_role"),
                    included_only=bool(arguments.get("included_only", False)), limit=_limit(), conn=conn)
                return {"packet_id": str(arguments["packet_id"]), "items": recs, "count": len(recs)}
            if tool_name == "assistant_get_research_packet_citations":
                recs = repo.list_research_packet_citations(
                    str(arguments["packet_id"]), packet_item_id=arguments.get("packet_item_id"),
                    limit=_limit(200), conn=conn)
                return {"packet_id": str(arguments["packet_id"]), "citations": recs, "count": len(recs)}
            if tool_name == "assistant_get_research_packet_export":
                try:
                    return PB.export_research_packet(
                        repo, packet_id=str(arguments["packet_id"]),
                        included_only=bool(arguments.get("included_only", True)), limit=_limit(200),
                        conn=conn)
                except ResearchPacketValidationError as e:
                    raise ValueError(str(e)) from None
            if tool_name == "assistant_get_research_packet_summary":
                return {"summary": repo.summary(conn=conn)}
            raise KeyError(f"tool_not_registered: {tool_name}")
        finally:
            conn.close()

    def _invoke_assistant_source_connector(self, cfg: NasMcpConfig, tool_name: str,
                                           arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a read-only N8C-12 source-root file connector tool over a READ-ONLY DB snapshot
        (``mode=ro&immutable=1`` + ``PRAGMA query_only=ON``), threaded via ``conn=`` into the source-index
        repository. Search/list read indexed rows only — no live recursive scan; the bounded ``read`` opens
        exactly one configured file (extension-gated, size-bounded, indexed-excerpt fallback). No
        scan/reindex, card-generation, answer, or action path is reachable.
        """
        from hb_assistant.obsidian_mcp import source_connector_service as svc
        from hb_assistant.obsidian_mcp.config import load_config
        from hb_assistant.obsidian_mcp.source_connector_models import SourceConnectorValidationError
        from hb_assistant.obsidian_mcp.source_index_repository import SourceIndexRepository

        def _limit(default: int = 25) -> int:
            return int(arguments.get("limit", default) or default)

        config = load_config()
        conn = sqlite3.connect(_ro_uri(str(cfg.db_path)), uri=True, timeout=5.0)
        conn.execute("PRAGMA query_only=ON")
        try:
            repo = SourceIndexRepository(str(cfg.db_path))
            try:
                if tool_name == "assistant_source_status":
                    return svc.source_status(repo, config, conn=conn)
                if tool_name == "assistant_source_roots_list":
                    return svc.list_source_roots(repo, config, conn=conn)
                if tool_name == "assistant_source_files_list":
                    return svc.list_source_files(
                        repo, config, source_root_key=str(arguments["source_root_key"]),
                        prefix=arguments.get("prefix"), limit=_limit(),
                        cursor=arguments.get("cursor"), conn=conn)
                if tool_name == "assistant_source_file_search":
                    return svc.search_source_files(
                        repo, config, query=str(arguments.get("query", "")),
                        source_root_key=arguments.get("source_root_key"),
                        file_ext=arguments.get("file_ext"), limit=_limit(),
                        cursor=arguments.get("cursor"), conn=conn)
                if tool_name == "assistant_source_file_metadata":
                    return svc.source_file_metadata(
                        repo, config, source_id=arguments.get("source_id"),
                        source_ref=arguments.get("source_ref"), conn=conn)
                if tool_name == "assistant_source_file_read":
                    return svc.read_source_file(
                        repo, config, source_id=arguments.get("source_id"),
                        source_ref=arguments.get("source_ref"),
                        max_chars=arguments.get("max_chars"),
                        prefer_live=bool(arguments.get("prefer_live", True)), conn=conn)
            except SourceConnectorValidationError as e:
                raise ValueError(str(e)) from None
            raise KeyError(f"tool_not_registered: {tool_name}")
        finally:
            conn.close()

    def _invoke_assistant_answer_drafts(self, cfg: NasMcpConfig, tool_name: str,
                                        arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a read-only N8C-14 answer-draft tool over a READ-ONLY DB snapshot
        (``mode=ro&immutable=1`` + ``PRAGMA query_only=ON``), threaded via ``conn=`` into the draft
        repository — physically cannot write, no live-DB fallback. These retrieve bounded, citation-safe
        DRAFT artifacts only; no build/apply, final-answer generation, or action path is reachable remotely
        (the export is a bounded read of already-persisted rows, and performs no live source file read).
        """
        from hb_assistant.obsidian_mcp import answer_draft_builder as AB
        from hb_assistant.obsidian_mcp.answer_draft_models import AnswerDraftValidationError
        from hb_assistant.obsidian_mcp.answer_draft_repository import AnswerDraftRepository

        def _limit(default: int = 25) -> int:
            return int(arguments.get("limit", default) or default)

        conn = sqlite3.connect(_ro_uri(str(cfg.db_path)), uri=True, timeout=5.0)
        conn.execute("PRAGMA query_only=ON")
        try:
            repo = AnswerDraftRepository(str(cfg.db_path))
            if tool_name == "assistant_list_drafts":
                recs = repo.list_answer_drafts(draft_type=arguments.get("draft_type"),
                                               status=arguments.get("status"),
                                               packet_id=arguments.get("packet_id"), limit=_limit(),
                                               conn=conn)
                return {"drafts": recs, "count": len(recs)}
            if tool_name == "assistant_get_draft":
                rec = repo.get_answer_draft(str(arguments["draft_id"]), conn=conn)
                if rec is None:
                    raise ValueError("draft_not_found")
                return {"draft": rec}
            if tool_name == "assistant_get_draft_sections":
                recs = repo.list_answer_draft_sections(
                    str(arguments["draft_id"]), section_type=arguments.get("section_type"),
                    limit=_limit(), conn=conn)
                return {"draft_id": str(arguments["draft_id"]), "sections": recs, "count": len(recs)}
            if tool_name == "assistant_get_draft_citations":
                recs = repo.list_answer_draft_citations(
                    str(arguments["draft_id"]), draft_section_id=arguments.get("draft_section_id"),
                    limit=_limit(200), conn=conn)
                return {"draft_id": str(arguments["draft_id"]), "citations": recs, "count": len(recs)}
            if tool_name == "assistant_get_draft_export":
                try:
                    return AB.export_answer_draft(repo, draft_id=str(arguments["draft_id"]),
                                                  limit=_limit(200), conn=conn)
                except AnswerDraftValidationError as e:
                    raise ValueError(str(e)) from None
            if tool_name == "assistant_get_draft_summary":
                return {"summary": repo.summary(conn=conn)}
            raise KeyError(f"tool_not_registered: {tool_name}")
        finally:
            conn.close()

    def _invoke_assistant_feedback(self, cfg: NasMcpConfig, tool_name: str,
                                   arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a read-only N8C-18 feedback tool over a READ-ONLY DB snapshot (``mode=ro&immutable=1`` +
        ``PRAGMA query_only=ON``), threaded via ``conn=`` into the feedback repository — physically cannot
        write, no live-DB fallback. These retrieve bounded operator feedback records + ADVISORY review-loop
        recommendations only; no write, no review-disposition, no build/apply, and no action path is reachable
        remotely (the ``feedback add --apply`` writer is CLI-only)."""
        from hb_assistant.obsidian_mcp import feedback_service as FS
        from hb_assistant.obsidian_mcp.feedback_models import FeedbackValidationError
        from hb_assistant.obsidian_mcp.feedback_repository import FeedbackRepository

        def _limit(default: int = 25) -> int:
            return int(arguments.get("limit", default) or default)

        conn = sqlite3.connect(_ro_uri(str(cfg.db_path)), uri=True, timeout=5.0)
        conn.execute("PRAGMA query_only=ON")
        try:
            repo = FeedbackRepository(str(cfg.db_path))
            if tool_name == "assistant_list_feedback":
                recs = repo.list_feedback(feedback_type=arguments.get("feedback_type"),
                                          status=arguments.get("status"),
                                          workflow_id=arguments.get("workflow_id"), limit=_limit(),
                                          conn=conn)
                return {"feedback": recs, "count": len(recs)}
            if tool_name == "assistant_get_feedback":
                rec = repo.get_feedback(str(arguments["feedback_id"]), conn=conn)
                if rec is None:
                    raise ValueError("feedback_not_found")
                return {"feedback": rec}
            if tool_name == "assistant_get_feedback_targets":
                recs = repo.list_targets(str(arguments["feedback_id"]), limit=_limit(100), conn=conn)
                return {"feedback_id": str(arguments["feedback_id"]), "targets": recs, "count": len(recs)}
            if tool_name == "assistant_get_feedback_recommendations":
                recs = repo.list_recommendations(
                    arguments.get("feedback_id"),
                    recommendation_type=arguments.get("recommendation_type"), limit=_limit(), conn=conn)
                return {"recommendations": recs, "count": len(recs)}
            if tool_name == "assistant_get_feedback_summary":
                return {"summary": repo.summary(conn=conn)}
            if tool_name == "assistant_get_feedback_export":
                try:
                    return FS.export_feedback(repo, feedback_id=str(arguments["feedback_id"]),
                                              limit=_limit(200), conn=conn)
                except FeedbackValidationError as e:
                    raise ValueError(str(e)) from None
            raise KeyError(f"tool_not_registered: {tool_name}")
        finally:
            conn.close()

    def _invoke_assistant_action_stages(self, cfg: NasMcpConfig, tool_name: str,
                                        arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a read-only N8C-19 action-stage tool over a READ-ONLY DB snapshot (``mode=ro&immutable=1``
        + ``PRAGMA query_only=ON``), threaded via ``conn=`` into the stage repository — physically cannot
        write, no live-DB fallback. These retrieve bounded staged follow-up CANDIDATES (every item pinned to
        not_executed / external_system=none / requires_operator_review=1) + provenance citations only; no
        write, no build/apply, no execution, no external system, and no action path is reachable remotely (the
        ``action-stage build --apply`` writer is CLI-only)."""
        from hb_assistant.obsidian_mcp import action_stage_builder as ASB
        from hb_assistant.obsidian_mcp.action_stage_models import ActionStageValidationError
        from hb_assistant.obsidian_mcp.action_stage_repository import ActionStageRepository

        def _limit(default: int = 25) -> int:
            return int(arguments.get("limit", default) or default)

        conn = sqlite3.connect(_ro_uri(str(cfg.db_path)), uri=True, timeout=5.0)
        conn.execute("PRAGMA query_only=ON")
        try:
            repo = ActionStageRepository(str(cfg.db_path))
            if tool_name == "assistant_list_action_stages":
                stages = repo.list_stages(stage_type=arguments.get("stage_type"),
                                          status=arguments.get("status"),
                                          workflow_type=arguments.get("workflow_type"), limit=_limit(),
                                          conn=conn)
                return {"stages": stages, "count": len(stages)}
            if tool_name == "assistant_get_action_stage":
                stage = repo.get_stage(str(arguments["stage_id"]), conn=conn)
                if stage is None:
                    raise ValueError("stage_not_found")
                return {"stage": stage}
            if tool_name == "assistant_get_action_stage_items":
                items = repo.list_items(str(arguments["stage_id"]),
                                        staged_state=arguments.get("staged_state"), limit=_limit(100),
                                        conn=conn)
                return {"stage_id": str(arguments["stage_id"]), "items": items, "count": len(items)}
            if tool_name == "assistant_get_action_stage_citations":
                cits = repo.list_citations(str(arguments["stage_id"]), limit=_limit(100), conn=conn)
                return {"stage_id": str(arguments["stage_id"]), "citations": cits, "count": len(cits)}
            if tool_name == "assistant_get_action_stage_summary":
                return {"summary": repo.summary(conn=conn)}
            if tool_name == "assistant_get_action_stage_export":
                try:
                    return ASB.export_action_stage(repo, stage_id=str(arguments["stage_id"]),
                                                   limit=_limit(200), conn=conn)
                except ActionStageValidationError as e:
                    raise ValueError(str(e)) from None
            raise KeyError(f"tool_not_registered: {tool_name}")
        finally:
            conn.close()

    def _invoke_assistant_quality(self, cfg: NasMcpConfig, tool_name: str,
                                  arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a read-only N8C-20 quality/evaluation tool over a READ-ONLY DB snapshot
        (``mode=ro&immutable=1`` + ``PRAGMA query_only=ON``), threaded via ``conn=`` into the quality
        repository — physically cannot write, no live-DB fallback. These retrieve bounded ADVISORY quality
        findings over existing N8C records only; no write, no build/apply/evaluate, no repair, no execution,
        no external system, and no review-disposition path is reachable remotely (the ``quality build
        --apply`` evaluator writer is CLI-only)."""
        from hb_assistant.obsidian_mcp import quality_evaluator as QE
        from hb_assistant.obsidian_mcp.quality_models import QualityValidationError
        from hb_assistant.obsidian_mcp.quality_repository import QualityRepository

        def _limit(default: int = 25) -> int:
            return int(arguments.get("limit", default) or default)

        conn = sqlite3.connect(_ro_uri(str(cfg.db_path)), uri=True, timeout=5.0)
        conn.execute("PRAGMA query_only=ON")
        try:
            repo = QualityRepository(str(cfg.db_path))
            if tool_name == "assistant_list_quality":
                runs = repo.list_quality_runs(target_kind=arguments.get("target_kind"),
                                              target_id=arguments.get("target_id"),
                                              status=arguments.get("status"), limit=_limit(), conn=conn)
                return {"quality_runs": runs, "count": len(runs)}
            if tool_name == "assistant_get_quality":
                run = repo.get_quality_run(str(arguments["quality_run_id"]), conn=conn)
                if run is None:
                    raise ValueError("quality_run_not_found")
                return {"run": run}
            if tool_name == "assistant_get_quality_findings":
                findings = repo.list_findings(str(arguments["quality_run_id"]),
                                              finding_type=arguments.get("finding_type"),
                                              severity=arguments.get("severity"), limit=_limit(200),
                                              conn=conn)
                return {"quality_run_id": str(arguments["quality_run_id"]), "findings": findings,
                        "count": len(findings)}
            if tool_name == "assistant_get_quality_targets":
                targets = repo.list_targets(str(arguments["quality_run_id"]), limit=_limit(200), conn=conn)
                return {"quality_run_id": str(arguments["quality_run_id"]), "targets": targets,
                        "count": len(targets)}
            if tool_name == "assistant_get_quality_summary":
                return {"summary": repo.summary(conn=conn)}
            if tool_name == "assistant_get_quality_export":
                try:
                    return QE.export_quality(repo, quality_run_id=str(arguments["quality_run_id"]),
                                             limit=_limit(200), conn=conn)
                except QualityValidationError as e:
                    raise ValueError(str(e)) from None
            raise KeyError(f"tool_not_registered: {tool_name}")
        finally:
            conn.close()

    _WORKFLOW_REQUEST_FIELDS = (
        "workflow_type", "query", "objective", "domain", "project_key", "source_root_key",
        "draft_id", "packet_id", "projection_id", "context_pack_id", "review_item_id",
        "memory_node_id", "decision_id", "preference_id", "open_loop_id",
    )

    def _invoke_assistant_workflows(self, cfg: NasMcpConfig, tool_name: str,
                                    arguments: dict[str, Any]) -> dict[str, Any]:
        """Dispatch a read-only N8C-16 live workflow-consumption tool. Every routing tool runs the N8C-15
        deterministic ``WorkflowRouter`` over a READ-ONLY DB snapshot (``mode=ro&immutable=1`` + ``PRAGMA
        query_only=ON``, threaded via ``conn=``) — physically cannot write, no live-DB fallback. It returns a
        bounded, whitelisted routing/context envelope built only from EXISTING N8C artifacts: no build/apply,
        no persistence, no final-answer generation, no action, and no live source file read. Every input is
        clamped by ``WorkflowRequest.from_inputs`` (text capped, ids trimmed). ``assistant_list_workflows``
        returns the static registry catalog and needs no DB at all.
        """
        from hb_assistant.obsidian_mcp.workflow_models import WorkflowRequest
        from hb_assistant.obsidian_mcp.workflow_registry import catalog as workflow_catalog
        from hb_assistant.obsidian_mcp.workflow_router import WorkflowRouter

        if tool_name == "assistant_list_workflows":
            return {"catalog": workflow_catalog()}

        request = WorkflowRequest.from_inputs(
            requested_by="mcp", **{k: arguments.get(k) for k in self._WORKFLOW_REQUEST_FIELDS})
        conn = sqlite3.connect(_ro_uri(str(cfg.db_path)), uri=True, timeout=5.0)
        conn.execute("PRAGMA query_only=ON")
        try:
            env = WorkflowRouter(str(cfg.db_path)).route(request, conn=conn)
            if tool_name == "assistant_route_workflow":
                return {"workflow": env}
            if tool_name == "assistant_get_workflow_context":
                return {"workflow_context": _workflow_context_view(env)}
            if tool_name == "assistant_get_workflow_artifacts":
                return {"workflow_artifacts": _workflow_artifacts_view(env)}
            if tool_name == "assistant_get_workflow_policy":
                return {"workflow_policy": _workflow_policy_view(env)}
            if tool_name == "assistant_get_workflow_summary":
                return {"workflow_summary": _workflow_summary_view(env)}
            raise KeyError(f"tool_not_registered: {tool_name}")
        finally:
            conn.close()
