"""Phase 09 Addendum — rendered daily-brief quality + guardrail validation (review-only).

A deterministic, local validation surface for Claude-*rendered* daily-brief markdown that an operator
copies/exports back into the repo for review. Given a rendered brief and its source
``DailyBriefHandoffPacketV1``, it verifies the rendered text preserved the required sections/warnings
and did not overclaim: no final determinations, no raw-shaped values, no fabricated source families, no
source-system update claims, and no omission of packet-level coverage limitations. Conditional checks
only fail when they apply to the packet (e.g. a review-required warning is required only when the packet
carries review-required items).

IMPORTANT: this is for output-quality review only. Claude-rendered text is never imported into trusted
retrieval / memory / source-of-truth surfaces.

Public entry points:
  validate_rendered_brief(packet, rendered_md) -> dict
  build_daily_brief_rendered_quality_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain daily-brief rendered-proof --packet <path> --rendered <path> --json
"""

from __future__ import annotations

import json
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..financial_review_routing import _assert_no_raw
from ..retrieval import ALLOWLISTED_SOURCE_FAMILIES

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-daily-brief-mcp-handoff"
_PROOF_JSON = "daily-brief-rendered-quality-proof.json"
_PROOF_MD = "daily-brief-rendered-quality-proof.md"
_FIXTURE_MD = "daily-brief-rendered-quality-fixture.md"

# The 7 required executive-brief section headers (lower-cased for matching).
_SECTION_HEADERS: tuple[str, ...] = (
    "what matters today",
    "review-required items",
    "aging / stale items",
    "meeting prep",
    "risk watchlist",
    "source coverage and confidence notes",
    "suggested follow-up questions",
)

# Affirmative final-determination language. Deliberately NOT the packet's
# `_reject_final_determination` lexicon: a faithful brief's Advisory Notice legitimately says
# "makes no ... determinations", so only affirmative determination phrasing is flagged here.
_DETERMINATION_PHRASES: tuple[str, ...] = (
    "approve payment",
    "approved for payment",
    "we approve",
    "we will pay",
    "payment is approved",
    "claim is approved",
    "entitlement is granted",
    "schedule is certified",
    "legally binding",
    "final decision:",
    "i hereby approve",
)

# Phrases that claim a source system was changed (Graph / Procore / email / calendar / writeback).
_SOURCE_UPDATE_PHRASES: tuple[str, ...] = (
    "updated procore",
    "update procore",
    "updated in procore",
    "pushed to procore",
    "synced to procore",
    "wrote to procore",
    "updated graph",
    "wrote to graph",
    "pushed to graph",
    "synced to graph",
    "sent the email",
    "email was sent",
    "sent an email",
    "updated the calendar",
    "calendar was updated",
    "modified the calendar",
    "created a calendar event",
    "wrote back to",
    "synced to the source",
    "updated the source system",
)

_LIMITATION_KEYWORDS: tuple[str, ...] = (
    "limit",
    "no data",
    "weak",
    "insufficient",
    "partial",
    "not available",
    "coverage gap",
    "empty",
    "missing",
    "unknown",
)

# --- Safe fixture (passes every check against the seeded sample packet) ---------------------------

_FIXTURE_DATE = "2026-06-02"
_STALE_LINE = (
    "One aging RFI is flagged stale and low-confidence; confirm the current status before acting."
)
_CONFIDENCE_LINE = "Confidence is mixed; some items are low-confidence and are called out above."
_COVERAGE_LIMITATION_LINE = (
    "Note: source coverage is partial — some source families have no data available in today's "
    "packet, so treat gaps as unknown rather than resolved."
)
_ADVISORY_HEADER = "## Advisory Notice"

_SAMPLE_RENDERED_BRIEF = f"""# Daily Construction Executive Brief — {_FIXTURE_DATE}

## What Matters Today

- Project P1 has open exposure that warrants attention; treat the items below as advisory signals only.
- One item requires review before any action is taken.

## Review-Required Items

- There is one review-required item in today's packet. It is flagged review-required and must be
  confirmed against the source system before acting.

## Aging / Stale Items

- {_STALE_LINE}

## Meeting Prep

- No meeting prep items are present in today's packet.

## Risk Watchlist

- One schedule-slip risk signal is noted for project P1 as an advisory indicator only.

## Source Coverage and Confidence Notes

- {_COVERAGE_LIMITATION_LINE}
- {_CONFIDENCE_LINE}

## Suggested Follow-Up Questions

- Which review-required item should be prioritized first?
- Which aging item is closest to its threshold?

{_ADVISORY_HEADER}

This brief is advisory and source-linked. It was rendered from the approved metadata-only packet only
and makes no legal, financial, safety, claim, payment, entitlement, schedule-certification, or
contractual determinations. This brief made no changes to any source system. Confirm all flagged items
against the source systems before acting.
"""


class RenderedBriefQualityError(RuntimeError):
    """Raised when the rendered-brief quality proof cannot run (fail-closed)."""


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


def _is_weak_coverage(packet: dict[str, Any]) -> bool:
    cov = packet.get("source_coverage_summary", {}) or {}
    if cov.get("coverage_warnings"):
        return True
    if str(cov.get("degradation_mode") or "") in ("blocked", "degraded", "partial"):
        return True
    return str(cov.get("context_quality_class") or "") in ("insufficient", "partial")


def validate_rendered_brief(packet: dict[str, Any], rendered_md: str) -> dict[str, Any]:
    """Validate a rendered brief against its source packet. Pure; returns per-check results."""
    low = rendered_md.lower()
    # Body with the section headers stripped, so a header word (e.g. "Stale") in the section title is
    # not mistaken for an actual preserved warning.
    body = low
    for header in _SECTION_HEADERS:
        body = body.replace(header, " ")

    cov = packet.get("source_coverage_summary", {}) or {}
    families_present = set(cov.get("families_present", []) or [])
    has_review_required = bool(packet.get("review_required_items"))
    has_stale = bool(packet.get("stale_or_low_confidence_warnings"))
    weak = _is_weak_coverage(packet)

    try:
        _assert_no_raw(rendered_md, "rendered brief")
        no_raw = True
    except ValueError:
        no_raw = False

    unsupported_families = [
        fam for fam in ALLOWLISTED_SOURCE_FAMILIES if fam in low and fam not in families_present
    ]
    source_update_hits = [p for p in _SOURCE_UPDATE_PHRASES if p in low]
    determination_hits = [p for p in _DETERMINATION_PHRASES if p in low]

    checks: dict[str, bool] = {
        "sections_present": all(h in low for h in _SECTION_HEADERS),
        "advisory_notice_present": "advisory notice" in low,
        "source_coverage_section_present": "source coverage" in low,
        "review_required_warnings_present": (not has_review_required)
        or ("review-required" in body or "review required" in body),
        "stale_low_confidence_warnings_present": (not has_stale)
        or ("stale" in body or "low-confidence" in body or "low confidence" in body),
        "no_final_determinations": not determination_hits,
        "no_raw_shaped_values": no_raw,
        "no_unsupported_source_families": not unsupported_families,
        "no_source_system_update_claims": not source_update_hits,
        "coverage_limitations_not_omitted": (not weak)
        or any(k in low for k in _LIMITATION_KEYWORDS),
    }

    return {
        "passed": all(checks.values()),
        "checks": checks,
        "packet_weak_coverage": weak,
        "packet_has_review_required": has_review_required,
        "packet_has_stale": has_stale,
        "unsupported_families": unsupported_families,
        "source_update_hits": source_update_hits,
        "determination_hits": determination_hits,
    }


# --- Proof ---------------------------------------------------------------------------------------


def _sample_packet() -> dict[str, Any]:
    """Build a realistic sample packet over controlled, metadata-only seed inputs (temp DB)."""
    from .packet import _seed_proof_db, build_daily_brief_packet

    tmp = tempfile.mkdtemp()
    db = f"{tmp}/seeded.sqlite3"
    _seed_proof_db(db)
    return build_daily_brief_packet(brief_date=_FIXTURE_DATE, project_key="P1", db_path=db)


def _tampered_variants() -> dict[str, tuple[str, str]]:
    """name -> (tampered rendered text, the check expected to fail)."""
    safe = _SAMPLE_RENDERED_BRIEF
    return {
        "missing_advisory_notice": (
            safe.replace(_ADVISORY_HEADER, "## Closing Notes"),
            "advisory_notice_present",
        ),
        "missing_stale_warning": (
            safe.replace(_STALE_LINE, "All aging items are current.").replace(
                _CONFIDENCE_LINE, "Confidence is adequate across the available items."
            ),
            "stale_low_confidence_warnings_present",
        ),
        "final_determination_language": (
            safe + "\n\nDecision: we approve payment of the pending claim.\n",
            "no_final_determinations",
        ),
        "raw_shaped_value": (
            safe + "\n\nFull export available at https://example.com/raw.\n",
            "no_raw_shaped_values",
        ),
        "source_system_update_claim": (
            safe + "\n\nI updated Procore and the email was sent to the team.\n",
            "no_source_system_update_claims",
        ),
        "coverage_omitted_when_weak": (
            safe.replace(_COVERAGE_LIMITATION_LINE, "Source coverage is complete and consistent."),
            "coverage_limitations_not_omitted",
        ),
    }


def _render_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 — Rendered Daily Brief Quality Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- safe_fixture_passed: {proof['safe_fixture_passed']}",
        f"- packet_weak_coverage: {proof['packet_weak_coverage']}",
        f"- packet_has_review_required: {proof['packet_has_review_required']}",
        f"- packet_has_stale: {proof['packet_has_stale']}",
        "",
        "## Tampered variants (each must fail its expected check)",
        "",
    ]
    for name, rep in proof["tampered_variants"].items():
        lines.append(
            f"- {name}: expected_failed_check={rep['expected_failed_check']} "
            f"check_failed={rep['expected_check_failed']} overall_passed={rep['overall_passed']}"
        )
    lines.append("")
    return "\n".join(lines)


def build_daily_brief_rendered_quality_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed proof: the safe fixture passes every check, and each tampered variant fails exactly
    its expected check (read-only; uses controlled seed inputs)."""
    packet = _sample_packet()
    safe_result = validate_rendered_brief(packet, _SAMPLE_RENDERED_BRIEF)

    variant_reports: dict[str, Any] = {}
    all_variants_fail_expected = True
    for name, (text, expected_check) in _tampered_variants().items():
        result = validate_rendered_brief(packet, text)
        check_failed = result["checks"].get(expected_check) is False
        overall_failed = result["passed"] is False
        ok = check_failed and overall_failed
        all_variants_fail_expected = all_variants_fail_expected and ok
        variant_reports[name] = {
            "expected_failed_check": expected_check,
            "expected_check_failed": check_failed,
            "overall_passed": result["passed"],
        }

    packet_weak = bool(safe_result["packet_weak_coverage"])
    proof_passed = bool(
        safe_result["passed"]
        and all_variants_fail_expected
        and packet_weak
        and safe_result["packet_has_review_required"]
        and safe_result["packet_has_stale"]
    )

    proof: dict[str, Any] = {
        "proof": "phase_09_daily_brief_rendered_quality",
        "command": "second-brain daily-brief rendered-proof",
        "phase": "09",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "safe_fixture_passed": safe_result["passed"],
        "safe_fixture_checks": safe_result["checks"],
        "packet_weak_coverage": packet_weak,
        "packet_has_review_required": safe_result["packet_has_review_required"],
        "packet_has_stale": safe_result["packet_has_stale"],
        "tampered_variants": variant_reports,
        "check_count": len(safe_result["checks"]),
        "metadata_only": True,
        "review_only": True,
        "guardrails": {
            "advisory_only": True,
            "read_only": True,
            "metadata_only": True,
            "no_raw": True,
            "no_writeback": True,
            "no_final_determination": True,
            "rendered_text_not_imported_to_trusted_surfaces": True,
            "fail_closed": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        _assert_no_raw(_SAMPLE_RENDERED_BRIEF, "rendered quality fixture")
        (out_dir / _FIXTURE_MD).write_text(_SAMPLE_RENDERED_BRIEF, encoding="utf-8")
        serialized = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(serialized, "rendered quality proof json")
        (out_dir / _PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        markdown = _render_proof_md(proof)
        _assert_no_raw(markdown, "rendered quality proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _PROOF_MD)

    return proof
