"""Read-only source/card identity, linkage, staleness, and duplicate detection (N8C-2).

Answers, for the Personal Intelligence Operating Layer:
  - which card represents a source (source -> card)
  - which source a card represents (card -> source; ambiguity-aware, never picks arbitrarily)
  - is a card current / stale / missing / duplicated / orphaned
  - is a note actually a source card, or an AI-Outputs / Email-Archive / user-authored note

Everything here is **read-only**: no DB mutation, no card write, no retire/delete/rewrite. Card
identity is **computed** (not stored) so there is no card-rendering byte change and no schema
migration. Both current and legacy source-card frontmatter are read; missing legacy fields are
classified **distinctly** (not treated as corruption). Source-deleted-but-card-active is a
classification only — N8C-2 never retires the card.
"""

from __future__ import annotations

import hashlib
from dataclasses import dataclass
from pathlib import Path

from hb_assistant import naming

from .config import ObsidianMcpConfig
from .source_archive_paths import is_attachments_path
from .source_card_repair import _frontmatter_value
from .source_index_repository import SourceIndexRepository
from .source_indexer import is_email_archive_path, is_source_notes_path
from .source_notes import CARD_VERSION, TEMPLATE_VERSION

# --- Note classification (a note is one of these) --------------------------------------
NOTE_SOURCE_CARD = "source_card"
NOTE_AI_OUTPUT = "ai_output"
NOTE_EMAIL_ARCHIVE = "email_archive"
NOTE_EMAIL_ATTACHMENT = "email_attachment"
NOTE_USER_AUTHORED = "user_authored"
NOTE_UNKNOWN = "unknown"

# --- Card state ------------------------------------------------------------------------
STATE_CURRENT = "current"
STATE_STALE = "stale"
STATE_MISSING = "missing"                # DB row says generated but the card file is gone
STATE_DUPLICATE = "duplicate"            # >1 active card for one source
STATE_SOURCE_DELETED = "source_deleted"  # source deleted/removed but card row still active
STATE_NO_CARD = "no_card"                # source exists, no card row

# --- Stale reasons (distinct; a stale card is NOT a corrupt card) ----------------------
STALE_NONE = "none"
STALE_SOURCE_DELETED = "source_deleted"
STALE_CARD_FILE_MISSING = "card_file_missing"
STALE_SOURCE_ID_MISMATCH = "source_id_mismatch"
STALE_CARD_VERSION_OBSOLETE = "card_version_obsolete"
STALE_SOURCE_DIGEST_DRIFT = "source_digest_drift"

# --- Legacy classifications (a legacy card lacking a field is NOT stale/corrupt) -------
LEGACY_NO_CARD_VERSION = "legacy_no_card_version"
LEGACY_NO_SOURCE_DIGEST = "legacy_no_source_digest"

# Expected/current card schema markers — the single source of truth is source_notes; re-bound here
# so card_version-obsolete detection compares against a named constant (not a magic literal).
EXPECTED_CARD_VERSION = CARD_VERSION
EXPECTED_TEMPLATE_VERSION = TEMPLATE_VERSION

_ACTIVE_STATUSES = ("generated", "stale")


def compute_card_id(source_id: str, note_rel_path: str) -> str:
    """Deterministic card identity, DISTINCT from source identity.

    A card is identified by ``(source_id, note_rel_path)`` — the same source rendered at a different
    path is a different card. 16-hex sha256 prefix: stable, storage-free, and never equal to a
    ``source_id`` (a 32-hex prefix over a different key space), so card identity is provably separate
    from source identity.
    """
    return hashlib.sha256(f"{source_id}|{note_rel_path}".encode("utf-8")).hexdigest()[:16]


@dataclass(frozen=True)
class SourceCardIdentity:
    note_rel_path: str
    source_id: str | None
    card_id: str | None
    note_type: str | None
    source_kind: str | None
    source_root_key: str | None
    source_sha256: str | None
    card_version: str | None
    template_version: str | None
    domain: str | None
    has_source_id: bool
    has_source_digest: bool  # False for legacy cards lacking source_sha256
    has_card_version: bool


def parse_source_card(card_text: str, note_rel_path: str = "") -> SourceCardIdentity | None:
    """Identity fields from a card's frontmatter, or ``None`` if it is not a source card.

    Uses the byte-safe ``_frontmatter_value`` reader (strips YAML quoting) and reads both current and
    legacy source-card frontmatter.
    """
    if _frontmatter_value(card_text, "note_type") != NOTE_SOURCE_CARD:
        return None
    source_id = _frontmatter_value(card_text, "source_id") or None
    source_sha = _frontmatter_value(card_text, "source_sha256") or None
    card_version = _frontmatter_value(card_text, "card_version") or None
    return SourceCardIdentity(
        note_rel_path=note_rel_path,
        source_id=source_id,
        card_id=compute_card_id(source_id, note_rel_path) if source_id else None,
        note_type=NOTE_SOURCE_CARD,
        source_kind=_frontmatter_value(card_text, "source_kind") or None,
        source_root_key=_frontmatter_value(card_text, "source_root_key") or None,
        source_sha256=source_sha,
        card_version=card_version,
        template_version=_frontmatter_value(card_text, "template_version") or None,
        domain=_frontmatter_value(card_text, "domain") or None,
        has_source_id=bool(source_id),
        has_source_digest=bool(source_sha),
        has_card_version=bool(card_version),
    )


def classify_note(card_text: str, rel_path: str = "",
                  config: ObsidianMcpConfig | None = None) -> str:
    """Classify a vault note so AI-Outputs / Email-Archive / user-authored notes are NEVER mistaken
    for a generated source card. Decisive frontmatter wins; the path is only a fallback."""
    note_type = _frontmatter_value(card_text, "note_type")
    managed_by = _frontmatter_value(card_text, "managed_by")
    source_type = _frontmatter_value(card_text, "source_type")
    if note_type == naming.NOTE_TYPE_AI_OUTPUT or managed_by == naming.MANAGED_BY:
        return NOTE_AI_OUTPUT
    if note_type == NOTE_EMAIL_ARCHIVE or source_type == "eml":
        return NOTE_EMAIL_ARCHIVE
    if note_type == NOTE_SOURCE_CARD:
        return NOTE_SOURCE_CARD
    # No decisive frontmatter -> fall back to path location.
    if rel_path:
        if is_email_archive_path(rel_path):
            return NOTE_EMAIL_ATTACHMENT if is_attachments_path(rel_path) else NOTE_EMAIL_ARCHIVE
        if config is not None and is_source_notes_path(rel_path, config):
            # A note inside the cards folder that lacks source-card frontmatter is anomalous, not a
            # confirmed source card and not a user note either.
            return NOTE_UNKNOWN
    return NOTE_USER_AUTHORED


@dataclass(frozen=True)
class ReverseLookup:
    note_rel_path: str
    sources: list[dict]      # 0, 1, or many source rows at this card path
    resolution: str          # "none" | "unique" | "ambiguous"
    source_id: str | None    # set ONLY when resolution == "unique"


def get_source_for_card(repo: SourceIndexRepository, note_rel_path: str, *,
                        conn=None) -> ReverseLookup:
    """Reverse lookup card path -> source, ambiguity-aware (revision: never pick arbitrarily).

    Because ``note_rel_path`` is not unique on its own, more than one source can claim a card path;
    that resolves to ``"ambiguous"`` with ``source_id=None`` and the full list for the caller.
    """
    rows = repo.get_sources_for_note(note_rel_path, conn=conn)
    if not rows:
        return ReverseLookup(note_rel_path, [], "none", None)
    if len(rows) == 1:
        return ReverseLookup(note_rel_path, rows, "unique", rows[0]["source_id"])
    return ReverseLookup(note_rel_path, rows, "ambiguous", None)


def get_card_for_source(repo: SourceIndexRepository, source_id: str, *, conn=None) -> dict | None:
    """The active card row for a source (prefers ``generated`` over ``stale``), or ``None``.

    Duplicates are surfaced separately by :func:`detect_duplicate_cards`; this returns the primary.
    """
    cards = repo.list_cards_for_source(source_id, conn=conn)
    for status in _ACTIVE_STATUSES:
        for c in cards:
            if c["generation_status"] == status:
                return {**c, "source_id": source_id,
                        "card_id": compute_card_id(source_id, c["note_rel_path"])}
    return None


@dataclass(frozen=True)
class DuplicateReport:
    source_id: str
    active_card_paths: list[str]
    is_duplicate: bool                    # >1 active card path for this source
    cross_source_conflicts: list[dict]    # other sources sharing one of this source's card paths


def detect_duplicate_cards(repo: SourceIndexRepository, source_id: str, *,
                           conn=None) -> DuplicateReport:
    """Duplicate-card detection (read-only). Covers the two vectors the DB UNIQUE(source_id,
    note_rel_path) does NOT: one source with multiple active card paths, and a card path claimed by
    more than one source."""
    rows = repo.list_cards_for_source(source_id, conn=conn)
    active = [r["note_rel_path"] for r in rows if r["generation_status"] in _ACTIVE_STATUSES]
    cross: list[dict] = []
    for path in dict.fromkeys(active):  # unique, order-preserving
        others = [s["source_id"] for s in repo.get_sources_for_note(path, conn=conn)
                  if s["source_id"] != source_id and s["generation_status"] in _ACTIVE_STATUSES]
        if others:
            cross.append({"note_rel_path": path, "other_source_ids": others})
    return DuplicateReport(source_id, active, len(active) > 1, cross)


@dataclass(frozen=True)
class StaleVerdict:
    source_id: str
    note_rel_path: str
    reason: str                     # STALE_* (STALE_NONE when current)
    is_stale: bool
    legacy_flags: tuple[str, ...]   # LEGACY_* — distinct signals, NOT staleness/corruption


def detect_stale_card(repo: SourceIndexRepository, vault_root, source_id: str, note_rel_path: str, *,
                      conn=None) -> StaleVerdict:
    """Read-only staleness verdict for one (source, card) pair.

    Ordered checks: source deleted -> card file missing -> source_id mismatch -> card_version
    obsolete -> source-content digest drift. A legacy card missing ``card_version``/``source_sha256``
    is flagged distinctly (``legacy_flags``) and is NOT declared stale on that basis alone.
    """
    legacy: list[str] = []
    detail = repo.get_source_detail(source_id, conn=conn)
    if detail is None or detail.get("deleted"):
        return StaleVerdict(source_id, note_rel_path, STALE_SOURCE_DELETED, True, ())
    card_path = Path(str(vault_root)) / note_rel_path
    if not card_path.is_file():
        return StaleVerdict(source_id, note_rel_path, STALE_CARD_FILE_MISSING, True, ())
    ident = parse_source_card(card_path.read_text(encoding="utf-8", errors="replace"), note_rel_path)
    if ident is None or not ident.has_source_id or ident.source_id != source_id:
        return StaleVerdict(source_id, note_rel_path, STALE_SOURCE_ID_MISMATCH, True, ())
    if not ident.has_card_version:
        legacy.append(LEGACY_NO_CARD_VERSION)
    elif ident.card_version != EXPECTED_CARD_VERSION:
        return StaleVerdict(source_id, note_rel_path, STALE_CARD_VERSION_OBSOLETE, True, tuple(legacy))
    current_sha = detail.get("content_sha256")
    if not ident.has_source_digest:
        legacy.append(LEGACY_NO_SOURCE_DIGEST)  # cannot compare — do NOT assert stale from absence
    elif current_sha and ident.source_sha256 != current_sha:
        return StaleVerdict(source_id, note_rel_path, STALE_SOURCE_DIGEST_DRIFT, True, tuple(legacy))
    return StaleVerdict(source_id, note_rel_path, STALE_NONE, False, tuple(legacy))


@dataclass(frozen=True)
class CardState:
    source_id: str
    state: str                      # STATE_*
    card_paths: list[str]
    reason: str                     # STALE_* detail when stale/deleted/missing
    legacy_flags: tuple[str, ...] = ()


def classify_card_state(repo: SourceIndexRepository, vault_root, source_id: str, *,
                        conn=None) -> CardState:
    """Roll up a source's card situation into one state. Read-only — never retires/deletes/rewrites
    (source-deleted-but-card-active is reported, not acted on)."""
    cards = repo.list_cards_for_source(source_id, conn=conn)
    active = [c for c in cards if c["generation_status"] in _ACTIVE_STATUSES]
    if not active:
        return CardState(source_id, STATE_NO_CARD, [], STALE_NONE)
    if len(active) > 1:
        return CardState(source_id, STATE_DUPLICATE, [c["note_rel_path"] for c in active], STALE_NONE)
    row = active[0]
    note_rel_path = row["note_rel_path"]
    detail = repo.get_source_detail(source_id, conn=conn)
    if detail is None or detail.get("deleted"):
        return CardState(source_id, STATE_SOURCE_DELETED, [note_rel_path], STALE_SOURCE_DELETED)
    verdict = detect_stale_card(repo, vault_root, source_id, note_rel_path, conn=conn)
    if verdict.reason == STALE_CARD_FILE_MISSING:
        return CardState(source_id, STATE_MISSING, [note_rel_path], verdict.reason, verdict.legacy_flags)
    if verdict.is_stale or row["generation_status"] == "stale":
        reason = verdict.reason if verdict.is_stale else STALE_NONE
        return CardState(source_id, STATE_STALE, [note_rel_path], reason, verdict.legacy_flags)
    return CardState(source_id, STATE_CURRENT, [note_rel_path], STALE_NONE, verdict.legacy_flags)


@dataclass(frozen=True)
class ValidationResult:
    is_source_card: bool
    ok: bool                        # True even with legacy flags; False only on real problems
    problems: tuple[str, ...]
    identity: SourceCardIdentity | None


def validate_card_frontmatter(card_text: str, rel_path: str = "",
                              config: ObsidianMcpConfig | None = None) -> ValidationResult:
    """Validate that a note is a well-formed source card (not an AI-Outputs / Email-Archive / user
    note). Legacy-missing fields are reported as ``legacy_*`` problems but do NOT fail validation."""
    cls = classify_note(card_text, rel_path, config)
    if cls != NOTE_SOURCE_CARD:
        return ValidationResult(False, False, (f"not_a_source_card:{cls}",), None)
    ident = parse_source_card(card_text, rel_path)
    if ident is None:
        return ValidationResult(True, False, ("unparseable_source_card",), None)
    problems: list[str] = []
    if not ident.has_source_id:
        problems.append("missing_source_id")
    if not ident.has_card_version:
        problems.append(LEGACY_NO_CARD_VERSION)
    if not ident.has_source_digest:
        problems.append(LEGACY_NO_SOURCE_DIGEST)
    ok = not any(not p.startswith("legacy_") for p in problems)
    return ValidationResult(True, ok, tuple(problems), ident)
