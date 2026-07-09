"""Tree parser + deterministic classifier unit tests."""

from __future__ import annotations

from hb_assistant.obsidian_mcp.source_structure_classifier import (
    classify_folder,
    classify_root,
    classify_tree,
    extract_project_number,
    is_noise_name,
)
from hb_assistant.obsidian_mcp.source_structure_models import FolderSample
from hb_assistant.obsidian_mcp.source_structure_tree_parser import parse_tree_text

TREE = """/Work/NAS - HB
├── 21-801-01 NORA
│   ├── Submittals
│   │   └── Log.xlsx
│   ├── RFIs
│   └── Drawings
│       └── A-101.pdf
├── @eaDir
└── 22-100-00
    └── Pay Applications
/Backup/MacBook-Pro.local
└── Documents
"""


# --- parser --------------------------------------------------------------------------------
def test_parser_recovers_roots_and_depths():
    t = parse_tree_text(TREE, is_noise_name=is_noise_name)
    assert {r.root_key for r in t.roots} == {"nas-hb", "macbook-pro-local"}
    by_rel = {(f.root_key, f.rel_path): f for f in t.folders}
    assert by_rel[("nas-hb", "21-801-01 NORA")].depth == 1
    assert by_rel[("nas-hb", "21-801-01 NORA/Submittals")].depth == 2


def test_parser_distinguishes_files_from_folders():
    t = parse_tree_text(TREE)
    sub = next(f for f in t.folders if f.rel_path == "21-801-01 NORA/Submittals")
    assert sub.file_count == 1  # Log.xlsx is a file
    assert sub.child_folder_count == 0
    assert "xlsx" in sub.dominant_extensions


def test_parser_counts_noise_children():
    t = parse_tree_text(TREE, is_noise_name=is_noise_name)
    root = next(f for f in t.folders if f.root_key == "nas-hb" and f.rel_path == "")
    assert root.noise_child_count == 1  # @eaDir


def test_parser_never_persists_absolute_paths():
    t = parse_tree_text(TREE)
    assert all(not f.rel_path.startswith("/") for f in t.folders)


# --- project number extraction --------------------------------------------------------------
def test_project_number_full_vs_partial():
    assert extract_project_number("21-801-01 NORA") == ("21-801-01", 0.9)
    assert extract_project_number("22-100 Old") == ("22-100", 0.35)  # partial: weak evidence
    assert extract_project_number("no digits") == (None, 0.0)


# --- root classification --------------------------------------------------------------------
def test_root_classification_matrix():
    assert classify_root("nas-hb", "NAS - HB").root_class == "construction_work"
    assert classify_root("work", "Work").root_class == "work"
    assert classify_root("home", "Home").is_sensitive is True
    b = classify_root("backup", "Backup")
    assert b.root_class == "backup_mirror" and b.is_backup_mirror is True
    g = classify_root("outputs", "mcp-outputs")
    assert g.root_class == "generated_output" and g.is_generated_output is True
    assert classify_root("vault", "Obsidian Vault").root_class == "vault"


# --- folder classification ------------------------------------------------------------------
def _c(name, root):
    return classify_folder(FolderSample(root_key=root.root_key, rel_path=name, name=name, depth=1), root)


def test_folder_safety_classes_take_precedence():
    nas = classify_root("nas-hb", "NAS - HB")
    assert _c("@eaDir", nas).is_noise is True
    assert _c("node_modules", nas).folder_class == "dev_runtime"
    assert _c("Old Backup", nas).is_backup_mirror is True
    assert _c("AI Outputs", nas).is_generated_output is True


def test_folder_doc_families():
    nas = classify_root("nas-hb", "NAS - HB")
    assert _c("Submittals", nas).doc_family == "submittal"
    assert _c("RFIs", nas).doc_family == "rfi"
    assert _c("Change Orders", nas).doc_family == "change_order"
    assert _c("Pay Applications", nas).doc_family == "pay_app"
    assert _c("Drawings", nas).doc_family == "drawings"
    assert _c("Closeout", nas).doc_family == "closeout"


def test_project_root_and_personal():
    nas = classify_root("nas-hb", "NAS - HB")
    pr = _c("21-801-01 NORA", nas)
    assert pr.folder_class == "project_root" and pr.project_number == "21-801-01"
    home = classify_root("home", "Home")
    assert _c("Personal Tax", home).is_sensitive is True


# --- classify_tree inheritance --------------------------------------------------------------
def test_classify_tree_inherits_project_numbers_to_descendants():
    t = parse_tree_text(TREE, is_noise_name=is_noise_name)
    _roots, records = classify_tree(t)
    by = {(r.root_key, r.rel_path): r for r in records}
    sub = by[("nas-hb", "21-801-01 NORA/Submittals")]
    assert sub.classification.project_number == "21-801-01"
    assert sub.classification.classification_source == "inherited"
    # Its own doc-family survives inheritance.
    assert sub.classification.doc_family == "submittal"


PARTIAL_TREE = """/Work/NAS - HB
└── 22-100 Riverside
    ├── Submittals
    └── RFIs
"""


def test_partial_project_number_inheritance_and_confidence():
    t = parse_tree_text(PARTIAL_TREE, is_noise_name=is_noise_name)
    _roots, records = classify_tree(t)
    by = {(r.root_key, r.rel_path): r for r in records}
    root = by[("nas-hb", "22-100 Riverside")]
    # Partial NN-NNN project root is low-confidence (0.35), still a project candidate.
    assert root.classification.project_number == "22-100"
    assert root.classification.classification_confidence == 0.35
    # Partial number inherits to descendants like a full one.
    sub = by[("nas-hb", "22-100 Riverside/Submittals")]
    assert sub.classification.project_number == "22-100"
    assert sub.classification.classification_source == "inherited"
