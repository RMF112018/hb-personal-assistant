"""Phase 10 V52 — local-model profile evaluator (receipt metadata only).

Measures reliability and advisory utility of the local model profiles used by the ranking/assembly
overlay, from ``local_model_run_receipts`` metadata and ranking-run status only. Never calls a
model, never reads a raw prompt/response, never stores raw output. Aggregates are advisory and
observational. Small samples are flagged.
"""

from __future__ import annotations

from typing import Any, Optional

from . import daily_brief_effectiveness_metrics as M
from .daily_brief_effectiveness_packets import RANKING_TASK_TYPE, normalize_dim

# Receipt status codes that count as degradation (mirrors the ranking overlay's honest statuses).
_TIMEOUT_STATUSES = frozenset({"timeout"})
_SCHEMA_INVALID_STATUSES = frozenset({"invalid_json", "schema_invalid"})
_SUCCESS_STATUSES = frozenset({"ok"})

# Ranking-run degraded reasons that map to safety-withheld / unknown-alias / lifecycle-excluded.
_WITHHELD_REASONS = frozenset({"raw_leak_in_model_output", "all_model_advice_dropped"})


def _percentile(values: list[float], pct: float) -> Optional[float]:
    """Deterministic nearest-rank percentile (e.g. ``pct=95``). ``None`` for an empty list."""
    if not values:
        return None
    ordered = sorted(values)
    if len(ordered) == 1:
        return round(ordered[0], 2)
    rank = max(1, min(len(ordered), int(round((pct / 100.0) * len(ordered) + 0.5))))
    return round(ordered[rank - 1], 2)


def evaluate_model_profiles(packet: dict[str, Any]) -> list[dict[str, Any]]:
    """Aggregate per-(model_profile_id, model_name) reliability rows over the window's receipts.

    When there are no receipts, returns a single ``model_telemetry_missing`` row so the report can
    state honestly that no model telemetry was available (deterministic-only window).
    """
    receipts = [
        rc
        for rc in packet.get("receipts", [])
        if str(rc.get("task_type") or "") == RANKING_TASK_TYPE
    ]
    runs = packet.get("ranking_runs", [])
    window_start = packet["window_start"]
    window_end = packet["window_end"]

    if not receipts:
        return [
            {
                "window_start": window_start,
                "window_end": window_end,
                "task_type": RANKING_TASK_TYPE,
                "model_profile_id": None,
                "model_name": None,
                "attempt_count": 0,
                "success_count": 0,
                "schema_invalid_count": 0,
                "safety_withheld_count": 0,
                "timeout_count": 0,
                "unknown_alias_count": 0,
                "lifecycle_excluded_ref_count": 0,
                "fallback_count": 0,
                "avg_latency_ms": None,
                "p95_latency_ms": None,
                "advisory_adoption_proxy": None,
                "model_degradation_rate": None,
                "sample_sufficient": False,
                "status": "model_telemetry_missing",
                "advisory": True,
            }
        ]

    # Map model_receipt_id -> ranking-run degraded reason for withheld/unknown-alias attribution.
    run_reason_by_receipt = {
        str(r.get("model_receipt_id")): str(r.get("degraded_reason") or "")
        for r in runs
        if r.get("model_receipt_id")
    }

    groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
    for rc in receipts:
        key = (normalize_dim(rc.get("profile_id")), normalize_dim(rc.get("model_name")))
        groups.setdefault(key, []).append(rc)

    rows: list[dict[str, Any]] = []
    for (profile_id, model_name), group in sorted(groups.items()):
        attempts = len(group)
        success = sum(
            1
            for rc in group
            if str(rc.get("status")) in _SUCCESS_STATUSES and rc.get("schema_valid")
        )
        schema_invalid = sum(
            1
            for rc in group
            if str(rc.get("status")) in _SCHEMA_INVALID_STATUSES or rc.get("schema_valid") is False
        )
        timeout = sum(1 for rc in group if str(rc.get("status")) in _TIMEOUT_STATUSES)
        fallback = sum(1 for rc in group if rc.get("fallback_used"))
        withheld = sum(
            1
            for rc in group
            if run_reason_by_receipt.get(str(rc.get("model_run_receipt_id")), "")
            in _WITHHELD_REASONS
        )
        unknown_alias = sum(
            1
            for rc in group
            if run_reason_by_receipt.get(str(rc.get("model_run_receipt_id")), "")
            == "all_model_advice_dropped"
        )
        latencies = [float(rc["latency_ms"]) for rc in group if rc.get("latency_ms") is not None]
        avg_latency = round(sum(latencies) / len(latencies), 2) if latencies else None
        degraded = attempts - success
        degradation_rate = M.model_degradation_rate(degraded, attempts)
        adoption = _adoption_proxy(packet, profile_id)

        rows.append(
            {
                "window_start": window_start,
                "window_end": window_end,
                "task_type": RANKING_TASK_TYPE,
                "model_profile_id": profile_id,
                "model_name": model_name,
                "attempt_count": attempts,
                "success_count": success,
                "schema_invalid_count": schema_invalid,
                "safety_withheld_count": withheld,
                "timeout_count": timeout,
                "unknown_alias_count": unknown_alias,
                "lifecycle_excluded_ref_count": 0,
                "fallback_count": fallback,
                "avg_latency_ms": avg_latency,
                "p95_latency_ms": _percentile(latencies, 95),
                "advisory_adoption_proxy": adoption,
                "model_degradation_rate": degradation_rate,
                "sample_sufficient": attempts >= M.MIN_OUTCOME_SAMPLE,
                "status": "ok",
                "advisory": True,
            }
        )
    return rows


def _adoption_proxy(packet: dict[str, Any], profile_id: str) -> Optional[float]:
    """Positively-acted items with model advice / positively-acted items with model advice available."""
    items = [
        it
        for it in packet.get("items", [])
        if normalize_dim(it.get("model_profile_id")) == profile_id and it.get("model_advisory_used")
    ]
    if not items:
        return None
    positives = sum(1 for it in items if it.get("outcome_type") in M.POSITIVE_OUTCOMES)
    return M.advisory_adoption_proxy(positives, len(items))
