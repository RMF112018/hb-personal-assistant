"""N8C-1: local-summary marker dual-READ compatibility (emit stays legacy this slice).

N8C-1 lands the neutral naming vocabulary and makes every local-summary reader recognise BOTH
the neutral ``assistant-local-summary`` marker and the legacy ``hb-local-summary`` marker. The
EMITTER intentionally stays on the legacy marker in this slice (the flip is deferred to N8C-2 to
avoid a wide test/asset rewrite), so these tests characterise exactly that: legacy emit + dual read.
"""

from __future__ import annotations

from hb_assistant import naming
from hb_assistant.obsidian_mcp import source_card_repair, source_local_summary, source_notes


def _card(marker: str) -> str:
    return (
        "---\ntitle: X\nnote_type: source_card\n---\n\n"
        "## Advisory Summary\n"
        f'<!-- {marker}:start model="qwen2.5:14b" status="pending" -->\n'
        "placeholder\n"
        f"<!-- {marker}:end -->\n"
        "## Source Basis\nkeep me\n"
    )


def test_emitter_stays_on_legacy_marker_this_slice() -> None:
    lines = source_notes._advisory_summary(None)
    block = "\n".join(lines)
    assert "hb-local-summary:start" in block
    assert "hb-local-summary:end" in block
    # The neutral marker is NOT yet emitted (deferred to N8C-2).
    assert "assistant-local-summary" not in block
    # The re-exported module constants still point at the legacy form for the emitter.
    assert source_notes.LOCAL_SUMMARY_BEGIN_PREFIX == naming.LEGACY_LOCAL_SUMMARY_BEGIN_PREFIX
    assert source_notes.LOCAL_SUMMARY_END == naming.LEGACY_LOCAL_SUMMARY_END


def test_predicates_recognise_both_forms() -> None:
    assert naming.is_local_summary_begin('<!-- hb-local-summary:start model="m" status="pending" -->')
    assert naming.is_local_summary_begin('<!-- assistant-local-summary:start model="m" status="pending" -->')
    assert naming.is_local_summary_end("<!-- hb-local-summary:end -->")
    assert naming.is_local_summary_end("<!-- assistant-local-summary:end -->")
    assert not naming.is_local_summary_begin("## Advisory Summary")
    assert not naming.is_local_summary_end("plain text")


def test_replace_block_recognises_both_and_preserves_surroundings() -> None:
    for marker in ("hb-local-summary", "assistant-local-summary"):
        out = source_notes.replace_local_summary_block(
            _card(marker), ["NEW BODY"], model="qwen2.5:14b", generated_at="2026-07-05"
        )
        assert "NEW BODY" in out
        # Surrounding canonical content is untouched.
        assert "## Source Basis\nkeep me" in out
        assert "title: X" in out
        # Exactly one block remains after replacement.
        starts = sum(naming.is_local_summary_begin(ln) for ln in out.splitlines())
        ends = sum(naming.is_local_summary_end(ln) for ln in out.splitlines())
        assert starts == 1 and ends == 1


def test_strip_block_removes_both_forms() -> None:
    for marker in ("hb-local-summary", "assistant-local-summary"):
        stripped = source_local_summary._strip_local_summary_block(_card(marker))
        assert "placeholder" not in stripped
        assert marker not in stripped
        assert "keep me" in stripped


def test_repair_reader_recognises_both_forms() -> None:
    for marker in ("hb-local-summary", "assistant-local-summary"):
        status, body = source_card_repair._summary_block(_card(marker))
        assert status == "pending"
        assert "placeholder" in body


def test_sanitizer_scrubs_both_marker_forms() -> None:
    dirty = (
        "Good advisory line.\n"
        '<!-- hb-local-summary:start model="m" status="x" -->\n'
        '<!-- assistant-local-summary:start model="m" status="x" -->\n'
        "Another good line.\n"
    )
    kept = source_local_summary.sanitize_advisory_markdown(dirty)
    joined = "\n".join(kept)
    assert "hb-local-summary" not in joined
    assert "assistant-local-summary" not in joined
    assert "Good advisory line." in joined
