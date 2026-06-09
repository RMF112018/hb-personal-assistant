"""Phase 10 V45 — local-only model route + strict structured output for email follow-up enrichment.

Adds the ``email_followup_raw_enrichment`` local model task family: a strict JSON output schema, a
prompt template that accepts ONLY a bounded sanitized raw window + deterministic candidate/watch
metadata, cross-context validation (cited refs must be provided, raw-excerpt hash must match, no raw
leakage), and a thin runner that routes fail-closed (local-only; never cloud) and validates the
model output before it is trusted.

This module performs no persistence and no writeback. It builds on the existing
:class:`StructuredOutputClient` (which already writes only hash-only receipts and never persists raw
prompts/responses) and the fail-closed :func:`route_task_family`. Persistence + eligibility + caps
live in the enrichment engine (Prompt 04).
"""

from __future__ import annotations

import re
from typing import Any, Optional

from pydantic import BaseModel, Field, field_validator

from .email_followup_models import (
    MODEL_TASK,
    PROMPT_TEMPLATE_VERSION,
    EnrichmentAssigneeType,
    EnrichmentWaitingState,
)
from .model_router import (
    LocalModelTaskRouting,
    RouteResult,
    load_local_model_task_routing,
    route_task_family,
)
from .models import LocalModelProfiles
from .raw_followup_window import RawFollowupWindow
from .structured_output import GenerationBackend, StaticOutputClient, StructuredOutputClient

TASK_FAMILY = MODEL_TASK  # "email_followup_raw_enrichment"

# --- Raw-leak scanner (shared) --------------------------------------------------------------------
# Detects raw/unsafe content that must never appear in a structured enriched field. Reused by the
# output validators, the engine's persistence guard, and the evidence forbidden-string scan.
_LEAK_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("url", re.compile(r"https?://", re.IGNORECASE)),
    ("bearer", re.compile(r"\bBearer\s+\S", re.IGNORECASE)),
    ("authorization", re.compile(r"\bAuthorization:\s*\S", re.IGNORECASE)),
    ("oauth_token", re.compile(r"\b(access_token|refresh_token|id_token|client_secret)\b", re.IGNORECASE)),
    ("jwt", re.compile(r"\beyJ[A-Za-z0-9._\-]{10,}")),
    ("private_key", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY", re.IGNORECASE)),
    ("join_link", re.compile(r"(teams\.microsoft\.com/l/meetup-join|join\.microsoft\.com|zoom\.us/j/)", re.IGNORECASE)),
    ("html", re.compile(r"<\s*/?\s*(html|body|div|span|table|a|img|p|br|head|script|style)\b", re.IGNORECASE)),
    ("email", re.compile(r"[A-Za-z0-9._%+\-]+@[A-Za-z0-9.\-]+\.[A-Za-z]{2,}")),
)


def find_raw_leak(text: Optional[str]) -> Optional[str]:
    """Return the first raw-leak category found in ``text`` (URL/token/HTML/email/…) or None."""
    if not text:
        return None
    for name, rx in _LEAK_PATTERNS:
        if rx.search(text):
            return name
    return None


# --- Strict structured output schema --------------------------------------------------------------
class EmailFollowupEnrichmentOutput(BaseModel):
    """Strict JSON contract the local model must produce (``extra="forbid"`` rejects raw fields).

    Format-level rules are enforced here (closed enums, confidence range, no raw leakage in free-text
    fields). Cross-context rules (cited refs must be provided in the input; raw-excerpt hash must
    match) are enforced by :func:`validate_enrichment_output`, which has the input context.
    """

    enriched_title: str = Field(min_length=1, max_length=240)
    waiting_state: EnrichmentWaitingState
    assignee_type: EnrichmentAssigneeType
    assignee_display: str = Field(default="", max_length=200)
    suggested_next_action: str = Field(default="", max_length=1000)
    due_at_utc: str | None = None
    confidence: float = Field(ge=0.0, le=1.0)
    reason_codes: list[str] = Field(default_factory=list)
    cited_source_aliases: list[str] = Field(default_factory=list)
    cited_candidate_ids: list[str] = Field(default_factory=list)
    cited_watch_item_ids: list[str] = Field(default_factory=list)
    raw_excerpt_hash: str = Field(min_length=1)

    model_config = {"extra": "forbid"}

    @field_validator("enriched_title", "suggested_next_action", "assignee_display")
    @classmethod
    def _no_raw_leak(cls, value: str) -> str:
        leak = find_raw_leak(value)
        if leak is not None:
            raise ValueError(f"free-text field contains raw {leak}")
        return value


def validate_enrichment_output(
    out: EmailFollowupEnrichmentOutput,
    *,
    allowed_aliases: list[str],
    allowed_candidate_ids: list[str],
    allowed_watch_item_ids: list[str],
    raw_excerpt_hash: str,
) -> list[str]:
    """Cross-context validation. Returns a list of violation codes (empty ⇒ output is trustworthy).

    Rejects: cited aliases / candidate ids / watch ids not present in the provided input; a
    ``raw_excerpt_hash`` that does not match the window's hash; a deadline asserted without a
    supporting ``due_date`` reason code (guards against invented deadlines); any raw leakage that
    slipped past the field validators.
    """
    violations: list[str] = []
    allowed_alias_set = set(allowed_aliases)
    if any(a not in allowed_alias_set for a in out.cited_source_aliases):
        violations.append("cited_alias_not_in_input")
    if any(c not in set(allowed_candidate_ids) for c in out.cited_candidate_ids):
        violations.append("cited_candidate_not_in_input")
    if any(w not in set(allowed_watch_item_ids) for w in out.cited_watch_item_ids):
        violations.append("cited_watch_item_not_in_input")
    if out.raw_excerpt_hash != raw_excerpt_hash:
        violations.append("raw_excerpt_hash_mismatch")
    if out.due_at_utc and "due_date" not in {r.lower() for r in out.reason_codes}:
        violations.append("due_date_unsupported")
    for field_value in (out.enriched_title, out.suggested_next_action, out.assignee_display):
        if find_raw_leak(field_value):
            violations.append("raw_leak_in_output")
            break
    return violations


# --- Prompt template ------------------------------------------------------------------------------
_SYSTEM = (
    "You enrich an EXISTING, already-source-linked follow-up item using a bounded, redacted excerpt "
    "of its email thread. Output ONLY one JSON object matching the required schema (no prose, no "
    "markdown).\n"
    "Rules:\n"
    "- Use ONLY the provided context. Do not infer commitments or deadlines without explicit "
    "evidence in the excerpt.\n"
    "- Do NOT quote raw email text. Do NOT output URLs, tokens, email addresses, HTML, or raw "
    "excerpts in any field.\n"
    "- Prefer waiting_state=unknown and low confidence when ambiguous.\n"
    "- Cite ONLY source aliases / candidate ids / watch item ids that appear in the provided "
    "context.\n"
    "- Copy raw_excerpt_hash verbatim from the provided context.\n"
    "- If you assert due_at_utc, include 'due_date' in reason_codes; otherwise leave due_at_utc null."
)


def build_enrichment_prompt(
    *, window: RawFollowupWindow, candidate_meta: dict[str, Any]
) -> tuple[str, str, str]:
    """Build (system, prompt, input_context) for one enrichment call.

    ``candidate_meta`` carries the deterministic, already-source-linked fields (candidate id/type,
    optional watch item id, redacted title, waiting-state hint, project, due hint). The prompt
    exposes the allowed aliases/ids and the raw_excerpt_hash the model must echo. ``input_context``
    is the hashed provenance string (the StructuredOutputClient hashes it for the receipt).
    """
    aliases = ", ".join(window.source_aliases) or "(none)"
    candidate_id = str(candidate_meta.get("candidate_id") or "")
    watch_item_id = candidate_meta.get("watch_item_id")
    lines = [
        "## Deterministic follow-up item (already source-linked)",
        f"candidate_id: {candidate_id}",
        f"candidate_type: {candidate_meta.get('candidate_type') or 'task'}",
        f"watch_item_id: {watch_item_id or '(none)'}",
        f"deterministic_title_redacted: {candidate_meta.get('title_redacted') or '(none)'}",
        f"deterministic_waiting_state: {candidate_meta.get('waiting_state') or 'unknown'}",
        f"project_key: {candidate_meta.get('project_key') or '(none)'}",
        f"deterministic_due_at_utc: {candidate_meta.get('due_at_utc') or '(none)'}",
        "",
        "## Allowed citations (cite only these)",
        f"source_aliases: {aliases}",
        f"candidate_ids: {candidate_id}",
        f"watch_item_ids: {watch_item_id or '(none)'}",
        f"raw_excerpt_hash: {window.raw_excerpt_hash}",
        "",
        "## Bounded redacted email excerpt (model context only; never quote verbatim)",
        f"subject: {window.subject_sanitized or '(none)'}",
        window.window_text or "(no content)",
    ]
    input_context = "\n".join(lines)
    prompt = (
        "Enrich the follow-up item above. Return ONLY the JSON object for the "
        "EmailFollowupEnrichmentOutput schema."
    )
    return _SYSTEM, prompt, input_context


def route_email_followup(
    *,
    profiles: Optional[LocalModelProfiles] = None,
    routing: Optional[LocalModelTaskRouting] = None,
    present_models: Optional[set[str]] = None,
    heavy_enabled: bool = False,
) -> RouteResult:
    """Resolve the local-only route for the enrichment task family (fail-closed; never cloud)."""
    return route_task_family(
        TASK_FAMILY,
        profiles=profiles,
        routing=routing,
        present_models=present_models,
        heavy_enabled=heavy_enabled,
    )


def run_email_followup_model(
    *,
    window: RawFollowupWindow,
    candidate_meta: dict[str, Any],
    profiles: LocalModelProfiles,
    routing: Optional[LocalModelTaskRouting] = None,
    present_models: Optional[set[str]] = None,
    backend: Optional[GenerationBackend] = None,
    mock_output: Optional[str] = None,
    store: Optional[Any] = None,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Route (fail-closed), generate, and validate one enrichment. No persistence here.

    Returns a structured dict: ``status`` (ok|degraded|invalid|blocked), ``validated`` (the parsed
    output dict when ok), ``violations``, ``route`` (selected profile / availability), plus the
    receipt hashes surfaced by the StructuredOutputClient. When the local model is unavailable the
    route is blocked and a controlled degraded result is returned without any backend call.
    """
    routing = routing or load_local_model_task_routing()
    route = route_email_followup(
        profiles=profiles, routing=routing, present_models=present_models
    )
    route_info = {
        "task_family": route.task_family,
        "selected_profile": route.selected_profile,
        "model_name": route.model_name,
        "available": route.available,
        "no_cloud": route.no_cloud,
        "reason_code": route.reason_code,
        "fallback_chain": route.fallback_chain,
    }
    if route.blocked or not route.available:
        return {
            "status": "blocked",
            "validated": None,
            "violations": [],
            "blockers": route.blockers,
            "route": route_info,
            "input_context_hash": None,
            "output_hash": None,
        }

    profile = next(
        (p for p in profiles.profiles if p.profile_id == route.selected_profile), None
    )
    if profile is None:  # pragma: no cover - route guarantees a known profile
        return {
            "status": "blocked",
            "validated": None,
            "violations": [],
            "blockers": ["profile_resolution_failed"],
            "route": route_info,
            "input_context_hash": None,
            "output_hash": None,
        }

    system, prompt, input_context = build_enrichment_prompt(
        window=window, candidate_meta=candidate_meta
    )
    b = backend if backend is not None else (
        StaticOutputClient(mock_output) if mock_output is not None else None
    )
    result = StructuredOutputClient().run(
        schema=EmailFollowupEnrichmentOutput,
        profile=profile,
        profiles=profiles,
        system=system,
        prompt=prompt,
        input_context=input_context,
        task_type=TASK_FAMILY,
        backend=b,
        store=store if not dry_run else None,
        dry_run=dry_run,
    )
    base = {
        "route": route_info,
        "input_context_hash": result.input_context_hash,
        "output_hash": result.output_hash,
        "fallback_used": result.fallback_used,
    }
    if result.status in {"unavailable", "timeout", "failed"}:
        return {**base, "status": "degraded", "validated": None, "violations": [],
                "error_redacted": result.error_redacted}
    if not result.schema_valid or not result.validated:
        return {**base, "status": "invalid", "validated": None,
                "violations": ["schema_invalid"], "error_redacted": result.error_redacted}

    out = EmailFollowupEnrichmentOutput.model_validate(result.validated)
    violations = validate_enrichment_output(
        out,
        allowed_aliases=window.source_aliases,
        allowed_candidate_ids=[str(candidate_meta.get("candidate_id") or "")],
        allowed_watch_item_ids=(
            [str(candidate_meta["watch_item_id"])] if candidate_meta.get("watch_item_id") else []
        ),
        raw_excerpt_hash=window.raw_excerpt_hash,
    )
    if violations:
        return {**base, "status": "invalid", "validated": None, "violations": violations}
    return {**base, "status": "ok", "validated": out.model_dump(mode="json"), "violations": []}


__all__ = [
    "TASK_FAMILY",
    "PROMPT_TEMPLATE_VERSION",
    "EmailFollowupEnrichmentOutput",
    "find_raw_leak",
    "validate_enrichment_output",
    "build_enrichment_prompt",
    "route_email_followup",
    "run_email_followup_model",
]
