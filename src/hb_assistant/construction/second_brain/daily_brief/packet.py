"""Phase 09 Addendum — Daily Brief Handoff Packet (``DailyBriefHandoffPacketV1``).

Projects the existing daily-brief context (broker → research packet → cards) into a stable,
**metadata-only** packet that Claude can safely consume through MCP. This module adds **no** new
retrieval: it reuses ``_assemble_daily_brief`` (one deterministic, read-only retrieval) and reshapes
the already-redacted, source-linked context/envelope into the contract packet. Source refs are emitted
only as **hashes** + safe labels; every section item is metadata-only; no raw body/document/calendar/
prompt/response/retrieved-context, no signed/download/Graph URLs, no tokens/secrets. Read-only:
persists nothing (no packet receipt table is added); fail-closed on missing contract or raw leakage.

Public entry points:
  build_daily_brief_packet(*, brief_date, project_key=None, mode="dry_run", db_path=None) -> dict
  build_daily_brief_packet_proof(*, evidence_dir=None, write_evidence=True) -> dict
  build_daily_brief_packet_v2(*, brief_date, project_key=None, mode="dry_run", db_path=None) -> dict
  build_daily_brief_packet_v2_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain daily-brief packet --date YYYY-MM-DD [--version v2] --json
     hb-assistant second-brain daily-brief packet-proof --json
     hb-assistant second-brain daily-brief packet-v2-proof --json

V2 (Phase 09 Addendum, Prompt 01) is a *projection* over the V1 packet: it splits user-facing
``render_payload`` from internal ``governance_metadata`` so governance never renders into the brief
body. It adds no new retrieval; sections without a current data source (calendar, email, deadlines,
yesterday) are emitted empty with honest ``data_gaps`` entries deferred to Prompt 02 (enrichment).
"""

from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ...store import ConstructionStore
from ..financial_review_routing import _assert_no_raw
from ..retrieval import RetrievalItem
from .context import _assemble_daily_brief

PACKET_VERSION = "DailyBriefHandoffPacketV1"
EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-daily-brief-mcp-handoff"
_CONTRACT_JSON = "daily-brief-packet-contract.json"
_CONTRACT_MD = "daily-brief-packet-contract.md"
_PROOF_JSON = "daily-brief-packet-proof.json"
_PROOF_MD = "daily-brief-packet-proof.md"

# Phase 09 Addendum V2 — Executive Utility Hardening (Prompt 01: packet contract).
PACKET_VERSION_V2 = "DailyBriefHandoffPacketV2"
EVIDENCE_DIR_V2 = "docs/evidence/construction-intelligence-phase-09-addendum-daily-brief-v2"
_V2_PROOF_JSON = "daily-brief-packet-v2-proof.json"
_V2_PROOF_MD = "daily-brief-packet-v2-proof.md"

# The exact guardrails block required by the packet contract (carried inside every packet).
PACKET_GUARDRAILS: dict[str, bool] = {
    "advisory_only": True,
    "source_linked": True,
    "metadata_only": True,
    "no_raw": True,
    "no_writeback": True,
    "no_final_determinations": True,
    "claude_rendering_only": True,
}

# Concise instructions for Claude (rendering-only consumer of the packet).
RENDERING_INSTRUCTIONS: dict[str, Any] = {
    "render_as": "human_readable_executive_brief",
    "instructions": [
        "Render as a human-readable executive brief.",
        "Preserve all warnings (stale, low-confidence, and review-required).",
        "Do not infer beyond the packet contents.",
        "Do not make final determinations (financial, legal, claim, payment, safety, schedule, contractual).",
        "Include the source coverage note.",
        "Include the suggested follow-up questions.",
        "Do not ask for raw records.",
    ],
}

_MEETING_FAMILY = "meeting_prep_brief_sections"
_AGING_FAMILY = "aging_exposure_report_items"
_RISK_FAMILY = "project_risk_digest_items"
_MEMORY_FAMILY = "accepted_long_term_memory"
_CHANGE_FAMILIES = frozenset({"cross_source_relationships", "project_issue_history_items"})
_LOW_CONFIDENCE = frozenset({"low", "weak_heuristic", "model_proposed", "stale_or_unresolved"})

_BLOCKED_USES: list[str] = [
    "final_determination",
    "source_system_writeback",
    "raw_record_request",
    "authoritative_claim",
]

# Lexicon used to flag (never emit) final-determination language.
_FINAL_DETERMINATION_LEXICON: tuple[str, ...] = (
    "approve payment",
    "approve the claim",
    "final determination",
    "final approval",
    "payment decision",
    "entitlement decision",
    "claim decision",
    "certify schedule",
    "legally binding",
    "we will pay",
)

# --- V2 contract constants (single source of truth for builder, proof, and emitted contract) ------

# The user-facing keys carried by ``render_payload`` (brief-ready data only).
RENDER_PAYLOAD_SECTIONS: list[str] = [
    "brief_date",
    "portfolio_scope",
    "yesterday",
    "today_agenda",
    "next_7_days",
    "schedule",
    "rfis",
    "submittals",
    "punch",
    "procurement",
    "needs_attention",
    "focus_recommendations",
    "project_signals",
    "email_activity",
    "calendar_activity",
    "data_gaps",
]

# Record-bearing sections held to the count-vs-detail rule (each is a ``RecordSection``).
RECORD_SECTION_NAMES: list[str] = [
    "yesterday",
    "today_agenda",
    "next_7_days",
    "schedule",
    "rfis",
    "submittals",
    "punch",
    "procurement",
    "email_activity",
    "calendar_activity",
]

# The uniform RecordSection envelope (Prompt 02): a count is only actionable if it is backed by
# listed records, otherwise the section must declare detail_available=False + a detail_gap_reason.
RECORD_SECTION_FIELDS: list[str] = [
    "count",
    "records",
    "detail_available",
    "detail_gap_reason",
    "source_family",
    "why_it_matters",
]

# Fields carried by every renderable item (e.g. ``needs_attention`` entries). Fields not yet
# sourced from the V1 retrieval path are emitted as null and flagged via ``detail_availability``.
RENDER_ITEM_FIELDS: list[str] = [
    "project_key",
    "project_name",
    "record_type",
    "record_id",
    "title",
    "status",
    "responsible_party",
    "due_date",
    "start_date",
    "finish_date",
    "source_family",
    "source_ref_hash",
    "confidence_class",
    "review_tier",
    "review_required",
    "freshness_label",
    "stale_warning",
    "why_it_matters",
    "recommended_focus",
    "detail_availability",
]

# Internal keys carried by ``governance_metadata`` — never rendered into the brief body.
GOVERNANCE_METADATA_FIELDS: list[str] = [
    "packet_id",
    "packet_version",
    "generated_utc",
    "brief_date",
    "mode",
    "source_coverage_summary",
    "source_refs",
    "guardrails",
    "rendering_instructions",
    "proof_metadata",
    "receipt_metadata",
    "status",
    "degradation_mode",
]

# Governance keys that must NOT leak into ``render_payload`` (separation invariant).
FORBIDDEN_IN_RENDER_PAYLOAD: list[str] = [
    "packet_id",
    "packet_version",
    "source_coverage_summary",
    "source_refs",
    "guardrails",
    "proof_metadata",
    "receipt_metadata",
]

# Concise instructions for Claude when consuming a V2 packet (render only ``render_payload``).
RENDERING_INSTRUCTIONS_V2: dict[str, Any] = {
    "render_as": "human_readable_executive_brief",
    "render_source": "render_payload",
    "instructions": [
        "Render only the render_payload. Never render governance_metadata into the brief body.",
        "Lead with yesterday, today's agenda, deadlines in the next 7 days, what needs attention, "
        "and what to focus on.",
        "Each record-bearing section is a RecordSection: render its listed records, never a bare "
        "count. When detail_available is false, state the detail_gap_reason plainly.",
        "Preserve all review-required, stale, and low-confidence warnings carried on items.",
        "Do not infer beyond the packet contents.",
        "Do not make final determinations (financial, legal, claim, payment, safety, schedule, contractual).",
        "Do not ask for raw records.",
    ],
}


class DailyBriefPacketError(RuntimeError):
    """Raised when the packet builder cannot resolve its contract or detects a leak (fail-closed)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_sha() -> str:
    try:
        repo_root = Path(__file__).resolve().parents[5]
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, stderr=subprocess.DEVNULL, timeout=5
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def load_daily_brief_packet_contract() -> dict[str, Any]:
    """Load the daily-brief packet contract (fail-closed if missing/invalid)."""
    from ..contracts import load_phase_09_contract

    contract = load_phase_09_contract("daily_brief_handoff_packet_contract")
    if not isinstance(contract, dict) or "required_packet_fields" not in contract:
        raise DailyBriefPacketError(
            "phase 09 daily-brief packet contract not found or missing required fields"
        )
    return contract


def load_daily_brief_packet_v2_contract() -> dict[str, Any]:
    """Load the daily-brief V2 packet contract (fail-closed if missing/invalid)."""
    from ..contracts import load_phase_09_contract

    contract = load_phase_09_contract("daily_brief_handoff_packet_v2_contract")
    if not isinstance(contract, dict) or "render_payload_sections" not in contract:
        raise DailyBriefPacketError(
            "phase 09 daily-brief packet V2 contract not found or missing required fields"
        )
    return contract


def _reject_final_determination(text: str | None) -> bool:
    """Return True if final-determination language is present (i.e., must be flagged)."""
    t = (text or "").lower()
    return any(token in t for token in _FINAL_DETERMINATION_LEXICON)


def _priority(it: RetrievalItem) -> str:
    if it.review_required or it.conflict_flags:
        return "high"
    if it.review_tier == 2 or it.stale_unknown_flags:
        return "medium"
    return "low"


def _freshness(it: RetrievalItem) -> str:
    r = str(it.recency or "")
    if r.startswith("2026"):
        return "current"
    if r.startswith(("2025", "2024")):
        return "recent"
    if r.startswith("rel-"):
        return "relative"
    return "unknown"


def _ref_label(it: RetrievalItem) -> str | None:
    """A safe, human-meaningful label that never carries the raw ref (family + record type only)."""
    label = f"{it.source_family}:{it.record_type}".strip(":")
    return label or None


def _stale_warning(it: RetrievalItem) -> str | None:
    flags = list(it.stale_unknown_flags or [])
    return ";".join(flags) if flags else None


def _build_item(it: RetrievalItem, *, section: str) -> dict[str, Any]:
    """Project one retrieval item into the metadata-only packet item shape."""
    allowed_use = (
        "advisory_context_only" if section == "accepted_memory_context" else "advisory_render"
    )
    return {
        "item_id": _hash(f"{section}:{it.source_family}:{it.source_ref}")[:48],
        "section": section,
        "priority": _priority(it),
        "project_key": it.project_key,
        "title_redacted": it.content_excerpt_redacted or it.record_type,
        "summary_redacted": it.content_excerpt_redacted,
        "source_family": it.source_family,
        "source_ref_hash": _hash(it.source_ref)[:48],
        "source_ref_label": _ref_label(it),
        "review_tier": it.review_tier,
        "review_required": it.review_required,
        "confidence_class": it.confidence_class,
        "freshness_label": _freshness(it),
        "stale_warning": _stale_warning(it),
        "allowed_use": allowed_use,
        "blocked_uses": list(_BLOCKED_USES),
    }


def _build_sections(items: list[RetrievalItem]) -> dict[str, list[dict[str, Any]]]:
    """Group items into the packet's source-linked sections (deterministic; items may appear in
    more than one lens, exactly as the daily brief surfaces them today)."""
    sections: dict[str, list[dict[str, Any]]] = {
        "recent_changes": [],
        "review_required_items": [],
        "aging_watchlist": [],
        "meeting_prep": [],
        "risk_watchlist": [],
        "stale_or_low_confidence_warnings": [],
        "accepted_memory_context": [],
    }
    for it in items:
        if it.review_required:
            sections["review_required_items"].append(
                _build_item(it, section="review_required_items")
            )
        if it.source_family == _MEETING_FAMILY:
            sections["meeting_prep"].append(_build_item(it, section="meeting_prep"))
        if it.source_family == _AGING_FAMILY:
            sections["aging_watchlist"].append(_build_item(it, section="aging_watchlist"))
        if it.source_family == _RISK_FAMILY:
            sections["risk_watchlist"].append(_build_item(it, section="risk_watchlist"))
        if it.source_family in _CHANGE_FAMILIES:
            sections["recent_changes"].append(_build_item(it, section="recent_changes"))
        if it.source_family == _MEMORY_FAMILY:
            sections["accepted_memory_context"].append(
                _build_item(it, section="accepted_memory_context")
            )
        if it.stale_unknown_flags or (it.confidence_class or "").lower() in _LOW_CONFIDENCE:
            sections["stale_or_low_confidence_warnings"].append(
                _build_item(it, section="stale_or_low_confidence_warnings")
            )
    return sections


def _packet_source_refs(items: list[RetrievalItem]) -> list[dict[str, Any]]:
    """Top-level metadata-only source refs (hashed; deduped by family + ref hash)."""
    seen: set[tuple[str, str]] = set()
    out: list[dict[str, Any]] = []
    for it in items:
        ref_hash = _hash(it.source_ref)[:48]
        key = (it.source_family, ref_hash)
        if key in seen:
            continue
        seen.add(key)
        out.append(
            {
                "source_family": it.source_family,
                "source_ref_hash": ref_hash,
                "source_ref_label": _ref_label(it),
                "review_tier": it.review_tier,
            }
        )
    return out


def _suggested_follow_ups(sections: dict[str, list[dict[str, Any]]]) -> list[str]:
    """Deterministic, safe follow-up questions (never request raw records)."""
    qs: list[str] = []
    if sections["review_required_items"]:
        qs.append("Which review-required items should I prioritize first?")
    if sections["aging_watchlist"]:
        qs.append("Which aging items are closest to their threshold band?")
    if sections["risk_watchlist"]:
        qs.append("What is driving the current risk signals?")
    if sections["meeting_prep"]:
        qs.append("Do you want the meeting prep context for today's meetings?")
    if sections["stale_or_low_confidence_warnings"]:
        qs.append("Which stale or low-confidence items need a status refresh?")
    if sections["accepted_memory_context"]:
        qs.append("Should I factor the accepted memory context into the summary?")
    qs.append("Would you like the full source coverage breakdown?")
    return qs[:6]


def build_daily_brief_packet(
    *,
    brief_date: str,
    project_key: str | None = None,
    mode: str = "dry_run",
    db_path: str | None = None,
) -> dict[str, Any]:
    """Build a ``DailyBriefHandoffPacketV1`` metadata-only packet (read-only, fail-closed).

    Reuses the existing daily-brief assembly (no new retrieval) and reshapes its redacted,
    source-linked context into the contract packet. Persists nothing.
    """
    # Validate the contract is present/shaped before doing work (fail-closed).
    load_daily_brief_packet_contract()

    context, _packet, _assessment, envelope, _receipt = _assemble_daily_brief(
        brief_date=brief_date,
        project_key=project_key,
        db_path=db_path,
        emit_receipt=False,
    )
    items = envelope.items
    sections = _build_sections(items)
    source_refs = _packet_source_refs(items)

    coverage_summary = {
        "source_coverage": context.source_coverage,
        "source_ref_count": context.source_ref_count,
        "project_count": context.project_count,
        "review_required_count": context.review_required_count,
        "stale_unknown_count": context.stale_unknown_count,
        "review_tier_counts": context.review_tier_counts,
        "context_quality_class": context.context_quality_class,
        "degradation_mode": context.degradation_mode,
        "families_present": sorted({it.source_family for it in items}),
        "coverage_warnings": context.warnings[:50],
    }

    packet_id = (
        "dbp_"
        + _hash(
            f"{PACKET_VERSION}|{brief_date}|{project_key or 'all'}|{mode}|{context.source_ref_count}|"
            + "|".join(sorted(r["source_ref_hash"] for r in source_refs))
        )[:32]
    )

    packet: dict[str, Any] = {
        "packet_id": packet_id,
        "packet_version": PACKET_VERSION,
        "generated_utc": _now(),
        "brief_date": brief_date,
        "project_scope": project_key or "all",
        "mode": mode,
        "source_coverage_summary": coverage_summary,
        "what_matters_today": list(context.what_matters_today),
        "recent_changes": sections["recent_changes"],
        "review_required_items": sections["review_required_items"],
        "aging_watchlist": sections["aging_watchlist"],
        "meeting_prep": sections["meeting_prep"],
        "risk_watchlist": sections["risk_watchlist"],
        "stale_or_low_confidence_warnings": sections["stale_or_low_confidence_warnings"],
        "accepted_memory_context": sections["accepted_memory_context"],
        "suggested_follow_up_questions": _suggested_follow_ups(sections),
        "source_refs": source_refs,
        "guardrails": dict(PACKET_GUARDRAILS),
        "rendering_instructions": dict(RENDERING_INSTRUCTIONS),
        "status": context.status,
        "degradation_mode": context.degradation_mode,
        "packet_receipt_emitted": False,
        "read_only": True,
    }

    # Fail-closed: never emit a packet that carries a raw-shaped value.
    _assert_no_raw(json.dumps(packet, default=str), "daily brief packet")
    return packet


# --- Proof ---------------------------------------------------------------------------------------


def _seed_proof_db(path: str) -> None:
    """Seed a controlled temp DB exercising every packet section (metadata-only, no raw)."""
    import sqlite3

    store = ConstructionStore(path)
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
    store.upsert_cross_source_relationship(
        relationship_id="rel-2",
        source_family="email",
        source_record_type="message",
        source_record_ref="m2",
        target_family="financial",
        target_record_type="invoice",
        target_record_ref="inv1",
        relationship_type="references",
        confidence_class="model_proposed",
        source_reference_json=json.dumps({"project_key": "P1"}),
        project_key="P1",
        promotion_status="promoted",
        promoted_by="human",
        review_required=True,
    )
    store.upsert_project_issue_history_item(
        issue_family_id="iss-1",
        project_key="P1",
        status="open",
        source_families_json=json.dumps(["procore"]),
        confidence_class="medium",
        issue_kind="rfi",
        age_days=30,
        review_required=False,
        stale_unknown_flags_json=json.dumps(["stale_status"]),
    )
    store.upsert_project_risk_digest_item(
        risk_digest_id="risk-1",
        project_key="P1",
        risk_indicator_type="schedule_slip_signal",
        risk_source_class="inferred_candidate",
        summary_redacted="open_rfi_count=3;aging_band=30_60",
        confidence_class="medium",
        review_required=False,
    )
    store.upsert_aging_exposure_report_item(
        aging_item_id="age-1",
        project_key="P1",
        record_family="procore",
        record_ref="rfi1",
        status="open",
        threshold_band="30_60",
        age_days=45,
        stale_flag=True,
        confidence_class="medium",
        review_required=False,
    )
    conn = sqlite3.connect(path)
    conn.execute(
        "INSERT INTO long_term_memory_items "
        "(memory_id, memory_type, statement_redacted, project_key, confidence_class, "
        " review_status) VALUES ('mem1','fact','kickoff confirmed','P1','high','accepted')"
    )
    conn.commit()
    conn.close()


def _seed_v2_enrichment_db(path: str) -> None:
    """Extend the V1 seed with record-level enrichment sources (calendar, email threads, Procore
    action signals) so the V2 proof exercises real, source-linked record sections (metadata-only,
    no raw). Brief date under proof is 2026-06-02; deadline falls inside the 7-day window."""
    import sqlite3

    _seed_proof_db(path)
    store = ConstructionStore(path)
    # Calendar source registry (FK target for calendar_event_index).
    store.upsert_calendar_source_location(
        source_id="cal-src-1", mailbox_owner_hash="owner-hash-1", calendar_role="primary"
    )
    # Calendar: one event today, one yesterday (relative to the 2026-06-02 proof brief date).
    store.upsert_calendar_event_index(
        event_index_id="cal-today",
        source_id="cal-src-1",
        graph_event_id_hash="hash-today",
        start_datetime_utc="2026-06-02T09:00:00+00:00",
        end_datetime_utc="2026-06-02T10:00:00+00:00",
        subject_redacted="Project coordination sync (redacted)",
        project_key="P1",
        is_online_meeting=True,
        review_required=False,
    )
    store.upsert_calendar_event_index(
        event_index_id="cal-yday",
        source_id="cal-src-1",
        graph_event_id_hash="hash-yday",
        start_datetime_utc="2026-06-01T14:00:00+00:00",
        end_datetime_utc="2026-06-01T15:00:00+00:00",
        subject_redacted="Owner review meeting (redacted)",
        project_key="P1",
        review_required=False,
    )
    store.upsert_calendar_event_attendee(
        event_index_id="cal-today", attendee_hash="att-1", attendee_role="required"
    )
    store.upsert_calendar_event_attendee(
        event_index_id="cal-today", attendee_hash="att-2", attendee_role="optional"
    )
    # Email thread summary (redacted topic only).
    store.upsert_email_thread_summary(
        thread_key="thr-1",
        project_key="P1",
        message_count=3,
        last_message_datetime="2026-06-01T16:00:00+00:00",
        participants_hash=["p-hash-1", "p-hash-2"],
        summary_redacted="Submittal coordination (redacted)",
        review_required=False,
    )
    # Procore action signals: a zero-float schedule signal and a deadline inside the 7-day window.
    conn = sqlite3.connect(path)
    conn.execute(
        "INSERT INTO procore_action_signals (action_signal_id, project_key, record_key,"
        " endpoint_id, signal_type, signal_status, importance, due_at_utc, title_redacted,"
        " summary_redacted, reason_codes_json, first_detected_at_utc, last_seen_at_utc,"
        " metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "sig-sched-1",
            "P1",
            "P1|schedule_activities|sch1|act1",
            "schedule_activities",
            "activity_zero_float",
            "open",
            "high",
            None,
            "Activity at or below zero float",
            None,
            "[]",
            "2026-06-02T00:00:00+00:00",
            "2026-06-02T00:00:00+00:00",
            json.dumps(
                {
                    "total_float": 0.0,
                    "float_band": "zero_or_negative",
                    "is_critical": True,
                    "constraint_type": "must_finish_on",
                    "constraint_date": "2026-06-10",
                    "deadline_variance": -2,
                    "percent_complete": 40,
                }
            ),
        ),
    )
    conn.execute(
        "INSERT INTO procore_action_signals (action_signal_id, project_key, record_key,"
        " endpoint_id, signal_type, signal_status, importance, due_at_utc, title_redacted,"
        " summary_redacted, reason_codes_json, first_detected_at_utc, last_seen_at_utc,"
        " metadata_json) VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?,?)",
        (
            "sig-due-1",
            "P1",
            "P1|rfis|rfi1",
            "rfis",
            "rfi_response_due",
            "open",
            "high",
            "2026-06-05T00:00:00+00:00",
            "RFI response due",
            None,
            "[]",
            "2026-06-02T00:00:00+00:00",
            "2026-06-02T00:00:00+00:00",
            "{}",
        ),
    )
    conn.commit()
    conn.close()


def _render_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 — Daily Brief Handoff Packet Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- packet_version: {proof['packet_version']}",
        f"- required_fields_present: {proof['required_fields_present']}",
        f"- item_fields_present: {proof['item_fields_present']}",
        f"- metadata_only: {proof['metadata_only']}",
        f"- review_flags_preserved: {proof['review_flags_preserved']}",
        f"- stale_or_low_confidence_preserved: {proof['stale_or_low_confidence_preserved']}",
        f"- source_coverage_present: {proof['source_coverage_present']}",
        f"- accepted_memory_advisory_only: {proof['accepted_memory_advisory_only']}",
        f"- raw_shaped_rejected: {proof['raw_shaped_rejected']}",
        f"- final_determination_flagged: {proof['final_determination_flagged']}",
        f"- no_external_writeback: {proof['no_external_writeback']}",
        "",
        "## Section counts",
        "",
    ]
    for name, count in proof["section_counts"].items():
        lines.append(f"- {name}: {count}")
    lines.append("")
    return "\n".join(lines)


def build_daily_brief_packet_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof that the packet validates against contract, stays metadata-only, preserves
    review/stale flags, carries source coverage + advisory-only memory, rejects raw-shaped values and
    flags final-determination language, and performs no external writeback."""
    import sqlite3
    import tempfile

    contract = load_daily_brief_packet_contract()
    required_fields = list(contract.get("required_packet_fields", []))
    item_fields = list(contract.get("item_fields", []))

    with tempfile.TemporaryDirectory() as tmp:
        seeded = f"{tmp}/seeded.sqlite3"
        _seed_proof_db(seeded)
        packet = build_daily_brief_packet(brief_date="2026-06-02", project_key="P1", db_path=seeded)

        # No writeback: the packet build persists nothing to the operator DB.
        conn = sqlite3.connect(seeded)
        try:
            brief_run_rows = conn.execute("SELECT COUNT(*) FROM daily_brief_runs").fetchone()[0]
        finally:
            conn.close()

    section_names = [
        "recent_changes",
        "review_required_items",
        "aging_watchlist",
        "meeting_prep",
        "risk_watchlist",
        "stale_or_low_confidence_warnings",
        "accepted_memory_context",
    ]
    all_items = [item for name in section_names for item in packet[name]]

    required_fields_present = all(f in packet for f in required_fields) and bool(required_fields)
    item_fields_present = bool(item_fields) and all(
        all(f in item for f in item_fields) for item in all_items
    )

    blob = json.dumps(packet, default=str)
    try:
        _assert_no_raw(blob, "daily brief packet proof")
        metadata_only = True
    except ValueError:
        metadata_only = False

    review_items = packet["review_required_items"]
    review_flags_preserved = (
        bool(review_items)
        and all(i["review_required"] is True for i in review_items)
        and any(i["review_tier"] == 3 for i in review_items)
    )

    stale_section = packet["stale_or_low_confidence_warnings"]
    stale_or_low_confidence_preserved = bool(stale_section) and any(
        i["stale_warning"] for i in stale_section
    )

    cov = packet["source_coverage_summary"]
    source_coverage_present = (
        isinstance(cov.get("source_coverage"), float)
        and cov.get("source_ref_count", 0) > 0
        and bool(cov.get("families_present"))
    )

    memory_items = packet["accepted_memory_context"]
    accepted_memory_advisory_only = bool(memory_items) and all(
        i["allowed_use"] == "advisory_context_only" and "final_determination" in i["blocked_uses"]
        for i in memory_items
    )

    # Raw-shaped rejection must be non-vacuous (the guard actually catches a planted token).
    try:
        _assert_no_raw(json.dumps({"x": "Bearer abc123XYZ"}), "raw probe")
        raw_shaped_rejected = False
    except ValueError:
        raw_shaped_rejected = True

    planted_flagged = _reject_final_determination(
        "Approve payment of the claim as a final determination"
    )
    real_unflagged = not any(
        _reject_final_determination(i["title_redacted"])
        or _reject_final_determination(i["summary_redacted"])
        for i in all_items
    ) and not any(_reject_final_determination(b) for b in packet["what_matters_today"])
    final_determination_flagged = planted_flagged and real_unflagged

    guardrails_exact = packet["guardrails"] == PACKET_GUARDRAILS
    no_external_writeback = brief_run_rows == 0

    proof_passed = (
        required_fields_present
        and item_fields_present
        and metadata_only
        and review_flags_preserved
        and stale_or_low_confidence_preserved
        and source_coverage_present
        and accepted_memory_advisory_only
        and raw_shaped_rejected
        and final_determination_flagged
        and guardrails_exact
        and no_external_writeback
    )

    proof: dict[str, Any] = {
        "proof": "phase_09_daily_brief_handoff_packet",
        "command": "second-brain daily-brief packet-proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "packet_version": PACKET_VERSION,
        "packet_id": packet["packet_id"],
        "required_fields_present": required_fields_present,
        "item_fields_present": item_fields_present,
        "metadata_only": metadata_only,
        "review_flags_preserved": review_flags_preserved,
        "stale_or_low_confidence_preserved": stale_or_low_confidence_preserved,
        "source_coverage_present": source_coverage_present,
        "accepted_memory_advisory_only": accepted_memory_advisory_only,
        "raw_shaped_rejected": raw_shaped_rejected,
        "final_determination_flagged": final_determination_flagged,
        "guardrails_exact": guardrails_exact,
        "no_external_writeback": no_external_writeback,
        "section_counts": {name: len(packet[name]) for name in section_names},
        "guardrails": dict(PACKET_GUARDRAILS),
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        out = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(out, "daily brief packet proof json")
        (out_dir / _PROOF_JSON).write_text(out + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "daily brief packet proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof


# --- V2 packet (Prompt 01: render_payload / governance_metadata split) ---------------------------

_WHY_BY_SECTION: dict[str, str] = {
    "review_required_items": "Flagged for mandatory review before any reliance.",
    "risk_watchlist": "Surfaced as a project risk signal.",
    "recent_changes": "Recent cross-source change relevant to the project.",
}
_FOCUS_BY_PRIORITY: dict[str, str] = {
    "high": "Triage first; confirm against the source system before acting.",
    "medium": "Review when time allows; not yet confirmed.",
    "low": "Awareness only.",
}


def _record_type_from_label(label: str | None, source_family: str) -> str | None:
    """Recover a safe record type from the family-scoped label (never the raw ref)."""
    if not label:
        return None
    _, _, tail = label.partition(":")
    return tail or None


def _build_render_item(v1_item: dict[str, Any]) -> dict[str, Any]:
    """Project one V1 packet item into the V2 renderable-item shape (metadata-only).

    Fields not yet sourced from the V1 retrieval path (project_name, record_id, status,
    responsible_party, due/start/finish dates) are emitted as ``None`` and flagged in
    ``detail_availability``. Carries no raw ref (hash only).
    """
    section = str(v1_item.get("section") or "")
    priority = str(v1_item.get("priority") or "low")
    record_type = _record_type_from_label(
        v1_item.get("source_ref_label"), str(v1_item.get("source_family") or "")
    )
    present = {
        "project_key": v1_item.get("project_key") is not None,
        "record_type": record_type is not None,
        "title": bool(v1_item.get("title_redacted")),
        "source_ref_hash": bool(v1_item.get("source_ref_hash")),
        "confidence_class": True,
        "review_tier": True,
        "freshness_label": True,
    }
    deferred = [
        "project_name",
        "record_id",
        "status",
        "responsible_party",
        "due_date",
        "start_date",
        "finish_date",
    ]
    return {
        "project_key": v1_item.get("project_key"),
        "project_name": None,
        "record_type": record_type,
        "record_id": None,
        "title": v1_item.get("title_redacted"),
        "status": None,
        "responsible_party": None,
        "due_date": None,
        "start_date": None,
        "finish_date": None,
        "source_family": v1_item.get("source_family"),
        "source_ref_hash": v1_item.get("source_ref_hash"),
        "confidence_class": v1_item.get("confidence_class"),
        "review_tier": v1_item.get("review_tier"),
        "review_required": v1_item.get("review_required"),
        "freshness_label": v1_item.get("freshness_label"),
        "stale_warning": v1_item.get("stale_warning"),
        "why_it_matters": _WHY_BY_SECTION.get(section, "Source-linked signal for this project."),
        "recommended_focus": _FOCUS_BY_PRIORITY.get(priority, _FOCUS_BY_PRIORITY["low"]),
        "detail_availability": {
            "present": sorted(k for k, v in present.items() if v),
            "deferred_to_prompt_02": deferred,
        },
    }


def _build_needs_attention(v1: dict[str, Any]) -> list[dict[str, Any]]:
    """Review-required items first, then high/medium-priority risk + recent-change items (deduped)."""
    out: list[dict[str, Any]] = []
    seen: set[str] = set()

    def _add(items: list[dict[str, Any]], *, only_priorities: set[str] | None = None) -> None:
        for it in items:
            if only_priorities is not None and it.get("priority") not in only_priorities:
                continue
            key = str(it.get("item_id") or "")
            if key in seen:
                continue
            seen.add(key)
            out.append(_build_render_item(it))

    _add(v1["review_required_items"])
    _add(v1["risk_watchlist"], only_priorities={"high", "medium"})
    _add(v1["recent_changes"], only_priorities={"high", "medium"})
    return out


def _build_project_signals(v1: dict[str, Any]) -> list[dict[str, Any]]:
    """Aggregate per-project signal objects from the V1 sections (descriptive enrichment lands in
    Prompt 02; this carries safe counts + families and flags deferred detail)."""
    section_names = [
        "recent_changes",
        "review_required_items",
        "aging_watchlist",
        "meeting_prep",
        "risk_watchlist",
    ]
    by_project: dict[str, dict[str, Any]] = {}
    for name in section_names:
        for it in v1[name]:
            pk = str(it.get("project_key") or "unknown")
            agg = by_project.setdefault(
                pk,
                {
                    "project_key": pk,
                    "project_name": None,
                    "item_count": 0,
                    "review_required_count": 0,
                    "max_review_tier": 0,
                    "families_present": set(),
                    "why_it_matters": "Aggregated project activity across source-linked signals.",
                    "detail_availability": {
                        "present": ["item_count", "review_required_count", "max_review_tier"],
                        "deferred_to_prompt_02": ["project_name", "descriptive_activity"],
                    },
                },
            )
            agg["item_count"] += 1
            if it.get("review_required"):
                agg["review_required_count"] += 1
            agg["max_review_tier"] = max(agg["max_review_tier"], int(it.get("review_tier") or 0))
            agg["families_present"].add(str(it.get("source_family") or ""))
    signals: list[dict[str, Any]] = []
    for agg in by_project.values():
        agg["families_present"] = sorted(f for f in agg["families_present"] if f)
        signals.append(agg)
    signals.sort(key=lambda s: (-s["max_review_tier"], -s["item_count"], s["project_key"]))
    return signals


def _build_focus_recommendations(needs_attention: list[dict[str, Any]]) -> list[dict[str, Any]]:
    """Derive advisory focus items from the top needs-attention items (never count-only strings)."""
    focus: list[dict[str, Any]] = []
    for it in needs_attention[:3]:
        focus.append(
            {
                "focus": it.get("title"),
                "project_key": it.get("project_key"),
                "why_it_matters": it.get("why_it_matters"),
                "recommended_focus": it.get("recommended_focus"),
                "source_family": it.get("source_family"),
                "review_tier": it.get("review_tier"),
                "detail_availability": {
                    "present": ["focus", "why_it_matters"],
                    "advisory_only": True,
                },
            }
        )
    return focus


def _build_data_gaps(
    v1: dict[str, Any], record_sections: dict[str, dict[str, Any]]
) -> list[dict[str, Any]]:
    """Explicit, honest gaps derived from the actual record sections (any that declare
    detail-unavailable) plus any V1 coverage warnings — never a stale claim about a populated section.
    """
    gaps: list[dict[str, Any]] = [
        {"section": name, "reason": sec.get("detail_gap_reason"), "status": "detail_unavailable"}
        for name, sec in record_sections.items()
        if sec.get("detail_available") is False and sec.get("detail_gap_reason")
    ]
    for warning in v1["source_coverage_summary"].get("coverage_warnings", []):
        gaps.append(
            {"section": "source_coverage", "reason": str(warning), "status": "coverage_warning"}
        )
    return gaps


def _count_detail_ok(section: dict[str, Any]) -> bool:
    """The count-vs-detail invariant: a count is only actionable if backed by listed records,
    otherwise the section must explicitly declare detail_available=False + a detail_gap_reason.

    Valid iff: count == 0 (nothing to report is not a bare count);
    OR records present AND detail_available AND count == len(records);
    OR a positive count with no records AND detail_available is False AND a non-empty
    detail_gap_reason (explicit detail-unavailable).
    """
    if not isinstance(section, dict):
        return False
    records = section.get("records")
    if not isinstance(records, list):
        return False
    count = section.get("count")
    if not isinstance(count, int):
        return False
    if count == 0 and not records:
        return True
    if records:
        return section.get("detail_available") is True and count == len(records)
    return section.get("detail_available") is False and bool(section.get("detail_gap_reason"))


def _project_v2_from_v1(
    v1: dict[str, Any], *, record_sections: dict[str, dict[str, Any]]
) -> dict[str, Any]:
    """Re-project an approved V1 packet into the V2 render_payload / governance_metadata split.

    V1-derived parts (needs_attention, focus, project_signals, data_gaps) are projected here; the
    record-bearing sections come from the read-only enrichment layer (``record_sections``). Invents
    no content; sections without a data source carry an explicit detail-unavailable reason.
    """
    coverage = v1["source_coverage_summary"]
    needs_attention = _build_needs_attention(v1)
    project_signals = _build_project_signals(v1)

    project_keys = sorted({str(s["project_key"]) for s in project_signals})
    render_payload: dict[str, Any] = {
        "brief_date": v1["brief_date"],
        "portfolio_scope": {
            "scope": v1["project_scope"],
            "project_count": coverage.get("project_count", 0),
            "projects": project_keys,
        },
        "yesterday": record_sections["yesterday"],
        "today_agenda": record_sections["today_agenda"],
        "next_7_days": record_sections["next_7_days"],
        "schedule": record_sections["schedule"],
        "rfis": record_sections["rfis"],
        "submittals": record_sections["submittals"],
        "punch": record_sections["punch"],
        "procurement": record_sections["procurement"],
        "needs_attention": needs_attention,
        "focus_recommendations": _build_focus_recommendations(needs_attention),
        "project_signals": project_signals,
        "email_activity": record_sections["email_activity"],
        "calendar_activity": record_sections["calendar_activity"],
        "data_gaps": _build_data_gaps(v1, record_sections),
    }

    governance_metadata: dict[str, Any] = {
        "packet_id": v1["packet_id"],
        "packet_version": PACKET_VERSION_V2,
        "generated_utc": v1["generated_utc"],
        "brief_date": v1["brief_date"],
        "mode": v1["mode"],
        "source_coverage_summary": coverage,
        "source_refs": v1["source_refs"],
        "guardrails": dict(PACKET_GUARDRAILS),
        "rendering_instructions": dict(RENDERING_INSTRUCTIONS_V2),
        "proof_metadata": {
            "contract_name": "daily_brief_handoff_packet_v2_contract",
            "packet_version": PACKET_VERSION_V2,
            "projected_from": v1["packet_version"],
        },
        "receipt_metadata": {"packet_receipt_emitted": False, "read_only": True},
        "status": v1["status"],
        "degradation_mode": v1["degradation_mode"],
    }

    return {"render_payload": render_payload, "governance_metadata": governance_metadata}


def build_daily_brief_packet_v2(
    *,
    brief_date: str,
    project_key: str | None = None,
    mode: str = "dry_run",
    db_path: str | None = None,
) -> dict[str, Any]:
    """Build a ``DailyBriefHandoffPacketV2`` (read-only, fail-closed).

    V2 splits user-facing ``render_payload`` from internal ``governance_metadata`` so governance
    never renders into the brief body. The V1 packet remains the canonical source-assembly path;
    the record-bearing sections come from the read-only enrichment layer. Every count-bearing
    section is held to the count-vs-detail rule (records or an explicit detail-unavailable reason).
    """
    from .enrichment import build_record_enrichment

    load_daily_brief_packet_v2_contract()
    v1 = build_daily_brief_packet(
        brief_date=brief_date, project_key=project_key, mode=mode, db_path=db_path
    )
    project_keys = sorted(
        {
            str(it.get("project_key"))
            for name in (
                "recent_changes",
                "review_required_items",
                "aging_watchlist",
                "meeting_prep",
                "risk_watchlist",
                "stale_or_low_confidence_warnings",
                "accepted_memory_context",
            )
            for it in v1[name]
            if it.get("project_key")
        }
    )
    record_sections = build_record_enrichment(
        brief_date=brief_date,
        project_key=project_key,
        db_path=db_path,
        project_keys=project_keys,
    )
    packet = _project_v2_from_v1(v1, record_sections=record_sections)
    _assert_no_raw(json.dumps(packet, default=str), "daily brief packet v2")
    return packet


def _render_v2_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 Addendum V2 — Daily Brief Packet V2 Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- packet_version: {proof['packet_version']}",
        f"- render_payload_present: {proof['render_payload_present']}",
        f"- governance_metadata_separated: {proof['governance_metadata_separated']}",
        f"- required_sections_present: {proof['required_sections_present']}",
        f"- source_refs_preserved: {proof['source_refs_preserved']}",
        f"- raw_shaped_rejected: {proof['raw_shaped_rejected']}",
        f"- review_stale_confidence_preserved: {proof['review_stale_confidence_preserved']}",
        f"- final_determination_rejected: {proof['final_determination_rejected']}",
        f"- metadata_only: {proof['metadata_only']}",
        f"- no_external_writeback: {proof['no_external_writeback']}",
        f"- count_detail_invariant_holds: {proof['count_detail_invariant_holds']}",
        f"- tampered_count_without_detail_rejected: {proof['tampered_count_without_detail_rejected']}",
        f"- detail_unavailable_explicit: {proof['detail_unavailable_explicit']}",
        f"- record_details_source_linked: {proof['record_details_source_linked']}",
        f"- no_raw_calendar_email_payload: {proof['no_raw_calendar_email_payload']}",
        f"- no_raw_payload_probe_rejected: {proof['no_raw_payload_probe_rejected']}",
        "",
        "## Record sections (count-vs-detail)",
        "",
    ]
    for name, info in proof["record_section_summary"].items():
        lines.append(
            f"- {name}: count={info['count']} detail_available={info['detail_available']}"
            f" reason={info['detail_gap_reason']}"
        )
    lines.append("")
    lines.append("## Render payload section counts")
    lines.append("")
    for name, count in proof["render_section_counts"].items():
        lines.append(f"- {name}: {count}")
    lines.append("")
    return "\n".join(lines)


def build_daily_brief_packet_v2_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof for the V2 packet: render_payload exists, governance_metadata is separated
    (and no governance keys leak into the render body), required sections exist, source refs are
    preserved, raw-shaped values are rejected, review/stale/confidence flags are preserved, and
    final-determination language is rejected. Performs no external writeback."""
    import sqlite3
    import tempfile

    contract = load_daily_brief_packet_v2_contract()
    render_sections = list(contract.get("render_payload_sections", []))
    render_item_fields = list(contract.get("render_item_fields", []))
    governance_fields = list(contract.get("governance_metadata_fields", []))
    forbidden_in_render = list(contract.get("forbidden_in_render_payload", []))

    with tempfile.TemporaryDirectory() as tmp:
        seeded = f"{tmp}/seeded.sqlite3"
        _seed_v2_enrichment_db(seeded)
        packet = build_daily_brief_packet_v2(
            brief_date="2026-06-02", project_key="P1", db_path=seeded
        )
        conn = sqlite3.connect(seeded)
        try:
            brief_run_rows = conn.execute("SELECT COUNT(*) FROM daily_brief_runs").fetchone()[0]
        finally:
            conn.close()

    render = packet.get("render_payload", {})
    governance = packet.get("governance_metadata", {})
    needs_attention = render.get("needs_attention", [])

    render_payload_present = isinstance(render, dict) and bool(render)
    governance_metadata_separated = (
        isinstance(governance, dict)
        and all(f in governance for f in governance_fields)
        and not any(k in render for k in forbidden_in_render)
    )
    required_sections_present = bool(render_sections) and all(s in render for s in render_sections)
    item_fields_present = bool(render_item_fields) and all(
        all(f in item for f in render_item_fields) for item in needs_attention
    )

    source_refs_preserved = (
        bool(governance.get("source_refs"))
        and isinstance(governance.get("source_coverage_summary"), dict)
        and bool(needs_attention)
        and all(i.get("source_family") and i.get("source_ref_hash") for i in needs_attention)
    )

    blob = json.dumps(packet, default=str)
    try:
        _assert_no_raw(blob, "daily brief packet v2 proof")
        metadata_only = True
    except ValueError:
        metadata_only = False

    try:
        _assert_no_raw(json.dumps({"x": "Bearer abc123XYZ"}), "raw probe")
        raw_shaped_rejected = False
    except ValueError:
        raw_shaped_rejected = True

    review_stale_confidence_preserved = (
        bool(needs_attention)
        and all(
            ("review_tier" in i and "confidence_class" in i and "freshness_label" in i)
            for i in needs_attention
        )
        and any(i.get("review_required") is True for i in needs_attention)
        and any(i.get("stale_warning") for i in needs_attention)
    )

    # --- Prompt 02: count-vs-detail invariant + record-level enrichment proofs ---
    record_sections = {name: render.get(name, {}) for name in RECORD_SECTION_NAMES}
    all_records = [r for sec in record_sections.values() for r in sec.get("records", [])]

    count_detail_invariant_holds = bool(record_sections) and all(
        _count_detail_ok(sec) for sec in record_sections.values()
    )
    # Non-vacuous: a positive count with no records and no explicit gap reason must be rejected.
    tampered_section = {
        "count": 3,
        "records": [],
        "detail_available": True,
        "detail_gap_reason": None,
        "source_family": "x",
        "why_it_matters": "y",
    }
    tampered_count_without_detail_rejected = _count_detail_ok(tampered_section) is False
    # At least one domain that has no dedicated reader is explicitly detail-unavailable (not a count).
    detail_unavailable_explicit = all(
        _count_detail_ok(render.get(name, {}))
        and render.get(name, {}).get("detail_available") is False
        and bool(render.get(name, {}).get("detail_gap_reason"))
        for name in ("rfis", "submittals", "punch", "procurement")
    )
    record_details_source_linked = bool(all_records) and all(
        r.get("source_family") and r.get("source_ref_hash") for r in all_records
    )
    # No raw calendar/email/source payload: whole-packet no-raw gate + non-vacuous join-URL probe.
    no_raw_calendar_email_payload = metadata_only and "web_link" not in blob
    try:
        _assert_no_raw('{"join":"https://teams.microsoft.com/meet/x"}', "raw calendar probe")
        no_raw_payload_probe_rejected = False
    except ValueError:
        no_raw_payload_probe_rejected = True

    planted_flagged = _reject_final_determination(
        "Approve payment of the claim as a final determination"
    )
    record_text_fields = [
        str(r.get(k) or "")
        for r in all_records
        for k in (
            "title",
            "meeting_title_redacted",
            "topic_redacted",
            "why_it_matters",
            "recommended_focus",
        )
    ] + [str(sec.get("why_it_matters") or "") for sec in record_sections.values()]
    render_text_fields = (
        [str(i.get("title") or "") for i in needs_attention]
        + [
            str(i.get(k) or "")
            for i in needs_attention
            for k in ("why_it_matters", "recommended_focus")
        ]
        + [str(g.get("reason") or "") for g in render.get("data_gaps", [])]
        + record_text_fields
    )
    real_unflagged = not any(_reject_final_determination(t) for t in render_text_fields)
    final_determination_rejected = planted_flagged and real_unflagged

    no_external_writeback = brief_run_rows == 0

    proof_passed = (
        render_payload_present
        and governance_metadata_separated
        and required_sections_present
        and item_fields_present
        and source_refs_preserved
        and metadata_only
        and raw_shaped_rejected
        and review_stale_confidence_preserved
        and final_determination_rejected
        and no_external_writeback
        and count_detail_invariant_holds
        and tampered_count_without_detail_rejected
        and detail_unavailable_explicit
        and record_details_source_linked
        and no_raw_calendar_email_payload
        and no_raw_payload_probe_rejected
    )

    proof: dict[str, Any] = {
        "proof": "phase_09_addendum_daily_brief_packet_v2",
        "command": "second-brain daily-brief packet-v2-proof",
        "phase": "09-addendum-v2",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "packet_version": PACKET_VERSION_V2,
        "packet_id": governance.get("packet_id"),
        "render_payload_present": render_payload_present,
        "governance_metadata_separated": governance_metadata_separated,
        "required_sections_present": required_sections_present,
        "item_fields_present": item_fields_present,
        "source_refs_preserved": source_refs_preserved,
        "metadata_only": metadata_only,
        "raw_shaped_rejected": raw_shaped_rejected,
        "review_stale_confidence_preserved": review_stale_confidence_preserved,
        "final_determination_rejected": final_determination_rejected,
        "no_external_writeback": no_external_writeback,
        "count_detail_invariant_holds": count_detail_invariant_holds,
        "tampered_count_without_detail_rejected": tampered_count_without_detail_rejected,
        "detail_unavailable_explicit": detail_unavailable_explicit,
        "record_details_source_linked": record_details_source_linked,
        "no_raw_calendar_email_payload": no_raw_calendar_email_payload,
        "no_raw_payload_probe_rejected": no_raw_payload_probe_rejected,
        "record_section_summary": {
            name: {
                "count": render.get(name, {}).get("count"),
                "detail_available": render.get(name, {}).get("detail_available"),
                "detail_gap_reason": render.get(name, {}).get("detail_gap_reason"),
            }
            for name in RECORD_SECTION_NAMES
        },
        "render_section_counts": {
            name: (
                render[name].get("count")
                if isinstance(render.get(name), dict)
                else (len(render[name]) if isinstance(render.get(name), list) else 1)
            )
            for name in render_sections
            if name in render
        },
        "guardrails": dict(PACKET_GUARDRAILS),
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR_V2)
        out_dir.mkdir(parents=True, exist_ok=True)
        out = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(out, "daily brief packet v2 proof json")
        (out_dir / _V2_PROOF_JSON).write_text(out + "\n", encoding="utf-8")
        markdown = _render_v2_proof_md(proof)
        _assert_no_raw(markdown, "daily brief packet v2 proof markdown")
        (out_dir / _V2_PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _V2_PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _V2_PROOF_MD)

    return proof
