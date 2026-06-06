"""Phase 09 Addendum (Daily Brief V2) — closeout & handoff bundle tests (Prompt 06)."""

from __future__ import annotations

import json
import re

from hb_assistant.construction.second_brain.daily_brief import build_daily_brief_v2_closeout

_SECRET_OR_URL = re.compile(
    r"Bearer\s+[A-Za-z0-9]|-----BEGIN|eyJ[A-Za-z0-9_-]{5,}|https?://|access_token|refresh_token|client_secret"
)


def test_closeout_reports_core_facts() -> None:
    c = build_daily_brief_v2_closeout(write_evidence=False)
    assert c["schema_version"] == 40
    assert c["schema_changed_by_addendum"] is False
    assert c["packet_version"] == "DailyBriefHandoffPacketV2"
    assert c["output_path"].endswith("Work/Daily Brief/2026-06-06-daily-brief.md")
    assert isinstance(c["files_changed"], list)
    assert c["next_improvement"]["title"].startswith("Phase 10")
    assert c["guardrails"]["production_readiness"] is False


def test_closeout_render_quality_and_rejected_fixture() -> None:
    c = build_daily_brief_v2_closeout(write_evidence=False)
    assert c["v2_render_quality"]["passed"] is True
    assert c["v2_render_quality"]["full_detail"]["passed"] is True
    assert c["v2_render_quality"]["detail_unavailable"]["passed"] is True
    # The internal-commentary fixture must be rejected.
    assert c["v2_render_quality"]["rejected_internal"]["passed"] is False
    assert c["closeout_complete"] is True


def test_closeout_enrichment_coverage_and_detail_unavailable() -> None:
    c = build_daily_brief_v2_closeout(write_evidence=False)
    cov = c["record_level_enrichment_coverage"]
    assert cov["detail_available_true"] >= 1
    assert cov["detail_unavailable"] >= 1
    assert cov["records_total"] >= 1
    # rfis/submittals/punch/procurement are detail-unavailable for a known reason.
    assert "dedicated_reader_not_available" in cov["detail_gap_reasons"]
    assert (
        c["detail_unavailable_counts"]["detail_unavailable_sections"] == cov["detail_unavailable"]
    )


def test_closeout_summarizes_validation_dir(tmp_path) -> None:
    (tmp_path / "mcp-no-writeback.json").write_text(
        json.dumps({"proof_passed": True}), encoding="utf-8"
    )
    (tmp_path / "llamaindex-build.json").write_text(
        json.dumps({"status": "deferred"}), encoding="utf-8"
    )
    c = build_daily_brief_v2_closeout(validation_dir=str(tmp_path), write_evidence=False)
    runs = c["validation_runs"]["runs"]
    assert c["validation_runs"]["captured"] is True
    assert runs["mcp-no-writeback"]["passed"] is True
    assert runs["mcp-no-writeback"]["status"] == "passed"
    # A captured output with no boolean pass key is recorded, not failed.
    assert runs["llamaindex-build"]["status"] == "captured"


def test_closeout_writes_artifacts_no_raw(tmp_path) -> None:
    c = build_daily_brief_v2_closeout(evidence_dir=str(tmp_path), write_evidence=True)
    for fname in ("daily-brief-v2-closeout.json", "daily-brief-v2-closeout.md"):
        assert (tmp_path / fname).exists(), fname
    blob = (tmp_path / "daily-brief-v2-closeout.json").read_text()
    assert not _SECRET_OR_URL.search(blob)
    assert c["closeout_path"].endswith("daily-brief-v2-closeout.json")
