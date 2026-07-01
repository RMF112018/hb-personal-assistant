"""Phase 10J — standalone tagging workflow (source_note_graph tagging helpers).

Proves the model may propose tags ONLY from the controlled related/* + review/* taxonomy, that every
related/* tag must be grounded in the card's deterministic facts (never body-derived), and that the
JSON gate returns the canonical reject reasons.
"""

from __future__ import annotations

import json

from hb_assistant.construction.classification.client import OllamaUnavailable
from hb_assistant.obsidian_mcp import source_note_graph as ng


def _nf(nid, rel, *, dt="rfi", **kw):
    base = rel.rsplit("/", 1)[-1].removesuffix(".md")
    d = {"note_id": nid, "note_rel": rel, "basename": base, "display": ng._display_name(base),
         "project": None, "vendor": None, "document_type": dt, "document_number": None,
         "doc_date": None, "disposition": "auto_card_high", "review_needed": False,
         "title_tokens": ng._title_tokens(base), "existing_tags": (), "summary_text": "s"}
    d.update(kw)
    return ng.NoteFact(**d)


def test_related_tag_supported_by_facts():
    rfi = _nf("1", "x/R.md", dt="rfi")
    assert ng._related_tag_supported("related/rfi", rfi) is True
    assert ng._related_tag_supported("related/schedule", rfi) is False  # wrong content family
    proj = _nf("2", "x/P.md", dt="general_document", project="23-435-01")
    assert ng._related_tag_supported("related/project", proj) is True
    email = _nf("3", "x/E.md", dt="email", thread_topic="tt")
    assert ng._related_tag_supported("related/email", email) is True
    assert ng._related_tag_supported("related/attachment", email) is False
    att = _nf("4", "x/A.md", dt="general_document", attachment_extension="pdf")
    assert ng._related_tag_supported("related/attachment", att) is True
    vend = _nf("5", "x/V.md", dt="contract", vendor="acme")
    assert ng._related_tag_supported("related/company", vend) is True


def test_validate_proposed_tags_shape_errors():
    f = _nf("1", "x/R.md", dt="rfi")
    assert ng.validate_proposed_tags("not a dict", f) == ([], "invalid_format")
    assert ng.validate_proposed_tags({"tags": "notalist"}, f) == ([], "invalid_format")
    assert ng.validate_proposed_tags({}, f) == ([], "invalid_format")


def test_validate_proposed_tags_unknown_and_off_taxonomy():
    f = _nf("1", "x/R.md", dt="rfi")
    assert ng.validate_proposed_tags({"tags": ["totally/invented"]}, f) == ([], "unknown_tag")
    # deterministic content-type tag is real but NOT model-proposable (only related/* + review/*)
    assert ng.validate_proposed_tags({"tags": ["source/type/rfi"]}, f) == ([], "unknown_tag")


def test_validate_proposed_tags_unsupported_related_claim():
    f = _nf("1", "x/R.md", dt="rfi")  # no schedule evidence
    assert ng.validate_proposed_tags({"tags": ["related/schedule"]}, f) == ([], "unsupported_claim")
    email_only = _nf("2", "x/E.md", dt="email", thread_topic="tt")  # not a project card
    assert ng.validate_proposed_tags({"tags": ["related/project"]}, email_only) == (
        [], "unsupported_claim")


def test_validate_proposed_tags_accepts_grounded_and_review_tags():
    f = _nf("1", "x/R.md", dt="rfi")
    tags, reason = ng.validate_proposed_tags(
        {"tags": ["related/rfi", "review/qwen-vetted", "related/rfi"]}, f)
    assert reason == "ok" and tags == ["related/rfi", "review/qwen-vetted"]  # deduped, grounded


def test_validate_proposed_tags_caps_at_eight():
    f = _nf("1", "x/R.md", dt="rfi")
    review_tags = ["review/qwen-vetted", "review/needs-human-check", "review/weak-relationship",
                   "review/metadata-only", "review/project-context"]
    tags, reason = ng.validate_proposed_tags({"tags": review_tags + ["related/rfi"]}, f)
    assert reason == "ok" and len(tags) <= 8


class _FakeClient:
    base_url = "http://localhost:11434"

    def __init__(self, *, raw=None, exc=None):
        self._raw, self._exc = raw, exc

    def generate_json(self, *, system, prompt):
        if self._exc:
            raise self._exc
        return self._raw


def test_propose_tags_paths():
    f = _nf("1", "x/R.md", dt="rfi")
    tags, reason = ng.propose_tags(_FakeClient(raw=json.dumps({"tags": ["related/rfi"]})), f)
    assert reason == "ok" and tags == ["related/rfi"]
    assert ng.propose_tags(_FakeClient(raw="not json"), f) == ([], "invalid_json")
    tags2, reason2 = ng.propose_tags(_FakeClient(exc=OllamaUnavailable("ollama_timeout")), f)
    assert tags2 == [] and reason2.startswith("ollama:")
