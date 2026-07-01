"""Phase 10G correction — email-card project-identity reconciliation (block-authoritative).

The managed hb-project-identity block is authoritative: the card's frontmatter project_key and the
visible "## Related Project" text must be corrected to agree with it (the DB may carry a stale key).
Reconcile is idempotent, preserves the block + everything else byte-for-byte, and is a no-op / hard
"no block" when the block is absent. Pure functions; no I/O.
"""

from __future__ import annotations

import re

from hb_assistant.obsidian_mcp import source_project_identity as pid
from hb_assistant.obsidian_mcp.source_note_graph import parse_frontmatter_tags

# A Tropical email card with the observed defect: frontmatter project_key holds the NUMBER, the block
# resolves project_key="tropical", and the visible text still says "no project record linked yet".
_CARD = (
    "---\n"
    "note_type: source_card\n"
    'document_type: "email"\n'
    'project_key: "23-435-01"\n'
    'project_number: "23-435-01"\n'
    "tags:\n"
    "  - source/type/correspondence\n"
    "  - project/23-435-01\n"
    "---\n"
    "# Email\n\n"
    "## Related Project\n"
    "- Detected project number: 23-435-01; no project record linked yet.\n\n"
    '<!-- hb-project-identity:start project_number="23-435-01" project_key="tropical" '
    'procore_project_id="2525840" -->\n'
    "- Resolved project: 23-435-01 · tropical · Tropical\n"
    "- Procore project id: 2525840\n"
    "<!-- hb-project-identity:end -->\n\n"
    "## Source Basis\n- keep me\n"
)


def _fm_key(text, key):
    m = re.search(rf'(?m)^{key}:\s*"?([^"\n]+)"?', text)
    return m.group(1) if m else None


def test_reconcile_makes_frontmatter_and_block_agree():
    out, reason = pid.reconcile_card_identity(_CARD)
    assert reason == "reconciled"
    ident = pid.parse_identity_marker(out)
    assert _fm_key(out, "project_key") == ident["project_key"] == "tropical"
    assert _fm_key(out, "project_number") == "23-435-01"
    # exactly one project/23-435-01 tag
    _ok, tags, _f, _l = parse_frontmatter_tags(out)
    assert tags.count("project/23-435-01") == 1


def test_reconcile_replaces_no_project_placeholder():
    out, _ = pid.reconcile_card_identity(_CARD)
    assert "no project record linked yet" not in out
    assert re.search(r"## Related Project\n- Project: 23-435-01 — Tropical", out)


def test_reconcile_preserves_identity_block_and_other_content():
    out, _ = pid.reconcile_card_identity(_CARD)
    assert out.count("hb-project-identity:start") == 1 and out.count("hb-project-identity:end") == 1
    # the block body + an unrelated section survive byte-for-byte
    assert "- Resolved project: 23-435-01 · tropical · Tropical" in out
    assert "## Source Basis\n- keep me" in out


def test_reconcile_is_idempotent():
    out1, r1 = pid.reconcile_card_identity(_CARD)
    out2, r2 = pid.reconcile_card_identity(out1)
    assert r1 == "reconciled" and r2 == "already_consistent" and out2 == out1


def test_reconcile_requires_a_resolving_block():
    no_block = _CARD.split("<!-- hb-project-identity:start")[0] + "## Source Basis\n- x\n"
    out, reason = pid.reconcile_card_identity(no_block)
    assert out is None and reason == "no_resolving_identity_block"


def test_block_is_authoritative_over_frontmatter():
    # Even though frontmatter says 23-435-01, the block's tropical wins.
    out, _ = pid.reconcile_card_identity(_CARD)
    assert _fm_key(out, "project_key") == "tropical"


def test_frontmatter_reconcile_only_touches_project_lines():
    out = pid.reconcile_frontmatter_identity(_CARD, project_number="23-435-01", project_key="tropical")
    assert "note_type: source_card" in out and 'document_type: "email"' in out  # untouched
    assert _fm_key(out, "project_key") == "tropical"
