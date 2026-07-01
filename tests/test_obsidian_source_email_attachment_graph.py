"""Phase 10F — attachment graph facts + candidate signals (deterministic; never body-derived).

Synthetic fixtures only. Proves attachment cards contribute parent-email + attachment-sha signals, that a
shared extension alone is weak, and that body text is never a strong signal.
"""

from __future__ import annotations

from hb_assistant.obsidian_mcp import source_email_attachments as att
from hb_assistant.obsidian_mcp import source_note_graph as ng


def _nf(note_id: str, *, basename: str = "att", document_type: str = "general_pdf",
        summary: str = "", parent: str | None = None, shas: frozenset[str] = frozenset(),
        ext: str | None = None, title=frozenset()) -> ng.NoteFact:
    return ng.NoteFact(
        note_id=note_id, note_rel=f"Source Notes/Work/{basename}__{note_id}.md", basename=basename,
        display=basename, project=None, vendor=None, document_type=document_type,
        document_number=None, doc_date=None, disposition="metadata_only", review_needed=False,
        title_tokens=title, existing_tags=(), summary_text=summary,
        parent_email_hash=parent, attachment_sha256s=shas, attachment_extension=ext)


def test_same_parent_email_is_strong_candidate():
    a = _nf("s1", parent="deadbeef0001")
    b = _nf("s2", parent="deadbeef0001")
    ok, signals = ng.is_candidate(a, b)
    assert ok and "same_parent_email" in signals


def test_same_attachment_sha256_is_strong_candidate():
    a = _nf("s1", shas=frozenset({"abc123"}))
    b = _nf("s2", shas=frozenset({"abc123"}))
    ok, signals = ng.is_candidate(a, b)
    assert ok and "same_attachment_sha256" in signals


def test_same_extension_only_is_weak_no_candidate():
    a = _nf("s1", ext="pdf", document_type="general_document")
    b = _nf("s2", ext="pdf", document_type="general_document")
    ok, signals = ng.is_candidate(a, b)
    assert "same_attachment_extension" in signals
    assert "same_attachment_extension" in ng._WEAK_SIGNALS
    assert not ok  # a shared extension alone must not create a candidate


def test_body_text_is_never_a_strong_signal():
    shared = "attachment mentions SECRETPHRASE and permit comments"
    a = _nf("s1", summary=shared, basename="alpha", document_type="general_document")
    b = _nf("s2", summary=shared, basename="beta", document_type="general_document")
    ok, signals = ng.is_candidate(a, b)
    strong = [s for s in signals if s not in ng._WEAK_SIGNALS]
    assert not ok and not strong  # body commonality alone yields no candidate


def test_candidate_basis_counts_surface_attachment_signals():
    a = _nf("s1", parent="p1", shas=frozenset({"sha-x"}), ext="pdf")
    b = _nf("s2", parent="p1", shas=frozenset({"sha-x"}), ext="pdf")
    cands = ng.build_candidates([a, b])
    counts = ng.candidate_basis_counts(cands)
    assert counts.get("same_parent_email") == 1
    assert counts.get("same_attachment_sha256") == 1
    assert counts.get("same_attachment_extension") == 1  # weak, still reported


class _FakeRepo:
    def __init__(self, detail):
        self._d = detail

    def get_source_detail(self, source_id):
        return dict(self._d, source_id=source_id)


def test_note_fact_from_parses_attachment_block():
    facts = att.attachment_card_facts("parent-src-id", type("E", (), {
        "sha256": "0123456789abcdef", "index": 0, "content_type": "application/pdf",
        "disposition": "attachment", "ext": "pdf", "status": "extracted"})())
    card = ("---\nnote_type: source_card\n---\n# Source Card: x\n\n"
            "## Source Basis\n- basis\n\n## Advisory Summary\n- none\n")
    card, _ = att.enrich_card_with_attachment(
        card, facts, "Source Notes/Work/parent__aaaaaaaaaaaa.md",
        "Email Archive/Work/Shared/parent__aaaaaaaaaaaa.md")
    detail = {"rel_path": "psid/permit__0123.pdf", "file_ext": "pdf", "project_number": None}
    row = {"source_id": "att1", "note_rel_path": "Source Notes/Work/permit__att1.md"}
    fact = ng.note_fact_from(_FakeRepo(detail), row, card)
    assert fact.parent_email_hash == facts["parent_email_hash"]
    assert "0123456789abcdef" in fact.attachment_sha256s
    assert fact.attachment_extension == "pdf"
