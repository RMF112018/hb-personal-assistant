"""Phase 10 V52 — daily-brief effectiveness packet builder (read-only join layer).

Builds raw-free evaluation packets by joining the V51 ranking/assembly overlay to the V50 lifecycle
read model, ``candidate_source_refs`` counts, local-model receipts, and advisory similarity edges.
Pure and read-only by default — it reads structured/redacted/hashed metadata only and mutates
nothing. The persisted exposure/outcome rows are *derived* facts produced by the helpers here and
written only by the apply path (never here).

Exposure events are **persisted V51 surfaced-item exposure proxies** — they record that a ranked /
assembled item was surfaced to the operator (the persisted ranking/assembly rows are that record).
They are NOT confirmed render impressions. Outcome events are derived from the V50 lifecycle read
model; absent feedback is never treated as acceptance and is only called ``ignored`` after the
configured lag window (default 72h).

Join map (``references/join_path_contract.md``):
    ranking run -> ranked candidate -> daily_brief_action_candidate_id -> candidate_source_refs
    ranked candidate -> review-queue subject -> V50 lifecycle state / lifecycle events
    ranked candidate -> model receipt / profile metadata
    ranked candidate/group -> similarity/duplicate edge metadata
    ranked candidate -> source family / candidate family / project_key
"""

from __future__ import annotations

import hashlib
from datetime import datetime
from typing import Any, Optional

from . import candidate_lifecycle as lc
from .candidate_lifecycle_read_model import build_review_queue
from .candidate_ranking_packets import _candidate_id
from .daily_brief_effectiveness_metrics import (
    DEFAULT_IGNORED_LAG_HOURS,
    IGNORED,
    REOPENED,
    STALE_NO_ACTION,
    outcome_weight,
)
from .model_eval_metrics import scan_text_for_forbidden

#: Canonical V50 disposition states → telemetry outcome types.
_DISPOSITION_STATE_TO_OUTCOME: dict[str, str] = {
    lc.STATE_ACCEPTED: "accepted",
    lc.STATE_REJECTED: "rejected",
    lc.STATE_SNOOZED: "snoozed",
    lc.STATE_MERGED: "merged",
    lc.STATE_SUPPRESSED: "suppressed",
    lc.STATE_CLOSED: "closed",
}

#: Local-model receipt task type used by the V51 ranking/assembly overlay.
RANKING_TASK_TYPE = "candidate_ranking_brief_assembly"

#: Stable value for normalized-missing rollup dimensions (refinement #6).
UNKNOWN = "unknown"

# Status codes.
STATUS_OK = "ok"
STATUS_DEGRADED = "degraded"
STATUS_NO_RANKED_BRIEFS = "no_ranked_briefs"
STATUS_INSUFFICIENT_OUTCOME = "insufficient_outcome_data"


def normalize_dim(value: Optional[str]) -> str:
    """Normalize a missing/empty rollup dimension to ``unknown`` for stable scope keys."""
    v = (value or "").strip()
    return v or UNKNOWN


def _exposure_time(brief_date: str) -> str:
    """Deterministic exposure-proxy time for a brief date (noon UTC, matching the daily run)."""
    return f"{brief_date}T12:00:00+00:00"


def _parse_iso(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    try:
        return datetime.fromisoformat(value.replace("Z", "+00:00"))
    except ValueError:
        return None


def _hours_between(start_iso: str, end_iso: Optional[str]) -> Optional[float]:
    start = _parse_iso(start_iso)
    end = _parse_iso(end_iso)
    if start is None or end is None:
        return None
    return round((end - start).total_seconds() / 3600.0, 4)


def _is_procore(*, source_family: str, section_key: str, candidate_family: str) -> bool:
    blob = f"{source_family}|{section_key}|{candidate_family}".lower()
    return "procore" in blob


def _artifact_hash(ranking_run: dict[str, Any]) -> str:
    seed = "|".join(
        (
            str(ranking_run.get("ranking_run_id") or ""),
            str(ranking_run.get("candidate_set_hash") or ""),
            str(ranking_run.get("feedback_digest_hash") or ""),
        )
    )
    return hashlib.sha256(seed.encode("utf-8")).hexdigest()[:32]


def _index_lifecycle_events(store: Any) -> dict[tuple[str, str], list[dict[str, Any]]]:
    """Index lifecycle events by (subject_type, subject_id), newest first within each subject."""
    events = store.list_lifecycle_events(limit=100000)
    index: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for ev in events:
        key = (str(ev.get("subject_type")), str(ev.get("subject_id")))
        index.setdefault(key, []).append(ev)
    for key in index:
        index[key].sort(key=lambda e: str(e.get("created_utc") or ""), reverse=True)
    return index


def _derive_item_outcome(
    *,
    lifecycle_state: str,
    subject_events: list[dict[str, Any]],
    exposure_time: str,
    now_utc: str,
    ignored_lag_hours: int,
) -> dict[str, Any]:
    """Return ``{outcome_type, outcome_weight, outcome_lag_hours, lifecycle_event_id}``.

    ``outcome_type`` is ``None`` for an open item still inside its lag window (pending, not ignored).
    Derived strictly from V50 lifecycle data; never inferred from rank and never a lifecycle write.
    """
    latest = subject_events[0] if subject_events else None
    if lifecycle_state in _DISPOSITION_STATE_TO_OUTCOME:
        outcome = _DISPOSITION_STATE_TO_OUTCOME[lifecycle_state]
        lifecycle_event_id = None
        lag = None
        if latest is not None:
            if str(latest.get("event_type") or "") == "reopen":
                outcome = REOPENED
            lifecycle_event_id = latest.get("lifecycle_event_id")
            lag = _hours_between(exposure_time, latest.get("created_utc"))
        return {
            "outcome_type": outcome,
            "outcome_weight": outcome_weight(outcome),
            "outcome_lag_hours": lag,
            "lifecycle_event_id": lifecycle_event_id,
        }

    # Open state: only call it ignored/stale once the lag window has elapsed.
    age = _hours_between(exposure_time, now_utc)
    if age is not None and age >= ignored_lag_hours:
        outcome = STALE_NO_ACTION if lifecycle_state == lc.STATE_STALE else IGNORED
        return {
            "outcome_type": outcome,
            "outcome_weight": outcome_weight(outcome),
            "outcome_lag_hours": None,
            "lifecycle_event_id": None,
        }
    return {
        "outcome_type": None,
        "outcome_weight": None,
        "outcome_lag_hours": None,
        "lifecycle_event_id": None,
    }


def build_effectiveness_packets(
    store: Any,
    *,
    window_start: str,
    window_end: str,
    now_utc: str,
    ignored_lag_hours: int = DEFAULT_IGNORED_LAG_HOURS,
    policy_version: Optional[str] = None,
    model_profile_id: Optional[str] = None,
) -> dict[str, Any]:
    """Build the read-only effectiveness packet for a brief-date window.

    Returns a dict with ``status``, sample sizes, per-candidate ``items``, derived ``exposure_events``
    and ``outcome_events`` (persist-ready, raw-free), ``ranking_runs`` metadata, filtered model
    ``receipts``, a ``similarity`` summary, and ``degradation`` flags. Reads only; writes nothing.
    """
    if window_end < window_start:
        window_start, window_end = window_end, window_start

    ranking_runs = [
        r
        for r in store.list_ranking_runs(limit=100000)
        if window_start <= str(r.get("brief_date") or "") <= window_end
        and (policy_version is None or str(r.get("policy_version") or "") == policy_version)
        and (model_profile_id is None or str(r.get("model_profile_id") or "") == model_profile_id)
    ]

    degradation: list[str] = []
    if not ranking_runs:
        return {
            "status": STATUS_NO_RANKED_BRIEFS,
            "window_start": window_start,
            "window_end": window_end,
            "ignored_lag_hours": ignored_lag_hours,
            "now_utc": now_utc,
            "briefs": [],
            "ranking_runs": [],
            "items": [],
            "exposure_events": [],
            "outcome_events": [],
            "receipts": [],
            "similarity": {"edge_count": 0, "reviewed_clusters": 0},
            "sample_size": {"briefs": 0, "candidates": 0, "outcomes": 0},
            "degradation": ["no_ranked_briefs"],
        }

    # One review-queue read (include hidden so dispositions like rejected/suppressed are visible).
    queue = build_review_queue(store, now_utc=now_utc, include_hidden=True)
    rq_by_cid: dict[str, dict[str, Any]] = {}
    for row in queue["rows"]:
        rq_by_cid[_candidate_id(row)] = row
    events_by_subject = _index_lifecycle_events(store)

    briefs = sorted({str(r.get("brief_date")) for r in ranking_runs})
    assembly_runs_by_date: dict[str, list[dict[str, Any]]] = {}
    for bdate in briefs:
        assembly_runs_by_date[bdate] = store.list_assembly_runs(brief_date=bdate, limit=1000)

    items: list[dict[str, Any]] = []
    exposure_events: list[dict[str, Any]] = []
    assembly_missing = False

    for run in ranking_runs:
        run_id = str(run.get("ranking_run_id"))
        bdate = str(run.get("brief_date"))
        rpolicy = run.get("policy_version")
        exposure_time = _exposure_time(bdate)
        artifact_hash = _artifact_hash(run)
        assemblies = assembly_runs_by_date.get(bdate, [])
        assembly_run_id = str(assemblies[0]["assembly_run_id"]) if assemblies else None
        if not assemblies:
            assembly_missing = True

        # Brief-level exposure proxy (one per ranking run).
        exposure_events.append(
            {
                "brief_date": bdate,
                "event_type": "brief_exposure_proxy",
                "ranking_run_id": run_id,
                "assembly_run_id": assembly_run_id,
                "section_key": None,
                "daily_brief_action_candidate_id": None,
                "rank_position": None,
                "exposure_surface": "persisted_ranking_overlay",
                "policy_version": rpolicy,
                "artifact_hash": artifact_hash,
            }
        )

        for ranked in store.list_ranked_candidates(ranking_run_id=run_id, limit=100000):
            cid = str(ranked.get("daily_brief_action_candidate_id"))
            rq = rq_by_cid.get(cid, {})
            section_key = str(ranked.get("section_key") or "")
            candidate_family = str(rq.get("family") or "")
            source_family = str(rq.get("source_family") or "")
            project_key = rq.get("project_key")
            lifecycle_state = str(rq.get("lifecycle_state") or lc.STATE_NEW)
            actionable = bool(rq.get("actionable"))
            _src_count = rq.get("source_ref_count")
            if _src_count is None:
                _src_count = ranked.get("source_ref_count")
            source_ref_count = int(_src_count or 0)
            subject_key = (str(rq.get("subject_type") or ""), str(rq.get("subject_id") or ""))
            outcome = _derive_item_outcome(
                lifecycle_state=lifecycle_state,
                subject_events=events_by_subject.get(subject_key, []),
                exposure_time=exposure_time,
                now_utc=now_utc,
                ignored_lag_hours=ignored_lag_hours,
            )

            exposure_events.append(
                {
                    "brief_date": bdate,
                    "event_type": "item_exposure_proxy",
                    "ranking_run_id": run_id,
                    "assembly_run_id": assembly_run_id,
                    "section_key": section_key or None,
                    "daily_brief_action_candidate_id": cid,
                    "rank_position": ranked.get("rank_position"),
                    "exposure_surface": "persisted_ranking_overlay",
                    "policy_version": rpolicy,
                    "artifact_hash": artifact_hash,
                }
            )

            items.append(
                {
                    "brief_date": bdate,
                    "ranking_run_id": run_id,
                    "assembly_run_id": assembly_run_id,
                    "policy_version": rpolicy,
                    "model_status": run.get("model_status"),
                    "model_profile_id": run.get("model_profile_id"),
                    "model_name": run.get("model_name"),
                    "feedback_calibration_version": run.get("feedback_digest_hash"),
                    "deterministic_fallback_used": bool(run.get("deterministic_fallback_used")),
                    "daily_brief_action_candidate_id": cid,
                    "rank_position": ranked.get("rank_position"),
                    "candidate_count": int(run.get("ranked_count") or 0),
                    "section_key": section_key,
                    "group_key": ranked.get("group_key"),
                    "duplicate_cluster_id": ranked.get("duplicate_cluster_id"),
                    "candidate_family": candidate_family,
                    "source_family": source_family,
                    "project_key": project_key,
                    "deterministic_score": ranked.get("deterministic_score"),
                    "feedback_score": ranked.get("feedback_score"),
                    "model_advisory_score": ranked.get("model_advisory_score"),
                    "final_score": ranked.get("final_score"),
                    "model_advisory_used": ranked.get("model_advisory_score") is not None,
                    "source_ref_count": source_ref_count,
                    "actionable": actionable,
                    "is_procore": _is_procore(
                        source_family=source_family,
                        section_key=section_key,
                        candidate_family=candidate_family,
                    ),
                    "outcome_type": outcome["outcome_type"],
                    "outcome_weight": outcome["outcome_weight"],
                    "outcome_lag_hours": outcome["outcome_lag_hours"],
                    "lifecycle_event_id": outcome["lifecycle_event_id"],
                }
            )

    outcome_events = derive_outcome_events(items, ignored_lag_hours=ignored_lag_hours)

    # Model receipts referenced by the window's ranking runs (metadata only).
    referenced = {str(r.get("model_receipt_id")) for r in ranking_runs if r.get("model_receipt_id")}
    receipts = [
        rc
        for rc in store.list_local_model_run_receipts(limit=100000)
        if str(rc.get("model_run_receipt_id")) in referenced
        or str(rc.get("task_type") or "") == RANKING_TASK_TYPE
    ]

    similarity_summary = _similarity_summary(store, briefs)

    outcomes_present = sum(1 for it in items if it.get("outcome_type"))

    # A fully deterministic (--no-client) run is a first-class success path: absent model receipts
    # are expected and informational, not a degradation. Missing receipts only degrade the run when
    # a ranking run actually reported model-assisted output yet left no receipt behind.
    model_was_used = any(
        str(r.get("model_status") or "") in ("ok", "model_enriched")
        and not bool(r.get("deterministic_fallback_used"))
        for r in ranking_runs
    )
    status_degrading: list[str] = []
    if assembly_missing:
        degradation.append("assembly_data_missing")
        status_degrading.append("assembly_data_missing")
    if not receipts:
        degradation.append(
            "model_telemetry_missing" if model_was_used else "model_telemetry_absent_expected"
        )
        if model_was_used:
            status_degrading.append("model_telemetry_missing")
    coverage_actionable = [it for it in items if it.get("actionable")]
    missing_refs = sum(1 for it in coverage_actionable if int(it.get("source_ref_count") or 0) == 0)
    if missing_refs:
        degradation.append("source_ref_coverage_incomplete")
        status_degrading.append("source_ref_coverage_incomplete")

    if outcomes_present == 0:
        status = STATUS_INSUFFICIENT_OUTCOME
    elif status_degrading:
        status = STATUS_DEGRADED
    else:
        status = STATUS_OK

    packet = {
        "status": status,
        "window_start": window_start,
        "window_end": window_end,
        "ignored_lag_hours": ignored_lag_hours,
        "now_utc": now_utc,
        "briefs": briefs,
        "ranking_runs": ranking_runs,
        "items": items,
        "exposure_events": exposure_events,
        "outcome_events": outcome_events,
        "receipts": receipts,
        "similarity": similarity_summary,
        "sample_size": {
            "briefs": len(briefs),
            "candidates": len(items),
            "outcomes": outcomes_present,
        },
        "degradation": degradation,
    }
    packet["raw_safety"] = _scan_packet(packet)
    return packet


def derive_exposure_events(packet: dict[str, Any]) -> list[dict[str, Any]]:
    """Return the persist-ready raw-free exposure-proxy rows from a built packet."""
    return list(packet.get("exposure_events", []))


def derive_outcome_events(
    items: list[dict[str, Any]], *, ignored_lag_hours: int = DEFAULT_IGNORED_LAG_HOURS
) -> list[dict[str, Any]]:
    """Return persist-ready raw-free outcome-event rows for items that carry an outcome.

    Pure: one row per item with a non-null ``outcome_type``. Never creates a lifecycle event.
    """
    rows: list[dict[str, Any]] = []
    for it in items:
        if not it.get("outcome_type"):
            continue
        rows.append(
            {
                "brief_date": it["brief_date"],
                "daily_brief_action_candidate_id": it["daily_brief_action_candidate_id"],
                "ranking_run_id": it.get("ranking_run_id"),
                "assembly_run_id": it.get("assembly_run_id"),
                "lifecycle_event_id": it.get("lifecycle_event_id"),
                "outcome_type": it["outcome_type"],
                "outcome_lag_hours": it.get("outcome_lag_hours"),
                "ignored_lag_hours": ignored_lag_hours,
                "rank_position": it.get("rank_position"),
                "section_key": it.get("section_key"),
                "candidate_family": it.get("candidate_family"),
                "project_key": it.get("project_key"),
                "source_ref_count": int(it.get("source_ref_count") or 0),
            }
        )
    return rows


def _similarity_summary(store: Any, briefs: list[str]) -> dict[str, Any]:
    edges: list[dict[str, Any]] = []
    for bdate in briefs:
        edges.extend(store.list_similarity_edges(brief_date=bdate, limit=100000))
    clusters = {str(e.get("cluster_id")) for e in edges if e.get("cluster_id")}
    return {"edge_count": len(edges), "reviewed_clusters": len(clusters)}


_SCAN_FIELDS = (
    "section_key",
    "exposure_surface",
    "policy_version",
    "candidate_family",
    "source_family",
    "project_key",
    "outcome_type",
)


def _scan_packet(packet: dict[str, Any]) -> dict[str, Any]:
    """Category-only redaction scan over the packet's free-text fields (raw-free attestation)."""
    categories: set[str] = set()
    for it in packet.get("items", []):
        for field in _SCAN_FIELDS:
            categories.update(scan_text_for_forbidden(_as_text(it.get(field))))
    for ev in packet.get("exposure_events", []):
        categories.update(scan_text_for_forbidden(_as_text(ev.get("section_key"))))
        categories.update(scan_text_for_forbidden(_as_text(ev.get("exposure_surface"))))
    return {"raw_free": not categories, "categories": sorted(categories)}


def _as_text(value: Any) -> Optional[str]:
    if value is None:
        return None
    return str(value)
