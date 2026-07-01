"""Deterministic project-identity resolution + card enrichment (Phase 10D).

Parses the `NN-NNN-NN - Name` project folder, resolves it read-only against `procore_ep_projects`
(reusing the existing project read model + alias seed — never mutating DB project rows), and writes a
machine-readable ``hb-project-identity`` managed block into a source card. The canonical identity
attributes (project_number/project_key/procore_project_id) live in the block's opening marker so the
note-graph facts layer can read them without a DB-schema change; the path-derived project_number on the
DB source row is retained separately.
"""

from __future__ import annotations

import re
from dataclasses import dataclass, field

# NN-NNN-NN project number code (matches source_indexer's HB_PROJECT_NUMBER_RE).
_PROJECT_NUM_RE = re.compile(r"\b(\d{2}-\d{3}-\d{2})\b")
# A "23-435-01 - Tropical" folder segment.
_PROJECT_FOLDER_RE = re.compile(r"(\d{2}-\d{3}-\d{2})\s*-\s*([^/]+)")
_YEAR_RE = re.compile(r"/(20\d{2})/")

IDENTITY_BEGIN_PREFIX = "<!-- hb-project-identity:start"
IDENTITY_END = "<!-- hb-project-identity:end -->"
_MARKER_ATTR_RE = re.compile(
    r'project_number="([^"]*)"\s+project_key="([^"]*)"\s+procore_project_id="([^"]*)"')


class ProjectResolveError(Exception):
    """Raised when the project cannot be resolved unambiguously (missing or >1 match)."""


@dataclass(frozen=True)
class ProjectIdentity:
    project_number: str
    project_key: str
    procore_project_id: str | None
    project_name: str
    project_acronym: str | None
    aliases: tuple[str, ...] = ()
    source_project_folder_name: str = ""
    match_basis: tuple[str, ...] = field(default_factory=tuple)


def parse_project_folder(path: str) -> dict[str, str] | None:
    """Extract {project_number, short_name, year, folder_name} from a `.../NN-NNN-NN - Name/...` path."""
    norm = str(path).replace("\\", "/")
    m = _PROJECT_FOLDER_RE.search(norm)
    if not m:
        return None
    number, rest = m.group(1), m.group(2).strip()
    short = rest.split("/")[0].strip() or rest
    ym = _YEAR_RE.search(norm)
    return {"project_number": number, "short_name": short,
            "year": ym.group(1) if ym else "", "folder_name": f"{number} - {short}"}


def resolve_project(*, number: str | None, name: str | None, db_path: str) -> ProjectIdentity:
    """Resolve a folder-derived (number, name) to the canonical Procore identity (read-only).

    Reuses ``ProjectSummaryReadModelService`` (over ``procore_ep_projects``) + the project alias seed.
    Raises ``ProjectResolveError`` on a missing or ambiguous match. Never writes to the DB.
    """
    from hb_assistant.construction.analytics.project_summary_readmodel import (
        ProjectSummaryReadModelService,
    )
    projects = ProjectSummaryReadModelService(db_path=db_path).build().get("projects", [])
    basis: list[str] = []
    row = None
    if number:
        by_num = [p for p in projects if str(p.get("project_number") or "") == number]
        if len(by_num) > 1:
            raise ProjectResolveError(f"ambiguous project_number {number} ({len(by_num)} rows)")
        if by_num:
            row, _ = by_num[0], basis.append("procore_project_number")
            basis.insert(0, "folder_project_number")
    if row is None and name:
        key = _alias_key(name)
        if key:
            by_key = [p for p in projects if p.get("project_key") == key]
            if len(by_key) > 1:
                raise ProjectResolveError(f"ambiguous project_key {key} ({len(by_key)} rows)")
            if by_key:
                row = by_key[0]
                basis.append("alias_name")
    if row is None:
        raise ProjectResolveError(
            f"no procore_ep_projects match for number={number!r} name={name!r}")
    pkey = str(row.get("project_key") or "")
    if pkey:
        basis.append("procore_project_key")
    acronym = "TWN" if _alias_key("TWN") == pkey else None
    aliases = tuple(a for a in (acronym,) if a)
    return ProjectIdentity(
        project_number=str(row.get("project_number") or number or ""),
        project_key=pkey,
        procore_project_id=(str(row["procore_project_id"]) if row.get("procore_project_id") else None),
        project_name=_strip_number_prefix(str(row.get("display_name") or "")),
        project_acronym=acronym, aliases=aliases,
        source_project_folder_name="", match_basis=tuple(dict.fromkeys(basis)))


def _alias_key(text: str) -> str | None:
    from hb_assistant.construction.second_brain.local_ai.project_aliases import (
        resolve_project_alias,
    )
    key, _tok = resolve_project_alias(text)
    return key


def _strip_number_prefix(display: str) -> str:
    return re.sub(r"^\s*\d{2}-\d{3}-\d{2}\s*-\s*", "", display).strip() or display


# --- Managed identity block (machine-readable in the start marker) ------------------------------
def identity_marker(identity: ProjectIdentity) -> str:
    return (f'{IDENTITY_BEGIN_PREFIX} project_number="{identity.project_number}" '
            f'project_key="{identity.project_key}" '
            f'procore_project_id="{identity.procore_project_id or ""}" -->')


def parse_identity_marker(card_text: str) -> dict[str, str] | None:
    """Read canonical identity attributes from a card's hb-project-identity start marker."""
    for ln in card_text.splitlines():
        if ln.startswith(IDENTITY_BEGIN_PREFIX):
            m = _MARKER_ATTR_RE.search(ln)
            if m:
                return {"project_number": m.group(1), "project_key": m.group(2),
                        "procore_project_id": m.group(3) or None}
    return None


def enrich_card_with_project_identity(card_text: str, identity: ProjectIdentity,
                                      ) -> tuple[str | None, str]:
    """Insert/replace ONE managed hb-project-identity block under `## Related Project`.

    Byte-safe outside the block; idempotent. Returns (new_text | None, reason).
    """
    body = [
        f"- Resolved project: {identity.project_number} · {identity.project_key} · {identity.project_name}",
    ]
    if identity.procore_project_id:
        body.append(f"- Procore project id: {identity.procore_project_id}")
    if identity.aliases:
        body.append(f"- Aliases: {', '.join(identity.aliases)}")
    if identity.match_basis:
        body.append(f"- Match basis: {', '.join(identity.match_basis)}")
    block = [identity_marker(identity), *body, IDENTITY_END]

    lines = card_text.splitlines()
    starts = [i for i, ln in enumerate(lines) if ln.startswith(IDENTITY_BEGIN_PREFIX)]
    ends = [i for i, ln in enumerate(lines) if ln.strip() == IDENTITY_END]
    trailing = "\n" if card_text.endswith("\n") else ""
    if len(starts) == 1 and len(ends) == 1 and ends[0] > starts[0]:
        new = lines[:starts[0]] + block + lines[ends[0] + 1:]
        return "\n".join(new) + trailing, "updated"
    if starts or ends:
        return None, "ambiguous_existing_block"
    section = "## Related Project"
    sec = next((i for i, ln in enumerate(lines) if ln == section), -1)
    if sec == -1:
        return None, "related_project_section_missing"
    end = next((i for i in range(sec + 1, len(lines)) if lines[i].startswith("## ")), len(lines))
    insert_at = end
    while insert_at > sec + 1 and not lines[insert_at - 1].strip():
        insert_at -= 1
    new = lines[:insert_at] + ["", *block] + lines[insert_at:]
    return "\n".join(new) + trailing, "inserted"
