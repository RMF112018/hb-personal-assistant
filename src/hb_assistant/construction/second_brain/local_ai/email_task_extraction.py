"""Phase 10 Prompt 07 — Email Task Candidate Extraction (deterministic signals + summaries).

A metadata-safe, deterministic-signal-first path that turns email *thread summaries / read models*
into advisory task/commitment :class:`ActionCandidate` records. This is the complementary sibling of
the Phase 10A raw-body extractor (``raw_action_intelligence.extract_action_candidates_from_raw``): it
does **not** duplicate that engine, the ``ActionCandidate`` model/schema, the ``StructuredOutputClient``,
or the candidate tables — it adds a cheaper, safer front-end for broad/background scanning.

Two modes:

- ``metadata_safe`` (default): scores deterministic task signals over redacted summary read models
  (subject-redacted, summary-redacted, sender domain, recency, sent-by-user) and runs the existing
  structured-output client. Persists only structured candidate fields + source refs + hashes +
  bounded reason codes — never raw bodies/prompts/responses.
- ``bounded_content`` (opt-in, policy-gated): when :func:`load_raw_content_policy` permits, augments
  the window with bounded local thread content read **ephemerally in-process** (reusing
  ``build_raw_email_context_packet``). The bounded content is never persisted; only a policy-approved
  bounded excerpt (<=400 chars) is stored as ``evidence_redacted``. If policy disallows it the mode
  falls back to ``metadata_safe`` with a recorded blocker.

Deterministic signals are advisory inputs that bias the prompt and seed confidence/reason codes; the
local model output is still strictly validated against ``ActionCandidate`` before any write, and every
write is dry-run-gated. Advisory only — candidates are review-only and never auto-accepted.

Public entry points (additive):
    score_email_task_signals(summary) -> dict
    extract_email_task_candidates(*, summaries=None, store=None, project_key=None,
        mode="metadata_safe", profile_id="default_extract", profiles=None, backend=None,
        mock_output=None, dry_run=True, max_items=20, policy=None) -> dict
"""

from __future__ import annotations

import hashlib
import re
import uuid
from typing import Any, Optional

from hb_assistant.procore.normalizers.hashing import hash_summary

from .contracts import load_local_model_profiles, load_raw_content_policy
from .models import ActionCandidate
from .raw_action_intelligence import _truncate, _validate_business_contract
from .structured_output import (
    GenerationBackend,
    StaticOutputClient,
    StructuredOutputClient,
)

# Closed vocabularies — mirror phase_10_email_task_signal_contract.json (parity test enforces this).
SIGNAL_CATEGORIES: tuple[str, ...] = (
    "direct_ask",
    "due_date",
    "waiting_on_me",
    "waiting_on_others",
    "unanswered_question",
    "follow_up_stale",
    "project_source_confidence",
)
REASON_CODES: tuple[str, ...] = SIGNAL_CATEGORIES + ("low_signal",)
MODES: tuple[str, ...] = ("metadata_safe", "bounded_content")
CANDIDATE_TYPES: tuple[str, ...] = ("task", "commitment")

# Deterministic keyword/regex signal patterns (code constants; no external config).
_DIRECT_ASK = re.compile(
    r"\b(please|can you|could you|would you|need you to|kindly|let me know|"
    r"send me|provide|confirm whether|action required)\b",
    re.IGNORECASE,
)
_DUE_DATE = re.compile(
    r"\b(by (eod|cob|end of day|today|tomorrow|monday|tuesday|wednesday|thursday|friday|"
    r"\d{1,2}(st|nd|rd|th)?)|due|deadline|no later than|asap|before \w+|"
    r"\d{4}-\d{2}-\d{2})\b",
    re.IGNORECASE,
)
_WAITING_OTHERS = re.compile(
    r"\b(waiting on|pending your|awaiting your|your response|your input|once you|"
    r"need (your|the team'?s))\b",
    re.IGNORECASE,
)
_UNANSWERED_Q = re.compile(r"\?|\b(confirm|clarify|which|when will|can we)\b", re.IGNORECASE)
_FOLLOW_UP = re.compile(
    r"\b(following up|follow up|circling back|checking in|gentle reminder|reminder|"
    r"still (need|waiting)|any update)\b",
    re.IGNORECASE,
)


def _normalize_summary(summary: dict[str, Any]) -> dict[str, Any]:
    """Normalize a fixture-shaped or persisted thread-summary read model to a common shape.

    Reads only metadata-safe / redacted fields. Never returns raw bodies.
    """
    inp = summary.get("input_redacted") or {}
    subject = inp.get("thread_subject_redacted") or summary.get("thread_subject_redacted") or ""
    summary_text = inp.get("summary_redacted") or summary.get("summary_redacted") or ""
    source_ref = (
        summary.get("source_ref")
        or summary.get("thread_key")
        or inp.get("source_ref")
        or summary.get("fixture_id")
        or "email_thread_summary:unknown"
    )
    return {
        "subject": str(subject),
        "summary_text": str(summary_text),
        "sender_domain": inp.get("sender_domain") or summary.get("sender_domain"),
        "received_at": inp.get("received_at")
        or summary.get("received_at")
        or summary.get("last_message_datetime"),
        "sent_by_user": bool(inp.get("sent_by_user") or summary.get("sent_by_user") or False),
        "source_ref": str(source_ref),
        "project_key": summary.get("project_key") or inp.get("project_key"),
    }


def score_email_task_signals(summary: dict[str, Any]) -> dict[str, Any]:
    """Deterministically score task/commitment signals over a metadata-safe thread summary.

    Pure function (no I/O). Returns fired signal flags, stable reason codes, a candidate_type /
    waiting_state hint, and a bounded deterministic-confidence contribution.
    """
    norm = _normalize_summary(summary)
    text = f"{norm['subject']} \n {norm['summary_text']}"
    sent_by_user = norm["sent_by_user"]

    signals: dict[str, bool] = {
        "direct_ask": bool(_DIRECT_ASK.search(text)),
        "due_date": bool(_DUE_DATE.search(text)),
        "waiting_on_me": (not sent_by_user) and bool(_DIRECT_ASK.search(text)),
        "waiting_on_others": sent_by_user or bool(_WAITING_OTHERS.search(text)),
        "unanswered_question": bool(_UNANSWERED_Q.search(text)),
        "follow_up_stale": bool(_FOLLOW_UP.search(text)),
        "project_source_confidence": bool(norm["project_key"]) and bool(norm["source_ref"]),
    }
    reason_codes = [c for c in SIGNAL_CATEGORIES if signals.get(c)]
    if not reason_codes:
        reason_codes = ["low_signal"]

    # A thread the user sent that contains a promise reads as a commitment; otherwise a task.
    candidate_type_hint = "commitment" if sent_by_user else "task"
    if sent_by_user:
        waiting_state_hint = "waiting_on_others"
    elif signals["direct_ask"] or signals["unanswered_question"]:
        waiting_state_hint = "waiting_on_me"
    else:
        waiting_state_hint = "unknown"

    fired = sum(1 for c in SIGNAL_CATEGORIES if signals[c])
    deterministic_confidence = round(min(0.9, 0.2 + 0.12 * fired), 3)

    return {
        "signals": signals,
        "reason_codes": reason_codes,
        "candidate_type_hint": candidate_type_hint,
        "waiting_state_hint": waiting_state_hint,
        "deterministic_confidence": deterministic_confidence,
        "source_ref": norm["source_ref"],
        "project_key": norm["project_key"],
    }


_EMAIL_TASK_SYSTEM = (
    "You extract advisory action candidates from a metadata-safe email thread summary.\n"
    "Output ONLY a JSON object matching the Phase 10 ActionCandidate schema (no prose, no markdown).\n"
    "Use ONLY the provided summary text and the deterministic signal hints. Do not invent content.\n"
    "candidate_type must be task or commitment; source_refs must include the provided source ref;\n"
    "confidence 0.0-1.0; recommended_next_action=review; review_status=pending;\n"
    "external_action_requires_approval=true. High-stakes items (contract/legal/financial/payment/\n"
    "claim/entitlement/schedule/safety) must set safety_category accordingly and recommend review.\n"
)


def _is_bounded_content_eligible(policy: Any) -> bool:
    """True when the raw-content policy permits bounded local email content for model context."""
    try:
        rc = policy.raw_content
        return bool(rc.enabled and rc.model_context.include_raw_content and rc.starting_sources.email)
    except Exception:
        return False


def _build_input_window(
    summary: dict[str, Any],
    *,
    mode: str,
    signals: dict[str, Any],
    store: Optional[Any],
    project_key: Optional[str],
    policy: Any,
) -> tuple[str, str, list[str], Optional[str], list[str]]:
    """Build the (metadata-safe or policy-bounded) model input window for one summary.

    Returns (input_text, input_window_hash, source_refs, bounded_excerpt, blockers). The bounded
    excerpt is only populated in bounded_content mode and is itself length-bounded; raw content is
    never returned beyond that bounded excerpt.
    """
    norm = _normalize_summary(summary)
    blockers: list[str] = []
    bounded_excerpt: Optional[str] = None

    lines = [
        f"subject_redacted: {norm['subject'] or '(none)'}",
        f"summary_redacted: {norm['summary_text'] or '(none)'}",
        f"sender_domain: {norm['sender_domain'] or '(none)'}",
        f"received_at: {norm['received_at'] or '(none)'}",
        f"sent_by_user: {norm['sent_by_user']}",
        f"deterministic_signals: {','.join(signals['reason_codes'])}",
        f"candidate_type_hint: {signals['candidate_type_hint']}",
        f"waiting_state_hint: {signals['waiting_state_hint']}",
        f"source_ref: {norm['source_ref']}",
    ]

    if mode == "bounded_content":
        if _is_bounded_content_eligible(policy) and store is not None:
            # Lazy import: raw_context imports from the package root; importing it at module top
            # would create a circular import during package initialization.
            from .raw_context import build_raw_email_context_packet

            try:
                packet = build_raw_email_context_packet(
                    project_key=project_key or norm["project_key"], store=store, policy=policy
                )
                threads = (packet.get("content") or {}).get("threads") or []
                for th in threads[:1]:
                    for m in (th.get("messages") or [])[:1]:
                        body = _truncate(m.get("body_text") or th.get("thread_subject"), 400)
                        if body:
                            bounded_excerpt = body
                            lines.append(f"bounded_excerpt: {body}")
                        break
            except Exception:
                blockers.append("bounded_content_unavailable")
        else:
            blockers.append("bounded_content_not_eligible_fell_back_to_metadata_safe")

    input_text = "\n".join(lines)
    input_window_hash = (hash_summary(input_text) or {}).get("hash_prefix") or ""
    return input_text, input_window_hash, [norm["source_ref"]], bounded_excerpt, blockers


def _persist_candidate(
    *,
    store: Any,
    cand: ActionCandidate,
    project_key: Optional[str],
    bounded_excerpt: Optional[str],
) -> None:
    """Persist one accepted candidate + its source ref (caller gates on not-dry-run)."""
    candidate_id = uuid.uuid4().hex
    refs_key = hashlib.sha256("|".join(sorted(cand.source_refs)).encode("utf-8")).hexdigest()[:16]
    common: dict[str, Any] = {
        "candidate_id": candidate_id,
        "title_redacted": cand.title,
        "project_key": cand.project_key or project_key,
        "due_at_utc": cand.due_at,
        "urgency": cand.urgency,
        "waiting_state": cand.waiting_state,
        "safety_category": cand.safety_category,
        "confidence": cand.confidence,
        "reason_redacted": cand.reason,
        "recommended_next_action": cand.recommended_next_action,
        "review_status": cand.review_status,
        "model_profile_id": cand.model_profile_id,
        "prompt_template_version": cand.prompt_template_version,
    }
    if cand.candidate_type == "commitment":
        store.upsert_commitment_candidate(
            stable_key=f"email-commit:{refs_key}",
            commitment_actor_class=cand.assignee,
            **common,
        )
    else:
        store.upsert_task_candidate(
            stable_key=f"email-task:{refs_key}",
            assignee_class=cand.assignee,
            **common,
        )
    for ref in cand.source_refs:
        store.upsert_candidate_source_ref(
            source_ref_id=uuid.uuid4().hex,
            candidate_type=cand.candidate_type,
            candidate_id=candidate_id,
            source_family="email_thread_summary",
            source_ref_hash=str(ref),
            evidence_redacted=_truncate(bounded_excerpt, 400) if bounded_excerpt else None,
        )


def extract_email_task_candidates(
    *,
    summaries: Optional[list[dict[str, Any]]] = None,
    store: Optional[Any] = None,
    project_key: Optional[str] = None,
    mode: str = "metadata_safe",
    profile_id: str = "default_extract",
    profiles: Optional[Any] = None,
    backend: Optional[GenerationBackend] = None,
    mock_output: Optional[str] = None,
    dry_run: bool = True,
    max_items: int = 20,
    policy: Optional[Any] = None,
) -> dict[str, Any]:
    """Extract advisory task/commitment candidates from email thread summaries (dry-run default).

    Resolves summaries from the explicit ``summaries`` arg or, failing that,
    ``store.list_email_thread_summaries(...)``. For each summary it scores deterministic signals,
    builds a metadata-safe (or policy-bounded) window, runs the schema-enforced structured-output
    client, and — only when ``dry_run`` is False and a ``store`` is given — persists accepted
    task/commitment candidates + source refs. Returns counts, candidates, rejections, signal
    summary, and blockers. Never persists raw bodies/prompts/responses.
    """
    if mode not in MODES:
        raise ValueError(f"unknown mode {mode!r}")
    profiles = profiles or load_local_model_profiles()
    profile = next((p for p in profiles.profiles if p.profile_id == profile_id), None)
    if profile is None:
        raise ValueError(f"unknown profile_id {profile_id!r}")
    policy = policy if policy is not None else _safe_load_policy()

    effective_mode = mode
    blockers: list[str] = []
    if mode == "bounded_content" and not _is_bounded_content_eligible(policy):
        effective_mode = "metadata_safe"
        blockers.append("bounded_content_not_eligible_fell_back_to_metadata_safe")

    if summaries is None:
        summaries = (
            store.list_email_thread_summaries(project_key=project_key, limit=max_items)
            if store is not None
            else []
        )
    summaries = list(summaries)[:max_items]

    client = StructuredOutputClient()
    produced = accepted = rejected = persisted = 0
    backend_unavailable = False
    error_redacted: Optional[str] = None
    candidates: list[dict[str, Any]] = []
    rejections: list[dict[str, Any]] = []
    signals_summary: dict[str, int] = dict.fromkeys(REASON_CODES, 0)

    for summary in summaries:
        signals = score_email_task_signals(summary)
        for code in signals["reason_codes"]:
            signals_summary[code] = signals_summary.get(code, 0) + 1
        input_text, _hash, _refs, bounded_excerpt, win_blockers = _build_input_window(
            summary,
            mode=effective_mode,
            signals=signals,
            store=store,
            project_key=project_key,
            policy=policy,
        )
        blockers.extend(win_blockers)
        b = backend if backend is not None else StaticOutputClient(mock_output or "{}")
        result = client.run(
            schema=ActionCandidate,
            profile=profile,
            profiles=profiles,
            system=_EMAIL_TASK_SYSTEM,
            prompt="Extract the single best action candidate (or none) from this summary.",
            input_context=input_text,
            task_type="extract_email_tasks",
            backend=b,
            store=store if not dry_run else None,
            dry_run=dry_run,
        )
        produced += 1
        if result.status in {"unavailable", "timeout", "failed"}:
            backend_unavailable = True
            error_redacted = result.error_redacted or result.status
            continue
        if not result.schema_valid or not result.validated:
            rejected += 1
            rejections.append({"reason": result.status, "source_ref": signals["source_ref"]})
            continue
        try:
            cand = ActionCandidate.model_validate(result.validated)
        except Exception as exc:  # pragma: no cover - client already validated
            rejected += 1
            rejections.append({"reason": f"revalidate_failed:{str(exc)[:80]}"})
            continue
        biz = _validate_business_contract(cand)
        if biz or cand.candidate_type not in CANDIDATE_TYPES:
            rejected += 1
            rejections.append({"reason": biz or f"unsupported_type:{cand.candidate_type}"})
            continue
        accepted += 1
        candidates.append(cand.model_dump(mode="json"))
        if not dry_run and store is not None:
            _persist_candidate(
                store=store, cand=cand, project_key=project_key, bounded_excerpt=bounded_excerpt
            )
            persisted += 1

    return {
        "mode": effective_mode,
        "requested_mode": mode,
        "produced": produced,
        "accepted": accepted,
        "rejected": rejected,
        "persisted": persisted,
        "backend_unavailable": backend_unavailable,
        "error_redacted": error_redacted,
        "candidates": candidates,
        "rejections": rejections,
        "signals_summary": signals_summary,
        "blockers": sorted(set(blockers)),
    }


def _safe_load_policy() -> Any:
    try:
        return load_raw_content_policy()
    except Exception:
        return None
