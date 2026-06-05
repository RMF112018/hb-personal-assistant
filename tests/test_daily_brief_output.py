"""Phase 08A Prompt 12 — daily-brief approved-output renderer + safe writer."""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hb_assistant.construction.second_brain.daily_brief import (
    build_daily_brief_context,
    render_brief_markdown,
    write_brief_output,
)
from hb_assistant.construction.second_brain.daily_brief.output import (
    SECTION_END,
    SECTION_START,
    resolve_brief_path,
)
from hb_assistant.construction.store import ConstructionStore


@pytest.fixture
def db_path(tmp_path: Path) -> str:
    return str(tmp_path / "out.sqlite")


def _seed(db_path: str) -> None:
    store = ConstructionStore(db_path)
    store.upsert_cross_source_relationship(
        relationship_id="rel-1",
        source_family="email",
        source_record_type="message",
        source_record_ref="m1",
        target_family="procore",
        target_record_type="rfi",
        target_record_ref="rfi1",
        relationship_type="references",
        confidence_class="human_promoted",
        source_reference_json=json.dumps({"project_key": "P1"}),
        project_key="P1",
        promotion_status="promoted",
        promoted_by="human",
        review_required=False,
    )


def _context(db_path: str):
    return build_daily_brief_context(
        brief_date="2026-06-02", project_key="P1", db_path=db_path, emit_receipt=False
    )


def test_render_is_redacted_markdown(db_path: str) -> None:
    _seed(db_path)
    md = render_brief_markdown(_context(db_path))
    assert md.startswith("# Daily Brief — 2026-06-02")
    assert "## Priority Actions" in md
    assert "Review exceptions" in md or "Batched/suppressed" in md  # new summary-first review burden section (replaced full queue dump)
    for forbidden in ("signed_url", "download_url", "raw_body", "raw_prompt", "raw_response"):
        assert forbidden not in md


def test_dry_run_writes_nothing(tmp_path: Path, db_path: str) -> None:
    _seed(db_path)
    vault = tmp_path / "briefs"
    md = render_brief_markdown(_context(db_path))
    res = write_brief_output(
        brief_date="2026-06-02", content=md, vault_brief_dir=str(vault), apply=False
    )
    assert res.written is False
    assert res.output_path_redacted is None
    assert res.content_hash  # hash still computed
    assert not vault.exists()


def test_default_brief_path_uses_approved_phase_08a_root() -> None:
    resolved = resolve_brief_path("2026-06-02")
    assert str(resolved).endswith(
        "Construction Intelligence/Phase 08A Daily Briefs/2026-06-02_daily_brief.md"
    )


def test_explicit_brief_dir_override_is_unchanged(tmp_path: Path) -> None:
    resolved = resolve_brief_path("2026-06-02", vault_brief_dir=tmp_path / "briefs")
    assert resolved == tmp_path / "briefs" / "2026-06-02_daily_brief.md"


def test_apply_writes_marker_bounded_file(tmp_path: Path, db_path: str) -> None:
    _seed(db_path)
    vault = tmp_path / "briefs"
    md = render_brief_markdown(_context(db_path))
    res = write_brief_output(
        brief_date="2026-06-02", content=md, vault_brief_dir=str(vault), apply=True
    )
    assert res.written is True
    target = vault / "2026-06-02_daily_brief.md"
    assert target.exists()
    text = target.read_text(encoding="utf-8")
    assert SECTION_START in text and SECTION_END in text
    assert "# Daily Brief — 2026-06-02" in text


def test_apply_preserves_user_text_outside_markers(tmp_path: Path, db_path: str) -> None:
    _seed(db_path)
    vault = tmp_path / "briefs"
    vault.mkdir(parents=True)
    target = vault / "2026-06-02_daily_brief.md"
    target.write_text(
        f"# My notes\nkeep me\n{SECTION_START}\nold\n{SECTION_END}\nkeep me too\n",
        encoding="utf-8",
    )
    md = render_brief_markdown(_context(db_path))
    write_brief_output(
        brief_date="2026-06-02", content=md, vault_brief_dir=str(vault), apply=True
    )
    text = target.read_text(encoding="utf-8")
    assert "keep me" in text
    assert "keep me too" in text
    assert "old" not in text  # replaced inside markers
