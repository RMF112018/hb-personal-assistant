"""Artifact-type → vault template mapping for template-based intelligence-artifact creation.

The operator directive is that structured-intelligence artifacts are **template-based** in the Obsidian
vault (not free-rendered cards, not DB records). ``pa_artifact_create`` resolves a destination folder via
``vault_path_resolver`` and the matching vault-resident template via this registry, then instantiates it
with ``obsidian_mcp.templates.create_note_from_template``.

Coverage is intentionally bounded to artifact types that have BOTH a routing destination
(``vault_path_resolver._ROUTING``) AND a seeded vault template
(``scripts/seed_obsidian_work_home_vault.py``). An unmapped type fails closed (``template_not_available``)
rather than silently free-rendering. Meeting/daily and the remaining canonical types are a follow-on
(they need routing entries and/or a chosen template).
"""

from __future__ import annotations


class ArtifactTemplateError(ValueError):
    """No template is available for the requested artifact type/domain (fail closed)."""


# (artifact_type, domain_class) -> vault-relative template path. domain_class ∈ {work, home, shared}.
# Only types whose destination folder is already routed by vault_path_resolver._ROUTING are listed.
_TEMPLATE_MAP: dict[tuple[str, str], str] = {
    ("decision", "work"): "Templates/Decisions/decision-log-template.md",
    ("decision", "home"): "Templates/Decisions/decision-log-template.md",
    ("person_note", "work"): "Templates/People/person-template.md",
    ("person_note", "home"): "Templates/People/person-template.md",
    ("company_note", "work"): "Templates/Companies/company-template.md",
    ("project_context", "work"): "Templates/Projects/work-project-template.md",
    ("source_card_annotation", "work"): "Templates/Source Cards/source-card-template.md",
    ("source_card_annotation", "home"): "Templates/Source Cards/source-card-template.md",
    ("source_card_annotation", "shared"): "Templates/Source Cards/source-card-template.md",
}

# Artifact types this surface can create (for tool help / discovery). Sorted, de-duplicated.
SUPPORTED_ARTIFACT_TYPES: tuple[str, ...] = tuple(sorted({t for (t, _d) in _TEMPLATE_MAP}))


def _domain_class(domain: str | None) -> str:
    """Mirror ``vault_path_resolver._domain_class`` so template and folder resolution agree."""
    d = (domain or "").strip().lower()
    if d == "work":
        return "work"
    if d in {"home", "personal", "home/personal"}:
        return "home"
    if d == "shared":
        return "shared"
    return "any"


def resolve_template(artifact_type: str, domain: str | None) -> str:
    """Vault-relative template path for an artifact type/domain, or raise ``ArtifactTemplateError``.

    Uses the same fallback order as the folder router: (type, domain_class) → (type, 'work'). Fails
    closed for any type without a seeded template so creation never free-renders off-taxonomy."""
    at = (artifact_type or "").strip()
    dc = _domain_class(domain)
    for key in ((at, dc), (at, "work")):
        if key in _TEMPLATE_MAP:
            return _TEMPLATE_MAP[key]
    raise ArtifactTemplateError(f"template_not_available:{at or 'unknown'}")
