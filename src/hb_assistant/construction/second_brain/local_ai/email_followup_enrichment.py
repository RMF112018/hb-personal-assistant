"""Phase 10 V45 — email follow-up raw enrichment engine + review-safe persistence.

Connects the deterministic accepted follow-up candidates (``accepted_tasks`` / ``accepted_commitments``
+ their ``follow_up_watch_items``) to the bounded raw window builder, the local-only model route, and
the review-safe V45 persistence. Dry-run is the default (zero writes); apply requires a positive
``max_persist`` cap and is idempotent. Only structured/redacted fields + hashes + source refs are
ever written — a final raw-leak guard scans every persisted text/JSON field before any write.

Public entry point:
    run_email_followup_enrichment(*, store, now_utc=None, candidate_id=None, include_closed=False,
        limit=200, dry_run=True, max_persist=None, profiles=None, routing=None, present_models=None,
        backend=None, mock_output=None, caps=None, user_domains=(), high_confidence=...,
        medium_confidence=...) -> dict
"""

from __future__ import annotations

import hashlib
import uuid
from typing import Any, Optional

from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

from .contracts import load_local_model_profiles
from .email_followup_models import (
    DEFAULT_HIGH_CONFIDENCE,
    DEFAULT_MEDIUM_CONFIDENCE,
    MODEL_TASK,
    PROMPT_TEMPLATE_VERSION,
    confidence_band_for,
)
from .email_followup_route import (
    find_raw_leak,
    run_email_followup_model,
)
from .raw_followup_window import (
    RawWindowCaps,
    build_raw_followup_window,
)
from .structured_output import GenerationBackend

# Email source families that make a candidate eligible (must resolve to local raw email rows).
_EMAIL_FAMILIES = frozenset(
    {
        "email_message",
        "email_thread",
        "email_thread_summary",
        "email_message_raw_content",
        "email_thread_raw_context",
    }
)
_TERMINAL_STATUSES = frozenset({"done", "completed", "closed", "resolved", "complete"})


def compute_idempotency_key(
    *,
    candidate_id: str,
    watch_item_id: Optional[str],
    message_ref_hashes: list[str],
    raw_excerpt_hash: str,
    model_task: str = MODEL_TASK,
    prompt_template_version: str = PROMPT_TEMPLATE_VERSION,
    schema_version: int = LATEST_SCHEMA_VERSION,
) -> str:
    """Deterministic idempotency key for one enrichment (stable across identical re-runs)."""
    parts = [
        candidate_id,
        watch_item_id or "",
        "|".join(sorted(message_ref_hashes)),
        raw_excerpt_hash,
        model_task,
        prompt_template_version,
        str(schema_version),
    ]
    digest = hashlib.sha256("\x1f".join(parts).encode("utf-8")).hexdigest()[:32]
    return f"efe-{digest}"


def _watch_index(store: Any) -> dict[str, dict[str, Any]]:
    """Map accepted_task_id/accepted_commitment_id -> its follow-up watch item (if any)."""
    idx: dict[str, dict[str, Any]] = {}
    for w in store.list_follow_up_watch_items(limit=100000):
        for key in ("accepted_task_id", "accepted_commitment_id"):
            v = w.get(key)
            if v:
                idx[str(v)] = w
    return idx


def select_eligible_candidates(
    *,
    store: Any,
    candidate_id: Optional[str] = None,
    include_closed: bool = False,
    limit: int = 200,
) -> list[dict[str, Any]]:
    """Select deterministic accepted task/commitment units that are email-source-linked + open.

    Returns candidate_meta dicts (candidate_id, candidate_type, accepted_id, watch_item_id,
    title_redacted, waiting_state, project_key, due_at_utc, status, email source refs). Closed/
    completed items are excluded unless ``include_closed``. Filters to one ``candidate_id`` when
    given. No model call, no window build here.
    """
    watch_idx = _watch_index(store)
    units: list[tuple[str, str, dict[str, Any]]] = []
    for row in store.list_accepted_tasks(limit=limit):
        units.append(("task", str(row.get("accepted_task_id")), row))
    for row in store.list_accepted_commitments(limit=limit):
        units.append(("commitment", str(row.get("accepted_commitment_id")), row))

    selected: list[dict[str, Any]] = []
    for kind, accepted_id, row in units:
        cid = str(row.get("candidate_id") or "")
        if candidate_id is not None and candidate_id not in (cid, accepted_id):
            continue
        watch = watch_idx.get(accepted_id)
        # Closed gate (status, completed timestamp, or terminal watch status).
        status = (row.get("status") or "").strip().lower()
        watch_status = (watch or {}).get("watch_status", "").strip().lower()
        is_closed = (
            bool(row.get("completed_utc"))
            or status in _TERMINAL_STATUSES
            or watch_status == "closed"
        )
        if is_closed and not include_closed:
            continue
        # Email source-ref gate.
        refs = [
            r
            for r in store.list_candidate_source_refs(
                candidate_id=cid, candidate_type=kind, limit=1000
            )
            if str(r.get("source_family") or "") in _EMAIL_FAMILIES
        ]
        if not refs:
            continue
        selected.append(
            {
                "candidate_id": cid,
                "candidate_type": kind,
                "accepted_id": accepted_id,
                "watch_item_id": (watch or {}).get("watch_item_id"),
                "title_redacted": row.get("title_redacted"),
                "waiting_state": row.get("waiting_state"),
                "project_key": row.get("project_key"),
                "due_at_utc": row.get("due_at_utc"),
                "status": row.get("status"),
                "is_closed": is_closed,
                "source_refs": refs,
            }
        )
    return selected


def _persisted_text_fields(
    *,
    enriched_title: str,
    suggested_next_action: str,
    assignee_display: str,
    reason_codes: list[str],
    source_refs: list[str],
) -> list[str]:
    """Every persisted text / JSON-list field, individually, for the pre-write leak guard."""
    fields = [enriched_title, suggested_next_action, assignee_display]
    fields.extend(reason_codes)
    fields.extend(source_refs)
    return [f for f in fields if f]


def run_email_followup_enrichment(
    *,
    store: Any,
    now_utc: Optional[str] = None,
    candidate_id: Optional[str] = None,
    include_closed: bool = False,
    limit: int = 200,
    dry_run: bool = True,
    max_persist: Optional[int] = None,
    profiles: Optional[Any] = None,
    routing: Optional[Any] = None,
    present_models: Optional[set[str]] = None,
    backend: Optional[GenerationBackend] = None,
    mock_output: Optional[str] = None,
    caps: Optional[RawWindowCaps] = None,
    user_domains: tuple[str, ...] = (),
    high_confidence: float = DEFAULT_HIGH_CONFIDENCE,
    medium_confidence: float = DEFAULT_MEDIUM_CONFIDENCE,
) -> dict[str, Any]:
    """Enrich eligible follow-up candidates from bounded raw email context (dry-run default).

    For each eligible candidate: build a bounded sanitized window (no persistence), run the local
    model (fail-closed), validate, scan every persisted field for raw leakage, then — only when
    ``dry_run`` is False with a positive ``max_persist`` — upsert a review-safe V45 row (idempotent).
    Returns a raw-free summary. Missing raw / unavailable model / no eligible items degrade cleanly.
    """
    if not dry_run and (max_persist is None or max_persist <= 0):
        raise ValueError("apply requires a positive max_persist cap")
    profiles = profiles or load_local_model_profiles()
    caps = caps or RawWindowCaps()

    candidates = select_eligible_candidates(
        store=store, candidate_id=candidate_id, include_closed=include_closed, limit=limit
    )

    would_persist = 0
    persisted = 0
    model_unavailable = False
    enrichments: list[dict[str, Any]] = []
    skipped: list[dict[str, Any]] = []
    remaining = max_persist if (not dry_run and max_persist is not None) else None

    for meta in candidates:
        window = build_raw_followup_window(
            candidate_id=meta["candidate_id"],
            candidate_type=meta["candidate_type"],
            source_refs=meta["source_refs"],
            store=store,
            caps=caps,
            user_domains=user_domains,
        )
        if not window.available:
            skipped.append(
                {
                    "candidate_id": meta["candidate_id"],
                    "watch_item_id": meta["watch_item_id"],
                    "reason": "no_raw_content_available",
                    "blockers": window.blockers,
                }
            )
            continue

        model_res = run_email_followup_model(
            window=window,
            candidate_meta=meta,
            profiles=profiles,
            routing=routing,
            present_models=present_models,
            backend=backend,
            mock_output=mock_output,
            store=store if not dry_run else None,
            dry_run=dry_run,
        )
        status = model_res["status"]
        if status == "blocked":
            model_unavailable = True
            skipped.append(
                {
                    "candidate_id": meta["candidate_id"],
                    "watch_item_id": meta["watch_item_id"],
                    "reason": "model_unavailable",
                    "blockers": model_res.get("blockers", []),
                }
            )
            continue
        if status == "degraded":
            model_unavailable = True
            skipped.append(
                {
                    "candidate_id": meta["candidate_id"],
                    "watch_item_id": meta["watch_item_id"],
                    "reason": "model_degraded",
                    "error_redacted": model_res.get("error_redacted"),
                }
            )
            continue
        if status != "ok" or not model_res.get("validated"):
            skipped.append(
                {
                    "candidate_id": meta["candidate_id"],
                    "watch_item_id": meta["watch_item_id"],
                    "reason": "validation_failed",
                    "violations": model_res.get("violations", []),
                }
            )
            continue

        out = model_res["validated"]
        source_refs = sorted(
            set(window.source_aliases)
            | {str(r.get("source_ref_hash")) for r in meta["source_refs"] if r.get("source_ref_hash")}
        )
        reason_codes = list(out.get("reason_codes") or [])
        enriched_title = str(out["enriched_title"])
        suggested_next_action = str(out.get("suggested_next_action") or "")
        assignee_display = str(out.get("assignee_display") or "")

        # Final defense-in-depth leak guard: scan EVERY persisted text/JSON field individually.
        leak_field = None
        for value in _persisted_text_fields(
            enriched_title=enriched_title,
            suggested_next_action=suggested_next_action,
            assignee_display=assignee_display,
            reason_codes=reason_codes,
            source_refs=source_refs,
        ):
            leak = find_raw_leak(value)
            if leak is not None:
                leak_field = leak
                break
        if leak_field is not None:
            skipped.append(
                {
                    "candidate_id": meta["candidate_id"],
                    "watch_item_id": meta["watch_item_id"],
                    "reason": "raw_leak_detected",
                    "leak": leak_field,
                }
            )
            continue

        confidence = float(out["confidence"])
        band = confidence_band_for(
            confidence, high=high_confidence, medium=medium_confidence
        )
        idem = compute_idempotency_key(
            candidate_id=meta["candidate_id"],
            watch_item_id=meta["watch_item_id"],
            message_ref_hashes=window.message_ref_hashes,
            raw_excerpt_hash=window.raw_excerpt_hash,
        )
        would_persist += 1
        entry = {
            "candidate_id": meta["candidate_id"],
            "candidate_type": meta["candidate_type"],
            "watch_item_id": meta["watch_item_id"],
            "review_status": "pending",
            "enriched_title": enriched_title,
            "waiting_state": out["waiting_state"],
            "assignee_type": out["assignee_type"],
            "suggested_next_action": suggested_next_action,
            "due_at_utc": out.get("due_at_utc"),
            "confidence": confidence,
            "confidence_band": band,
            "reason_codes": reason_codes,
            "source_refs": source_refs,
            "raw_excerpt_hash": window.raw_excerpt_hash,
            "persisted": False,
        }

        if not dry_run and remaining is not None and remaining > 0:
            store.upsert_email_followup_enrichment(
                enrichment_id=uuid.uuid4().hex,
                idempotency_key=idem,
                source_candidate_id=meta["candidate_id"],
                source_candidate_type=meta["candidate_type"],
                raw_excerpt_hash=window.raw_excerpt_hash,
                enriched_title=enriched_title,
                waiting_state=out["waiting_state"],
                assignee_type=out["assignee_type"],
                confidence=confidence,
                confidence_band=band,
                input_context_hash=model_res.get("input_context_hash") or "",
                output_hash=model_res.get("output_hash") or "",
                prompt_template_version=PROMPT_TEMPLATE_VERSION,
                watch_item_id=meta["watch_item_id"],
                email_thread_ref_hash=window.thread_ref_hash,
                email_message_ref_hashes=window.message_ref_hashes,
                assignee_display=assignee_display or None,
                suggested_next_action=suggested_next_action or None,
                due_at_utc=out.get("due_at_utc"),
                reason_codes=reason_codes,
                source_refs=source_refs,
                model_profile_id=model_res.get("route", {}).get("selected_profile"),
                model_task=MODEL_TASK,
            )
            persisted += 1
            remaining -= 1
            entry["persisted"] = True
        enrichments.append(entry)

    note = None
    if not candidates:
        note = "no_eligible_candidates"

    return {
        "command": "second-brain follow-up-watch enrich",
        "ok": True,
        "mode": "dry_run" if dry_run else "apply",
        "with_raw_enrichment": True,
        "applied": not dry_run,
        "max_persist": max_persist,
        "note": note,
        "eligible": len(candidates),
        "would_persist": would_persist,
        "persisted": persisted,
        "model_unavailable": model_unavailable,
        "enrichments": enrichments,
        "skipped": skipped,
        "guardrails": {
            "dry_run_default": True,
            "apply_requires_max_persist": True,
            "idempotent": True,
            "source_linked_only": True,
            "no_raw_persistence": True,
            "no_cloud": True,
            "no_writeback": True,
            "local_only": True,
        },
    }
