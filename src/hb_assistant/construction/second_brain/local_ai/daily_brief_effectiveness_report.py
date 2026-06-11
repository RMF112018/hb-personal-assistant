"""Phase 10 V52 — raw-free daily-brief effectiveness report / dashboard.

Renders the effectiveness packet + evaluators + rollups into a raw-free JSON payload and a Markdown
report (CLI/report-first surface per ``references/dashboard_report_contract.md``). Every emitted
field is a count, rate, score, id, hash, family, section, project key, or reason code — never a raw
title/body/URL/token/path. The renderer scans its own output and reports a category-only attestation.
"""

from __future__ import annotations

import json
from typing import Any, Optional

from . import daily_brief_effectiveness_metrics as M
from .daily_brief_effectiveness_packets import (
    STATUS_INSUFFICIENT_OUTCOME,
    STATUS_NO_RANKED_BRIEFS,
    build_effectiveness_packets,
)
from .effectiveness_rollups import build_rollups
from .model_eval_metrics import scan_text_for_forbidden
from .model_profile_evaluator import evaluate_model_profiles
from .procore_noise_evaluator import evaluate_procore_noise, evaluate_source_families
from .ranking_policy_evaluator import EVAL_MODES, evaluate_ranking_policy

_GUARDRAILS = {
    "observational_only": True,
    "no_lifecycle_mutation": True,
    "no_source_ref_mutation": True,
    "no_external_writeback": True,
    "raw_free": True,
}


def build_effectiveness_report(
    packet: dict[str, Any], ranking_eval: dict[str, Any]
) -> dict[str, Any]:
    """Assemble the raw-free effectiveness report (JSON payload + Markdown + scan attestation)."""
    model_profiles = evaluate_model_profiles(packet)
    procore = evaluate_procore_noise(packet)
    source_families = evaluate_source_families(packet)
    metrics = ranking_eval.get("metrics", {})

    sample = packet.get("sample_size", {})
    sufficient = ranking_eval.get("sample_sufficient", False)
    status = packet.get("status")

    payload: dict[str, Any] = {
        "command": "second-brain daily-brief evaluate-effectiveness",
        "status": status,
        "window_start": packet["window_start"],
        "window_end": packet["window_end"],
        "ignored_lag_hours": packet.get("ignored_lag_hours", M.DEFAULT_IGNORED_LAG_HOURS),
        "data_sufficiency": "sufficient" if sufficient else "insufficient_sample",
        "confidence_note": ranking_eval.get("confidence_note", "observational_only"),
        "sample_size": sample,
        "metrics": metrics,
        "outcome_distribution": _outcome_distribution(packet),
        "source_ref_coverage": metrics.get("source_ref_coverage"),
        "procore_noise": {
            "exposed_procore_candidates": procore.get("exposed_procore_candidates"),
            "procore_noise_score": procore.get("procore_noise_score"),
            "top_noisy_groups": procore.get("top_noisy_groups"),
            "recommendations": procore.get("recommendations"),
            "advisory": True,
        },
        "source_families": source_families,
        "model_profiles": model_profiles,
        "duplicate_similarity": _duplicate_block(packet),
        "feedback_calibration_lift": metrics.get("deterministic_vs_model_delta"),
        "degradation": packet.get("degradation", []),
        "next_tuning_actions": _tuning_actions(packet, metrics, procore),
        "guardrails": _GUARDRAILS,
    }

    markdown = _render_markdown(payload)
    payload["markdown"] = markdown
    payload["raw_safety"] = _scan_payload(payload, markdown)
    return payload


def _outcome_distribution(packet: dict[str, Any]) -> dict[str, int]:
    dist: dict[str, int] = {}
    for it in packet.get("items", []):
        outcome = it.get("outcome_type")
        if outcome:
            dist[outcome] = dist.get(outcome, 0) + 1
    return dist


def _duplicate_block(packet: dict[str, Any]) -> dict[str, Any]:
    reviewed = int(packet.get("similarity", {}).get("reviewed_clusters") or 0)
    merged = sum(1 for it in packet.get("items", []) if it.get("outcome_type") == M.MERGED)
    proxy = M.duplicate_precision_proxy(merged, reviewed)
    return {
        "reviewed_clusters": reviewed,
        "edge_count": packet.get("similarity", {}).get("edge_count", 0),
        "duplicate_precision_proxy": proxy["value"],
        "insufficient_sample": proxy["insufficient_sample"],
    }


def _tuning_actions(
    packet: dict[str, Any], metrics: dict[str, Any], procore: dict[str, Any]
) -> list[str]:
    """Raw-free, advisory next-tuning actions with a metric basis (never auto-applied)."""
    actions: list[str] = []
    coverage = metrics.get("source_ref_coverage")
    if coverage is not None and coverage < 1.0:
        actions.append(
            f"investigate_source_ref_coverage: coverage={coverage} (<1.0 — some surfaced "
            "actionable items lack source refs)"
        )
    ignored = metrics.get("ignored_rate")
    if ignored is not None and ignored >= 0.4:
        actions.append(
            f"review_low_engagement: ignored_rate={ignored} after {packet.get('ignored_lag_hours')}h "
            "lag window"
        )
    actions.extend(procore.get("recommendations", []))
    degradation_rate = metrics.get("model_degradation_rate")
    if degradation_rate is not None and degradation_rate >= 0.5:
        actions.append(
            f"review_model_reliability: model_degradation_rate={degradation_rate} (deterministic "
            "fallback dominated)"
        )
    if not actions:
        actions.append("no_tuning_recommended: metrics within normal observational ranges")
    return actions


def _fmt(value: Any) -> str:
    if value is None:
        return "—"
    return str(value)


def _render_markdown(payload: dict[str, Any]) -> str:
    m = payload["metrics"]
    dist = payload["outcome_distribution"]
    procore = payload["procore_noise"]
    dup = payload["duplicate_similarity"]
    sample = payload["sample_size"]
    lines = [
        f"# Daily Brief Effectiveness — {payload['window_start']} to {payload['window_end']}",
        "",
        f"_Status:_ {payload['status']}",
        "",
        f"_Data sufficiency:_ {payload['data_sufficiency']}",
        "",
        f"_Confidence note:_ {payload['confidence_note']}",
        "",
        f"_Ignored lag window:_ {payload['ignored_lag_hours']}h",
        "",
        "## Summary",
        "",
        f"- Brief count: {_fmt(sample.get('briefs'))}",
        f"- Candidate count: {_fmt(sample.get('candidates'))}",
        f"- Outcome count: {_fmt(sample.get('outcomes'))}",
        f"- Source-ref coverage: {_fmt(m.get('source_ref_coverage'))}",
        f"- Brief usefulness score: {_fmt(m.get('brief_usefulness_score'))}",
        f"- Rank-outcome score: {_fmt(m.get('rank_outcome_score'))}",
    ]
    if payload["data_sufficiency"] == "insufficient_sample":
        lines += [
            "",
            "> ⚠️ Insufficient reviewed-outcome sample — metrics are advisory and not yet reliable.",
        ]
    lines += [
        "",
        "## Outcome Distribution",
        "",
        f"- Accepted: {dist.get('accepted', 0)}",
        f"- Rejected: {dist.get('rejected', 0)}",
        f"- Snoozed: {dist.get('snoozed', 0)}",
        f"- Ignored: {dist.get('ignored', 0)}",
        f"- Merged: {dist.get('merged', 0)}",
        f"- Suppressed: {dist.get('suppressed', 0)}",
        f"- Closed: {dist.get('closed', 0)}",
        f"- Reopened: {dist.get('reopened', 0)}",
        f"- Stale (no action): {dist.get('stale_no_action', 0)}",
        "",
        "## Ranking Policy",
        "",
        f"- Policy version: {_fmt(payload.get('window_start') and m.get('policy_version'))}",
        f"- Deterministic baseline rank-outcome: {_fmt(m.get('deterministic_baseline_rank_outcome'))}",
        f"- Model-assisted rank-outcome: {_fmt(m.get('model_assisted_rank_outcome'))}",
        f"- Deterministic-vs-model delta: {_fmt((m.get('deterministic_vs_model_delta') or {}).get('value'))} (observational, non-causal)",
        "",
        "## Source-Ref Coverage",
        "",
        f"- Coverage: {_fmt(m.get('source_ref_coverage'))} (1.0 = every surfaced actionable item is source-linked)",
        "",
        "## Procore Noise",
        "",
        f"- Exposed Procore candidates: {_fmt(procore.get('exposed_procore_candidates'))}",
        f"- Noise score: {_fmt(procore.get('procore_noise_score'))}",
        "",
        "## Model Profile Reliability",
        "",
    ]
    for row in payload["model_profiles"]:
        lines.append(
            f"- profile={_fmt(row.get('model_profile_id'))} attempts={row.get('attempt_count')} "
            f"degradation_rate={_fmt(row.get('model_degradation_rate'))} "
            f"fallback={row.get('fallback_count')} status={row.get('status')}"
        )
    lines += [
        "",
        "## Duplicate / Similarity Proxy",
        "",
        f"- Reviewed clusters: {dup.get('reviewed_clusters')}",
        f"- Duplicate precision proxy: {_fmt(dup.get('duplicate_precision_proxy'))}",
        f"- Insufficient sample: {dup.get('insufficient_sample')}",
        "",
        "## Safe Next Tuning Actions",
        "",
    ]
    for i, action in enumerate(payload["next_tuning_actions"], start=1):
        lines.append(f"{i}. {action}")
    lines += [
        "",
        "## Guardrails",
        "",
        "- Observational only: true",
        "- No lifecycle mutation: true",
        "- No source-ref mutation: true",
        "- No external writeback: true",
        "- Raw-free report: true",
    ]
    return "\n".join(lines) + "\n"


def _scan_payload(payload: dict[str, Any], markdown: str) -> dict[str, Any]:
    """Category-only scan of the JSON (sans markdown) + the Markdown body."""
    json_text = json.dumps({k: v for k, v in payload.items() if k != "markdown"}, default=str)
    categories = set(scan_text_for_forbidden(json_text)) | set(scan_text_for_forbidden(markdown))
    return {"raw_free": not categories, "categories": sorted(categories)}


def report_status_is_terminal(status: Optional[str]) -> bool:
    """True for statuses that mean there is no quantitative report to render."""
    return status in (STATUS_NO_RANKED_BRIEFS, STATUS_INSUFFICIENT_OUTCOME)


STATUS_FAIL_CLOSED = "fail_closed"


def run_daily_brief_effectiveness_evaluation(
    store: Any,
    *,
    window_start: str,
    window_end: str,
    now_utc: str,
    ignored_lag_hours: int = M.DEFAULT_IGNORED_LAG_HOURS,
    eval_mode: str = "observed",
    policy_version: Optional[str] = None,
    model_profile_id: Optional[str] = None,
    include_procore_noise: bool = True,
    include_model_profile: bool = True,
    include_rollups: bool = True,
    dry_run: bool = True,
    max_persist: Optional[int] = None,
) -> dict[str, Any]:
    """Orchestrate a full effectiveness evaluation: build → evaluate → report → (optional) persist.

    Read-only by default. Apply persists telemetry/eval/rollup rows ONLY, capped by ``max_persist``
    which bounds the **total projected insert count across all V52 tables**: if the projected total
    exceeds the cap, the run fails closed (status ``fail_closed``) BEFORE inserting anything — no
    partial writes. Mutates no lifecycle/source-ref/ranking/assembly rows. Never calls a model.
    """
    if eval_mode not in EVAL_MODES:
        raise ValueError(f"eval_mode must be one of {EVAL_MODES}")
    if not dry_run and max_persist is None:
        raise ValueError("apply requires max_persist (cap on total projected persisted rows)")

    packet = build_effectiveness_packets(
        store,
        window_start=window_start,
        window_end=window_end,
        now_utc=now_utc,
        ignored_lag_hours=ignored_lag_hours,
        policy_version=policy_version,
        model_profile_id=model_profile_id,
    )

    # No ranked briefs: emit an honest terminal report (still raw-free), nothing to persist.
    if packet["status"] == STATUS_NO_RANKED_BRIEFS:
        return _terminal_result(packet, eval_mode=eval_mode, dry_run=dry_run)

    ranking_eval = evaluate_ranking_policy(
        packet, eval_mode=eval_mode, policy_version=policy_version
    )
    report = build_effectiveness_report(packet, ranking_eval)
    model_profiles = report["model_profiles"] if include_model_profile else []
    persistable_profiles = [r for r in model_profiles if r.get("status") == "ok"]
    rollups = (
        build_rollups(
            packet, model_degradation_rate=ranking_eval["metrics"].get("model_degradation_rate")
        )
        if include_rollups
        else []
    )

    exposure_events = packet["exposure_events"]
    outcome_events = packet["outcome_events"]
    eval_items = ranking_eval["eval_items"]
    projected = {
        "exposure_events": len(exposure_events),
        "outcome_events": len(outcome_events),
        "ranking_policy_eval_runs": 1,
        "ranking_policy_eval_items": len(eval_items),
        "model_profile_eval_results": len(persistable_profiles),
        "brief_effectiveness_rollups": len(rollups),
    }
    projected_total = sum(projected.values())

    result: dict[str, Any] = {
        **report,
        "eval_mode": eval_mode,
        "applied": False,
        "dry_run": dry_run,
        "persistence": {
            "projected": projected,
            "projected_total": projected_total,
            "max_persist": max_persist,
            "persisted_total": 0,
        },
    }

    # Fail closed if the report (or packet) is not raw-free — never emit/persist unsafe content.
    if not report["raw_safety"]["raw_free"] or not packet["raw_safety"]["raw_free"]:
        result["status"] = STATUS_FAIL_CLOSED
        result["fail_closed_reason"] = "raw_leak_detected"
        return result

    if dry_run:
        return result

    # Apply: enforce the total-projected cap BEFORE any insert (no partial writes).
    if projected_total > int(max_persist or 0):
        result["status"] = STATUS_FAIL_CLOSED
        result["fail_closed_reason"] = (
            f"max_persist_exceeded: projected_total={projected_total} cap={max_persist}"
        )
        return result

    persisted = _persist_all(
        store,
        exposure_events=exposure_events,
        outcome_events=outcome_events,
        ranking_eval=ranking_eval,
        eval_items=eval_items,
        model_profiles=persistable_profiles,
        rollups=rollups,
    )
    result["applied"] = True
    result["persistence"]["persisted_total"] = persisted["persisted_total"]
    result["persistence"]["persisted"] = persisted["by_table"]
    result["persistence"]["eval_run_id"] = persisted["eval_run_id"]
    return result


def _terminal_result(packet: dict[str, Any], *, eval_mode: str, dry_run: bool) -> dict[str, Any]:
    payload = {
        "command": "second-brain daily-brief evaluate-effectiveness",
        "status": packet["status"],
        "window_start": packet["window_start"],
        "window_end": packet["window_end"],
        "ignored_lag_hours": packet.get("ignored_lag_hours", M.DEFAULT_IGNORED_LAG_HOURS),
        "eval_mode": eval_mode,
        "data_sufficiency": "insufficient_sample",
        "confidence_note": "no_ranked_briefs_in_window",
        "sample_size": packet.get("sample_size", {"briefs": 0, "candidates": 0, "outcomes": 0}),
        "metrics": {},
        "degradation": packet.get("degradation", []),
        "applied": False,
        "dry_run": dry_run,
        "persistence": {"projected_total": 0, "persisted_total": 0, "max_persist": None},
        "guardrails": _GUARDRAILS,
    }
    payload["raw_safety"] = packet.get("raw_safety", {"raw_free": True, "categories": []})
    return payload


def _persist_all(
    store: Any,
    *,
    exposure_events: list[dict[str, Any]],
    outcome_events: list[dict[str, Any]],
    ranking_eval: dict[str, Any],
    eval_items: list[dict[str, Any]],
    model_profiles: list[dict[str, Any]],
    rollups: list[dict[str, Any]],
) -> dict[str, Any]:
    """Persist all V52 telemetry rows idempotently. Caller has already enforced the total cap."""
    by_table = {
        "exposure_events": 0,
        "outcome_events": 0,
        "ranking_policy_eval_runs": 0,
        "ranking_policy_eval_items": 0,
        "model_profile_eval_results": 0,
        "brief_effectiveness_rollups": 0,
    }
    for ev in exposure_events:
        _, inserted = store.insert_daily_brief_exposure_event(**ev)
        by_table["exposure_events"] += 1 if inserted else 0
    for oe in outcome_events:
        _, inserted = store.insert_daily_brief_item_outcome_event(**oe)
        by_table["outcome_events"] += 1 if inserted else 0

    m = ranking_eval["metrics"]
    eval_run_id, run_inserted = store.insert_ranking_policy_eval_run(
        window_start=ranking_eval["window_start"],
        window_end=ranking_eval["window_end"],
        eval_mode=ranking_eval["eval_mode"],
        policy_version=ranking_eval.get("policy_version"),
        ranking_algorithm_version=ranking_eval.get("ranking_algorithm_version"),
        assembly_policy_version=ranking_eval.get("assembly_policy_version"),
        model_profile_id=ranking_eval.get("model_profile_id"),
        model_name=ranking_eval.get("model_name"),
        feedback_calibration_version=ranking_eval.get("feedback_calibration_version"),
        ignored_lag_hours=int(ranking_eval.get("ignored_lag_hours", M.DEFAULT_IGNORED_LAG_HOURS)),
        candidate_count=ranking_eval.get("candidate_count", 0),
        outcome_count=ranking_eval.get("outcome_count", 0),
        source_ref_coverage=m.get("source_ref_coverage"),
        brief_usefulness_score=m.get("brief_usefulness_score"),
        rank_outcome_score=m.get("rank_outcome_score"),
        model_degradation_rate=m.get("model_degradation_rate"),
        procore_noise_score=m.get("procore_noise_score"),
        sample_sufficient=bool(ranking_eval.get("sample_sufficient")),
    )
    by_table["ranking_policy_eval_runs"] += 1 if run_inserted else 0
    for item in eval_items:
        inserted = store.insert_ranking_policy_eval_item(eval_run_id=eval_run_id, **item)
        by_table["ranking_policy_eval_items"] += 1 if inserted else 0

    for row in model_profiles:
        _, inserted = store.insert_model_profile_eval_result(
            window_start=row["window_start"],
            window_end=row["window_end"],
            task_type=row.get("task_type"),
            model_profile_id=row.get("model_profile_id"),
            model_name=row.get("model_name"),
            attempt_count=row.get("attempt_count", 0),
            success_count=row.get("success_count", 0),
            schema_invalid_count=row.get("schema_invalid_count", 0),
            safety_withheld_count=row.get("safety_withheld_count", 0),
            timeout_count=row.get("timeout_count", 0),
            unknown_alias_count=row.get("unknown_alias_count", 0),
            lifecycle_excluded_ref_count=row.get("lifecycle_excluded_ref_count", 0),
            fallback_count=row.get("fallback_count", 0),
            avg_latency_ms=row.get("avg_latency_ms"),
            p95_latency_ms=row.get("p95_latency_ms"),
            advisory_adoption_proxy=row.get("advisory_adoption_proxy"),
            model_degradation_rate=row.get("model_degradation_rate"),
            sample_sufficient=bool(row.get("sample_sufficient")),
        )
        by_table["model_profile_eval_results"] += 1 if inserted else 0

    for row in rollups:
        _, inserted = store.insert_brief_effectiveness_rollup(**row)
        by_table["brief_effectiveness_rollups"] += 1 if inserted else 0

    by_table_total = sum(by_table.values())
    return {"by_table": by_table, "persisted_total": by_table_total, "eval_run_id": eval_run_id}
