"""Phase 10 convergence — Model Enriched Intelligence render surfaces (browser + Obsidian, offline).

Proves the exact label renders on the browser HTML card and the Obsidian markdown, safe source ids
appear, raw/private patterns are scrubbed/absent, the withheld state renders honestly, the pending
V45 subsection is folded under the one label, and the browser stays egress-clean / never auto-opens.
"""

from __future__ import annotations

from hb_assistant.construction.second_brain.local_ai.daily_run_html import (
    render_daily_run_html,
    scan_daily_run_html,
)
from hb_assistant.construction.second_brain.local_ai.model_enriched_intelligence import (
    render_model_enriched_markdown,
)

_LABEL = "Model Enriched Intelligence"


def _available_mei() -> dict:
    return {
        "enabled": True,
        "available": True,
        "label": _LABEL,
        "degraded": False,
        "withheld_reason": None,
        "bullets_kept": 1,
        "pending_followup_count": 1,
        "intelligence": {
            "executive_catchup": ["One priority and one pending item today."],
            "top_priorities": [
                {"text": "Respond to the slab RFI", "source_ids": ["dbac-abc123def456"],
                 "confidence": 0.9, "reason_code": "due_today"}
            ],
            "open_loops": [], "waiting_on_me": [], "waiting_on_others": [],
            "meeting_prep": [], "project_risk": [],
        },
        "pending_followup": {
            "count": 1,
            "items": [
                {
                    "label": "Model-enriched / pending review",
                    "enriched_title": "Send revised submittal",
                    "waiting_state": "waiting_on_me", "assignee_type": "me",
                    "confidence": 0.82, "confidence_band": "high",
                    "suggested_next_action": "Draft and send",
                    "enrichment_id": "enr-1", "candidate_id": "c1", "watch_item_id": "w1",
                    "source_refs": ["sha256:abc123"],
                }
            ],
            "omitted_low_confidence": 0,
        },
    }


def _withheld_mei() -> dict:
    return {
        "enabled": True, "available": False, "label": _LABEL, "degraded": True,
        "withheld_reason": "model_unavailable", "bullets_kept": 0,
        "pending_followup_count": 0, "intelligence": None,
        "pending_followup": {"count": 0, "items": [], "omitted_low_confidence": 0},
    }


def _render_html(mei: dict) -> str:
    return render_daily_run_html(
        brief_date="2026-06-09", status="success", sections=[], summary={"rendered": 0},
        warnings=[], generated_label="2026-06-09T05:00:00-04:00", model_enriched=mei,
    )


def test_browser_card_exact_label_and_source_ids() -> None:
    html = _render_html(_available_mei())
    assert _LABEL in html
    assert "Respond to the slab RFI" in html
    assert "dbac-abc123def" in html  # short safe candidate id
    assert "Send revised submittal" in html  # pending item folded under the one label
    assert scan_daily_run_html(html) == []


def test_browser_card_withheld_renders_honestly() -> None:
    html = _render_html(_withheld_mei())
    assert _LABEL in html
    assert "withheld" in html.lower()
    assert "model_unavailable" in html
    assert scan_daily_run_html(html) == []


def test_browser_never_auto_opens_marker() -> None:
    # The renderer is pure HTML; there is no auto-open path. Assert no script/window.open injected.
    html = _render_html(_available_mei())
    assert "window.open" not in html
    assert "<script" not in html.lower()


def test_obsidian_markdown_label_and_sources() -> None:
    md = render_model_enriched_markdown(_available_mei())
    assert md.startswith("## Model Enriched Intelligence")
    assert "Respond to the slab RFI" in md
    assert "sources:" in md
    assert "Send revised submittal" in md


def test_obsidian_markdown_withheld_banner() -> None:
    md = render_model_enriched_markdown(_withheld_mei())
    assert md.startswith("## Model Enriched Intelligence")
    assert "withheld" in md.lower()
    assert "model_unavailable" in md


def test_render_is_raw_free() -> None:
    html = _render_html(_available_mei())
    md = render_model_enriched_markdown(_available_mei())
    for blob in (html, md):
        for forbidden in ("http://", "https://", "@example", "Bearer ", "eyJ"):
            assert forbidden not in blob
