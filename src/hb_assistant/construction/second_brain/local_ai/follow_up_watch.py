"""Phase 10 — deterministic Follow-up Watch Monitor (advisory, no writeback).

Closes the local-agent chain after acceptance: the accepted tasks/commitments
(``accepted_tasks`` / ``accepted_commitments``) are scanned and each is classified
into a watch status from the follow-up contract
(``phase_10_follow_up_watch_contract.json`` → open / waiting_on_me /
waiting_on_others / possibly_resolved / stale / closed). Persistence — when
explicitly applied and capped — writes only ``follow_up_watch_items`` +
``follow_up_status_events`` (guard columns stay 0).

Pure/deterministic: the classifier never reads a clock. ``now_utc`` is passed in
by the caller (mirrors ``relationship_scoring`` and ``created_at_utc`` stamping),
so a given (row, now_utc) always yields the same status — re-runnable and
testable. No model is used; no raw bodies move (only redacted titles/excerpts and
source-ref hashes already present on the candidate's source refs).
"""

from __future__ import annotations

from datetime import datetime, timedelta
from typing import Any, Optional

# Watch statuses produced by the deterministic scan (subset of the contract's
# `statuses`; snoozed/suppressed are operator-only states, not auto-produced).
WATCH_OPEN = "open"
WATCH_WAITING_ON_ME = "waiting_on_me"
WATCH_WAITING_ON_OTHERS = "waiting_on_others"
WATCH_POSSIBLY_RESOLVED = "possibly_resolved"
WATCH_STALE = "stale"
WATCH_CLOSED = "closed"

_TERMINAL_STATUSES = {"done", "completed", "closed", "resolved", "complete"}
_DEFAULT_STALE_AFTER_DAYS = 14


def _parse_dt(value: Any) -> Optional[datetime]:
    """Parse an ISO-8601 UTC string to datetime (tolerant of a trailing ``Z``).

    Mirrors ``relationship_scoring._parse_dt``. Returns None on anything unparseable.
    """
    if not value or not isinstance(value, str):
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def classify_watch_status(
    *,
    waiting_state: Optional[str],
    status: Optional[str],
    due_at_utc: Optional[str],
    accepted_utc: Optional[str],
    now_utc: str,
    completed_utc: Optional[str] = None,
    stale_after_days: int = _DEFAULT_STALE_AFTER_DAYS,
) -> dict[str, Any]:
    """Deterministically classify one accepted item into a watch status.

    Pure: no clock read — ``now_utc`` is provided by the caller. First-match order:
      1. completed/terminal status        → closed (local_completion)
      2. due date passed (overdue)         → waiting_on_others if waiting on others,
                                             else waiting_on_me (due_date_passed)
      3. waiting_state == waiting_on_others → waiting_on_others
      4. waiting_state == waiting_on_me     → waiting_on_me
      5. aged past stale window, no due     → stale (source_stale)
      6. otherwise                          → open

    Returns: {watch_status, reason_codes, signal_type, stale_after_utc, next_check_utc}.
    ``signal_type`` is the best-fitting contract signal, else ``"reclassified"`` for a
    plain (re)scan with no external trigger.
    """
    now_dt = _parse_dt(now_utc)
    waiting = (waiting_state or "").strip().lower()
    norm_status = (status or "").strip().lower()
    reason_codes: list[str] = []

    # Deterministic stale window from accepted_utc (no clock).
    accepted_dt = _parse_dt(accepted_utc)
    stale_after_utc: Optional[str] = None
    if accepted_dt is not None:
        stale_after_utc = (accepted_dt + timedelta(days=stale_after_days)).isoformat()

    due_dt = _parse_dt(due_at_utc)
    # next_check defaults to the due date if known, else the stale boundary.
    next_check_utc = due_at_utc or stale_after_utc

    # 1. Terminal / completed.
    if completed_utc or norm_status in _TERMINAL_STATUSES:
        reason_codes.append("status_terminal")
        return {
            "watch_status": WATCH_CLOSED,
            "reason_codes": reason_codes,
            "signal_type": "local_completion",
            "stale_after_utc": stale_after_utc,
            "next_check_utc": next_check_utc,
        }

    # 2. Overdue (due date passed relative to now_utc).
    if due_dt is not None and now_dt is not None and due_dt < now_dt:
        reason_codes.append("overdue")
        ws = WATCH_WAITING_ON_OTHERS if waiting == "waiting_on_others" else WATCH_WAITING_ON_ME
        return {
            "watch_status": ws,
            "reason_codes": reason_codes,
            "signal_type": "due_date_passed",
            "stale_after_utc": stale_after_utc,
            "next_check_utc": next_check_utc,
        }

    # 3 / 4. Explicit waiting state.
    if waiting == "waiting_on_others":
        reason_codes.append("waiting_on_others")
        return {
            "watch_status": WATCH_WAITING_ON_OTHERS,
            "reason_codes": reason_codes,
            "signal_type": "reclassified",
            "stale_after_utc": stale_after_utc,
            "next_check_utc": next_check_utc,
        }
    if waiting == "waiting_on_me":
        reason_codes.append("waiting_on_me")
        return {
            "watch_status": WATCH_WAITING_ON_ME,
            "reason_codes": reason_codes,
            "signal_type": "reclassified",
            "stale_after_utc": stale_after_utc,
            "next_check_utc": next_check_utc,
        }

    # 5. Aged past the stale window with no due date.
    if (
        due_dt is None
        and accepted_dt is not None
        and now_dt is not None
        and stale_after_utc is not None
        and now_dt > _parse_dt(stale_after_utc)  # type: ignore[operator]
    ):
        reason_codes.append("aged_no_due")
        return {
            "watch_status": WATCH_STALE,
            "reason_codes": reason_codes,
            "signal_type": "source_stale",
            "stale_after_utc": stale_after_utc,
            "next_check_utc": next_check_utc,
        }

    # 6. Default: active/open.
    reason_codes.append("active")
    return {
        "watch_status": WATCH_OPEN,
        "reason_codes": reason_codes,
        "signal_type": "reclassified",
        "stale_after_utc": stale_after_utc,
        "next_check_utc": next_check_utc,
    }


def _first_source_ref(
    store: Any, *, candidate_id: str, candidate_type: str
) -> Optional[dict[str, Any]]:
    """Return the most recent source ref for a candidate, or None if it has none."""
    if not candidate_id:
        return None
    refs = store.list_candidate_source_refs(
        candidate_id=candidate_id, candidate_type=candidate_type, limit=1
    )
    return refs[0] if refs else None


def run_follow_up_watch_scan(
    *,
    store: Any,
    now_utc: str,
    limit: int = 200,
    dry_run: bool = True,
    max_persist: Optional[int] = None,
    stale_after_days: int = _DEFAULT_STALE_AFTER_DAYS,
) -> dict[str, Any]:
    """Scan accepted tasks/commitments → advisory follow-up watch items/status events.

    Dry-run is the default (zero writes). ``--apply`` (dry_run=False) requires
    ``max_persist`` and caps ACTUAL watch-item writes; once the cap is hit, remaining
    changed items are counted (``would_persist``) but not written. Items with no
    source refs are never persisted (``skipped_no_source_refs``). An item whose
    classification already matches its stored watch status is skipped
    (``skipped_existing``); a new/changed status upserts the watch item and inserts
    one status event. No raw content, no writeback.
    """
    if not dry_run and max_persist is None:
        raise ValueError("apply requires max_persist (cap on actual watch-item writes)")

    accepted_tasks = store.list_accepted_tasks(limit=limit)
    accepted_commitments = store.list_accepted_commitments(limit=limit)

    # Existing watch state, keyed by watch_item_id, for dedup vs same-status.
    existing = {
        str(w.get("watch_item_id")): str(w.get("watch_status"))
        for w in store.list_follow_up_watch_items(limit=100000)
    }

    by_status: dict[str, int] = {}
    summary = {
        "scanned": 0,
        "would_persist": 0,
        "persisted": 0,
        "status_events_written": 0,
        "skipped_existing": 0,
        "skipped_no_source_refs": 0,
    }
    results: list[dict[str, Any]] = []
    remaining: Optional[int] = max_persist if (not dry_run and max_persist is not None) else None

    units: list[tuple[str, str, str, dict[str, Any]]] = []
    for row in accepted_tasks:
        units.append(("task", str(row.get("accepted_task_id")), str(row.get("candidate_id")), row))
    for row in accepted_commitments:
        units.append(
            (
                "commitment",
                str(row.get("accepted_commitment_id")),
                str(row.get("candidate_id")),
                row,
            )
        )

    for kind, accepted_id, candidate_id, row in units:
        summary["scanned"] += 1
        cls = classify_watch_status(
            waiting_state=row.get("waiting_state"),
            status=row.get("status"),
            due_at_utc=row.get("due_at_utc"),
            accepted_utc=row.get("accepted_utc"),
            completed_utc=row.get("completed_utc"),
            now_utc=now_utc,
            stale_after_days=stale_after_days,
        )
        watch_status = cls["watch_status"]
        by_status[watch_status] = by_status.get(watch_status, 0) + 1

        watch_item_id = f"watch:{accepted_id}"
        entry: dict[str, Any] = {
            "kind": kind,
            "accepted_id": accepted_id,
            "watch_item_id": watch_item_id,
            "watch_status": watch_status,
            "reason_codes": cls["reason_codes"],
            "persisted": False,
        }

        # Source-ref gate: advisory items must be source-linked to persist.
        source_ref = _first_source_ref(store, candidate_id=candidate_id, candidate_type=kind)
        if source_ref is None:
            summary["skipped_no_source_refs"] += 1
            entry["skipped_reason"] = "no_source_refs"
            results.append(entry)
            continue

        prior_status = existing.get(watch_item_id)
        if prior_status == watch_status:
            summary["skipped_existing"] += 1
            entry["skipped_reason"] = "unchanged"
            results.append(entry)
            continue

        # New or status-changed item: would persist.
        summary["would_persist"] += 1
        if dry_run or (remaining is not None and remaining <= 0):
            results.append(entry)
            continue

        store.upsert_follow_up_watch_item(
            watch_item_id=watch_item_id,
            watch_status=watch_status,
            waiting_state=str(row.get("waiting_state") or "unknown"),
            accepted_task_id=accepted_id if kind == "task" else None,
            accepted_commitment_id=accepted_id if kind == "commitment" else None,
            project_key=row.get("project_key"),
            next_check_utc=cls["next_check_utc"],
            last_checked_utc=now_utc,
            stale_after_utc=cls["stale_after_utc"],
            reason_redacted=",".join(cls["reason_codes"]),
        )
        store.insert_follow_up_status_event(
            watch_item_id=watch_item_id,
            new_status=watch_status,
            prior_status=prior_status,
            signal_type=cls["signal_type"],
            source_ref_hash=source_ref.get("source_ref_hash"),
            evidence_redacted=source_ref.get("evidence_redacted"),
            confidence=source_ref.get("confidence"),
        )
        summary["persisted"] += 1
        summary["status_events_written"] += 1
        existing[watch_item_id] = watch_status
        if remaining is not None:
            remaining -= 1
        entry["persisted"] = True
        entry["prior_status"] = prior_status
        results.append(entry)

    note = None
    if summary["scanned"] == 0:
        note = "no_accepted_items"

    return {
        "command": "second-brain follow-up-watch scan",
        "ok": True,
        "applied": not dry_run,
        "now_utc": now_utc,
        "limit": limit,
        "max_persist": max_persist,
        "note": note,
        "summary": summary,
        "by_status": by_status,
        "guardrails": {
            "dry_run_default": True,
            "apply_requires_max_persist": True,
            "deterministic_no_clock": True,
            "source_linked_only": True,
            "no_raw_persistence": True,
            "no_writeback": True,
            "advisory_only": True,
        },
        "results": results,
    }
