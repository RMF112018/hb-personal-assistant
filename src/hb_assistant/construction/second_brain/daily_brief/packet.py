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
CLI: hb-assistant second-brain daily-brief packet --date YYYY-MM-DD --json
     hb-assistant second-brain daily-brief packet-proof --json
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
