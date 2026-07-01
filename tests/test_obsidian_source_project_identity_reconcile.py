"""Phase 10H — block-authoritative identity reconcile works for ANY Tropical source card.

Phase 10G proved the reconcile on email cards; Phase 10H relies on the SAME helpers for non-email
(general_document / submittal / drawing / cost) cards. These tests assert the helpers are document-type
agnostic, block-authoritative, idempotent, and byte-preserving outside the frontmatter project fields +
the visible Related Project line. Pure functions; no I/O.
"""

from __future__ import annotations

import re

from hb_assistant.obsidian_mcp import source_project_identity as pid
from hb_assistant.obsidian_mcp.source_note_graph import parse_frontmatter_tags


def _card(doctype, *, fm_key='"23-435-01"'):
    return (
        "---\n"
        "note_type: source_card\n"
        f'document_type: "{doctype}"\n'
        f"project_key: {fm_key}\n"
        'project_number: "23-435-01"\n'
        "tags:\n  - source/type/spreadsheet\n  - project/23-435-01\n---\n"
        "# Card\n\n## Related Project\n"
        "- Detected project number: 23-435-01; no project record linked yet.\n\n"
        '<!-- hb-project-identity:start project_number="23-435-01" project_key="tropical" '
        'procore_project_id="2525840" -->\n'
        "- Resolved project: 23-435-01 · tropical · Tropical World Nursery Senior Living Facility\n"
        "- Procore project id: 2525840\n"
        "<!-- hb-project-identity:end -->\n\n"
        "## Key Facts\n- keep me exactly\n"
    )


def _fmk(text, key):
    m = re.search(rf'(?m)^{key}:\s*"?([^"\n]+)"?', text)
    return m.group(1) if m else None


def test_reconcile_non_email_general_document_card():
    out, reason = pid.reconcile_card_identity(_card("general_document"))
    assert reason == "reconciled"
    assert _fmk(out, "project_key") == "tropical" and _fmk(out, "project_number") == "23-435-01"
    assert "no project record linked yet" not in out
    assert re.search(r"## Related Project\n- Project: 23-435-01 — Tropical World Nursery", out)


def test_reconcile_is_document_type_agnostic():
    for dt in ("submittal", "mep_drawing", "cost_document", "spreadsheet"):
        out, reason = pid.reconcile_card_identity(_card(dt))
        assert reason == "reconciled", dt
        assert _fmk(out, "project_key") == "tropical", dt


def test_block_authoritative_and_idempotent_and_preserves_other_sections():
    out1, r1 = pid.reconcile_card_identity(_card("cost_document"))
    out2, r2 = pid.reconcile_card_identity(out1)
    assert r1 == "reconciled" and r2 == "already_consistent" and out2 == out1
    assert "## Key Facts\n- keep me exactly" in out1  # unrelated section byte-preserved
    assert out1.count("hb-project-identity:start") == 1
    _ok, tags, _f, _l = parse_frontmatter_tags(out1)
    assert tags.count("project/23-435-01") == 1 and "source/type/spreadsheet" in tags


def test_reconcile_requires_resolving_block():
    no_block = _card("general_document").split("<!-- hb-project-identity:start")[0] + "## Key Facts\n- x\n"
    out, reason = pid.reconcile_card_identity(no_block)
    assert out is None and reason == "no_resolving_identity_block"


def test_frontmatter_helper_overwrites_wrong_key_only():
    out = pid.reconcile_frontmatter_identity(_card("submittal"), project_number="23-435-01",
                                             project_key="tropical")
    assert 'document_type: "submittal"' in out and "note_type: source_card" in out
    assert _fmk(out, "project_key") == "tropical" and _fmk(out, "project_number") == "23-435-01"
