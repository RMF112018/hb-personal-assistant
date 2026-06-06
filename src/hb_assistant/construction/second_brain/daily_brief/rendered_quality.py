"""Phase 09 Addendum V2 — rendered daily-brief quality + guardrail validation (review-only).

A deterministic, local validation surface for Claude-*rendered* daily-brief markdown (Daily Brief V2)
that an operator copies/exports back into the repo for review. The V2 executive brief is concise and
free of internal proof/governance commentary, so validation is **structural + forbidden-content**:

- it must carry the five executive sections (Yesterday / Today / Next 7 Days / Needs Attention /
  Focus) and a single one-line advisory footer;
- it must NOT render any internal proof/governance content (packet provenance/hash table, guardrail
  matrix, source-coverage wall, source-family lists / relationship counts, proof paths, generated
  utc, mode/dry-run commentary, suggested follow-up questions, raw JSON), must not repeat the
  advisory disclaimer, must not present a count-only schedule table without activity rows or a
  "detail unavailable" notice, must make no final determination, and must claim no source-system
  writeback.

IMPORTANT: this is for output-quality review only. Claude-rendered text is never imported into trusted
retrieval / memory / source-of-truth surfaces.

Public entry points:
  validate_rendered_brief(packet, rendered_md) -> dict
  build_daily_brief_rendered_quality_proof(*, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain daily-brief rendered-proof --packet <path> --rendered <path> --json
"""

from __future__ import annotations

import json
import re
import subprocess
import tempfile
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from ..financial_review_routing import _assert_no_raw

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-daily-brief-mcp-handoff"
_PROOF_JSON = "daily-brief-rendered-quality-proof.json"
_PROOF_MD = "daily-brief-rendered-quality-proof.md"
_FIXTURE_MD = "daily-brief-rendered-quality-fixture.md"

# The five required executive-brief sections + title (lower-cased for matching).
_REQUIRED_SECTIONS: tuple[str, ...] = (
    "# daily brief",
    "## yesterday",
    "## today",
    "## next 7 days",
    "## needs attention",
    "## focus",
)

# Affirmative final-determination language (only affirmative phrasing is flagged).
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

# Internal proof/governance content that must NEVER appear in the executive brief body.
_PROVENANCE_MARKERS: tuple[str, ...] = (
    "packet_id",
    "source_ref_hash",
    "source ref hash",
    "packet hash",
    "correlation id",
    "provenance",
)
_COVERAGE_MARKERS: tuple[str, ...] = (
    "## source coverage",
    "source_coverage_summary",
    "families_present",
    "coverage_warnings",
    "source coverage and confidence",
)
_SOURCE_FAMILY_MARKERS: tuple[str, ...] = (
    "source_family",
    "cross_source_relationships",
    "review_controlled_correspondence_context",
    "procore_action_signals",
    "calendar_event_index",
    "accepted_long_term_memory",
    "meeting_prep_brief_sections",
)
_PROOF_PATH_MARKERS: tuple[str, ...] = (
    "docs/evidence",
    "proof_path",
    "proof_md_path",
    "-proof.json",
)
_GUARDRAIL_TOKENS: tuple[str, ...] = (
    "advisory_only",
    "no_writeback",
    "metadata_only",
    "claude_rendering_only",
    "no_final_determinations",
    "source_linked",
    "no_raw",
)


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


def _section_text(low: str, header: str) -> str:
    """Return a section's text from its ``## header`` to the next ``## `` (lower-cased input)."""
    idx = low.find(header)
    if idx == -1:
        return ""
    rest = low[idx + len(header) :]
    nxt = rest.find("\n## ")
    return rest if nxt == -1 else rest[:nxt]


def _has_guardrail_matrix(low: str) -> bool:
    if "| guardrail" in low or "guardrail matrix" in low:
        return True
    return sum(1 for t in _GUARDRAIL_TOKENS if t in low) >= 2


def _has_json_blob(md: str) -> bool:
    if "```json" in md.lower():
        return True
    return bool(re.search(r'[\{\[]\s*"[\w_]+"\s*:', md))


def _focus_item_count(low: str) -> int:
    focus = _section_text(low, "## focus")
    return len(re.findall(r"(?m)^\s*\d+\.\s", focus))


def _schedule_detail_or_unavailable(low: str) -> bool:
    """A schedule section, if present, must carry table rows or a 'detail unavailable' notice —
    never a count-only schedule table."""
    sched = _section_text(low, "## schedule")
    if not sched.strip():
        return True
    return ("|" in sched) or ("detail unavailable" in sched)


def validate_rendered_brief(packet: dict[str, Any], rendered_md: str) -> dict[str, Any]:
    """Validate a rendered V2 brief. Structural + forbidden-content; ``packet`` is accepted for
    signature stability but the V2 brief is validated on its own (governance is not rendered)."""
    low = rendered_md.lower()

    try:
        _assert_no_raw(rendered_md, "rendered brief")
        no_raw = True
    except ValueError:
        no_raw = False

    determination_hits = [p for p in _DETERMINATION_PHRASES if p in low]
    source_update_hits = [p for p in _SOURCE_UPDATE_PHRASES if p in low]

    checks: dict[str, bool] = {
        "required_sections_present": all(h in low for h in _REQUIRED_SECTIONS),
        "single_advisory_disclaimer": low.count("advisory") <= 1,
        "focus_items_within_limit": _focus_item_count(low) <= 5,
        "no_provenance_table": not any(m in low for m in _PROVENANCE_MARKERS),
        "no_guardrail_matrix": not _has_guardrail_matrix(low),
        "no_source_coverage_section": not any(m in low for m in _COVERAGE_MARKERS),
        "no_source_family_lists": not any(m in low for m in _SOURCE_FAMILY_MARKERS),
        "no_proof_paths": not any(m in low for m in _PROOF_PATH_MARKERS),
        "no_generated_utc": "generated_utc" not in low and "generated utc" not in low,
        "no_mode_dry_run": "dry_run" not in low and "dry-run" not in low,
        "no_follow_up_questions": "follow-up question" not in low
        and "suggested follow-up" not in low,
        "no_json_blobs": not _has_json_blob(rendered_md),
        "schedule_detail_or_unavailable": _schedule_detail_or_unavailable(low),
        "no_final_determinations": not determination_hits,
        "no_source_system_update_claims": not source_update_hits,
        "no_raw_shaped_values": no_raw,
    }

    return {
        "passed": all(checks.values()),
        "checks": checks,
        "focus_item_count": _focus_item_count(low),
        "advisory_disclaimer_count": low.count("advisory"),
        "determination_hits": determination_hits,
        "source_update_hits": source_update_hits,
    }


# --- Safe fixture (passes every check) ------------------------------------------------------------

_FIXTURE_DATE = "2026-06-02"

_SAMPLE_RENDERED_BRIEF = f"""# Daily Brief — {_FIXTURE_DATE}

## Yesterday
- Owner review meeting was held for Tropical; coordination items were discussed.
- Several email threads on Tropical saw activity, including submittal coordination.

## Today
| Time | Meeting | Project | Prep / Related Items |
|---|---|---|---|
| 09:00–10:00 | Project coordination sync | Tropical | Review open coordination items before the call |

## Next 7 Days
| Date | Project | Item | Type | Responsible | Why It Matters |
|---|---|---|---|---|---|
| 2026-06-05 | Tropical | RFI response | rfis | Detail unavailable | Response is due this week; confirm status |

## Needs Attention
| Priority | Project | Item | Reason | Recommended Focus |
|---|---|---|---|---|
| High | Tropical | Activity at or below zero float | Critical-path schedule signal | Confirm float against the schedule of record |
| Medium | Tropical | Open RFIs | Detail unavailable for individual RFIs | Review the RFI log directly |

## Focus
1. Confirm the zero-float activity on Tropical before its deadline.
2. Prepare for today's coordination sync.
3. Check the RFI due on 2026-06-05.

---
_Source-linked advisory brief. Verify in source systems before final action._
"""


def _sample_packet() -> dict[str, Any]:
    """Build a realistic sample packet over controlled, metadata-only seed inputs (temp DB).

    Retained for callers that pass a packet to ``validate_rendered_brief`` (e.g. the output-receipt
    proof). The V2 validator does not depend on packet shape.
    """
    from .packet import _seed_proof_db, build_daily_brief_packet

    tmp = tempfile.mkdtemp()
    db = f"{tmp}/seeded.sqlite3"
    _seed_proof_db(db)
    return build_daily_brief_packet(brief_date=_FIXTURE_DATE, project_key="P1", db_path=db)


def _tampered_variants() -> dict[str, tuple[str, str]]:
    """name -> (tampered rendered text, the check expected to fail)."""
    safe = _SAMPLE_RENDERED_BRIEF
    return {
        "packet_provenance_table": (
            safe
            + "\n\n## Provenance\n\n| packet_id | source_ref_hash |\n|---|---|\n| dbp_x | a1b2 |\n",
            "no_provenance_table",
        ),
        "guardrail_matrix": (
            safe
            + "\n\n## Guardrails\n\n| guardrail | value |\n|---|---|\n"
            + "| advisory_only | true |\n| no_writeback | true |\n| metadata_only | true |\n",
            "no_guardrail_matrix",
        ),
        "source_coverage_wall": (
            safe
            + "\n\n## Source Coverage and Confidence Notes\n\nsource_coverage_summary: "
            + "families_present across 6 families; coverage_warnings none.\n",
            "no_source_coverage_section",
        ),
        "multiple_disclaimers": (
            safe + "\n\n_This is an advisory brief and makes no determinations._\n",
            "single_advisory_disclaimer",
        ),
        "count_only_schedule": (
            safe + "\n\n## Schedule\n\n257 critical-path activities are flagged this period.\n",
            "schedule_detail_or_unavailable",
        ),
        "json_blob": (
            safe + '\n\n```json\n{"packet_version": "DailyBriefHandoffPacketV2"}\n```\n',
            "no_json_blobs",
        ),
        "final_determination_language": (
            safe + "\n\nDecision: we approve payment of the pending claim.\n",
            "no_final_determinations",
        ),
        "source_system_update_claim": (
            safe + "\n\nI updated Procore and the email was sent to the team.\n",
            "no_source_system_update_claims",
        ),
    }


def _render_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 Addendum V2 — Rendered Daily Brief Quality Proof",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- safe_fixture_passed: {proof['safe_fixture_passed']}",
        f"- check_count: {proof['check_count']}",
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
    its expected forbidden-content check (read-only; the brief is validated on its own)."""
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

    proof_passed = bool(safe_result["passed"] and all_variants_fail_expected)

    proof: dict[str, Any] = {
        "proof": "phase_09_addendum_daily_brief_rendered_quality",
        "command": "second-brain daily-brief rendered-proof",
        "phase": "09-addendum-v2",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "safe_fixture_passed": safe_result["passed"],
        "safe_fixture_checks": safe_result["checks"],
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
