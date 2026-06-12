"""Phase 10 (252) — bounded local-Ollama advisory overlay for the New Today digest.

Wraps the schema-enforced :class:`StructuredOutputClient` (local-only, hash-only receipts, bounded
retry, single-hop fallback) so the model can *polish framing* but never *invent facts*. Per the
reviewer's Ollama input policy, the packet carries bounded **local** context — the deterministic
business facts plus a short raw title/subject excerpt for grounding — consumed inside the local
pipeline only; it is never persisted, committed, or sent to any cloud service.

What the model may influence (advisory, bounded):

* ``why_it_matters`` and ``recommended_action`` wording;
* the ``attention_class`` suggestion — and only by at most one adjacency step, and only when the
  deterministic confidence is below a close threshold (deterministic always wins otherwise).

What it may NOT touch: the deterministic ``summary_text`` (the factual sentence — names, timestamps,
project, record number/title/status, amount, meeting time, source refs stay exactly as the
deterministic extractor produced them). Any model field that carries a forbidden token (URL, email,
token, key) withholds the entire model layer — raw safety beats partial advice. Fail-closed to the
deterministic digest on daemon-unavailable / timeout / invalid schema / leak.
"""

from __future__ import annotations

import hashlib
import json
from typing import Any, Optional

from pydantic import BaseModel, Field

from .model_eval_metrics import scan_text_for_forbidden
from .models import LocalModelProfile, LocalModelProfiles
from .new_today_digest import ATTENTION_ORDER
from .structured_output import GenerationBackend, StructuredOutputClient

TASK_TYPE = "daily_brief_new_today"

# --- Named conservative tunables (bounded influence; deterministic authoritative) -------------
#: Max steps the model may move an item's attention class along ATTENTION_ORDER.
MAX_ATTENTION_STEP = 1
#: The model attention suggestion is only honored when deterministic confidence is below this.
MODEL_ATTENTION_OVERRIDE_BELOW = 0.85
_WHY_MAX = 300
_ACTION_MAX = 300
_RAW_EXCERPT_MAX = 240

_ATTENTION_INDEX = {a: i for i, a in enumerate(ATTENTION_ORDER)}

_SYSTEM = (
    "You refine the wording of an ALREADY-DECIDED overnight change brief. The deterministic facts "
    "(names, dates, times, project, record numbers, amounts, statuses) are authoritative and you "
    "MUST NOT change, add, or invent any of them. For each item you may only: rewrite 'why it "
    "matters' and the 'recommended action' in clear executive English, and optionally suggest an "
    "attention class from exactly {needs_attention, team_follow_up, awareness}. Never add names, "
    "numbers, dates, amounts, URLs, emails, or claims that are not already in the item. Return JSON "
    "only, matching the schema."
)


class NewTodayAdviceItem(BaseModel):
    """Per-event advisory hint. ``ref`` must match a packet event id or the item is ignored."""

    ref: str = Field(min_length=1, max_length=64)
    why_it_matters: Optional[str] = Field(default=None, max_length=_WHY_MAX)
    recommended_action: Optional[str] = Field(default=None, max_length=_ACTION_MAX)
    attention_class: Optional[str] = None

    model_config = {"extra": "forbid"}


class NewTodayAdvice(BaseModel):
    """The complete advisory output. Strict: unknown fields / raw content fail validation."""

    items: list[NewTodayAdviceItem] = Field(default_factory=list, max_length=500)

    model_config = {"extra": "forbid"}


def _packet(events: list[Any]) -> dict[str, Any]:
    """Bounded local-context packet (deterministic facts + short raw excerpt for grounding)."""
    rows = []
    for ev in events:
        excerpt = str(getattr(ev, "business_record_title", "") or "")[:_RAW_EXCERPT_MAX]
        rows.append(
            {
                "ref": ev.event_id,
                "source_family": ev.source_family,
                "record_type": ev.business_record_type,
                "record_number": ev.business_record_number,
                "status": ev.business_record_status,
                "project": ev.project_display_name,
                "actor": ev.actor_display_name or ev.actor_company,
                "amount": ev.amount,
                "deterministic_summary": ev.summary_text,
                "raw_excerpt": excerpt,
                "attention_class": ev.attention_class,
                "confidence": ev.confidence,
            }
        )
    return {"items": rows}


def _bounded_attention(current: str, suggestion: Optional[str], confidence: float) -> str:
    """Honor a model attention suggestion only when bounded and the deterministic call is not firm."""
    if not suggestion or suggestion not in _ATTENTION_INDEX:
        return current
    if confidence >= MODEL_ATTENTION_OVERRIDE_BELOW:
        return current  # deterministic confidence is firm — keep it
    cur_i = _ATTENTION_INDEX.get(current, len(ATTENTION_ORDER))
    new_i = _ATTENTION_INDEX[suggestion]
    if abs(new_i - cur_i) > MAX_ATTENTION_STEP:
        return current
    return suggestion


def apply_model_overlay(
    events: list[Any],
    *,
    profile: LocalModelProfile,
    profiles: LocalModelProfiles,
    backend: Optional[GenerationBackend] = None,
    store: Optional[Any] = None,
    dry_run: bool = True,
    heavy_enabled: bool = False,
) -> dict[str, Any]:
    """Apply the bounded advisory overlay to ``events`` in place; return status + hash-only receipt.

    Returns ``status`` (``ok`` | ``withheld`` | ``degraded``), the hash-only receipt fields, and the
    count of events the model enriched. Deterministic facts (``summary_text``) are never overwritten.
    On any failure the events are returned unchanged (deterministic fallback).
    """
    if not events:
        return {"status": "degraded", "degraded_reason": "no_events", "enriched_count": 0}

    by_ref = {ev.event_id: ev for ev in events}
    input_context = hashlib.sha256(
        ("|".join(sorted(by_ref)) + events[0].brief_date).encode("utf-8")
    ).hexdigest()[:24]

    result = StructuredOutputClient().run(
        schema=NewTodayAdvice,
        profile=profile,
        profiles=profiles,
        system=_SYSTEM,
        prompt=json.dumps(_packet(events), sort_keys=True, separators=(",", ":")),
        input_context=input_context,
        task_type=TASK_TYPE,
        backend=backend,
        store=store,
        dry_run=dry_run,
        heavy_enabled=heavy_enabled,
    )

    receipt = {
        "model_status": result.status,
        "model_profile_id": result.profile_id,
        "model_name": result.model_name,
        "model_receipt_id": result.receipt_id,
        "output_hash": result.output_hash,
        "input_context_hash": result.input_context_hash,
        "fallback_used": result.fallback_used,
        "would_write_receipt": result.would_write_receipt,
    }

    if result.status != "ok" or not result.validated:
        return {
            "status": "degraded",
            "degraded_reason": f"model_{result.status}",
            "enriched_count": 0,
            **receipt,
        }

    advice = NewTodayAdvice.model_validate(result.validated)

    # Raw safety beats partial advice: any leaky field withholds the whole model layer.
    for ai in advice.items:
        if scan_text_for_forbidden(ai.why_it_matters) or scan_text_for_forbidden(
            ai.recommended_action
        ):
            return {
                "status": "withheld",
                "degraded_reason": "raw_leak_in_model_output",
                "enriched_count": 0,
                **receipt,
            }

    enriched = 0
    for ai in advice.items:
        ev = by_ref.get(ai.ref)
        if ev is None:
            continue
        touched = False
        if ai.why_it_matters:
            ev.why_it_matters = ai.why_it_matters.strip()
            touched = True
        if ai.recommended_action:
            ev.recommended_action = ai.recommended_action.strip()
            touched = True
        new_attention = _bounded_attention(ev.attention_class, ai.attention_class, ev.confidence)
        if new_attention != ev.attention_class:
            ev.attention_class = new_attention
            touched = True
        if touched:
            ev.enrichment_status = "model_enriched"
            ev.model_profile_id = result.profile_id
            ev.model_name = result.model_name
            ev.model_run_receipt_id = result.receipt_id
            enriched += 1

    return {
        "status": "ok" if enriched else "degraded",
        "degraded_reason": None if enriched else "all_model_advice_dropped",
        "enriched_count": enriched,
        **receipt,
    }
