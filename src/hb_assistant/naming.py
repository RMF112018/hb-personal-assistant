"""Domain-neutral identifiers for personal-assistant-generated vault content.

Single source of truth for the neutral names that replace the construction-era
``hb_*`` markers as part of the N8C personal second-brain foundation. This module is
deliberately dependency-free (it imports nothing from ``nas_mcp`` or ``obsidian_mcp``)
so both the NAS AI-Outputs writer and the Obsidian source-card renderer can import it
*downward* without inverting the ``nas_mcp -> obsidian_mcp`` dependency arrow or
creating an import cycle.

Only a subset of these identifiers is consumed today (the AI-Outputs frontmatter and
the local-summary marker). The remaining names are the declared vocabulary that the
later N8C slices (claim memory, graph, context packs) will build on; they are defined
here now so no future slice reintroduces employer-specific naming.
"""

from __future__ import annotations

import re

# --- Provenance -----------------------------------------------------------------------
# Frontmatter provenance stamped on anything this assistant generates into the vault.
MANAGED_BY = "personal_assistant"

# Origin of a generated card. Fixed server-side per surface (never accepted from a caller).
CREATED_VIA_MCP = "mcp"

# --- note_type vocabulary -------------------------------------------------------------
# The single sanctioned remote AI-Outputs card. Distinct from the Obsidian source card's
# existing ``note_type: source_card`` so the two can never be confused by a reader.
NOTE_TYPE_AI_OUTPUT = "ai_output"

# --- Domain tag (neutral, metadata-only) ----------------------------------------------
# A free-form, domain-agnostic label (work/home/parenting/coding/…) so future domains need no
# code change. Sanitised to a YAML-safe, path-inert charset; never influences any file path.
DOMAIN_UNKNOWN = "unknown"
DOMAIN_MAX_LEN = 40
_DOMAIN_STRIP = re.compile(r"[^a-z0-9_-]+")


def sanitize_domain(value: str | None) -> str:
    """Coerce an untrusted domain label to a safe, metadata-only frontmatter value.

    Lowercased and reduced to ``[a-z0-9_-]`` (so YAML-special chars, whitespace, path separators,
    ``.``/``..`` traversal, and NUL are all removed), then length-bounded. Empty/``None``/invalid
    input collapses to ``"unknown"``. The result never contains a path separator and is never used
    to build a path — it is card metadata only.
    """
    if value is None:
        return DOMAIN_UNKNOWN
    cleaned = _DOMAIN_STRIP.sub("", str(value).strip().lower())[:DOMAIN_MAX_LEN]
    return cleaned or DOMAIN_UNKNOWN

# --- Local-summary managed block (neutral, replacing legacy "hb-local-summary") -------
LOCAL_SUMMARY_MARKER = "assistant-local-summary"
LOCAL_SUMMARY_BEGIN_PREFIX = f"<!-- {LOCAL_SUMMARY_MARKER}:start"
LOCAL_SUMMARY_END = f"<!-- {LOCAL_SUMMARY_MARKER}:end -->"

# Legacy marker retained for dual-READ compatibility with source cards already on disk.
# Never emitted by new code; only recognised on read so existing cards keep round-tripping.
LEGACY_LOCAL_SUMMARY_MARKER = "hb-local-summary"
LEGACY_LOCAL_SUMMARY_BEGIN_PREFIX = f"<!-- {LEGACY_LOCAL_SUMMARY_MARKER}:start"
LEGACY_LOCAL_SUMMARY_END = f"<!-- {LEGACY_LOCAL_SUMMARY_MARKER}:end -->"


def is_local_summary_begin(line: str) -> bool:
    """True if ``line`` opens a local-summary block in EITHER the neutral or legacy form."""
    stripped = line.strip()
    return stripped.startswith(LOCAL_SUMMARY_BEGIN_PREFIX) or stripped.startswith(
        LEGACY_LOCAL_SUMMARY_BEGIN_PREFIX
    )


def is_local_summary_end(line: str) -> bool:
    """True if ``line`` closes a local-summary block in EITHER the neutral or legacy form."""
    return line.strip() in (LOCAL_SUMMARY_END, LEGACY_LOCAL_SUMMARY_END)


# --- Declared vocabulary for later N8C slices (no consumers yet) -----------------------
# Defined now so future generated content stays domain-neutral by construction.
SECOND_BRAIN = "second_brain"
SOURCE_CARD = "source_card"
LOCAL_SUMMARY = "local_summary"
ENRICHMENT = "enrichment"
CONTEXT_PACK = "context_pack"
MEMORY_GRAPH = "memory_graph"

# Claim-memory type identifiers (N8C-4).
CLAIM = "claim"
DECISION = "decision"
OPEN_LOOP = "open_loop"
CONTRADICTION = "contradiction"
