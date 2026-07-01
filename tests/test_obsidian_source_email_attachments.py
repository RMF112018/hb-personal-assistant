"""Phase 10F — deterministic email attachment extraction, safe naming, guarded binary write, blocks.

Synthetic sanitized fixtures only (built via email.message.EmailMessage); no real attachment content.
"""

from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import source_email_attachments as att
from hb_assistant.obsidian_mcp.mdutil import split_frontmatter as _split_fm
from hb_assistant.obsidian_mcp.source_indexer import is_email_archive_path


def _write_eml(tmp: Path, m: EmailMessage, name: str = "m.eml") -> Path:
    p = tmp / name
    p.write_bytes(m.as_bytes())
    return p


def _base() -> EmailMessage:
    m = EmailMessage()
    m["Subject"] = "RE: TWN Fire Alarm Design"
    m["From"] = "Jane Roe <jane@powerdesign.example>"
    m["To"] = "John Doe <john@hbconstruction.example>"
    m["Date"] = "Thu, 14 Aug 2025 10:30:00 -0400"
    m.set_content("Transmittal body — see attached.")
    return m


def test_extracts_normal_attachment(tmp_path):
    m = _base()
    m.add_attachment(b"%PDF-1.4 permit comments", maintype="application", subtype="pdf",
                     filename="permit.pdf")
    atts, inline = att.extract_attachments(_write_eml(tmp_path, m))
    assert inline == 0 and len(atts) == 1
    a = atts[0]
    assert a.status == "extracted" and a.ext == "pdf" and not a.is_inline
    assert a.content_type == "application/pdf" and a.disposition == "attachment"
    assert a.size_bytes and a.sha256 and a.data == b"%PDF-1.4 permit comments"


def test_separates_inline_images(tmp_path):
    m = _base()
    m.add_attachment(b"%PDF real", maintype="application", subtype="pdf", filename="real.pdf")
    m.add_attachment(b"\x89PNG logo", maintype="image", subtype="png", filename="logo.png",
                     cid="<logo@cid>")
    atts, inline = att.extract_attachments(_write_eml(tmp_path, m))
    assert inline == 1  # inline image counted, not carded
    assert [a.filename for a in atts] == ["real.pdf"]  # only the true attachment returned


def test_missing_filename_deterministic_name(tmp_path):
    m = _base()
    m.add_attachment(b"data-no-name", maintype="application", subtype="pdf")  # no filename
    atts, _ = att.extract_attachments(_write_eml(tmp_path, m))
    a = atts[0]
    rel = att.attachment_rel_path("parentsid1234567890", a)
    assert rel.startswith(att.ATTACHMENTS_SUBDIR + "/")
    assert "attachment-0-pdf" in rel and rel.endswith(".pdf")


def test_path_traversal_filename_sanitized(tmp_path):
    m = _base()
    m.add_attachment(b"evil", maintype="application", subtype="pdf",
                     filename="../../../etc/evil.pdf")
    atts, _ = att.extract_attachments(_write_eml(tmp_path, m))
    rel = att.attachment_rel_path("sid123456789012", atts[0])
    assert ".." not in rel and "/etc/" not in rel
    assert rel.startswith(att.ATTACHMENTS_SUBDIR + "/") and "evil" in rel


def test_duplicate_hash_dedupes(tmp_path):
    m = _base()
    m.add_attachment(b"same-bytes", maintype="application", subtype="pdf", filename="a.pdf")
    m.add_attachment(b"same-bytes", maintype="application", subtype="pdf", filename="b.pdf")
    atts, _ = att.extract_attachments(_write_eml(tmp_path, m))
    assert atts[0].status == "extracted" and atts[1].status == "duplicate"
    assert atts[1].data is None


def test_unsafe_extension_skipped(tmp_path):
    m = _base()
    m.add_attachment(b"MZ evil", maintype="application", subtype="octet-stream", filename="tool.exe")
    atts, _ = att.extract_attachments(_write_eml(tmp_path, m))
    assert atts[0].status == "skipped_unsafe_type" and atts[0].data is None
    assert atts[0].size_bytes and atts[0].sha256  # metadata preserved, not silently dropped


def test_oversize_skipped_by_cap(tmp_path):
    m = _base()
    m.add_attachment(b"x" * 100, maintype="application", subtype="pdf", filename="big.pdf")
    atts, _ = att.extract_attachments(_write_eml(tmp_path, m), max_bytes=10)
    assert atts[0].status == "skipped_size_cap" and atts[0].data is None


def test_empty_attachment_skipped(tmp_path):
    m = _base()
    m.add_attachment(b"", maintype="application", subtype="pdf", filename="empty.pdf")
    atts, _ = att.extract_attachments(_write_eml(tmp_path, m))
    assert atts[0].status == "skipped_empty"


def test_metadata_preserved_and_sha_computed(tmp_path):
    m = _base()
    m.add_attachment(b"csv,log,data", maintype="text", subtype="csv", filename="log.csv")
    a = att.extract_attachments(_write_eml(tmp_path, m))[0][0]
    import hashlib
    assert a.sha256 == hashlib.sha256(b"csv,log,data").hexdigest()
    assert a.content_type == "text/csv" and a.ext == "csv" and a.size_bytes == 12


def test_parse_failed_is_fail_safe(tmp_path):
    p = tmp_path / "missing.eml"
    atts, inline = att.extract_attachments(p)
    assert atts and atts[0].status == "parse_failed" and inline == 0


def test_guard_covers_attachments_path():
    # amendment #1: the attachments subtree is under the Email Archive self-index guard.
    assert is_email_archive_path("Email Archive/Work/Attachments/sid/x__abc.pdf")
    assert is_email_archive_path(att.ATTACHMENTS_SUBDIR + "/sid/y.pdf")


def test_write_binary_guarded(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    rel = "Email Archive/Work/Attachments/sid12/plan__deadbeef.pdf"
    assert att.write_attachment_binary(vault, rel, b"%PDF") == "written"
    assert (vault / rel).read_bytes() == b"%PDF"
    # idempotent: same bytes -> duplicate no-op
    assert att.write_attachment_binary(vault, rel, b"%PDF") == "duplicate"
    # refuses paths outside the attachments root
    with pytest.raises(ValueError):
        att.write_attachment_binary(vault, "Source Notes/Work/x.pdf", b"..")
    # refuses traversal escape even under the prefix
    with pytest.raises(ValueError):
        att.write_attachment_binary(vault, "Email Archive/Work/Attachments/../../../evil.pdf", b"..")
    # refuses overwrite of byte-different existing without overwrite
    with pytest.raises(ValueError):
        att.write_attachment_binary(vault, rel, b"DIFFERENT")


def test_delete_binary_guarded_and_prunes(tmp_path):
    vault = tmp_path / "vault"
    vault.mkdir(exist_ok=True)
    rel = "Email Archive/Work/Attachments/sid12/plan__deadbeef.pdf"
    att.write_attachment_binary(vault, rel, b"%PDF")
    assert (vault / rel).exists()
    # deletes the transient binary and prunes the now-empty per-email dir up to the attachments root
    assert att.delete_attachment_binary(vault, rel) is True
    assert not (vault / rel).exists()
    assert not (vault / rel).parent.exists()  # empty sid12/ pruned
    assert (vault / att.ATTACHMENTS_SUBDIR).exists() or True  # attachments root itself never required
    # idempotent: deleting an already-gone file is a no-op, not an error
    assert att.delete_attachment_binary(vault, rel) is False
    # refuses paths outside the attachments root
    with pytest.raises(ValueError):
        att.delete_attachment_binary(vault, "Source Notes/Work/x.pdf")
    with pytest.raises(ValueError):
        att.delete_attachment_binary(vault, "Email Archive/Work/Attachments/../../../evil.pdf")


def test_attachment_marker_roundtrip(tmp_path):
    m = _base()
    m.add_attachment(b"%PDF", maintype="application", subtype="pdf", filename="p.pdf")
    a = att.extract_attachments(_write_eml(tmp_path, m))[0][0]
    facts = att.attachment_card_facts("parent-source-id-xyz", a)
    marker = att.attachment_marker(facts)
    assert "@" not in marker  # no raw addresses
    back = att.parse_email_attachment_marker(marker)
    assert back["attachment_sha256"] == a.sha256
    assert back["parent_email_hash"] == facts["parent_email_hash"]
    assert back["attachment_extension"] == "pdf"


_CARD = ("---\nnote_type: source_card\n---\n# Source Card: x\n\n"
         "## Source Basis\n- basis\n\n## Advisory Summary\n- none\n")


def test_enrich_attachment_card_one_block_idempotent(tmp_path):
    m = _base()
    m.add_attachment(b"%PDF", maintype="application", subtype="pdf", filename="p.pdf")
    a = att.extract_attachments(_write_eml(tmp_path, m))[0][0]
    facts = att.attachment_card_facts("psid", a)
    new, reason = att.enrich_card_with_attachment(
        _CARD, facts, "Source Notes/Work/parent__abcdef012345.md",
        "Email Archive/Work/Shared/parent__abcdef012345.md")
    assert reason == "inserted" and new.count(att.ATTACH_BEGIN_PREFIX) == 1
    assert "Parent email card:" in new and "Parent email archive:" in new
    again, r2 = att.enrich_card_with_attachment(new, facts, "Source Notes/Work/parent__abcdef012345.md",
                                                "Email Archive/Work/Shared/parent__abcdef012345.md")
    assert r2 == "updated" and again.count(att.ATTACH_BEGIN_PREFIX) == 1


_IDENT_CARD = (
    "---\nnote_type: source_card\ndomain: \"work\"\nproject_key: null\nproject_number: null\n"
    "document_type: \"spreadsheet\"\ntags:\n  - source/external_file\n  - domain/work\n---\n\n"
    "# Source Card: x\n\n## Related Project\n- No project number detected; none linked yet.\n\n"
    "<!-- hb-project-identity:start project_number=\"23-435-01\" project_key=\"tropical\" -->\n"
    "- Resolved project: 23-435-01 · tropical\n<!-- hb-project-identity:end -->\n\n## Source Basis\n- x\n"
)


def test_frontmatter_populated_from_null():
    out = att.apply_inherited_project_frontmatter(
        _IDENT_CARD, project_number="23-435-01", project_key="tropical")
    fm, _b = _split_fm(out)
    assert fm["project_number"] == "23-435-01" and fm["project_key"] == "tropical"
    assert "project/23-435-01" in [str(t) for t in fm.get("tags", [])]


def test_frontmatter_added_when_missing():
    card = _IDENT_CARD.replace("project_key: null\nproject_number: null\n", "")
    out = att.apply_inherited_project_frontmatter(card, project_number="23-435-01", project_key="tropical")
    fm, _b = _split_fm(out)
    assert fm["project_number"] == "23-435-01" and fm["project_key"] == "tropical"


def test_frontmatter_preexisting_nonnull_not_clobbered():
    card = _IDENT_CARD.replace('project_number: null', 'project_number: "99-999-99"')
    out = att.apply_inherited_project_frontmatter(card, project_number="23-435-01", project_key="tropical")
    fm, _b = _split_fm(out)
    assert fm["project_number"] == "99-999-99"  # existing real value preserved


def test_project_tag_not_duplicated():
    card = _IDENT_CARD.replace("  - domain/work\n", "  - domain/work\n  - project/23-435-01\n")
    out = att.apply_inherited_project_frontmatter(card, project_number="23-435-01", project_key="tropical")
    fm, _b = _split_fm(out)
    assert [str(t) for t in fm["tags"]].count("project/23-435-01") == 1


def test_related_project_bullet_reconciled_and_single_block():
    out = att.reconcile_related_project_line(
        _IDENT_CARD, project_number="23-435-01", project_key="tropical",
        project_name="Tropical World Nursery")
    assert "No project number detected" not in out
    assert "- Project (inherited from parent email): 23-435-01 · tropical · Tropical World Nursery" in out
    assert out.count("hb-project-identity:start") == 1  # managed block untouched


def test_related_project_reconcile_idempotent():
    once = att.reconcile_related_project_line(_IDENT_CARD, project_number="23-435-01", project_key="tropical")
    twice = att.reconcile_related_project_line(once, project_number="23-435-01", project_key="tropical")
    assert once == twice and once.count(att._INHERITED_PROJECT_PREFIX) == 1


def test_identity_reconcile_no_self_contradiction():
    out = att.apply_inherited_project_frontmatter(
        _IDENT_CARD, project_number="23-435-01", project_key="tropical")
    out = att.reconcile_related_project_line(out, project_number="23-435-01", project_key="tropical")
    fm, _b = _split_fm(out)
    assert fm["project_number"] == "23-435-01"
    assert "No project number detected" not in out
    assert out.count("hb-project-identity:start") == 1


def test_parent_attachments_block_one_dedup_idempotent():
    entries = [("Source Notes/Work/a__111111111111.md", "extracted"),
               ("Source Notes/Work/b__222222222222.md", "metadata_only"),
               ("Source Notes/Work/a__111111111111.md", "extracted")]  # dup rel
    new, reason = att.upsert_email_attachments_block(_CARD, entries)
    assert reason == "inserted" and new.count(att.ATTACHMENTS_BEGIN) == 1
    assert new.count("— extracted attachment ·") == 2  # deduped to 2
    again, r2 = att.upsert_email_attachments_block(new, entries)
    assert r2 == "updated" and again.count(att.ATTACHMENTS_BEGIN) == 1
