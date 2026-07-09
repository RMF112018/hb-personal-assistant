"""Typed models + bounds for the NAS Source-Structure Layered Index (V115).

Pure data holders shared by the parser, classifier, repository, service, CLI, API, and MCP layers.
Enum vocabularies are imported from the schema module (``store.source_structure_tables``) so the DDL
CHECK constraints and the Python code share a single source of truth. Bounds here are the hard caps
enforced on anything returned to a client — no unbounded lists, no absolute paths.
"""

from __future__ import annotations

from dataclasses import dataclass, field

from hb_assistant.store.source_structure_tables import (
    DOC_FAMILY_VALUES,
    FINDING_SEVERITY_VALUES,
    FOLDER_CLASS_VALUES,
    HINT_TYPE_VALUES,
    INDEX_POLICY_VALUES,
    ROOT_CLASS_VALUES,
    TRUST_TIER_VALUES,
)

# --- Hard client-facing bounds ----------------------------------------------------------------
MAX_PAGE_SIZE = 200
DEFAULT_PAGE_SIZE = 50
MAX_SAMPLE_NAMES = 12
MAX_DOMINANT_EXTENSIONS = 10
MAX_SUMMARY_CHARS = 800
MAX_CLIENT_DEPTH = 8  # deepest rel_path depth a single client call will return
MAX_HINTS = 25

# Allowed vocabularies re-exported for validation at the module boundary.
ALLOWED_ROOT_CLASSES = frozenset(ROOT_CLASS_VALUES)
ALLOWED_TRUST_TIERS = frozenset(TRUST_TIER_VALUES)
ALLOWED_INDEX_POLICIES = frozenset(INDEX_POLICY_VALUES)
ALLOWED_FOLDER_CLASSES = frozenset(FOLDER_CLASS_VALUES)
ALLOWED_DOC_FAMILIES = frozenset(DOC_FAMILY_VALUES)
ALLOWED_HINT_TYPES = frozenset(HINT_TYPE_VALUES)
ALLOWED_FINDING_SEVERITIES = frozenset(FINDING_SEVERITY_VALUES)


@dataclass(slots=True)
class SourceStructureRoot:
    root_key: str
    display_name: str
    root_class: str
    trust_tier: str
    index_policy: str
    default_search_rank: int
    is_sensitive: bool = False
    is_generated_output: bool = False
    is_backup_mirror: bool = False
    is_active: bool = True
    last_seen_at: str | None = None
    last_indexed_at: str | None = None
    folder_count: int = 0
    file_count: int = 0
    noise_count: int = 0
    max_depth: int | None = None
    notes: str | None = None


@dataclass(slots=True)
class FolderStats:
    """Counts derived deterministically for a single folder."""

    child_folder_count: int = 0
    file_count: int = 0
    dominant_extensions: list[str] = field(default_factory=list)
    sample_names: list[str] = field(default_factory=list)


@dataclass(slots=True)
class FolderSample:
    """Bounded metadata handed to the classifier (and, in a later increment, Ollama).

    Deliberately contains NO raw file bodies and NO absolute paths — only root-relative structure.
    """

    root_key: str
    rel_path: str
    name: str
    depth: int
    child_folder_names: list[str] = field(default_factory=list)
    stats: FolderStats = field(default_factory=FolderStats)


@dataclass(slots=True)
class FolderClassification:
    folder_class: str
    doc_family: str | None
    trust_tier: str
    search_rank: int
    is_noise: bool = False
    is_backup_mirror: bool = False
    is_generated_output: bool = False
    is_sensitive: bool = False
    is_project_candidate: bool = False
    project_number: str | None = None
    project_name_hint: str | None = None
    classification_source: str = "rule"
    classification_confidence: float = 0.0


@dataclass(slots=True)
class SourceStructureFolder:
    folder_id: str
    root_key: str
    parent_folder_id: str | None
    rel_path: str
    name: str
    depth: int
    classification: FolderClassification
    stats: FolderStats = field(default_factory=FolderStats)
    fingerprint: str | None = None
    last_seen_at: str | None = None
    last_indexed_at: str | None = None


@dataclass(slots=True)
class SourceStructureEntity:
    entity_id: str
    entity_type: str
    canonical_key: str
    display_name: str | None = None
    project_number: str | None = None
    project_name: str | None = None
    confidence: float = 0.0


@dataclass(slots=True)
class EntityFolderLink:
    entity_id: str
    folder_id: str
    relationship_type: str
    confidence: float = 0.0
    evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SourceStructureSummary:
    summary_id: str
    subject_type: str
    subject_id: str
    summary_text: str
    summary_kind: str = "deterministic"
    model_name: str | None = None
    prompt_version: str | None = None
    input_fingerprint: str | None = None
    confidence: float = 0.0


@dataclass(slots=True)
class SourceStructureHint:
    hint_id: str
    hint_type: str
    query_family: str | None
    rank: int
    hint_text: str
    root_key: str | None = None
    folder_id: str | None = None
    entity_id: str | None = None
    evidence: list[str] = field(default_factory=list)


@dataclass(slots=True)
class SourceStructureFinding:
    finding_id: str
    finding_type: str
    severity: str
    title: str
    root_key: str | None = None
    folder_id: str | None = None
    entity_id: str | None = None
    details: str | None = None
    evidence: list[str] = field(default_factory=list)
    status: str = "open"


@dataclass(slots=True)
class SourceStructureRun:
    run_id: str
    run_type: str
    started_at: str
    status: str
    finished_at: str | None = None
    roots: list[str] = field(default_factory=list)
    options: dict | None = None
    counts: dict | None = None
    error_text: str | None = None


@dataclass(slots=True)
class FolderRecord:
    """A fully-classified folder ready to persist (parsed structure + classification)."""

    root_key: str
    rel_path: str
    name: str
    depth: int
    parent_rel_path: str | None
    classification: "FolderClassification"
    child_folder_count: int = 0
    file_count: int = 0
    dominant_extensions: list[str] = field(default_factory=list)
    sample_names: list[str] = field(default_factory=list)


@dataclass(slots=True)
class StructureCursor:
    """Opaque forward-only pagination cursor (offset-based, serialized as a string)."""

    offset: int = 0

    def encode(self) -> str:
        return str(self.offset)

    @classmethod
    def decode(cls, raw: str | None) -> StructureCursor:
        if not raw:
            return cls(offset=0)
        try:
            return cls(offset=max(0, int(raw)))
        except (TypeError, ValueError):
            return cls(offset=0)


@dataclass(slots=True)
class StructurePage:
    items: list[dict]
    next_cursor: str | None = None
    total_estimate: int | None = None


def clamp_limit(limit: int | None) -> int:
    """Coerce a client-supplied limit into [1, MAX_PAGE_SIZE]."""

    if not limit or limit < 1:
        return DEFAULT_PAGE_SIZE
    return min(int(limit), MAX_PAGE_SIZE)
