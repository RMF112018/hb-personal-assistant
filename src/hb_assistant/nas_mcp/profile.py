"""MCP exposure profiles + capability-split write gates for the NAS surface.

Foundation for N8B (Cloudflare remote exposure). The exposed origin (nas_mcp:8765)
must be strictly read (tiers 0-2) plus the single ``ai_outputs_card_upsert`` write
(tier 3). Broad vault mutation (tier 4) and admin/destructive (tier 5) are denied.

Write capability is split into THREE independent gates — never one broad flag:

* ``ai_outputs`` — the narrow AI Outputs card create/update tool (tier 3).
* ``scratch_output`` — the native output-sandbox writers (local scratch).
* ``legacy_vault`` — the 5 broad Obsidian vault-mutation tools (tier 4).

In the ``remote_cloudflare`` profile the scratch + legacy gates are **hard-denied**
regardless of any env override, so a stray flag can never re-open broad writes on
the internet-facing surface.
"""

from __future__ import annotations

import os

from .capability_registry import CapabilityProfile, resolve_profile

# Tier-4 broad Obsidian vault-mutation tools.
LEGACY_VAULT_WRITE_TOOLS = frozenset(
    {
        "create_note",
        "patch_note",
        "vault_update_frontmatter",
        "vault_create_note_from_template",
        "vault_append_to_daily_note",
    }
)
# Native output-sandbox writers (local scratch, tier 3-ish but not AI Outputs).
SCRATCH_OUTPUT_WRITE_TOOLS = frozenset({"hb_output_write_file", "hb_output_create_dir"})
# N8C-24 connected-client generated-output write tools (gated by client_output_write_enabled()).
CLIENT_OUTPUT_WRITE_TOOLS = frozenset({
    "pa_output_stage", "pa_output_commit", "pa_output_archive_commit", "pa_output_cancel",
    "assistant_output_stage", "assistant_output_commit", "assistant_output_archive_commit",
    "assistant_output_cancel",
})
# The single sanctioned remote write (tier 3).
AI_OUTPUTS_WRITE_TOOL = "ai_outputs_card_upsert"

PROFILE_REMOTE_CLOUDFLARE = "remote_cloudflare"
PROFILE_LOCAL_TRUSTED = "local_trusted"
KNOWN_PROFILES = (PROFILE_REMOTE_CLOUDFLARE, PROFILE_LOCAL_TRUSTED)
DEFAULT_PROFILE = PROFILE_REMOTE_CLOUDFLARE


def active_capability_profile() -> CapabilityProfile:
    """Startup-static public capability profile, separate from the transport/security profile."""
    return resolve_profile()


def active_profile() -> str:
    raw = os.environ.get("HB_MCP_PROFILE", "").strip() or DEFAULT_PROFILE
    return raw if raw in KNOWN_PROFILES else DEFAULT_PROFILE


def _env_bool(name: str) -> bool | None:
    value = os.environ.get(name)
    if value is None:
        return None
    return value.strip() == "1"


def _profile_defaults(profile: str) -> tuple[bool, bool, bool]:
    """(ai_outputs, scratch_output, legacy_vault) default gate posture per profile."""
    if profile == PROFILE_LOCAL_TRUSTED:
        return (True, True, True)
    # remote_cloudflare: only the AI Outputs write; broad + scratch denied.
    return (True, False, False)


def ai_outputs_write_enabled() -> bool:
    default = _profile_defaults(active_profile())[0]
    override = _env_bool("HB_MCP_ALLOW_AI_OUTPUTS_WRITE")
    return default if override is None else override


def scratch_output_write_enabled() -> bool:
    profile = active_profile()
    if profile == PROFILE_REMOTE_CLOUDFLARE:
        return False  # hard-denied on the internet-facing surface, no override
    override = _env_bool("HB_MCP_ALLOW_SCRATCH_OUTPUT_WRITE")
    return _profile_defaults(profile)[1] if override is None else override


def legacy_vault_write_enabled() -> bool:
    profile = active_profile()
    if profile == PROFILE_REMOTE_CLOUDFLARE:
        return False  # broad vault mutation always blocked remotely, no override
    override = _env_bool("HB_MCP_ALLOW_LEGACY_VAULT_WRITE")
    return _profile_defaults(profile)[2] if override is None else override


def client_output_write_enabled() -> bool:
    """N8C-24 connected-client generated-output workspace write gate. Deliberately distinct from the
    local-scratch writer: default ON in both remote_cloudflare and local_trusted (operator-authorized),
    since it is a narrow, receipt-backed, extension-allowlisted, staged+approved+idempotent write class.
    Kill-switch: ``HB_MCP_ALLOW_CLIENT_OUTPUT_WRITE=0``."""
    override = _env_bool("HB_MCP_ALLOW_CLIENT_OUTPUT_WRITE")
    return True if override is None else override


def prompt_preflight_enabled() -> bool:
    """Prompt Preflight & Tool Routing read-only routing layer. Default ON in every profile — it never
    writes, stages, promotes, or reads source content, so it carries no write risk. Kill-switch:
    ``HB_MCP_PROMPT_PREFLIGHT=0``."""
    override = _env_bool("HB_MCP_PROMPT_PREFLIGHT")
    return True if override is None else override


def artifact_author_enabled() -> bool:
    """Template-based structured-intelligence artifact author (``pa_artifact_author``) write gate. Its OWN
    flag, distinct from the AI Outputs / client-output write gates (split-write-gate discipline). Default
    ON (operator-authorized): it writes markdown to in-taxonomy vault folders from a vault template only —
    no DB records, no new top-level folders. Kill-switch: ``HB_MCP_ALLOW_ARTIFACT_AUTHOR=0``."""
    override = _env_bool("HB_MCP_ALLOW_ARTIFACT_AUTHOR")
    return True if override is None else override


HEALTH_MODE_MINIMAL_PUBLIC = "minimal_public"
HEALTH_MODE_PROTECTED = "protected"
KNOWN_HEALTH_MODES = (HEALTH_MODE_MINIMAL_PUBLIC, HEALTH_MODE_PROTECTED)


def origin_auth_required() -> bool:
    """Whether the NAS MCP origin (nas_mcp:8765) requires a valid bearer token.

    Defense-in-depth: this is *in addition to* Cloudflare Access at the edge, never a
    replacement. In the internet-facing ``remote_cloudflare`` profile origin auth is
    **hard-on regardless of any env override** — mirroring the write-gate lockdown so a
    stray flag can never expose an unauthenticated MCP to the tunnel. Only the
    ``local_trusted`` profile may run without origin auth (default off, opt-in on).
    """
    if active_profile() == PROFILE_REMOTE_CLOUDFLARE:
        return True
    override = _env_bool("HB_MCP_ORIGIN_AUTH_REQUIRED")
    return False if override is None else override


def health_mode() -> str:
    """``minimal_public`` (default) exposes only liveness unauthenticated; ``protected``
    requires origin auth for /health too. Detailed health is always reachable via the
    authenticated ``hb_mcp_status`` tool regardless of this mode."""
    raw = os.environ.get("HB_MCP_ORIGIN_AUTH_HEALTH_MODE", "").strip() or HEALTH_MODE_MINIMAL_PUBLIC
    return raw if raw in KNOWN_HEALTH_MODES else HEALTH_MODE_MINIMAL_PUBLIC


def assistant_nav_enabled() -> bool:
    """N8C-3 read-only source/card/note navigation tools (``assistant_*``).

    These are **reads only** — they never write, so they are independent of the three write gates
    and are enabled by DEFAULT (operator-authorized full-content navigation of the personal
    knowledge base). Origin auth still applies (hard-on in ``remote_cloudflare``), so the tools are
    only reachable by an authenticated caller. Kill-switch: ``HB_MCP_ASSISTANT_NAV=0``.
    """
    override = _env_bool("HB_MCP_ASSISTANT_NAV")
    return True if override is None else override


def assistant_context_packs_enabled() -> bool:
    """N8C-6 read-only enrichment-review + context-pack tools (``assistant_list_context_packs`` etc.).

    Reads only — they never write (the pack BUILD/apply path is CLI-only and never exposed remotely),
    so they are independent of the three write gates and enabled by DEFAULT, like the N8C-3 nav tools.
    Origin auth still applies. Kill-switch: ``HB_MCP_ASSISTANT_CONTEXT_PACKS=0``.
    """
    override = _env_bool("HB_MCP_ASSISTANT_CONTEXT_PACKS")
    return True if override is None else override


def assistant_memory_enabled() -> bool:
    """N8C-7 read-only memory-compiler tools (``assistant_list_memory_nodes`` etc.).

    Reads only — they never write (the memory compile/apply path is CLI-only and never exposed
    remotely), so they are independent of the three write gates and enabled by DEFAULT, like the
    N8C-3 nav and N8C-6 context-pack tools. Origin auth still applies. Kill-switch:
    ``HB_MCP_ASSISTANT_MEMORY=0``.
    """
    override = _env_bool("HB_MCP_ASSISTANT_MEMORY")
    return True if override is None else override


def assistant_decision_memory_enabled() -> bool:
    """N8C-8 read-only decision/preference/open-loop tools (``assistant_list_decisions`` etc.).

    Reads only — they never write (the extract/apply path is CLI-only and never exposed remotely), so
    they are independent of the three write gates and enabled by DEFAULT, like the N8C-3 nav, N8C-6
    context-pack, and N8C-7 memory tools. Origin auth still applies. Kill-switch:
    ``HB_MCP_ASSISTANT_DECISION_MEMORY=0``.
    """
    override = _env_bool("HB_MCP_ASSISTANT_DECISION_MEMORY")
    return True if override is None else override


def assistant_review_enabled() -> bool:
    """N8C-9 read-only review-queue tools (``assistant_list_review_items`` etc.).

    Reads only — they never write (the build/apply and disposition/apply writers are CLI-only and never
    exposed remotely), so they are independent of the three write gates and enabled by DEFAULT, like the
    N8C-3 nav, N8C-6 context-pack, N8C-7 memory, and N8C-8 decision-memory tools. Origin auth still
    applies. Kill-switch: ``HB_MCP_ASSISTANT_REVIEW=0``.
    """
    override = _env_bool("HB_MCP_ASSISTANT_REVIEW")
    return True if override is None else override


def assistant_intelligence_enabled() -> bool:
    """N8C-10 read-only review-aware intelligence-projection tools
    (``assistant_list_intelligence_projections`` etc.).

    Reads only — they never write (the build/apply writer is CLI-only and never exposed remotely), so they
    are independent of the three write gates and enabled by DEFAULT, like the N8C-3 nav, N8C-6 context-pack,
    N8C-7 memory, N8C-8 decision-memory, and N8C-9 review tools. Origin auth still applies. Kill-switch:
    ``HB_MCP_ASSISTANT_INTELLIGENCE=0``.
    """
    override = _env_bool("HB_MCP_ASSISTANT_INTELLIGENCE")
    return True if override is None else override


def assistant_research_packets_enabled() -> bool:
    """N8C-11 read-only review-aware research-packet + citation tools
    (``assistant_list_research_packets`` etc.).

    Reads only — they never write (the build/apply writer is CLI-only and never exposed remotely) and they
    never generate an answer or execute an action, so they are independent of the three write gates and
    enabled by DEFAULT, like the N8C-3 nav … N8C-10 intelligence tools. Origin auth still applies.
    Kill-switch: ``HB_MCP_ASSISTANT_RESEARCH_PACKETS=0``.
    """
    override = _env_bool("HB_MCP_ASSISTANT_RESEARCH_PACKETS")
    return True if override is None else override


def assistant_source_connector_enabled() -> bool:
    """N8C-12 read-only NAS source-root file connector tools
    (``assistant_source_status`` / ``assistant_source_file_search`` etc.).

    Read-only: they search/list/inspect and bounded-READ indexed NAS source-root FILES — they never scan a
    root, reindex, generate a card, or mutate anything, so they are independent of the three write gates and
    enabled by DEFAULT, like the N8C-3 nav … N8C-11 research-packet tools. Origin auth still applies.
    Kill-switch: ``HB_MCP_ASSISTANT_SOURCE_CONNECTOR=0``.
    """
    override = _env_bool("HB_MCP_ASSISTANT_SOURCE_CONNECTOR")
    return True if override is None else override


def assistant_answer_drafts_enabled() -> bool:
    """N8C-14 read-only citation-safe answer-draft tools
    (``assistant_list_answer_drafts`` / ``assistant_get_answer_draft_export`` etc.).

    Reads only — they retrieve bounded, citation-safe DRAFT artifacts (never a final/authoritative answer)
    and never write (the build/apply writer is CLI-only and never exposed remotely), never generate an
    answer, and execute nothing, so they are independent of the three write gates and enabled by DEFAULT,
    like the N8C-3 nav … N8C-12 source-connector tools. Origin auth still applies.
    Kill-switch: ``HB_MCP_ASSISTANT_ANSWER_DRAFTS=0``.
    """
    override = _env_bool("HB_MCP_ASSISTANT_ANSWER_DRAFTS")
    return True if override is None else override


def assistant_workflows_enabled() -> bool:
    """N8C-16 read-only live workflow-consumption tools (``assistant_list_workflows`` /
    ``assistant_route_workflow`` / ``assistant_get_workflow_context`` etc.).

    Reads only — they expose the N8C-15 deterministic workflow ROUTER: they resolve a bounded workflow
    request to EXISTING N8C read surfaces and return a bounded, whitelisted routing/context envelope. They
    never write, build/apply, generate a final answer, execute an action, or read a live source file, so
    they are independent of the three write gates and enabled by DEFAULT, like the N8C-3 nav … N8C-14
    answer-draft tools. Origin auth still applies.
    Kill-switch: ``HB_MCP_ASSISTANT_WORKFLOWS=0``.
    """
    override = _env_bool("HB_MCP_ASSISTANT_WORKFLOWS")
    return True if override is None else override


def assistant_feedback_enabled() -> bool:
    """N8C-18 read-only feedback / review-loop inspection tools (``assistant_list_feedback`` /
    ``assistant_get_feedback`` / ``assistant_get_feedback_recommendations`` etc.).

    Reads only — they retrieve bounded operator feedback records + ADVISORY review-loop recommendations. They
    never write (the ``feedback add --apply`` writer is CLI-only and never exposed remotely), never change a
    review disposition, never mutate a source/workflow/upstream record, and execute nothing, so they are
    independent of the three write gates and enabled by DEFAULT, like the N8C-3 nav … N8C-16 workflow tools.
    Origin auth still applies.
    Kill-switch: ``HB_MCP_ASSISTANT_FEEDBACK=0``.
    """
    override = _env_bool("HB_MCP_ASSISTANT_FEEDBACK")
    return True if override is None else override


def assistant_action_stages_enabled() -> bool:
    """N8C-19 read-only action-stage inspection tools (``assistant_list_action_stages`` /
    ``assistant_get_action_stage`` / ``assistant_get_action_stage_items`` etc.).

    Reads only — they retrieve bounded staged follow-up CANDIDATES (every item pinned to not_executed /
    external_system=none / requires_operator_review=1) + their provenance citations. They never write (the
    ``action-stage build --apply`` writer is CLI-only and never exposed remotely), never execute an action,
    never contact an external system, never change a review state, and never mutate an upstream record, so
    they are independent of the three write gates and enabled by DEFAULT, like the N8C-3 nav … N8C-18 feedback
    tools. Origin auth still applies.
    Kill-switch: ``HB_MCP_ASSISTANT_ACTION_STAGES=0``.
    """
    override = _env_bool("HB_MCP_ASSISTANT_ACTION_STAGES")
    return True if override is None else override


def assistant_quality_enabled() -> bool:
    """N8C-20 read-only quality/evaluation inspection tools (``assistant_list_quality`` /
    ``assistant_get_quality`` / ``assistant_get_quality_findings`` etc.).

    Reads only — they retrieve bounded ADVISORY quality findings over existing N8C records (freshness /
    citation coverage / review-state consistency / source-ref validity / policy compliance / duplication /
    boundedness). They never write (the ``quality build --apply`` evaluator writer is CLI-only and never
    exposed remotely), never repair/execute anything, never accept/reject/defer/dispose a review disposition,
    never contact an external system, and never mutate an upstream record, so they are independent of the
    three write gates and enabled by DEFAULT, like the N8C-3 nav … N8C-19 action-stage tools. Origin auth
    still applies.
    Kill-switch: ``HB_MCP_ASSISTANT_QUALITY=0``.
    """
    override = _env_bool("HB_MCP_ASSISTANT_QUALITY")
    return True if override is None else override


def assistant_source_structure_enabled() -> bool:
    """NAS Source-Structure Layered Index read-only map/route tools (``assistant_source_root_map`` /
    ``assistant_source_folder_map`` / ``assistant_source_search_route`` etc.).

    Reads only — they return bounded, root-relative maps / routing hints / quality findings from the
    precomputed source-structure index (built out-of-band by ``hb-assistant source-structure``). They
    never scan a root, reindex, call a model, mutate anything, or expose an absolute path.

    **DEFAULT-ON** for connected clients so map/tree/project navigation is not file-search-only.
    Kill-switch: ``HB_MCP_ASSISTANT_SOURCE_STRUCTURE=0``.
    """
    override = _env_bool("HB_MCP_ASSISTANT_SOURCE_STRUCTURE")
    return True if override is None else override


def artifact_workspace_enabled() -> bool:
    """N8C-23 Structured Intelligence Artifact Workspace tools (``pa_session_capture_*`` /
    ``pa_artifact_proposal_*`` / ``pa_artifact_promotion_*`` / ``pa_canonical_artifact_*`` /
    ``pa_vault_path_resolve``).

    Read/advisory + staged-write tools never finalize; the single canonical write
    (``pa_artifact_promotion_apply``) is additionally guarded by a server-minted operator_approval_id, a
    passed validation receipt, a recomputed validation hash, and a server-derived idempotency key. Enabled by
    DEFAULT in every profile (the amendments' approval/validation/idempotency chain is the control, not a
    default-off gate); this kill-switch (``HB_MCP_ARTIFACT_WORKSPACE=0``) is a defense-in-depth master off.
    """
    override = _env_bool("HB_MCP_ARTIFACT_WORKSPACE")
    return True if override is None else override


def client_tool_manifest_enabled() -> bool:
    """N8C-23 Client Tool Operating Manifest tools (``pa_tool_manifest_*``).

    Read/advisory + a staged refresh; materializing the manifest (``pa_tool_manifest_refresh_promote``)
    requires a server-minted operator approval + a no-drift checksum (never a silent rewrite). Enabled by
    DEFAULT; kill-switch ``HB_MCP_CLIENT_TOOL_MANIFEST=0``.
    """
    override = _env_bool("HB_MCP_CLIENT_TOOL_MANIFEST")
    return True if override is None else override


def safe_mode_enabled() -> bool:
    """Global incident/safe mode. When on, the surface stays readable (status, freshness,
    Tier 0-1 reads) but ALL mutations are denied. Default off; set only by the operator via
    ``HB_MCP_SAFE_MODE=1`` (env/config) — there is no MCP tool that toggles it, so a remote
    LLM can never enable or disable it. Origin auth remains required (safe mode creates no
    unauthenticated path)."""
    return _env_bool("HB_MCP_SAFE_MODE") is True


def oauth_enabled() -> bool:
    """Whether the NAS surface also accepts OAuth 2.1 access tokens (in addition to the
    static origin bearer). Default off; opt-in via ``HB_MCP_OAUTH_ENABLED=1``. This is
    strictly ADDITIVE — it never relaxes ``origin_auth_required()`` or the write gates;
    it only adds OAuth as a second accepted credential + mounts the OAuth discovery/flow
    endpoints. Requires a configured public base URL to build discovery metadata."""
    return _env_bool("HB_MCP_OAUTH_ENABLED") is True


def blocked_write_tools() -> frozenset[str]:
    """Tool names denied under the current profile/gate posture."""
    blocked: set[str] = set()
    if not legacy_vault_write_enabled():
        blocked |= set(LEGACY_VAULT_WRITE_TOOLS)
    if not scratch_output_write_enabled():
        blocked |= set(SCRATCH_OUTPUT_WRITE_TOOLS)
    if not ai_outputs_write_enabled():
        blocked |= {AI_OUTPUTS_WRITE_TOOL}
    if not client_output_write_enabled():
        blocked |= set(CLIENT_OUTPUT_WRITE_TOOLS)
    return frozenset(blocked)


def gate_status() -> dict[str, object]:
    return {
        "profile": active_profile(),
        "capability_profile": active_capability_profile().value,
        "ai_outputs_write_enabled": ai_outputs_write_enabled(),
        "client_output_write_enabled": client_output_write_enabled(),
        "local_scratch_output_write_enabled": scratch_output_write_enabled(),
        "legacy_broad_vault_write_enabled": legacy_vault_write_enabled(),
        "origin_auth_required": origin_auth_required(),
        "health_mode": health_mode(),
        "safe_mode": safe_mode_enabled(),
        "oauth_enabled": oauth_enabled(),
        "assistant_nav_enabled": assistant_nav_enabled(),
        "assistant_context_packs_enabled": assistant_context_packs_enabled(),
        "assistant_memory_enabled": assistant_memory_enabled(),
        "assistant_decision_memory_enabled": assistant_decision_memory_enabled(),
        "assistant_review_enabled": assistant_review_enabled(),
        "assistant_intelligence_enabled": assistant_intelligence_enabled(),
        "assistant_research_packets_enabled": assistant_research_packets_enabled(),
        "assistant_source_connector_enabled": assistant_source_connector_enabled(),
        "assistant_answer_drafts_enabled": assistant_answer_drafts_enabled(),
        "assistant_workflows_enabled": assistant_workflows_enabled(),
        "assistant_feedback_enabled": assistant_feedback_enabled(),
        "assistant_action_stages_enabled": assistant_action_stages_enabled(),
        "assistant_quality_enabled": assistant_quality_enabled(),
        "assistant_source_structure_enabled": assistant_source_structure_enabled(),
        "artifact_workspace_enabled": artifact_workspace_enabled(),
        "client_tool_manifest_enabled": client_tool_manifest_enabled(),
        "prompt_preflight_enabled": prompt_preflight_enabled(),
    }
