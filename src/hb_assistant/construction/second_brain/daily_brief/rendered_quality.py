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

# Configured maximum executive-brief length (chars). An executive brief must stay concise.
_MAX_BRIEF_CHARS = 8000

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

# "Nothing to report" phrases per content section (lower-cased).
_AGENDA_NONE_PHRASES: tuple[str, ...] = (
    "no calendar item",
    "no meeting",
    "no agenda",
    "nothing scheduled",
    "none",
)
_DEADLINE_NONE_PHRASES: tuple[str, ...] = (
    "no deadline",
    "nothing due",
    "none",
)
_FOCUS_NONE_PHRASES: tuple[str, ...] = (
    "no focus item",
    "no specific focus",
    "none",
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


def _section_has_rows_or_none(low: str, header: str, none_phrases: tuple[str, ...]) -> bool:
    """A required content section must be non-empty and either carry table rows / bullet content,
    or explicitly state there is nothing to report (one of ``none_phrases``)."""
    sec = _section_text(low, header)
    if not sec.strip():
        return False
    if "|" in sec:
        return True
    if any(p in sec for p in none_phrases):
        return True
    return bool(re.search(r"(?m)^\s*[-*]\s+\S", sec))


# Domains whose counts must be backed by listed rows or an explicit detail-unavailable notice.
_ATTENTION_COUNT_RE = re.compile(
    r"(?:\b\d+\s+(?:rfis?|submittals?|punch|procurement|deadlines?)\b"
    r"|\b(?:rfis?|submittals?|punch|procurement|deadlines?)\s*[:=]\s*\d+)"
)


def _attention_counts_backed_or_unavailable(low: str) -> bool:
    """RFI/submittal/punch/procurement/deadline counts must be backed by rows or a 'detail
    unavailable' notice — never a bare count-only line passed off as actionable detail."""
    for chunk in ("\n" + low).split("\n## "):
        for line in chunk.splitlines():
            if "|" in line:
                continue  # table rows are backed detail
            if _ATTENTION_COUNT_RE.search(line) and "detail unavailable" not in chunk:
                return False
    return True


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

    focus_count = _focus_item_count(low)
    focus_section = _section_text(low, "## focus")

    checks: dict[str, bool] = {
        "required_sections_present": all(h in low for h in _REQUIRED_SECTIONS),
        "brief_length_within_max": len(rendered_md) <= _MAX_BRIEF_CHARS,
        "single_advisory_disclaimer": low.count("advisory") <= 1,
        "focus_items_within_limit": focus_count <= 5,
        "focus_count_in_range_or_none": (3 <= focus_count <= 5)
        or any(p in focus_section for p in _FOCUS_NONE_PHRASES),
        "agenda_today_or_none": _section_has_rows_or_none(low, "## today", _AGENDA_NONE_PHRASES),
        "next_7_days_deadlines_or_none": _section_has_rows_or_none(
            low, "## next 7 days", _DEADLINE_NONE_PHRASES
        ),
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
        "attention_counts_backed_or_unavailable": _attention_counts_backed_or_unavailable(low),
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


# --- Prompt 05: golden fixtures + V2 executive-quality proof ---------------------------------------

_V2_QUALITY_EVIDENCE_DIR = (
    "docs/evidence/construction-intelligence-phase-09-addendum-daily-brief-v2"
)
_V2_QUALITY_PROOF_JSON = "daily-brief-v2-quality-proof.json"
_V2_QUALITY_PROOF_MD = "daily-brief-v2-quality-proof.md"
_GOLDEN_FULL_DETAIL_MD = "daily-brief-v2-golden-full-detail.md"
_GOLDEN_DETAIL_UNAVAILABLE_MD = "daily-brief-v2-golden-detail-unavailable.md"
_GOLDEN_REJECTED_INTERNAL_MD = "daily-brief-v2-golden-rejected-internal.md"

_GOLDEN_DATE = "2026-06-06"

# Fixture A — full record-level detail. Concise, useful, record-level tables, no internal commentary.
_GOLDEN_FULL_DETAIL = f"""# Daily Brief — {_GOLDEN_DATE}

## Yesterday
- Owner–architect coordination meeting was held for Tropical; long-lead procurement was discussed.
- Three email threads on Tropical saw activity, including submittal turnaround follow-up.

## Today
| Time | Meeting | Project | Prep / Related Items |
|---|---|---|---|
| 09:00–09:30 | Schedule stand-up | Tropical | Confirm the zero-float activity status |
| 13:00–14:00 | Procurement review | Tropical | Bring the long-lead equipment list |

## Next 7 Days
| Date | Project | Item | Type | Responsible | Why It Matters |
|---|---|---|---|---|---|
| 2026-06-09 | Tropical | Curtain wall RFI response | rfis | Detail unavailable | Response is due; fabrication is waiting |
| 2026-06-11 | Tropical | Switchgear submittal return | submittals | Detail unavailable | Long-lead procurement gate |

## Needs Attention
| Priority | Project | Item | Reason | Recommended Focus |
|---|---|---|---|---|
| High | Tropical | Activity at or below zero float | Critical-path schedule signal | Confirm float against the schedule of record |
| High | Tropical | Curtain wall RFI open | Deadline within the week | Expedite the response with the design team |
| Medium | Tropical | Switchgear submittal pending | Procurement dependency | Confirm the reviewer turnaround |

## Focus
1. Confirm the zero-float activity on Tropical before its deadline.
2. Expedite the curtain wall RFI response due 2026-06-09.
3. Track the switchgear submittal so long-lead procurement is not delayed.
4. Prepare for today's procurement review.

---
_Source-linked advisory brief. Verify in source systems before final action._
"""

# Fixture B — aggregate counts only; record-level detail is honestly unavailable.
_GOLDEN_DETAIL_UNAVAILABLE = f"""# Daily Brief — {_GOLDEN_DATE}

## Yesterday
- No notable activity was recorded yesterday.

## Today
No calendar items present.

## Next 7 Days
No deadlines in the next 7 days.

## Needs Attention
- Open RFIs: 5 — detail unavailable (dedicated reader not available); review the RFI log directly.
- Open submittals: 3 — detail unavailable (dedicated reader not available); review the submittal log.
- Open punch items: 12 — detail unavailable (dedicated reader not available); review the punch list.

## Focus
No focus items at this time.

---
_Source-linked advisory brief. Verify in source systems before final action._
"""

# Fixture C — unsafe / internal commentary that MUST be rejected. Contains internal-governance leakage
# and a final determination. Deliberately carries no real URLs/tokens/emails so the evidence no-raw
# gate passes; raw-shaped-value rejection is exercised separately (synthetic, in-memory) in tests.
_GOLDEN_REJECTED_INTERNAL = f"""# Daily Brief — {_GOLDEN_DATE}

## Yesterday
- Coordination occurred on Tropical.

## Today
| Time | Meeting | Project | Prep |
|---|---|---|---|
| 09:00 | Sync | Tropical | — |

## Next 7 Days
| Date | Project | Item |
|---|---|---|
| 2026-06-09 | Tropical | RFI |

## Needs Attention
| Priority | Project | Item |
|---|---|---|
| High | Tropical | Zero float |

## Provenance
| packet_id | source_ref_hash |
|---|---|
| dbp_x | a1b2c3 |

## Guardrails
| guardrail | value |
|---|---|
| advisory_only | true |
| no_writeback | true |
| metadata_only | true |

## Source Coverage and Confidence Notes
source_coverage_summary: families_present across 6 families; coverage_warnings none.

## Focus
1. Decision: we approve payment of the pending claim.

---
_Source-linked advisory brief. Verify in source systems before final action._
"""


def _golden_fixtures() -> dict[str, str]:
    """name -> rendered markdown. A and B must pass; C must be rejected."""
    return {
        "full_detail": _GOLDEN_FULL_DETAIL,
        "detail_unavailable": _GOLDEN_DETAIL_UNAVAILABLE,
        "rejected_internal": _GOLDEN_REJECTED_INTERNAL,
    }


def _render_v2_quality_proof_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 Addendum V2 — Daily Brief Executive-Quality Proof (Golden Fixtures)",
        "",
        f"- proof_passed: {proof['proof_passed']}",
        f"- generated_utc: {proof['generated_utc']}",
        f"- check_count: {proof['check_count']}",
        f"- max_brief_chars: {proof['max_brief_chars']}",
        "",
        "## Golden fixtures",
        "",
        f"- full_detail (must pass): passed={proof['fixtures']['full_detail']['passed']}",
        f"- detail_unavailable (must pass): passed={proof['fixtures']['detail_unavailable']['passed']}",
        f"- rejected_internal (must fail): passed={proof['fixtures']['rejected_internal']['passed']}"
        f" failing_checks={proof['fixtures']['rejected_internal']['failing_checks']}",
        "",
    ]
    return "\n".join(lines)


def build_daily_brief_v2_quality_proof(
    *, evidence_dir: str | None = None, write_evidence: bool = True
) -> dict[str, Any]:
    """Fail-closed executive-quality proof over three golden fixtures: the full-detail and
    detail-unavailable briefs pass every check, and the unsafe/internal brief is rejected.

    Validates the comprehensive V2 executive-utility standard (required sections, length, no internal
    governance/provenance/coverage/JSON/raw, count-backing, agenda/deadline/focus presence-or-none,
    no final determinations, no source-system writeback). Read-only; rendered text is never imported
    into trusted surfaces."""
    fixtures = _golden_fixtures()
    fixture_reports: dict[str, Any] = {}
    for name, text in fixtures.items():
        result = validate_rendered_brief({}, text)
        fixture_reports[name] = {
            "passed": result["passed"],
            "checks": result["checks"],
            "failing_checks": sorted(k for k, v in result["checks"].items() if not v),
        }

    full = fixture_reports["full_detail"]
    unavailable = fixture_reports["detail_unavailable"]
    rejected = fixture_reports["rejected_internal"]
    proof_passed = bool(full["passed"] and unavailable["passed"] and not rejected["passed"])

    required_checks = sorted(validate_rendered_brief({}, _SAMPLE_RENDERED_BRIEF)["checks"].keys())

    proof: dict[str, Any] = {
        "proof": "phase_09_addendum_daily_brief_v2_quality",
        "command": "second-brain daily-brief v2-proof",
        "phase": "09-addendum-v2",
        "proof_passed": proof_passed,
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "check_count": len(required_checks),
        "required_checks": required_checks,
        "max_brief_chars": _MAX_BRIEF_CHARS,
        "fixtures": fixture_reports,
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
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(_V2_QUALITY_EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        for fname, text in (
            (_GOLDEN_FULL_DETAIL_MD, _GOLDEN_FULL_DETAIL),
            (_GOLDEN_DETAIL_UNAVAILABLE_MD, _GOLDEN_DETAIL_UNAVAILABLE),
            (_GOLDEN_REJECTED_INTERNAL_MD, _GOLDEN_REJECTED_INTERNAL),
        ):
            _assert_no_raw(text, f"golden fixture {fname}")
            (out_dir / fname).write_text(text, encoding="utf-8")
        serialized = json.dumps(proof, indent=2, default=str)
        _assert_no_raw(serialized, "v2 quality proof json")
        (out_dir / _V2_QUALITY_PROOF_JSON).write_text(serialized + "\n", encoding="utf-8")
        markdown = _render_v2_quality_proof_md(proof)
        _assert_no_raw(markdown, "v2 quality proof markdown")
        (out_dir / _V2_QUALITY_PROOF_MD).write_text(markdown, encoding="utf-8")
        proof["proof_path"] = str(out_dir / _V2_QUALITY_PROOF_JSON)
        proof["proof_md_path"] = str(out_dir / _V2_QUALITY_PROOF_MD)

    return proof
