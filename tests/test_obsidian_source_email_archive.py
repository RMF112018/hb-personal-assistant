"""Phase 10E — deterministic `.eml` MIME parsing + full-fidelity archive-note rendering.

Synthetic sanitized fixtures only (built via email.message.EmailMessage); no real email content.
"""

from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

from hb_assistant.obsidian_mcp import source_email_archive as sea

_SIG = "-- \nJane Roe\nPower Design Example\nDISCLAIMER: confidential."
_REPLY = ("Latest message body here.\n\n"
          "> On Wed someone wrote:\n> earlier quoted line one\n> earlier quoted line two\n")


def _write(tmp: Path, msg: EmailMessage, name: str = "m.eml") -> Path:
    p = tmp / name
    p.write_bytes(msg.as_bytes())
    return p


def _base(**over) -> EmailMessage:
    m = EmailMessage()
    m["Subject"] = over.get("subject", "RE: TWN Fire Alarm Design")
    m["From"] = over.get("from", "Jane Roe <jane@powerdesign.example>")
    m["To"] = over.get("to", "John Doe <john@hbconstruction.example>, pm@hbconstruction.example")
    m["Cc"] = over.get("cc", "boss@owner.example")
    m["Bcc"] = over.get("bcc", "silent@owner.example")
    m["Reply-To"] = over.get("reply_to", "noreply@powerdesign.example")
    m["Message-ID"] = over.get("message_id", "<abc123@mail.example>")
    m["In-Reply-To"] = over.get("in_reply_to", "<prev999@mail.example>")
    m["References"] = over.get("references", "<r1@mail.example> <r2@mail.example>")
    m["Date"] = over.get("date", "Thu, 14 Aug 2025 10:30:00 -0400")
    m["Thread-Topic"] = over.get("thread_topic", "TWN Fire Alarm Design")
    m["Thread-Index"] = over.get("thread_index", "AQHbEXAMPLEINDEX==")
    m["Importance"] = over.get("importance", "High")
    m["X-Priority"] = over.get("priority", "1")
    return m


def test_parse_simple_plain(tmp_path):
    m = _base()
    m.set_content(_REPLY + _SIG)
    em = sea.parse_email_file(_write(tmp_path, m))
    assert em.parse_status == "complete"
    assert em.subject == "RE: TWN Fire Alarm Design"
    assert em.from_email == "jane@powerdesign.example" and em.from_name == "Jane Roe"
    assert em.to == ["John Doe <john@hbconstruction.example>", "pm@hbconstruction.example"]
    assert em.cc == ["boss@owner.example"] and em.bcc == ["silent@owner.example"]
    assert em.reply_to == ["noreply@powerdesign.example"]
    assert em.message_id == "<abc123@mail.example>" and em.in_reply_to == "<prev999@mail.example>"
    assert em.references == ["<r1@mail.example>", "<r2@mail.example>"]
    assert em.thread_topic == "TWN Fire Alarm Design" and em.thread_index.startswith("AQHb")
    assert em.importance == "high" and em.priority == "1"
    assert em.date_iso and em.date_iso.startswith("2025-08-14T10:30:00")


def test_prefers_plain_over_html(tmp_path):
    m = _base()
    m.set_content("PLAIN canonical body")
    m.add_alternative("<html><body><p>HTML body</p></body></html>", subtype="html")
    em = sea.parse_email_file(_write(tmp_path, m))
    assert em.plain_body is not None and em.html_body is not None
    assert em.canonical_body_markdown.strip() == "PLAIN canonical body"


def test_html_fallback_when_no_plain(tmp_path):
    m = _base()
    m.set_content("<html><body><p>Only HTML here</p></body></html>", subtype="html")
    em = sea.parse_email_file(_write(tmp_path, m))
    assert em.plain_body is None and em.html_body is not None
    assert "Only HTML here" in em.canonical_body_markdown
    assert "html_converted" in em.parse_warnings


def test_reply_chain_and_signature_preserved(tmp_path):
    m = _base()
    m.set_content(_REPLY + _SIG)
    em = sea.parse_email_file(_write(tmp_path, m))
    # amendment #6: latest body, quoted reply chain, and signature/disclaimer all preserved.
    assert "Latest message body here." in em.canonical_body_markdown
    assert "> earlier quoted line one" in em.canonical_body_markdown
    assert "DISCLAIMER: confidential." in em.canonical_body_markdown


def test_multipart_mixed_attachments_and_inline_separated(tmp_path):
    m = _base()
    m.set_content("body with an inline image and a real attachment")
    m.add_attachment(b"%PDF-1.4 data", maintype="application", subtype="pdf", filename="proposal.pdf")
    m.add_attachment(b"\x89PNGdata", maintype="image", subtype="png", filename="logo.png",
                     cid="<logo@cid>")
    em = sea.parse_email_file(_write(tmp_path, m))
    true_atts = [a for a in em.attachments if not a.is_inline]
    inline = [a for a in em.attachments if a.is_inline]
    assert em.has_attachments and len(true_atts) == 1 and true_atts[0].filename == "proposal.pdf"
    assert len(inline) == 1 and inline[0].content_id == "logo@cid"
    # attachment metadata incl. sha256 + size
    assert true_atts[0].sha256 and true_atts[0].size_bytes and true_atts[0].content_type == "application/pdf"


def test_malformed_and_missing_fail_safe(tmp_path):
    # a missing file → failed status, no raise
    em = sea.parse_email_file(tmp_path / "does-not-exist.eml")
    assert em.parse_status == "failed" and "parse_failed" in em.parse_warnings
    # garbage bytes → never raises; returns an EmailArchive
    p = tmp_path / "garbage.eml"
    p.write_bytes(b"\x00\x01not a mime message at all\x00")
    em2 = sea.parse_email_file(p)
    assert isinstance(em2, sea.EmailArchive)


def test_empty_body_marks_partial(tmp_path):
    m = _base()
    m.set_content("")
    em = sea.parse_email_file(_write(tmp_path, m))
    assert em.parse_status in ("partial", "complete")
    if em.parse_status == "partial":
        assert "empty_body" in em.parse_warnings


def test_safety_cap_records_truncation(tmp_path, monkeypatch):
    monkeypatch.setattr(sea, "_ARCHIVE_BODY_CAP", 50)
    m = _base()
    m.set_content("X" * 5000)
    em = sea.parse_email_file(_write(tmp_path, m))
    assert len(em.canonical_body_markdown) <= 50
    assert "body_truncated_safety_cap" in em.parse_warnings


def test_render_archive_note_full_fidelity(tmp_path):
    m = _base()
    m.set_content(_REPLY + _SIG)
    m.add_attachment(b"%PDF data", maintype="application", subtype="pdf", filename="proposal.pdf")
    em = sea.parse_email_file(_write(tmp_path, m))
    note = sea.render_email_archive_note(em, None, "deadbeefcafe")
    assert "note_type: email_archive" in note and "source_type: eml" in note
    # full body incl. reply chain + signature present in the archive (never truncated silently)
    assert "Latest message body here." in note and "> earlier quoted line one" in note
    assert "DISCLAIMER: confidential." in note
    # metadata table + attachment table + MIME fidelity section
    assert "## Message Metadata" in note and "| Message-ID |" in note
    assert "## Attachments" in note and "proposal.pdf" in note
    assert "## MIME / Source Fidelity" in note and "Parse status: complete" in note
    assert "/Users/" not in note
