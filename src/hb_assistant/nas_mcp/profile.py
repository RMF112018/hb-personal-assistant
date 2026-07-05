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
# The single sanctioned remote write (tier 3).
AI_OUTPUTS_WRITE_TOOL = "ai_outputs_card_upsert"

PROFILE_REMOTE_CLOUDFLARE = "remote_cloudflare"
PROFILE_LOCAL_TRUSTED = "local_trusted"
KNOWN_PROFILES = (PROFILE_REMOTE_CLOUDFLARE, PROFILE_LOCAL_TRUSTED)
DEFAULT_PROFILE = PROFILE_REMOTE_CLOUDFLARE


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


def safe_mode_enabled() -> bool:
    """Global incident/safe mode. When on, the surface stays readable (status, freshness,
    Tier 0-1 reads) but ALL mutations are denied. Default off; set only by the operator via
    ``HB_MCP_SAFE_MODE=1`` (env/config) — there is no MCP tool that toggles it, so a remote
    LLM can never enable or disable it. Origin auth remains required (safe mode creates no
    unauthenticated path)."""
    return _env_bool("HB_MCP_SAFE_MODE") is True


def blocked_write_tools() -> frozenset[str]:
    """Tool names denied under the current profile/gate posture."""
    blocked: set[str] = set()
    if not legacy_vault_write_enabled():
        blocked |= set(LEGACY_VAULT_WRITE_TOOLS)
    if not scratch_output_write_enabled():
        blocked |= set(SCRATCH_OUTPUT_WRITE_TOOLS)
    if not ai_outputs_write_enabled():
        blocked |= {AI_OUTPUTS_WRITE_TOOL}
    return frozenset(blocked)


def gate_status() -> dict[str, object]:
    return {
        "profile": active_profile(),
        "ai_outputs_write_enabled": ai_outputs_write_enabled(),
        "local_scratch_output_write_enabled": scratch_output_write_enabled(),
        "legacy_broad_vault_write_enabled": legacy_vault_write_enabled(),
        "origin_auth_required": origin_auth_required(),
        "health_mode": health_mode(),
        "safe_mode": safe_mode_enabled(),
    }
