"""Phase 10J — unified enrichment orchestrator (scripts/obsidian_source_enrich.py).

Proves: dry-run default writes nothing and holds the whole-run invariants; apply requires --backup-dir
+ matching confirm flags + backend-down; the tags-native workflow proposes in dry-run and writes with
backup/rollback under --apply; reject reasons are aggregated into the canonical taxonomy; and model
observability is recorded. Synthetic temp only; no real Ollama, no network.
"""

from __future__ import annotations

import importlib.util
import json
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import source_note_graph as ng
from tests.test_obsidian_source_note_graph import _env  # reuse the temp vault+db+config fixture

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "obsidian_source_enrich.py"
_spec = importlib.util.spec_from_file_location("obsidian_source_enrich", _SCRIPT)
assert _spec and _spec.loader
em = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(em)


@pytest.fixture
def env(tmp_path, monkeypatch):
    return _env(tmp_path, monkeypatch)


@pytest.fixture(autouse=True)
def _no_backend(monkeypatch):
    monkeypatch.setattr(em.ag, "_backend_listening", lambda *a, **k: False)
    monkeypatch.setattr(em.ag, "list_ollama_models", lambda **k: ["qwen2.5:14b"])
    monkeypatch.setattr(em, "list_ollama_models", lambda **k: ["qwen2.5:14b"])


class _Dual:
    """Fake client that answers both the JSON (tags/backlinks) and text (summaries) seams."""

    base_url = "http://localhost:11434"
    model = "qwen2.5:14b"

    def generate_json(self, *, system, prompt):
        return json.dumps({"tags": ["related/rfi", "review/qwen-vetted"]})

    def generate_text(self, *, system, prompt):
        return "_Advisory_\n\n### Summary\nx\n\n### PM Attention\n- a\n"


def _factory(*_a, **_k):
    return _Dual()


def _nf(nid, rel, *, dt="rfi", **kw):
    base = rel.rsplit("/", 1)[-1].removesuffix(".md")
    d = {"note_id": nid, "note_rel": rel, "basename": base, "display": ng._display_name(base),
         "project": None, "vendor": None, "document_type": dt, "document_number": None,
         "doc_date": None, "disposition": "auto_card_high", "review_needed": False,
         "title_tokens": ng._title_tokens(base), "existing_tags": (), "summary_text": "s"}
    d.update(kw)
    return ng.NoteFact(**d)


def _argv(env, modes, *, apply=False, project_key="tropical", backup=None, confirm=True):
    a = ["--db-path", env["db"], "--config-path", env["cfgp"], "--vault-path", str(env["vault"]),
         "--model", "qwen2.5:14b"]
    for m in modes:
        a.append("--" + m)
    if project_key:
        a += ["--project-key", project_key]
    if apply:
        a.append("--apply")
        if backup:
            a += ["--backup-dir", str(backup)]
        if confirm:
            a += ["--confirm-db-path", env["db"], "--confirm-vault-path", str(env["vault"]),
                  "--confirm-model", "qwen2.5:14b"]
    return a


def _eargs(env, modes, **kw):
    return em._build_parser().parse_args(_argv(env, modes, **kw))


# --------------------------------------------------------------------------- refusals

def test_no_mode_refuses(env):
    with pytest.raises(em.EnrichError):
        em.run(_eargs(env, [], project_key=""), client_factory=_factory)


def test_tags_require_bounded_project(env):
    with pytest.raises(em.EnrichError):
        em.run(_eargs(env, ["tags"], project_key=""), client_factory=_factory)


def test_apply_without_backup_dir_exit3(env):
    rc = em.main(_argv(env, ["tags"], apply=True), client_factory=_factory)
    assert rc == 3


def test_apply_without_matching_confirm_refuses(env, tmp_path):
    with pytest.raises(em.EnrichError):
        em.run(_eargs(env, ["tags"], apply=True, backup=tmp_path / "bk", confirm=False),
               client_factory=_factory)


def test_apply_refuses_when_backend_listening(env, tmp_path, monkeypatch):
    monkeypatch.setattr(em.ag, "_backend_listening", lambda *a, **k: True)
    with pytest.raises(em.EnrichError):
        em.run(_eargs(env, ["tags"], apply=True, backup=tmp_path / "bk"), client_factory=_factory)


# --------------------------------------------------------------------------- composition / aggregation

def test_composition_aggregates_reasons_and_records_invariants(env, monkeypatch):
    monkeypatch.setattr(em, "_run_summaries", lambda *a, **k: (
        {"cards_eligible": 2, "summaries_generated": 1, "summaries_rejected": 1,
         "cards_left_pending": 1}, [{"result": "rejected", "reason": "timeout"}], {"timeout": 1}))
    monkeypatch.setattr(em.ag, "run", lambda a, **k: {
        "safe": {"candidate_pairs": 3, "vetted_pairs": 3, "approved_pairs": 1,
                 "relationships_applied": 0, "rejection_reasons": {"rejected": 2}},
        "detail_rows": []})
    monkeypatch.setattr(em.rev, "run", lambda a: {
        "safe": {"cards_checked": 5, "duplicate_review_pairs": 1, "isolated_high_value_cards": 0},
        "detail_rows": []})
    out = em.run(_eargs(env, ["summaries", "backlinks", "review"]), client_factory=_factory)
    safe = out["safe"]
    assert safe["mode"] == "dry-run"
    assert safe["reject_reasons"] == {"model_timeout": 1, "weak_basis": 2}
    assert safe["invariants"] == {"db_mutations": 0, "queue_delta": 0, "created": 0, "deleted": 0}
    assert safe["summaries"]["summaries_generated"] == 1 and safe["backlinks"]["approved_pairs"] == 1
    assert safe["review"]["cards_checked"] == 5 and "observability" in safe


# --------------------------------------------------------------------------- tags-native workflow

def _seed_cards(env, monkeypatch):
    facts, texts = {}, {}
    body = "---\nnote_type: source_card\ntags:\n  - source/type/rfi\n---\n# Card\nbody\n"
    for i in (1, 2):
        rel = f"Source Notes/Work/Enrich T{i}.md"
        p = env["vault"] / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(body, encoding="utf-8")
        f = _nf(str(i), rel, dt="rfi")
        facts[f.note_id], texts[f.note_id] = f, body
    monkeypatch.setattr(em.cg, "_select", lambda repo, vr, args: (facts, texts))
    return facts


def test_tags_dry_run_proposes_without_writing(env, monkeypatch):
    _seed_cards(env, monkeypatch)
    out = em.run(_eargs(env, ["tags"]), client_factory=_factory)
    tags = out["safe"]["tags"]
    assert tags["cards_checked"] == 2 and tags["tags_proposed"] == 4 and tags["would_tag_cards"] == 2
    assert out["safe"]["invariants"]["db_mutations"] == 0
    # nothing written to disk in dry-run
    assert "related/rfi" not in (env["vault"] / "Source Notes/Work/Enrich T1.md").read_text()


def test_tags_max_cards_bounds_and_reports_truncation(env, monkeypatch):
    _seed_cards(env, monkeypatch)  # two Tropical cards
    args = em._build_parser().parse_args(_argv(env, ["tags"]) + ["--tags-max-cards", "1"])
    out = em.run(args, client_factory=_factory)
    tags = out["safe"]["tags"]
    assert tags["cards_available"] == 2 and tags["cards_checked"] == 1
    assert tags["selection_truncated"] is True and tags["would_tag_cards"] == 1


def test_tags_apply_writes_with_backup_and_holds_invariants(env, monkeypatch, tmp_path):
    _seed_cards(env, monkeypatch)
    bk = tmp_path / "bk"
    out = em.run(_eargs(env, ["tags"], apply=True, backup=bk), client_factory=_factory)
    tags = out["safe"]["tags"]
    assert tags["cards_written"] == 2 and tags["cards_tagged"] == 2
    assert (bk / "tags" / "Source Notes/Work/Enrich T1.md").is_file()  # backup taken
    written = (env["vault"] / "Source Notes/Work/Enrich T1.md").read_text()
    assert "related/rfi" in written and "review/qwen-vetted" in written
    assert "source/type/rfi" in written  # existing tag preserved
    assert out["safe"]["invariants"] == {"db_mutations": 0, "queue_delta": 0, "created": 0, "deleted": 0}
    assert out["safe"]["observability"]["ollama_calls"] == 2  # one JSON call per card


# --------------------------------------------------------------------------- summaries-native workflow

# Minimal card that passes summ._eligibility: source_card, current card_version, pending hb-local-summary
# marker, and EXACTLY the canonical 11 `## ` sections in order.
_CANON_CARD = """---
note_type: source_card
card_version: phase10a-v1
tags:
  - source/type/contract
---
# Source Card

## Source Summary
s
## Why This Matters
s
## PM Review Cues
s
## Key Facts
s
## Related Project
s
## Related People / Companies
s
## Related Decisions
s
## Related Meetings
s
## Source Basis
s
## Advisory Summary
<!-- hb-local-summary:start model="qwen2.5:14b" status="pending" -->
_pending_
<!-- hb-local-summary:end -->
## Follow-Up
s
"""


# Source excerpt the summary must be GROUNDED in (>=3 shared content tokens, non-metadata).
_SUMMARY_EXCERPT = (
    "The submitted foundation schedule identifies concrete placement beginning October fourteenth. "
    "Rebar inspection reports were attached and approved. The contractor requested confirmation on the "
    "anchor bolt embedment depth before proceeding with the structural steel package."
)
# A grounded FIVE-section source-card summary: shares foundation/concrete/rebar/anchor/embedment/steel
# with the excerpt and carries a substantive Key Extracted Details section.
_GROUNDED_FIVE = (
    "_Advisory — locally generated by qwen2.5:14b. Verify against the source before relying on this "
    "summary._\n\n"
    "### Summary\nA submitted foundation schedule covering concrete placement and rebar inspection.\n\n"
    "### Key Extracted Details\n- Foundation concrete placement begins mid-October.\n"
    "- Rebar inspection reports attached and approved.\n"
    "- Anchor bolt embedment depth pending confirmation before structural steel proceeds.\n\n"
    "### PM Attention\n- Confirm anchor bolt embedment before the structural steel package proceeds.\n\n"
    "### Follow-Up Questions\n- Is the embedment depth resolved?\n\n"
    "### Limits / Uncertainty\n- Advisory only; verify against the source.\n"
)
# A well-formed FOUR-section advisory (old validate_advisory shape) — MISSING "Key Extracted Details".
# The old four-section validate_advisory would ACCEPT this; the new validate_summary_quality rejects it
# (format_invalid), which is exactly what proves the orchestrator now uses the five-section validator.
_FOUR_SECTION = (
    "_Advisory — locally generated by qwen2.5:14b. Verify against the source._\n\n"
    "### Summary\nA submitted foundation schedule covering concrete and rebar.\n\n"
    "### PM Attention\n- Confirm anchor bolt embedment.\n\n"
    "### Follow-Up Questions\n- Is the embedment depth resolved?\n\n"
    "### Limits / Uncertainty\n- Advisory only.\n"
)


class _SummaryClient:
    base_url = "http://localhost:11434"
    model = "qwen2.5:14b"

    def __init__(self, *, valid=True, shape=None):
        # valid=True -> grounded five-section; valid=False defaults to the four-section shape so the
        # new five-section validator (not the old four-section one) is what rejects it.
        self._shape = shape or ("five" if valid else "four")

    def generate_text(self, *, system, prompt):
        if self._shape == "five":
            return _GROUNDED_FIVE
        if self._shape == "four":
            return _FOUR_SECTION
        return "### Summary\nOnly one section here.\n"  # 'one' -> format_invalid

    def generate_json(self, *, system, prompt):
        return "{}"


def _seed_summary_cards(env, monkeypatch, n=2):
    facts, texts = {}, {}
    for i in range(1, n + 1):
        rel = f"Source Notes/Work/Sum T{i}.md"
        p = env["vault"] / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_CANON_CARD, encoding="utf-8")
        f = _nf(str(i), rel, dt="contract")
        facts[f.note_id], texts[f.note_id] = f, _CANON_CARD
    monkeypatch.setattr(em.cg, "_select", lambda repo, vr, args: (facts, texts))
    # Supply a real source excerpt so the grounding gate in validate_summary_quality is exercised.
    monkeypatch.setattr(em.SourceIndexRepository, "get_source_detail",
                        lambda self, sid, **k: {"text_excerpt": _SUMMARY_EXCERPT})
    return facts


def test_summaries_dry_run_eligibility_no_model(env, monkeypatch):
    _seed_summary_cards(env, monkeypatch, n=2)
    out = em.run(_eargs(env, ["summaries"]), client_factory=lambda *a: _SummaryClient(valid=True))
    s = out["safe"]["summaries"]
    assert s["cards_eligible"] == 2 and s["cards_attempted"] == 2 and s["would_attempt_cards"] == 2
    assert s["summaries_generated"] == 0 and s["cards_left_pending"] == 2
    assert out["safe"]["observability"]["ollama_calls"] == 0  # dry-run never calls the model
    assert out["safe"]["invariants"]["db_mutations"] == 0
    assert 'status="pending"' in (env["vault"] / "Source Notes/Work/Sum T1.md").read_text()


def test_summaries_apply_generates_and_flips_marker(env, monkeypatch, tmp_path):
    _seed_summary_cards(env, monkeypatch, n=2)
    out = em.run(_eargs(env, ["summaries"], apply=True, backup=tmp_path / "bk"),
                 client_factory=lambda *a: _SummaryClient(valid=True))
    s = out["safe"]["summaries"]
    assert s["summaries_generated"] == 2 and s["summaries_rejected"] == 0
    assert s["cards_written"] == 2 and s["marker_transitions_pending_to_generated"] == 2
    assert s["cards_left_pending"] == 0
    card = (env["vault"] / "Source Notes/Work/Sum T1.md").read_text()
    # marker flipped + the FIVE-section source-card summary (incl. Key Extracted Details) written
    assert 'status="generated"' in card and "### Summary" in card and "### Key Extracted Details" in card
    assert (tmp_path / "bk" / "summaries" / "Source Notes/Work/Sum T1.md").is_file()  # backup taken
    assert out["safe"]["invariants"] == {"db_mutations": 0, "queue_delta": 0, "created": 0, "deleted": 0}
    assert out["safe"]["observability"]["ollama_calls"] == 2


def test_summaries_apply_invalid_leaves_pending(env, monkeypatch, tmp_path):
    _seed_summary_cards(env, monkeypatch, n=2)
    out = em.run(_eargs(env, ["summaries"], apply=True, backup=tmp_path / "bk"),
                 client_factory=lambda *a: _SummaryClient(shape="one"))
    s = out["safe"]["summaries"]
    assert s["summaries_generated"] == 0 and s["summaries_rejected"] == 2
    assert s["cards_written"] == 0 and s["marker_transitions_pending_to_generated"] == 0
    assert s["cards_left_pending"] == 2
    assert out["safe"]["reject_reasons"].get("invalid_format") == 2  # format_invalid -> canonical
    card = (env["vault"] / "Source Notes/Work/Sum T1.md").read_text()
    assert 'status="pending"' in card and "Only one section here" not in card  # left unchanged


def test_summaries_four_section_rejected_proves_new_validator(env, monkeypatch, tmp_path):
    # A four-section advisory (Summary/PM Attention/Follow-Up Questions/Limits) is valid under the OLD
    # validate_advisory but is missing "### Key Extracted Details" — the new five-section
    # validate_summary_quality must reject it. This is the regression that proves the orchestrator
    # summary path uses the five-section schema/validator, not the legacy four-section one.
    _seed_summary_cards(env, monkeypatch, n=1)
    out = em.run(_eargs(env, ["summaries"], apply=True, backup=tmp_path / "bk"),
                 client_factory=lambda *a: _SummaryClient(shape="four"))
    s = out["safe"]["summaries"]
    assert s["summaries_generated"] == 0 and s["summaries_rejected"] == 1
    assert s["cards_written"] == 0 and s["cards_left_pending"] == 1
    assert out["safe"]["reject_reasons"].get("invalid_format") == 1  # missing 5th section
    card = (env["vault"] / "Source Notes/Work/Sum T1.md").read_text()
    assert 'status="pending"' in card and "Key Extracted Details" not in card


def test_summaries_max_cards_and_skip_bound_attempts(env, monkeypatch):
    _seed_summary_cards(env, monkeypatch, n=3)
    a = em._build_parser().parse_args(_argv(env, ["summaries"]) + ["--summaries-max-cards", "1"])
    s = em.run(a, client_factory=lambda *x: _SummaryClient(valid=True))["safe"]["summaries"]
    assert s["cards_eligible"] == 3 and s["cards_attempted"] == 1 and s["selection_truncated"] is True
    a2 = em._build_parser().parse_args(
        _argv(env, ["summaries"]) + ["--summaries-max-cards", "1", "--summaries-skip", "2"])
    s2 = em.run(a2, client_factory=lambda *x: _SummaryClient(valid=True))["safe"]["summaries"]
    assert s2["cards_attempted"] == 1 and s2["selection_truncated"] is False  # skip 2, 1 left, cap 1


def test_summaries_note_rel_targets_exact_cards(env, monkeypatch):
    _seed_summary_cards(env, monkeypatch, n=3)
    # Restrict to exactly two of the three eligible cards by note-rel; the third is not attempted.
    a = em._build_parser().parse_args(
        _argv(env, ["summaries"]) + ["--summaries-note-rel", "Source Notes/Work/Sum T1.md",
                                     "--summaries-note-rel", "Source Notes/Work/Sum T3.md"])
    s = em.run(a, client_factory=lambda *x: _SummaryClient(valid=True))["safe"]["summaries"]
    assert s["cards_eligible"] == 3 and s["cards_attempted"] == 2  # filtered to the 2 named cards
    assert s["would_attempt_cards"] == 2
