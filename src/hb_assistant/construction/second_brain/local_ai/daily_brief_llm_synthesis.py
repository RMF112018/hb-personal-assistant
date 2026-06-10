"""Phase 10 correction — local-model executive daily-brief synthesis (schema-enforced, fail-closed).

Turns the bounded context packet (:mod:`daily_brief_context_packet`) into a validated
:class:`DailyBriefSynthesis` using the approved local model profile via the reusable
:class:`StructuredOutputClient` (schema validation, bounded retry/self-repair, single-hop fallback,
hash-only receipts). No cloud LLM. No raw prompt/response is ever persisted or logged.

Fail-closed posture (amendment 5): if the model is unavailable / times out / returns malformed or
schema-invalid output, OR the validated brief is empty (low quality), the result is marked
``degraded`` and is NOT a success — the caller must not update the last-successful pointer and must
clearly mark the brief as degraded.
"""

from __future__ import annotations

import json
from dataclasses import dataclass
from typing import Any, Optional

from .contracts import Phase10ContractError, load_local_model_profiles
from .daily_brief_context_packet import build_daily_brief_context_packet
from .daily_brief_synthesis_schema import DailyBriefSynthesis
from .daily_brief_window import DailyBriefWindow
from .models import LocalModelProfile, LocalModelProfiles
from .structured_output import GenerationBackend, StructuredOutputClient

_DEFAULT_PROFILE_ID = "brief_synthesis"
_TASK_TYPE = "daily_brief_synthesis"

_SYSTEM_PROMPT = (
    "You are the chief of staff for a senior construction executive (Bobby) at a general "
    "contractor. You receive a bounded, source-linked JSON context packet describing one operating "
    "day: the weekday date window, open commitments/tasks/follow-ups, action candidates, "
    "relationship signals, Procore project signals, and classified calendar meetings.\n\n"
    "Write a concise, decision-ready OPERATOR brief as JSON only (no prose outside JSON), matching "
    "the required schema exactly. Rules:\n"
    "- Executive Summary: 3-7 crisp bullets answering what matters today and why.\n"
    "- What Changed Since Last Brief: respect date_window (weekend/prior-week carryover on Monday; "
    "next-week prep on Friday). Use the carryover_section_label when present.\n"
    "- Critical / Due Today: only genuinely urgent/overdue items; say why and the next action.\n"
    "- Open Commitments & Follow-Ups: who owes what, what is stale, recommended action.\n"
    "- Today's Meetings: only meetings worth prepping (the packet already excludes noise). Include "
    "local_time, project, why it matters, prep notes, open questions, and the source id.\n"
    "- Project Signals: group by project; highlight overdue/aging Procore signals in plain English.\n"
    "- Recommended Next Actions: a short prioritized list (most important first).\n"
    "- FYI / Low Priority: optional, demoted, capped.\n"
    "- Needs Review / Data Gaps: unassigned-project items, ambiguous relationships, missing data.\n\n"
    "Use ONLY facts present in the packet — do NOT invent meetings, people, amounts, dates, or "
    "links. Reference items by their provided short id in source_id where relevant. Never output "
    "email addresses, URLs, join links, or tokens. If a section has no items, return an empty list.\n\n"
    "Return EXACTLY this JSON shape (string lists where shown as strings; object lists where shown "
    "as objects):\n"
    "{\n"
    '  "executive_summary": ["..."],\n'
    '  "what_changed_since_last_brief": [{"text": "...", "source_id": "...", "project": "..."}],\n'
    '  "critical_due_today": [{"text": "...", "source_id": "...", "project": "..."}],\n'
    '  "open_commitments_follow_ups": [{"text": "...", "source_id": "...", "project": "..."}],\n'
    '  "todays_meetings": [{"local_time": "...", "title": "...", "project": "...", '
    '"why_it_matters": "...", "prep": "...", "open_questions": ["..."], "source_id": "...", '
    '"recommended_next_action": "..."}],\n'
    '  "project_signals": [{"project": "...", "summary": "...", "items": [{"text": "..."}]}],\n'
    '  "recommended_next_actions": ["..."],\n'
    '  "fyi_low_priority": ["..."],\n'
    '  "needs_review_data_gaps": ["..."]\n'
    "}"
)


@dataclass
class BriefSynthesisResult:
    """Outcome of a synthesis run (advisory; receipt is hash-only)."""

    status: str  # ok | schema_invalid | unavailable | timeout | failed | blocked | profile_error
    degraded: bool
    profile_id: str
    model_name: str
    schema_valid: bool
    fallback_used: bool
    attempts: int
    latency_ms: int
    synthesis: Optional[DailyBriefSynthesis]
    error_redacted: Optional[str]
    degraded_reason: Optional[str]
    would_write_receipt: Optional[dict[str, Any]] = None

    def metadata(self) -> dict[str, Any]:
        """Safe, surfaceable model metadata (no raw prompt/response). For status + brief footer."""
        return {
            "profile_id": self.profile_id,
            "model_name": self.model_name,
            "status": self.status,
            "schema_valid": self.schema_valid,
            "fallback_used": self.fallback_used,
            "attempts": self.attempts,
            "latency_ms": self.latency_ms,
            "degraded": self.degraded,
            "degraded_reason": self.degraded_reason,
            "error_redacted": self.error_redacted,
        }


def _bullet(text: str, *, source_id: str = "", project: str = "") -> str:
    parts = [text.strip()]
    if project and project not in {"", "Needs Project Review"}:
        parts.append(f"project:{project}")
    if source_id:
        parts.append(f"id:{source_id}")
    return "- " + " · ".join(parts)


def _window_heading_suffix(window: DailyBriefWindow) -> str:
    label = (window.carryover_section_label or "").strip()
    return f" · {label}" if label else ""


def render_synthesis_markdown(
    synthesis: DailyBriefSynthesis,
    *,
    brief_date: str,
    window: DailyBriefWindow,
    model_metadata: dict[str, Any],
    generated_label: str,
) -> str:
    """Render the validated synthesis into the executive operator-brief markdown (9 sections).

    Empty sections render a meaningful empty state (never silently omitted). A model-metadata footer
    records the profile/model/status + generated timestamp (no raw prompt/response)."""
    s = synthesis
    changed_label = (window.carryover_section_label or "").strip()
    changed_heading = (
        f"What Changed Since Last Brief — {changed_label}"
        if changed_label
        else "What Changed Since Last Brief"
    )
    lines: list[str] = [
        f"# Daily Brief — {brief_date} ({window.run_weekday}{_window_heading_suffix(window)})",
        "",
        f"_Local-model operator brief. {window.explanation}_",
        "",
        "## Executive Summary",
        *([f"- {b}" for b in s.executive_summary] or ["_No high-level summary generated._"]),
        "",
        f"## {changed_heading}",
        *(
            [
                _bullet(b.text, source_id=b.source_id, project=b.project)
                for b in s.what_changed_since_last_brief
            ]
            or ["_No notable changes since the last working-period brief._"]
        ),
        "",
        "## Critical / Due Today",
        *(
            [
                _bullet(b.text, source_id=b.source_id, project=b.project)
                for b in s.critical_due_today
            ]
            or ["_No critical due-today actions found._"]
        ),
        "",
        "## Open Commitments & Follow-Ups",
        *(
            [
                _bullet(b.text, source_id=b.source_id, project=b.project)
                for b in s.open_commitments_follow_ups
            ]
            or ["_No open commitments or follow-up items found for this run._"]
        ),
        "",
        "## Today's Meetings",
    ]
    if s.todays_meetings:
        for m in s.todays_meetings:
            head = " — ".join(p for p in (m.local_time, m.title) if p)
            lines.append(f"- **{head}** ({m.project})")
            if m.why_it_matters:
                lines.append(f"  - Why: {m.why_it_matters}")
            if m.prep:
                lines.append(f"  - Prep: {m.prep}")
            if m.open_questions:
                lines.append("  - Open questions: " + "; ".join(m.open_questions))
            tail = []
            if m.recommended_next_action:
                tail.append(f"next:{m.recommended_next_action}")
            if m.source_id:
                tail.append(f"id:{m.source_id}")
            if tail:
                lines.append("  - " + " · ".join(tail))
    else:
        lines.append("_No meeting-prep items required attention._")
    lines += ["", "## Project / Procore Signals"]
    if s.project_signals:
        for g in s.project_signals:
            lines.append(f"### {g.project}")
            if g.summary:
                lines.append(g.summary)
            for it in g.items:
                lines.append(_bullet(it.text, source_id=it.source_id))
    else:
        lines.append("_No Procore project signals were generated in this run._")
    lines += [
        "",
        "## Recommended Next Actions",
        *(
            [f"{i}. {a}" for i, a in enumerate(s.recommended_next_actions, start=1)]
            or ["_No prioritized next actions generated._"]
        ),
        "",
        "## FYI / Low Priority",
        *([f"- {b}" for b in s.fyi_low_priority] or ["_None._"]),
        "",
        "## Needs Review / Data Gaps",
        *([f"- {b}" for b in s.needs_review_data_gaps] or ["_No data gaps flagged._"]),
        "",
        "---",
        (
            f"_Synthesized by local model {model_metadata.get('model_name', '?')} "
            f"(profile {model_metadata.get('profile_id', '?')}, status {model_metadata.get('status', '?')}) "
            f"· generated {generated_label}._"
        ),
    ]
    return "\n".join(lines).strip() + "\n"


def render_degraded_markdown(
    *,
    brief_date: str,
    window: DailyBriefWindow,
    model_metadata: dict[str, Any],
    generated_label: str,
    deterministic_markdown: str,
) -> str:
    """Render a clearly-marked DEGRADED brief when synthesis failed/low-quality (never 'success')."""
    reason = model_metadata.get("degraded_reason") or model_metadata.get("status") or "unknown"
    banner = (
        "> ⚠ **DEGRADED BRIEF — local-model synthesis unavailable.** "
        f"(reason: {reason}; model {model_metadata.get('model_name', '?')}). "
        "This is NOT a full operator brief; it falls back to the deterministic source-linked "
        "candidate list below. The run is NOT counted as successful."
    )
    return (
        f"# Daily Brief — {brief_date} ({window.run_weekday}{_window_heading_suffix(window)})\n\n"
        f"{banner}\n\n"
        f"_{window.explanation}_\n\n"
        f"{deterministic_markdown.strip()}\n\n"
        "---\n"
        f"_Degraded fallback · generated {generated_label}._\n"
    )


def render_deterministic_fallback_markdown(
    *,
    brief_date: str,
    window: DailyBriefWindow,
    model_metadata: dict[str, Any],
    generated_label: str,
    deterministic_markdown: str,
) -> str:
    """Render an OPERATOR-USABLE deterministic-fallback brief.

    Used when the deterministic usefulness gate PASSED but local-model executive synthesis degraded:
    the source-linked deterministic brief is published as a safe fallback (NOT the same class as an
    unusable/degraded brief). The banner says so explicitly.
    """
    reason = model_metadata.get("degraded_reason") or model_metadata.get("status") or "unknown"
    banner = (
        "> ✓ **Deterministic source-linked brief published.** "
        f"Local-model synthesis was degraded: {reason} "
        f"(model {model_metadata.get('model_name', '?')}). "
        "This brief is operator-usable because the deterministic usefulness gate passed; it is not a "
        "full model-synthesized brief."
    )
    return (
        f"# Daily Brief — {brief_date} ({window.run_weekday}{_window_heading_suffix(window)})\n\n"
        f"{banner}\n\n"
        f"_{window.explanation}_\n\n"
        f"{deterministic_markdown.strip()}\n\n"
        "---\n"
        f"_Deterministic fallback (usefulness gate passed) · generated {generated_label}._\n"
    )


def _select_profile(profiles: LocalModelProfiles, profile_id: str) -> Optional[LocalModelProfile]:
    for p in profiles.profiles:
        if p.profile_id == profile_id:
            return p
    return None


def synthesize_daily_brief(
    *,
    store: Any,
    brief_date: str,
    window: DailyBriefWindow,
    now_utc: str,
    db_path: Optional[str] = None,
    profile_id: str = _DEFAULT_PROFILE_ID,
    backend: Optional[GenerationBackend] = None,
    dry_run: bool = True,
    packet: Optional[dict[str, Any]] = None,
) -> BriefSynthesisResult:
    """Synthesize the executive brief for one date via the local model (schema-enforced, fail-closed).

    ``backend`` is injected for offline tests (e.g. ``StaticOutputClient``); when omitted a real
    Ollama backend is built from the profile. ``packet`` may be supplied to reuse an already-built
    context packet (avoids a second calendar pass); otherwise it is built here.
    """
    try:
        profiles = load_local_model_profiles()
    except Phase10ContractError as exc:
        return BriefSynthesisResult(
            status="profile_error",
            degraded=True,
            profile_id=profile_id,
            model_name="",
            schema_valid=False,
            fallback_used=False,
            attempts=0,
            latency_ms=0,
            synthesis=None,
            error_redacted=str(exc)[:120],
            degraded_reason="profiles_unavailable",
        )

    profile = _select_profile(profiles, profile_id)
    if profile is None:
        return BriefSynthesisResult(
            status="profile_error",
            degraded=True,
            profile_id=profile_id,
            model_name="",
            schema_valid=False,
            fallback_used=False,
            attempts=0,
            latency_ms=0,
            synthesis=None,
            error_redacted=f"profile_not_found:{profile_id}",
            degraded_reason="profile_not_found",
        )

    if packet is None:
        packet = build_daily_brief_context_packet(
            store=store, brief_date=brief_date, window=window, now_utc=now_utc, db_path=db_path
        )

    # Source-ref gate: if deterministic candidates exist but NONE are source-linked, withhold the
    # model entirely (fail-closed) — the model must not claim meetings/risks/actions with no source.
    gate = packet.get("source_ref_gate") or {}
    if gate.get("withhold_synthesis"):
        return BriefSynthesisResult(
            status="blocked",
            degraded=True,
            profile_id=profile_id,
            model_name=profile.model_name,
            schema_valid=False,
            fallback_used=False,
            attempts=0,
            latency_ms=0,
            synthesis=None,
            error_redacted=None,
            degraded_reason="no_source_linked_context",
        )

    input_context = json.dumps(packet, default=str, sort_keys=True)
    prompt = (
        "Synthesize the daily operator brief from this bounded, source-linked context packet. "
        "Return ONLY the JSON object matching the schema.\n\nCONTEXT_PACKET:\n" + input_context
    )

    result = StructuredOutputClient().run(
        schema=DailyBriefSynthesis,
        profile=profile,
        profiles=profiles,
        system=_SYSTEM_PROMPT,
        prompt=prompt,
        input_context=input_context,
        task_type=_TASK_TYPE,
        backend=backend,
        store=store if not dry_run else None,
        dry_run=dry_run,
    )

    synthesis: Optional[DailyBriefSynthesis] = None
    degraded = True
    degraded_reason: Optional[str] = result.error_redacted or result.status
    if result.status == "ok" and result.validated is not None:
        synthesis = DailyBriefSynthesis.model_validate(result.validated)
        if synthesis.is_empty():
            degraded = True
            degraded_reason = "empty_synthesis_low_quality"
            synthesis = None  # do not present an empty model brief as a real brief
        else:
            degraded = False
            degraded_reason = None

    return BriefSynthesisResult(
        status=result.status,
        degraded=degraded,
        profile_id=result.profile_id,
        model_name=result.model_name,
        schema_valid=result.schema_valid,
        fallback_used=result.fallback_used,
        attempts=result.attempts,
        latency_ms=result.latency_ms,
        synthesis=synthesis,
        error_redacted=result.error_redacted,
        degraded_reason=degraded_reason,
        would_write_receipt=result.would_write_receipt,
    )
