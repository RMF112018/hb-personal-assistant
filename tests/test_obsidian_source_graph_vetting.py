"""Phase 10G — fact-only qwen vetting prompt + schema-bound rejection (amendment 4).

The vetting prompt must carry ONLY normalized graph facts + the deterministic basis — never note
bodies, summaries, titles, paths, addresses, message ids, or file names. Vetting is advisory: invalid /
off-enum / below-threshold / invented-tag outputs must all reject. Pure functions; no network.
"""

from __future__ import annotations

import json

from hb_assistant.construction.classification.client import OllamaUnavailable
from hb_assistant.obsidian_mcp import source_note_graph as ng


def _nf(nid, rel, **kw):
    from pathlib import Path
    base = Path(rel).stem
    d = {"note_id": nid, "note_rel": rel, "basename": base, "display": ng._display_name(base),
         "project": None, "vendor": None, "document_type": "rfi", "document_number": None,
         "doc_date": None, "disposition": "auto_card_high", "review_needed": False,
         "title_tokens": ng._title_tokens(base), "existing_tags": (), "summary_text": "s"}
    d.update(kw)
    return ng.NoteFact(**d)


def test_prompt_is_fact_only_no_bodies_titles_paths_addresses():
    a = _nf("a", "Source Notes/Work/Secret RFI Title__aaaaaaaa1111.md",
            vendor="acme", document_number="RFI-1", document_type="rfi",
            procore_project_id="2525840",
            summary_text="CONFIDENTIAL BODY: john@example.com decided to demolish the east wing")
    b = _nf("b", "Source Notes/Work/Another Title__bbbbbbbb2222.md",
            vendor="acme", document_number="RFI-1", document_type="rfi")
    prompt = ng.build_vetting_prompt(a, b, ["same_document_number", "same_vendor"])
    # no bodies/summaries/titles/paths/addresses/ids/file names leak into the prompt
    for leak in ("CONFIDENTIAL", "demolish", "john@example.com", "Secret RFI Title",
                 "Another Title", "Source Notes/Work", "aaaaaaaa1111", ".md"):
        assert leak not in prompt, leak
    # but the deterministic facts + basis + allowed enums ARE present
    assert "document_type=rfi" in prompt and "vendor=acme" in prompt
    assert "has_project_identity=yes" in prompt and "has_project_identity=no" in prompt
    assert "same_document_number" in prompt and "same_vendor" in prompt
    assert "potential_duplicate" in prompt  # allowed enum listed


def test_vetting_fact_line_classifies_kind_without_identity_leak():
    email = _nf("e", "x/E__eeeeeeee0000.md", thread_topic="topic-hash", subject_norm="subj")
    att = _nf("t", "x/T__tttttttt0000.md", attachment_extension="pdf", parent_email_hash="H")
    doc = _nf("d", "x/D__dddddddd0000.md")
    assert "kind=email" in ng._vetting_fact_line(email)
    assert "kind=attachment" in ng._vetting_fact_line(att)
    assert "kind=document" in ng._vetting_fact_line(doc)
    for line in (ng._vetting_fact_line(email), ng._vetting_fact_line(att)):
        assert "topic-hash" not in line and "pdf" not in line  # raw values not echoed


_APPROVE = {"approved": True, "relationship_type": "same_company", "confidence": 0.9,
            "reason": "Both notes name the same subcontractor.",
            "tags_for_source": ["related/company"], "tags_for_target": ["related/company"]}


class _Client:
    base_url = "http://localhost:11434"

    def __init__(self, *, payload=None, raw=None, exc=None):
        self._payload, self._raw, self._exc = payload, raw, exc

    def generate_json(self, *, system, prompt):
        if self._exc is not None:
            raise self._exc
        return self._raw if self._raw is not None else json.dumps(self._payload or _APPROVE)


def _cand():
    a = _nf("a", "w/A.md", document_number="RFI-1", vendor="acme")
    b = _nf("b", "w/B.md", document_number="RFI-1", vendor="acme")
    return ng.Candidate(a=a, b=b, strong=2, signals=("same_document_number", "same_vendor"))


def test_vet_rejects_invalid_and_offenum_and_below_threshold_and_invented_tags():
    cand = _cand()
    assert ng.vet_candidate(_Client(raw="not json"), cand)[0] is None
    assert ng.vet_candidate(_Client(exc=OllamaUnavailable("timeout")), cand)[0] is None
    assert ng.vet_candidate(_Client(payload={**_APPROVE, "relationship_type": "made_up"}), cand)[0] is None
    assert ng.vet_candidate(_Client(payload={**_APPROVE, "relationship_type": "reject"}), cand)[0] is None
    assert ng.vet_candidate(_Client(payload={**_APPROVE, "relationship_type": "potential_duplicate"}),
                            cand)[0] is None  # duplicate is review-only, never a durable link
    assert ng.vet_candidate(_Client(payload={**_APPROVE, "confidence": 0.5}), cand)[0] is None
    assert ng.vet_candidate(_Client(payload={**_APPROVE, "tags_for_source": ["made/up"]}),
                            cand)[0] is None
    ok, _ = ng.vet_candidate(_Client(payload=_APPROVE), cand)
    assert ok is not None and ok["relationship_type"] == "same_company"


def test_same_project_and_duplicate_types_are_rejected_for_durable_apply():
    cand = _cand()
    for t in ("same_project", "same_source_duplicate", "same_email_duplicate", "potential_duplicate"):
        assert ng.validate_vet({**_APPROVE, "relationship_type": t}) is None, t
        assert ng.vet_candidate(_Client(payload={**_APPROVE, "relationship_type": t}), cand)[0] is None, t
    # same_project must never produce a durable link OR a tag (strict reject → whole vet is None)
    assert ng.validate_vet({**_APPROVE, "relationship_type": "same_project",
                            "tags_for_source": ["review/project-context"]}) is None
