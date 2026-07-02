"""Phase 10K — source-card classifier repair (planner/helpers + bounded script behaviour).

Proves: managed blocks + source ID/SHA/path/timestamps are preserved byte-for-byte; only the allowed
frontmatter/section fields change; a generated summary that still asserts the old type forces a
``summary_refresh_required`` skip; missing sections fail safe; re-run is idempotent; the script dry-run
writes nothing, constructs no Ollama client, and its safe evidence is count-only (leak-proof renderer).
"""

from __future__ import annotations

import importlib.util
from pathlib import Path

import pytest

from hb_assistant.obsidian_mcp import source_card_repair as cr
from tests.test_obsidian_source_graph_apply import _nf
from tests.test_obsidian_source_note_graph import _env  # temp vault+db+config fixture

_SCRIPT = Path(__file__).resolve().parents[1] / "scripts" / "obsidian_source_classifier_repair.py"
_spec = importlib.util.spec_from_file_location("obsidian_source_classifier_repair", _SCRIPT)
assert _spec and _spec.loader
km = importlib.util.module_from_spec(_spec)
_spec.loader.exec_module(km)


@pytest.fixture
def env(tmp_path, monkeypatch):
    return _env(tmp_path, monkeypatch)

_VA_TXT = ("VALUE ANALYSIS TRACKING LOG\nItem 1 Alternate glazing Status Open Value #REF!\n"
           "Item 2 Roofing membrane Status Accepted Value 45000\nItem 3 HVAC Status Rejected")
_VA_DETAIL = {"rel_path": "Exhibits/20241016_TWN_VA_Log.pdf", "file_ext": "pdf",
              "text_excerpt": _VA_TXT, "size_bytes": 100, "page_count": 3, "extraction_status": "ok"}

_IDENTITY = (
    '<!-- hb-project-identity:start project_number="23-435-01" project_key="tropical" '
    'procore_project_id="2525840" -->\n- Resolved project: 23-435-01 · tropical\n'
    "<!-- hb-project-identity:end -->")


def _card(document_type="warranty", type_slug="unknown", *, summary_status=None, summary_body="",
          why="A warranty document defines coverage and obligations after completion.",
          basis_extra=""):
    summary = ""
    if summary_status is not None:
        summary = (f'\n<!-- hb-local-summary:start model="qwen2.5:14b" status="{summary_status}" -->\n'
                   f"{summary_body}\n<!-- hb-local-summary:end -->")
    return f"""---
note_type: source_card
source_id: "abc123def456"
source_kind: "external_file"
source_path: "NAS/Projects/23-435-01/Exhibits/20241016_TWN_VA_Log.pdf"
source_sha256: "deadbeefcafe"
source_mtime_ns: 1758534756783500432
indexed_at: "2026-07-01T07:15:25.922492+00:00"
generated_at: "2026-07-01T07:15:25+00:00"
project_number: "23-435-01"
document_type: "{document_type}"
review_status: "unreviewed"
card_version: "phase10a-v1"
tags:
  - source/external_file
  - domain/work
  - source/type/{type_slug}
  - related/project
---

# Source Card: x

## Source Summary
- PDF document · 100 bytes · 3 pages · extraction ok
- Document type: {document_type} (deterministic — filename/metadata)

## Why This Matters
- {why}

## PM Review Cues
- Confirm coverage scope, term, and start date.
- Tie to project 23-435-01.

## Key Facts
- Project number: 23-435-01

## Related Project
- Project: 23-435-01

{_IDENTITY}

## Source Basis
- Card basis: full extracted text (bounded)
- Document type: {document_type} (deterministic — filename/metadata)
- Classification reason: doc_type:{document_type}{basis_extra}
- Source ID: `abc123def456`
- SHA-256: `deadbeefcafe`

## Advisory Summary{summary}

## Follow-Up
- x
"""


def _block(text, marker):
    lines = text.splitlines()
    s = next((i for i, ln in enumerate(lines) if ln.strip().startswith(marker)), None)
    if s is None:
        return None
    end_pfx = marker.split(":")[0] + ":end"
    e = next((i for i in range(s + 1, len(lines)) if lines[i].strip().startswith(end_pfx)), None)
    return "\n".join(lines[s:e + 1]) if e is not None else None


# --------------------------------------------------------------------------- planner
def test_repair_plan_changes_only_allowed_fields():
    card = _card("warranty", "unknown")
    plan = cr.plan_card_classification_repair(card, _VA_DETAIL)
    assert plan.action == "repair" and plan.from_type == "warranty" and plan.to_type == "value_analysis"
    assert plan.confidence == "high" and plan.classification_conflict is True
    new = plan.new_text
    # identity block byte-identical; source id/sha/path/timestamps unchanged
    assert _block(card, "<!-- hb-project-identity:start") == _block(new, "<!-- hb-project-identity:start")
    for k in ("source_id", "source_sha256", "source_path", "generated_at", "indexed_at",
              "source_mtime_ns", "review_status"):
        assert cr._frontmatter_value(card, k) == cr._frontmatter_value(new, k)
    # allowed changes applied
    assert cr._frontmatter_value(new, "document_type") == "value_analysis"
    assert "source/type/value-analysis" in new and "source/type/unknown" not in new
    assert "value-analysis log tracks" in new  # Why This Matters regenerated
    assert "doc_type:value_analysis (Phase 10K repair from 'warranty'" in new


def test_repair_preserves_generated_consistent_summary_byte_for_byte():
    body = "### Summary\nA value-analysis tracking log; the warranty hint is contradicted.\n"
    card = _card("warranty", "unknown", summary_status="generated", summary_body=body)
    plan = cr.plan_card_classification_repair(card, _VA_DETAIL)
    assert plan.action == "repair"
    assert _block(card, "<!-- hb-local-summary:start") == _block(plan.new_text, "<!-- hb-local-summary:start")


def test_generated_summary_asserting_old_type_forces_skip():
    body = "### Summary\nThis warranty document defines coverage and obligations for the roofing.\n"
    card = _card("warranty", "unknown", summary_status="generated", summary_body=body)
    plan = cr.plan_card_classification_repair(card, _VA_DETAIL)
    assert plan.action == "skip" and plan.skip_reason == "summary_refresh_required"
    assert plan.new_text is None


def test_missing_section_fails_safe():
    card = _card("warranty", "unknown").replace("## Why This Matters\n- A warranty document defines "
                                                "coverage and obligations after completion.\n\n", "")
    plan = cr.plan_card_classification_repair(card, _VA_DETAIL)
    assert plan.action == "skip" and plan.new_text is None
    assert plan.skip_reason.startswith("Why This Matters:")


def test_non_family_card_is_noop():
    detail = {"rel_path": "Roof Warranty.pdf", "file_ext": "pdf",
              "text_excerpt": "This warranty covers the roofing membrane for twenty years."}
    plan = cr.plan_card_classification_repair(_card("warranty", "unknown"), detail)
    assert plan.action == "noop" and plan.new_text is None


def test_rerun_on_repaired_card_is_idempotent():
    card = _card("warranty", "unknown")
    first = cr.plan_card_classification_repair(card, _VA_DETAIL)
    second = cr.plan_card_classification_repair(first.new_text, _VA_DETAIL)
    assert second.action == "noop"


def test_replace_section_body_refuses_managed_marker():
    card = _card("warranty", "unknown")
    # inject a marker into Why This Matters -> the section-body replace must refuse
    bad = card.replace("- A warranty document defines coverage and obligations after completion.",
                       "<!-- gc-graph-links:start -->\n- x\n<!-- gc-graph-links:end -->")
    out, reason = cr.replace_section_body(bad, "## Why This Matters", ["- new"])
    assert out is None and reason == "managed_marker_in_section"


# --------------------------------------------------------------------------- script: safe evidence
def test_render_repair_report_leaks_nothing_sensitive():
    safe = {"mode": "dry-run", "project_number": "23-435-01", "cards_scanned": 3,
            "cards_with_conflict": 3, "repairs_planned": 3, "repairs_applicable": 3,
            "review_required": 0, "skipped": 0, "cards_modified": 0, "db_mutations": 0,
            "ollama_calls": 0, "repairs_by_existing_type": {"warranty": 1},
            "repairs_by_proposed_type": {"value_analysis": 1}, "skips_by_reason": {},
            "invariants": {"db_mutations": 0, "queue_delta": 0, "created": 0, "deleted": 0},
            # a sensitive string stuffed into an UNKNOWN key must never render
            "leak": "john@example.com [[Secret Title]] /Users/bobby/vault/VA_Log.pdf"}
    report = km.render_repair_report(safe)
    for bad in ("john@example.com", "Secret Title", "/Users/bobby", "VA_Log.pdf"):
        assert bad not in report


def test_safe_only_drops_unknown_keys():
    safe = km._safe_only({"cards_scanned": 1, "note_rel": "Source Notes/Work/x.md", "leak": "secret"})
    assert safe == {"cards_scanned": 1}


# --------------------------------------------------------------------------- script: dry-run integration
def _seed(env, monkeypatch, cards):
    facts, texts, details = {}, {}, {}
    for i, (rel, dt, detail) in enumerate(cards, 1):
        p = env["vault"] / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(_card(dt, "unknown"), encoding="utf-8")
        f = _nf(str(i), rel, document_type=dt)
        facts[f.note_id], texts[f.note_id] = f, p.read_text()
        details[f.note_id] = detail
    monkeypatch.setattr(km.cg, "_select", lambda repo, vr, args: (facts, texts))
    monkeypatch.setattr(km.SourceIndexRepository, "get_source_detail",
                        lambda self, sid, **k: details.get(sid))


def _args(env, **over):
    a = [f"--db-path={env['db']}", f"--config-path={env['cfgp']}", f"--vault-path={env['vault']}",
         "--project-key=tropical", "--dry-run"]
    for k, v in over.items():
        a.append(f"--{k.replace('_', '-')}={v}")
    return km._build_parser().parse_args(a)


def test_dryrun_writes_nothing_and_counts(env, monkeypatch):
    cards = [("Source Notes/Work/VA.md", "warranty", _VA_DETAIL),
             ("Source Notes/Work/OK.md", "rfi",
              {"rel_path": "rfi.pdf", "file_ext": "pdf", "text_excerpt": "RFI question about doors."})]
    _seed(env, monkeypatch, cards)
    before = (env["vault"] / "Source Notes/Work/VA.md").read_text()
    out = km.run(_args(env))
    s = out["safe"]
    assert s["cards_scanned"] == 2 and s["repairs_planned"] == 1 and s["cards_with_conflict"] == 1
    assert s["cards_modified"] == 0 and s["invariants"]["db_mutations"] == 0 and s["ollama_calls"] == 0
    assert s["repairs_by_proposed_type"] == {"value_analysis": 1}
    assert (env["vault"] / "Source Notes/Work/VA.md").read_text() == before  # untouched


def test_note_rel_targeting_bounds_scan(env, monkeypatch):
    cards = [("Source Notes/Work/VA.md", "warranty", _VA_DETAIL),
             ("Source Notes/Work/Other.md", "warranty", _VA_DETAIL)]
    _seed(env, monkeypatch, cards)
    args = _args(env)
    args.note_rel = ["Source Notes/Work/VA.md"]
    s = km.run(args)["safe"]
    assert s["cards_scanned"] == 1 and s["repairs_planned"] == 1


def test_apply_without_confirm_refuses(env, monkeypatch, tmp_path):
    _seed(env, monkeypatch, [("Source Notes/Work/VA.md", "warranty", _VA_DETAIL)])
    monkeypatch.setattr(km.ag, "_backend_listening", lambda *a, **k: False)
    args = _args(env)
    args.apply = True
    args.backup_dir = str(tmp_path / "bk")
    with pytest.raises(km.RepairError):
        km.run(args)  # missing --confirm-classifier-repair / confirm paths


# =========================================================================== Phase 10K.1 polish
_SUMMARY = ('\n<!-- hb-local-summary:start model="qwen2.5:14b" status="generated" -->\n'
            "### Summary\nA value-analysis tracking log for the project.\n<!-- hb-local-summary:end -->")


def _pcard(document_type, tags, *, followup="- [ ] stale follow-up", graph_links=False, summary=True):
    tag_lines = "\n".join(f"  - {t}" for t in tags)
    gl = ("\n<!-- gc-graph-links:start -->\n- [[Other Card]]\n<!-- gc-graph-links:end -->\n"
          if graph_links else "")
    adv = _SUMMARY if summary else ""
    return f"""---
note_type: source_card
source_id: "abc123def456"
source_kind: "external_file"
source_path: "NAS/Projects/23-435-01/x.pdf"
source_sha256: "deadbeefcafe"
source_mtime_ns: 1758534756783500432
indexed_at: "2026-07-01T07:15:25.922492+00:00"
generated_at: "2026-07-01T07:15:25+00:00"
project_number: "23-435-01"
document_type: "{document_type}"
review_status: "unreviewed"
card_version: "phase10a-v1"
tags:
{tag_lines}
---

# Source Card: x

## Related Project
- Project: 23-435-01
{gl}
{_IDENTITY}

## Advisory Summary{adv}

## Follow-Up
{followup}
"""


def _tags(card):
    ok, tags, _f, _l = cr.ng.parse_frontmatter_tags(card)
    assert ok
    return tags


def test_polish_value_analysis_regenerates_followup_keeps_grounded_and_gates_review():
    card = _pcard("value_analysis", ["source/type/value-analysis", "related/project",
                                     "review/project-context"])
    p = cr.plan_card_polish(card, {}, add_review=("review/project-context",),
                            remove_review=("review/metadata-only",))
    assert p.action == "polish" and p.followup_changed is True
    # VA-log Follow-Up regenerated from guidance (checkboxes), warranty language gone
    assert "- [ ] Confirm pending/conditional VA items." in p.new_text
    assert "#REF" in p.new_text and "stale follow-up" not in p.new_text
    # grounded related/project kept; no prune
    assert p.related_pruned == () and "related/project" in _tags(p.new_text)
    # review change NOT justified for value_analysis -> skipped, not applied; existing tag untouched
    assert p.review_added == () and p.review_removed == ()
    assert set(p.review_skipped) == {"review/project-context", "review/metadata-only"}
    assert "review/project-context" in _tags(p.new_text)


def test_polish_specification_template_prunes_submittal_and_swaps_review():
    card = _pcard("specification_template", ["source/type/specification-template", "related/submittal",
                                             "review/metadata-only"])
    p = cr.plan_card_polish(card, {}, add_review=("review/project-context",),
                            remove_review=("review/metadata-only",))
    assert p.action == "polish"
    assert p.related_pruned == ("related/submittal",)
    tags = _tags(p.new_text)
    assert "related/submittal" not in tags
    assert "review/metadata-only" not in tags and "review/project-context" in tags
    assert p.review_added == ("review/project-context",) and p.review_removed == ("review/metadata-only",)
    assert "- [ ] Confirm whether this template was adopted, edited, or superseded" in p.new_text


def test_polish_clarification_memo_prunes_scope_keeps_review():
    card = _pcard("clarification_memo", ["source/type/clarification-memo", "related/project",
                                         "related/scope", "review/project-context"])
    p = cr.plan_card_polish(card, {}, add_review=("review/project-context",),
                            remove_review=("review/metadata-only",))
    assert p.action == "polish" and p.related_pruned == ("related/scope",)
    tags = _tags(p.new_text)
    assert "related/scope" not in tags
    assert "related/project" in tags and "review/project-context" in tags  # both kept
    assert p.review_added == () and p.review_removed == ()  # not justified for memo
    fu = p.new_text.lower()
    assert "responses" in fu or "owners" in fu
    assert "scope inclusions" not in fu and "addenda" not in fu


def test_polish_does_not_prune_when_graph_links_present():
    card = _pcard("specification_template", ["source/type/specification-template", "related/submittal"],
                  graph_links=True)
    p = cr.plan_card_polish(card, {})
    # ungrounded related/submittal is NOT pruned because a gc-graph-links block justifies it
    assert p.related_pruned == () and "related/submittal" in _tags(p.new_text)
    assert cr.ng.REL_BLOCK_BEGIN in p.new_text  # graph block preserved


def test_polish_preserves_managed_blocks_and_identifiers():
    card = _pcard("specification_template", ["source/type/specification-template", "related/submittal",
                                             "review/metadata-only"])
    p = cr.plan_card_polish(card, {}, add_review=("review/project-context",),
                            remove_review=("review/metadata-only",))
    new = p.new_text
    assert _block(card, "<!-- hb-project-identity:start") == _block(new, "<!-- hb-project-identity:start")
    assert _block(card, "<!-- hb-local-summary:start") == _block(new, "<!-- hb-local-summary:start")
    for k in ("source_id", "source_sha256", "source_path", "generated_at", "indexed_at",
              "source_mtime_ns", "document_type"):
        assert cr._frontmatter_value(card, k) == cr._frontmatter_value(new, k)
    assert "source/type/specification-template" in _tags(new)  # source-type tag untouched


def test_polish_is_idempotent():
    card = _pcard("specification_template", ["source/type/specification-template", "related/submittal",
                                             "review/metadata-only"])
    first = cr.plan_card_polish(card, {}, add_review=("review/project-context",),
                               remove_review=("review/metadata-only",))
    assert first.action == "polish"
    second = cr.plan_card_polish(first.new_text, {}, add_review=("review/project-context",),
                                remove_review=("review/metadata-only",))
    assert second.action == "noop" and second.new_text is None
    assert second.followup_changed is False and second.related_pruned == ()
    assert second.review_added == () and second.review_removed == ()


def test_polish_fails_safe_on_marker_in_followup():
    card = _pcard("value_analysis", ["source/type/value-analysis", "related/project"],
                  followup="<!-- gc-graph-links:start -->\n- x\n<!-- gc-graph-links:end -->")
    p = cr.plan_card_polish(card, {})
    assert p.action == "skip" and p.skip_reason == "Follow-Up:managed_marker_in_section"
    assert p.new_text is None


def test_polish_dryrun_writes_nothing_and_counts(env, monkeypatch):
    # seed a value_analysis card (already repaired) — polish regenerates its Follow-Up only
    p = env["vault"] / "Source Notes/Work/VA.md"
    p.parent.mkdir(parents=True, exist_ok=True)
    p.write_text(_card("value_analysis", "value-analysis"), encoding="utf-8")
    f = _nf("1", "Source Notes/Work/VA.md", document_type="value_analysis")
    monkeypatch.setattr(km.cg, "_select", lambda repo, vr, args: ({f.note_id: f}, {f.note_id: p.read_text()}))
    monkeypatch.setattr(km.SourceIndexRepository, "get_source_detail", lambda self, sid, **k: _VA_DETAIL)
    before = p.read_text()
    args = _args(env)
    args.polish = True
    args.add_review = ["review/project-context"]
    args.drop_review = ["review/metadata-only"]
    s = km.run(args)["safe"]
    assert s["cards_scanned"] == 1 and s["cards_changed"] == 1 and s["followup_updated"] == 1
    assert s["related_tags_pruned"] == 0  # related/project grounded, kept
    assert s["review_tags_added"] == 0 and s["review_tags_removed"] == 0  # gated: not justified for VA
    assert s["cards_modified"] == 0 and s["invariants"]["db_mutations"] == 0 and s["ollama_calls"] == 0
    assert p.read_text() == before  # dry-run wrote nothing


def test_polish_rejects_non_review_tag(env, monkeypatch):
    _seed(env, monkeypatch, [("Source Notes/Work/VA.md", "value_analysis", _VA_DETAIL)])
    args = _args(env)
    args.polish = True
    args.add_review = ["related/project"]  # not a review/* tag
    with pytest.raises(km.RepairError):
        km.run(args)
