"""Phase 10E — graph-safe email card facts + deterministic email graph signals.

Proves the concise card carries graph-safe facts only (no raw addresses / no full message-id / no body),
that the note graph consumes them, and that body-only or shared-domain-only commonality never creates a
candidate (amendments #3 and #7). Synthetic fixtures only.
"""

from __future__ import annotations

from email.message import EmailMessage
from pathlib import Path

from hb_assistant.obsidian_mcp import source_email_archive as sea
from hb_assistant.obsidian_mcp import source_note_graph as ng

_BODY = "Sensitive body text mentioning SECRETPHRASE and jane@powerdesign.example inline."


def _email(subject, frm, to, cc="", *, attach=None, thread=None):
    m = EmailMessage()
    m["Subject"] = subject
    m["From"] = frm
    m["To"] = to
    if cc:
        m["Cc"] = cc
    m["Message-ID"] = f"<{abs(hash(subject)) % 10_000}@mail.example>"
    m["Date"] = "Thu, 14 Aug 2025 10:30:00 -0400"
    if thread:
        m["Thread-Topic"] = thread
    m.set_content(_BODY)
    if attach:
        m.add_attachment(b"data", maintype="application", subtype="pdf", filename=attach)
    return m


def _parse(tmp, m, name):
    p = Path(tmp) / name
    p.write_bytes(m.as_bytes())
    return sea.parse_email_file(p)


def test_card_facts_are_graph_safe(tmp_path):
    em = _parse(tmp_path, _email("RE: TWN Fire Alarm Design",
                                 "Jane Roe <jane@powerdesign.example>",
                                 "John Doe <john@hbconstruction.example>", "boss@owner.example",
                                 attach="proposal.pdf"), "a.eml")
    facts = sea.email_card_facts(em)
    marker = sea.email_marker(facts)
    # graph-safe: domains present, but NO raw address, NO full message-id, NO body text in the marker.
    assert facts["from_domain"] == "powerdesign.example"
    assert "hbconstruction.example" in facts["recipient_domains"]
    assert facts["participant_count"] == 3 and facts["message_id_hash"] and "@" not in facts["message_id_hash"]
    assert facts["project_alias_key"] == "tropical" and facts["project_alias_display"] == "TWN"
    assert facts["attachment_count"] == 1 and facts["attachment_hashes"]
    assert "@" not in marker and "SECRETPHRASE" not in marker
    assert "<" + "abc" not in marker  # no raw message-id angle-brackets form
    # roundtrip
    parsed = sea.parse_email_marker(marker + "\n")
    assert parsed["thread_topic"] == "twn fire alarm design" and parsed["from_domain"] == "powerdesign.example"


def test_enriched_card_excludes_body(tmp_path):
    em = _parse(tmp_path, _email("TWN Update", "jane@powerdesign.example",
                                 "john@hbconstruction.example"), "b.eml")
    card = ("---\nnote_type: source_card\n---\n# Source Card: x\n\n"
            "## Source Basis\n- basis\n\n## Advisory Summary\n- none\n")
    new, reason = sea.enrich_card_with_email(card, em, "Email Archive/Work/Shared/x-archive-note.md")
    assert reason == "inserted" and new.count(sea.EMAIL_BEGIN_PREFIX) == 1
    assert "SECRETPHRASE" not in new and "jane@powerdesign.example" not in new
    # idempotent update, still one block
    again, r2 = sea.enrich_card_with_email(new, em, "Email Archive/Work/Shared/x-archive-note.md")
    assert r2 == "updated" and again.count(sea.EMAIL_BEGIN_PREFIX) == 1


class _FakeRepo:
    def __init__(self, detail):
        self._d = detail

    def get_source_detail(self, source_id):
        return dict(self._d, source_id=source_id)


def _fact(tmp, source_id, note_rel, *, subject, thread, frm, to, project=None, attach=None):
    em = _parse(tmp, _email(subject, frm, to, thread=thread, attach=attach), f"{source_id}.eml")
    facts = sea.email_card_facts(em)
    card = ("---\nnote_type: source_card\n---\n# Source Card: x\n\n"
            "## Source Basis\n- basis\n\n## Advisory Summary\n- none\n")
    card, _ = sea.enrich_card_with_email(card, em, f"Email Archive/Work/Shared/{note_rel}", facts=facts)
    detail = {"rel_path": f"{source_id}.eml", "file_ext": "eml", "project_number": project}
    row = {"source_id": source_id, "note_rel_path": f"cards/{note_rel}"}
    return ng.note_fact_from(_FakeRepo(detail), row, card)


def test_note_fact_populates_email_fields(tmp_path):
    f = _fact(tmp_path, "s1", "one.md", subject="RE: TWN Fire Alarm Design",
              thread="TWN Fire Alarm Design", frm="jane@powerdesign.example",
              to="john@hbconstruction.example", project="23-435-01", attach="p.pdf")
    assert f.document_type == "email"
    assert f.thread_topic == "twn fire alarm design" and f.subject_norm == "twn fire alarm design"
    assert f.from_domain == "powerdesign.example" and "hbconstruction.example" in f.email_domains
    assert f.participant_hashes and f.attachment_hashes and f.project_alias == "tropical"


def test_strong_email_signal_creates_candidate(tmp_path):
    # same thread topic → strong candidate even with NO shared project.
    a = _fact(tmp_path, "s1", "a.md", subject="RE: Fire Alarm Design",
              thread="Fire Alarm Design", frm="jane@powerdesign.example",
              to="john@hbconstruction.example")
    b = _fact(tmp_path, "s2", "b.md", subject="FW: Fire Alarm Design",
              thread="Fire Alarm Design", frm="mark@subcontractor.example",
              to="pm@gc.example")
    ok, signals = ng.is_candidate(a, b)
    assert ok and "same_thread_topic" in signals and "same_subject_normalized" in signals


def test_shared_domain_only_is_weak_no_candidate(tmp_path):
    # different threads/subjects/participants/projects; only a shared recipient domain in common.
    a = _fact(tmp_path, "s1", "a.md", subject="Elevator shaft coordination",
              thread="Elevator shaft coordination", frm="jane@powerdesign.example",
              to="alice@owner.example")
    b = _fact(tmp_path, "s2", "b.md", subject="Roofing delay claim",
              thread="Roofing delay claim", frm="mark@subcontractor.example",
              to="bob@owner.example")
    ok, signals = ng.is_candidate(a, b)
    assert "same_email_domain" in signals  # reported...
    assert "same_email_domain" in ng._WEAK_SIGNALS
    assert not ok  # ...but weak alone → not a candidate (amendment #7)


def test_body_only_commonality_never_candidates(tmp_path):
    # Both bodies contain SECRETPHRASE, but no shared deterministic metadata → no candidate.
    a = _fact(tmp_path, "s1", "a.md", subject="Alpha topic one",
              thread="Alpha topic one", frm="jane@powerdesign.example", to="x@acme.example")
    b = _fact(tmp_path, "s2", "b.md", subject="Beta topic two",
              thread="Beta topic two", frm="mark@zeta.example", to="y@beta.example")
    ok, signals = ng.is_candidate(a, b)
    assert not ok and not [s for s in signals if s not in ng._WEAK_SIGNALS]
