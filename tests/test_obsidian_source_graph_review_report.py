"""Phase 10G — safe review report is count-only / sanitized (amendment 6 basis-vs-applied separation).

The human-review report renders ONLY counts and distributions — never titles, paths, subjects,
addresses, message ids, attachment names, or raw qwen text. Basis counts (deterministic signals) are
reported separately from applied relationship types (qwen-approved). Pure function; no I/O.
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "obsidian_source_note_apply_graph.py"
_spec = importlib.util.spec_from_file_location("apply_note_graph_rr", _SCRIPT)
assert _spec and _spec.loader
mod = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(mod)


def _safe():
    return {
        "mode": "apply", "eligibility_mode": "primary_secondary",
        "project_number": "23-435-01", "project_key": "tropical", "procore_project_id": "2525840",
        "notes_selected": 100, "selection_truncated": False,
        "project_cards": 40, "email_cards": 35, "attachment_cards": 25,
        "excluded_outside_project": 7,
        "candidate_pairs": 12, "lineage_pairs_excluded": 3, "duplicate_review_candidates": 2,
        "candidate_basis_counts": {"same_parent_email": 5, "same_procore_id": 12, "same_vendor": 4},
        "ollama_calls": 12, "vetted_pairs": 12, "approved_pairs": 6,
        "rejection_reasons": {"rejected": 5, "invalid_json": 1},
        "relationships_applied": 6, "reciprocal_links_applied": 12,
        "applied_relationship_types": {"same_company": 4, "supports_or_explains": 2},
        "notes_modified": 9, "tags_added": 14,
        "backlink_integrity_passed": True, "backlinks_verified": 6,
        "queue_delta": 0, "db_mutations": 0, "created": 0, "deleted": 0,
    }


def test_report_is_count_only_and_reports_all_sections():
    md = mod._render_review_report(_safe())
    # counts + distributions present
    assert "notes_selected: 100" in md
    assert "candidate_pairs: 12" in md and "lineage_pairs_excluded: 3" in md
    assert "duplicate_review_candidates" in md and ": 2" in md
    assert "approved_pairs: 6" in md and "relationships_applied: 6" in md
    assert "backlink_integrity_passed: True" in md
    assert "queue_delta: 0" in md and "db_mutations: 0" in md
    # basis and applied are separate sections, not conflated
    assert "same_procore_id: 12" in md  # basis
    assert "same_company: 4" in md  # applied relationship type
    assert "candidate_basis_counts" in md and "applied_relationship_types" in md


def test_report_leaks_nothing_sensitive():
    safe = _safe()
    # even if callers were to stuff sensitive-looking strings into unrelated keys, the renderer must
    # only read the known count fields — never echo bodies/paths/titles/subjects/addresses/ids.
    safe["_should_not_render"] = "john@example.com [[Secret Title]] /Users/bobby/vault/x.md"
    md = mod._render_review_report(safe)
    for leak in ("john@example.com", "[[", "Secret Title", "/Users/", ".md", "vault"):
        assert leak not in md, leak


def test_report_handles_empty_distributions():
    safe = _safe()
    safe["candidate_basis_counts"] = {}
    safe["applied_relationship_types"] = {}
    safe["rejection_reasons"] = {}
    md = mod._render_review_report(safe)
    assert "none" in md  # empty distributions render as "none", not a crash
