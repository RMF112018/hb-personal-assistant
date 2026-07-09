"""Deterministic, rule-first classification for the source-structure index.

Every classification here is a pure function of names/paths/counts — no model, no filesystem, no
network. Safety-critical classes (noise, backup/mirror, generated-output, sensitive/personal) take
precedence over doc-family and are the ones a later Ollama phase must NEVER override.

Lower ``search_rank`` = searched first. Backup/mirror and generated-output roots are downranked;
construction work roots and project/doc-family folders are upranked.
"""

from __future__ import annotations

import re

from hb_assistant.obsidian_mcp.source_structure_models import (
    FolderClassification,
    FolderRecord,
    FolderSample,
    FolderStats,
    SourceStructureRoot,
)

# --- Lexicons ---------------------------------------------------------------------------------
NOISE_NAMES: frozenset[str] = frozenset(
    {
        "@eadir",
        "__macosx",
        ".ds_store",
        ".trash",
        ".trashes",
        ".git",
        ".svn",
        ".hg",
        ".pytest_cache",
        ".mypy_cache",
        ".ruff_cache",
        ".idea",
        ".vscode",
        "thumbs.db",
    }
)

# Dev/runtime folders — a distinct noise subclass (still is_noise=True).
DEV_RUNTIME_NAMES: frozenset[str] = frozenset(
    {
        "node_modules",
        ".venv",
        "venv",
        "__pycache__",
        ".next",
        ".cache",
        "dist",
        "build",
        ".terraform",
        ".gradle",
    }
)

# Backup / mirror signals (substring match, lowercased).
BACKUP_SUBSTRINGS: tuple[str, ...] = (
    "backup",
    "one drive backup",
    "onedrive backup",
    "dropbox backup",
    "macbook-pro.local",
    "time machine",
    "timemachine",
)
BACKUP_EXACT: frozenset[str] = frozenset({"old", "copy", "archive", "archives"})

# Generated-output signals.
GENERATED_SUBSTRINGS: tuple[str, ...] = (
    "mcp-outputs",
    "mcp outputs",
    "ai outputs",
    "ai-outputs",
    "generated",
)
GENERATED_EXACT: frozenset[str] = frozenset(
    {"receipts", "manifests", "evidence", "exports", "_generated"}
)

# Personal / sensitive signals.
PERSONAL_SUBSTRINGS: tuple[str, ...] = (
    "personal",
    "tax",
    "medical",
    "health",
    "family",
    "kids",
    "financial statements",
    "estate",
)

# Construction document families → (keywords, resulting folder_class).
# Order matters: earlier entries win when names overlap.
DOC_FAMILY_RULES: tuple[tuple[str, str, tuple[str, ...]], ...] = (
    ("rfi", "rfis", ("rfi", "rfis", "request for information")),
    ("submittal", "submittals", ("submittal", "submittals", "shop drawing")),
    ("change_order", "change_orders", ("change order", "change orders", "pco", "cco", "co log")),
    (
        "pay_app",
        "financials",
        ("pay app", "pay application", "payapp", "invoice", "budget", "forecast",
         "cost report", "sage", "commitment", "prime contract", "sov", "billing"),
    ),
    ("contract", "contracts", ("contract", "agreement", "subcontract", "owner contract")),
    ("drawings", "drawings", ("drawing", "drawings", "plans", "sheets", "bluebeam")),
    ("specifications", "construction_docs", ("spec", "specs", "specification", "project manual")),
    ("schedule", "construction_docs", ("schedule", "cpm", "lookahead", "pull plan", "baseline")),
    (
        "closeout",
        "closeout",
        ("closeout", "close-out", "warranty", "o&m", "as-built", "asbuilt", "punch"),
    ),
    ("photos", "photos", ("photo", "photos", "progress photos", "site photos", "images")),
    ("estimate", "construction_docs", ("estimate", "estimating", "bid", "bids", "proposal", "leveling")),
    ("daily_log", "construction_docs", ("daily log", "field report", "manpower", "weather")),
    ("safety", "construction_docs", ("safety", "inspection", "quality", "observation")),
)

# --- Project number extraction ----------------------------------------------------------------
_PROJECT_FULL_RE = re.compile(r"\b(\d{2}-\d{3}-\d{2})\b")
_PROJECT_PARTIAL_RE = re.compile(r"\b(\d{2}-\d{3})\b")


def extract_project_number(text: str) -> tuple[str | None, float]:
    """Return (project_number, confidence). Full ``NN-NNN-NN`` is high-conf; ``NN-NNN`` low-conf."""
    m = _PROJECT_FULL_RE.search(text)
    if m:
        return m.group(1), 0.9
    m = _PROJECT_PARTIAL_RE.search(text)
    if m:
        # Partial numbers are weak evidence (0.35) — deliberately below the 0.5 "supporting" threshold,
        # especially once inherited to descendants; a partial-only mapping raises a quality finding.
        return m.group(1), 0.35
    return None, 0.0


def is_partial_project_number(number: str | None) -> bool:
    """True when ``number`` is a partial ``NN-NNN`` (not a full ``NN-NNN-NN``) project number."""
    if not number:
        return False
    return bool(_PROJECT_PARTIAL_RE.fullmatch(number)) and not _PROJECT_FULL_RE.fullmatch(number)


def is_noise_name(name: str) -> bool:
    low = name.strip().lower()
    return low in NOISE_NAMES or low in DEV_RUNTIME_NAMES


def _lower(name: str) -> str:
    return name.strip().lower()


# Canonical per-root-class defaults (trust_tier, index_policy, default_search_rank, safety flags).
# Single source of truth shared by classify_root and operator-override rank/trust recomputation.
ROOT_CLASS_DEFAULTS: dict[str, tuple[str, str, int, dict[str, bool]]] = {
    "generated_output": ("generated", "generated_outputs_only", 7, {"is_generated_output": True}),
    "backup_mirror": ("low", "shallow_map", 9, {"is_backup_mirror": True}),
    "personal": ("medium", "selective_metadata", 5, {"is_sensitive": True}),
    "vault": ("supplemental", "vault_notes_only", 6, {}),
    "construction_work": ("high", "deep_metadata", 1, {}),
    "work": ("high", "deep_metadata", 2, {}),
    "unknown": ("medium", "selective_metadata", 8, {}),
}


def root_class_defaults(root_class: str) -> tuple[str, str, int, dict[str, bool]]:
    """Canonical (trust_tier, index_policy, default_search_rank, flags) for a root class."""
    return ROOT_CLASS_DEFAULTS.get(root_class, ROOT_CLASS_DEFAULTS["unknown"])


# --- Root classification ----------------------------------------------------------------------
def classify_root(
    root_key: str, display_name: str, source_header: str | None = None
) -> SourceStructureRoot:
    """Classify a root. SAFETY CLASSES WIN FIRST — generated → backup → personal → vault — before the
    construction/work rules, so a root like "NAS - HB Backup" or a "/Backup/…" header is downranked
    rather than treated as high-trust construction work.

    ``source_header`` (the original absolute path, when available) is used ONLY to strengthen the
    generated/backup *substring* signals (e.g. a "/Backup/Old" root whose basename lost the parent
    context). It is never persisted — rows still carry only the neutral ``root_key``.
    """
    key = _lower(root_key)
    name = _lower(display_name)
    blob = f"{key} {name}"
    # header_blob adds the lowered header path for substring safety-signal matching only.
    header_blob = f"{blob} {_lower(source_header)}" if source_header else blob

    def _mk(root_class, trust, policy, rank, **flags) -> SourceStructureRoot:
        return SourceStructureRoot(
            root_key=root_key,
            display_name=display_name,
            root_class=root_class,
            trust_tier=trust,
            index_policy=policy,
            default_search_rank=rank,
            **flags,
        )

    # 1. Generated output (safety).
    if any(s in header_blob for s in GENERATED_SUBSTRINGS) or key in {"outputs", "mcp-outputs"}:
        return _mk("generated_output", "generated", "generated_outputs_only", 7,
                   is_generated_output=True)
    # 2. Backup / mirror (safety).
    if any(s in header_blob for s in BACKUP_SUBSTRINGS) or key.startswith("backup"):
        return _mk("backup_mirror", "low", "shallow_map", 9, is_backup_mirror=True)
    # 3. Personal / sensitive (safety).
    if key in {"home", "personal"} or any(s in blob for s in PERSONAL_SUBSTRINGS):
        return _mk("personal", "medium", "selective_metadata", 5, is_sensitive=True)
    # 4. Vault / supplemental.
    if "vault" in blob or "obsidian" in blob:
        return _mk("vault", "supplemental", "vault_notes_only", 6)
    # 5. Construction work (only after every safety class has been ruled out).
    if "nas - hb" in blob or "nas-hb" in blob or ("nas" in blob and "hb" in blob):
        return _mk("construction_work", "high", "deep_metadata", 1)
    # 6. General work.
    if key in {"work"} or "work" in blob:
        return _mk("work", "high", "deep_metadata", 2)
    return _mk("unknown", "medium", "selective_metadata", 8)


# --- Folder classification --------------------------------------------------------------------
def _base_rank(root: SourceStructureRoot | None) -> int:
    return (root.default_search_rank if root else 8) * 10


def classify_folder(
    sample: FolderSample, root: SourceStructureRoot | None = None
) -> FolderClassification:
    """Classify one folder. Safety classes (noise/backup/generated/sensitive) win over doc-family."""
    low = _lower(sample.name)
    base = _base_rank(root)

    # 1. Noise / dev-runtime — highest precedence, high confidence.
    if low in NOISE_NAMES:
        return FolderClassification(
            folder_class="noise", doc_family=None, trust_tier="low",
            search_rank=base + 900, is_noise=True, classification_confidence=0.99,
        )
    if low in DEV_RUNTIME_NAMES:
        return FolderClassification(
            folder_class="dev_runtime", doc_family=None, trust_tier="low",
            search_rank=base + 900, is_noise=True, classification_confidence=0.99,
        )

    # 2. Backup / mirror.
    if any(s in low for s in BACKUP_SUBSTRINGS) or low in BACKUP_EXACT:
        return FolderClassification(
            folder_class="backup_mirror", doc_family=None, trust_tier="low",
            search_rank=base + 500, is_backup_mirror=True, classification_confidence=0.85,
        )

    # 3. Generated output.
    if any(s in low for s in GENERATED_SUBSTRINGS) or low in GENERATED_EXACT:
        return FolderClassification(
            folder_class="generated_output", doc_family=None, trust_tier="generated",
            search_rank=base + 300, is_generated_output=True, classification_confidence=0.85,
        )

    # 4. Sensitive / personal (also inherits sensitivity from a personal root).
    root_sensitive = bool(root and root.is_sensitive)
    if any(s in low for s in PERSONAL_SUBSTRINGS):
        return FolderClassification(
            folder_class="personal", doc_family=None, trust_tier="medium",
            search_rank=base + 20, is_sensitive=True, classification_confidence=0.7,
        )

    # 5. Project number → project candidate (may still carry a doc-family below).
    proj, proj_conf = extract_project_number(sample.name)

    # 6. Construction doc-family (name-first, then rel_path fallback).
    haystack = f"{low} {_lower(sample.rel_path)}"
    doc_family: str | None = None
    folder_class = "unknown"
    confidence = 0.4
    for family, fclass, keywords in DOC_FAMILY_RULES:
        if any(kw in haystack for kw in keywords):
            doc_family = family
            folder_class = fclass
            confidence = 0.75
            break

    trust = root.trust_tier if root else "medium"
    rank = base
    is_project = False
    name_hint: str | None = None

    if proj:
        is_project = True
        # A folder whose name *is* the project (and no more specific family) is a project_root; its
        # confidence IS the project-number confidence (0.9 full / 0.35 partial), so a partial-only
        # project root reads as low-confidence rather than being masked by the generic default.
        if folder_class == "unknown":
            folder_class = "project_root"
            confidence = proj_conf
        # Project name hint = the non-numeric remainder of the folder name.
        remainder = _PROJECT_FULL_RE.sub("", sample.name)
        remainder = _PROJECT_PARTIAL_RE.sub("", remainder).strip(" -_")
        name_hint = remainder or None
        rank -= 5

    if doc_family is not None:
        rank -= 3

    # Under a construction root, an otherwise-unknown folder is at least construction_docs.
    if folder_class == "unknown" and root and root.root_class == "construction_work":
        folder_class = "construction_docs"
        confidence = 0.5

    if folder_class == "unknown" and root_sensitive:
        folder_class = "personal"
        trust = "medium"

    return FolderClassification(
        folder_class=folder_class,
        doc_family=doc_family,
        trust_tier=trust,
        search_rank=max(1, rank),
        is_project_candidate=is_project,
        is_sensitive=root_sensitive,
        project_number=proj,
        project_name_hint=name_hint,
        classification_source="rule",
        classification_confidence=confidence,
    )


def classify_tree(parsed_tree) -> tuple[dict[str, SourceStructureRoot], list[FolderRecord]]:
    """Classify a parsed tree into roots + folder records, propagating project numbers to descendants.

    A doc-family folder nested under a project folder (e.g. ``21-801-01/Submittals``) inherits the
    ancestor's project number so project maps show full document-family coverage. Inherited numbers
    are marked ``classification_source='inherited'`` and never override a folder's own extracted number.
    """
    from hb_assistant.obsidian_mcp.source_structure_tree_parser import (
        ParsedTree,  # local: avoid cycle
    )

    assert isinstance(parsed_tree, ParsedTree)
    roots: dict[str, SourceStructureRoot] = {
        pr.root_key: classify_root(pr.root_key, pr.display_name, pr.source_header)
        for pr in parsed_tree.roots
    }

    records: list[FolderRecord] = []
    for pf in parsed_tree.folders:
        root = roots.get(pf.root_key)
        sample = FolderSample(
            root_key=pf.root_key,
            rel_path=pf.rel_path or pf.name,
            name=pf.name,
            depth=pf.depth,
            child_folder_names=pf.child_folder_names,
            stats=FolderStats(
                child_folder_count=pf.child_folder_count,
                file_count=pf.file_count,
                dominant_extensions=pf.dominant_extensions,
                sample_names=pf.sample_names,
            ),
        )
        records.append(
            FolderRecord(
                root_key=pf.root_key,
                rel_path=pf.rel_path,
                name=pf.name,
                depth=pf.depth,
                parent_rel_path=pf.parent_rel_path,
                classification=classify_folder(sample, root),
                child_folder_count=pf.child_folder_count,
                file_count=pf.file_count,
                dominant_extensions=pf.dominant_extensions,
                sample_names=pf.sample_names,
            )
        )

    # Project-number inheritance: index by (root_key, rel_path), walk parent chain.
    by_key: dict[tuple[str, str], FolderRecord] = {(r.root_key, r.rel_path): r for r in records}
    for rec in records:
        if rec.classification.project_number:
            continue
        parent_rel = rec.parent_rel_path
        seen = 0
        while parent_rel is not None and seen < 32:
            seen += 1
            ancestor = by_key.get((rec.root_key, parent_rel))
            if ancestor is None:
                break
            if ancestor.classification.project_number:
                rec.classification.project_number = ancestor.classification.project_number
                rec.classification.project_name_hint = (
                    rec.classification.project_name_hint or ancestor.classification.project_name_hint
                )
                if rec.classification.classification_source == "rule":
                    rec.classification.classification_source = "inherited"
                break
            parent_rel = ancestor.parent_rel_path

    return roots, records
