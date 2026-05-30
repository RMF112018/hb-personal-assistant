"""Phase 06 Prompt 07 — deterministic project matcher.

Fixture messages covering each confidence band against the tropical descriptor.
These cases are the source of the email-project-match-test-results.json evidence.
"""

from __future__ import annotations

import pytest

from hb_assistant.construction.email.project_matcher import (
    ProjectDescriptor,
    ProjectMatcher,
    load_pilot_project_descriptors,
)

# tropical: project_number 23-435-01, names "Tropical" / "Tropical - S L", procore 2525840.
TROPICAL = ProjectDescriptor(
    project_key="tropical",
    project_number="23-435-01",
    display_name="Tropical",
    project_name_normalized="tropical_s_l",
    procore_project_id="2525840",
    procore_project_name="Tropical - S L",
    known_domains=["tropicalvendor.com"],
)

# (label, kwargs) -> expected (signal_name or None, confidence, review_required)
FIXTURES = [
    ("number_in_subject", {"subject": "RFI 12 — 23-435-01 slab", "body_preview": None, "sender_domain": "gc.com"},
     ("hb_project_number_in_subject", 1.00, False)),
    ("number_in_preview", {"subject": "RFI response", "body_preview": "ref 23-435-01 attached", "sender_domain": "gc.com"},
     ("hb_project_number_in_body_preview", 0.95, True)),
    ("name_in_subject", {"subject": "Tropical weekly schedule", "body_preview": None, "sender_domain": "gc.com"},
     ("project_name_in_subject", 0.80, False)),
    ("name_in_preview", {"subject": "weekly schedule", "body_preview": "updates for Tropical - S L", "sender_domain": "gc.com"},
     ("project_name_in_body_preview", 0.70, True)),
    ("procore_notification", {"subject": "New RFI on Tropical - S L", "body_preview": "project 2525840", "sender_domain": "mail.procore.com"},
     ("procore_notification_identifier", 0.85, False)),
    ("known_domain", {"subject": "site logistics", "body_preview": None, "sender_domain": "tropicalvendor.com"},
     ("known_participant_domain_contact", 0.60, True)),
    ("no_match", {"subject": "lunch plans friday", "body_preview": "see you at noon", "sender_domain": "friends.com"},
     (None, 0.0, False)),
    ("other_project_number", {"subject": "PGA 22-112-01 punchlist", "body_preview": None, "sender_domain": "gc.com"},
     (None, 0.0, False)),
]


@pytest.mark.parametrize("label,kwargs,expected", FIXTURES, ids=[f[0] for f in FIXTURES])
def test_matcher_bands(label: str, kwargs: dict, expected: tuple) -> None:
    signals = ProjectMatcher().match(descriptor=TROPICAL, **kwargs)
    exp_name, exp_conf, exp_review = expected
    if exp_name is None:
        assert signals == [], f"{label}: expected no match, got {[s.name for s in signals]}"
        return
    names = {s.name: s for s in signals}
    assert exp_name in names, f"{label}: expected {exp_name}, got {list(names)}"
    s = names[exp_name]
    assert s.confidence == exp_conf
    assert s.review_required is exp_review
    assert s.evidence_redacted  # non-empty, redacted


def test_number_in_subject_takes_precedence_over_preview() -> None:
    # When the number is in the subject, the 0.95 preview signal is not also emitted.
    signals = ProjectMatcher().match(
        descriptor=TROPICAL, subject="23-435-01 RFI", body_preview="23-435-01 again", sender_domain="gc.com"
    )
    names = {s.name for s in signals}
    assert "hb_project_number_in_subject" in names
    assert "hb_project_number_in_body_preview" not in names


def test_pilot_descriptors_loaded_from_seeds() -> None:
    ds = load_pilot_project_descriptors()
    keys = {d.project_key for d in ds}
    assert {"tropical", "pga-modern-garage", "alton-hilltop-pbg", "the-wellington"} <= keys
    trop = load_pilot_project_descriptors("tropical")
    assert len(trop) == 1
    assert trop[0].project_number == "23-435-01"
    assert trop[0].procore_project_id == "2525840"
