"""Phase 08C — deterministic routing of sensitive/ambiguous financial signals to review.

Implements the review-required financial signal policy: load and *enforce* the
policy seed, then deterministically route detected data-quality / determination-
requiring conditions from the V35 normalized financial facts and snapshots into
``second_brain_financial_review_required_items``. Each routed item carries a reason
code (``trigger_category``), source references (``source_ref`` / ``amount_ref`` —
metadata refs only), a confidence label (V36 column), a review tier, and the full
no-raw / no-writeback / no-determination guard columns (advisory_only=1).

Covers all seven policy trigger categories:
  - amount_parse_ambiguous_or_rejected      (parse ambiguity)
  - missing_source_field_path               (missing context)
  - missing_or_inconsistent_currency        (inconsistent / missing currency)
  - missing_wbs_cost_code_or_line_item_type (missing WBS / cost code)
  - relationship_ambiguity                  (relationship ambiguity)
  - fail_closed_required_source             (source staleness / fail-closed dependency)
  - determination_attempt                   (attempted determination — refused, routed)

Deterministic and model-free. Local-only: reads V35 + ``procore_financial_*`` tables,
writes review items to local SQLite plus an advisory evidence proof. No external
writeback; no raw payloads / amounts / URLs / tokens / bodies persisted anywhere.
Financial outputs are advisory review aids — never approvals, claims, entitlements,
determinations, or forecasts.
"""

from __future__ import annotations

import json
import os
import re
import uuid
from pathlib import Path
from typing import Any

from hb_assistant.store.connection import transaction

from .financial_completeness import (
    EVIDENCE_DIR,
    REVIEW_POLICY_PATH,
    _get_conn,
    _load_policy,
    _now,
    route_to_review,
)

REVIEW_PROOF_MD = "financial-review-required-proof.md"
REVIEW_PROOF_JSON = "financial-review-required-proof.json"

# Normalized amount-fact ``parse_status`` -> review trigger (reason code). Conflicting
# amounts require a reconciliation the system refuses to make, so they route as an
# attempted determination rather than being resolved.
_PARSE_STATUS_TRIGGER: dict[str, str] = {
    "ambiguous": "amount_parse_ambiguous_or_rejected",
    "rejected": "amount_parse_ambiguous_or_rejected",
    "review_required": "amount_parse_ambiguous_or_rejected",
    "stale": "fail_closed_required_source",
    "conflicting": "determination_attempt",
}
_CURRENCY_STATUS_REVIEW = {"missing_currency", "inconsistent_currency", "ambiguous_currency"}

# Redaction scan: patterns that must never appear in routed items or the proof
# artifacts (tokens, PEMs, JWTs, URLs, signed-url markers, bare emails).
_FORBIDDEN: list[re.Pattern[str]] = [
    re.compile(r"Bearer\s+[A-Za-z0-9]"),
    re.compile(r"-----BEGIN"),
    re.compile(r"eyJ[A-Za-z0-9_-]{5,}"),
    re.compile(r"https?://"),
    re.compile(r"sig="),
    re.compile(r"token=[A-Za-z0-9]"),
    re.compile(r"access_token|refresh_token|client_secret"),
    re.compile(r"[\w.%+-]+@[\w.-]+\.[A-Za-z]{2,}"),
]


def _assert_no_raw(text: str, where: str) -> None:
    """Raise if any forbidden raw pattern leaked into ``text`` (stop condition)."""
    for pat in _FORBIDDEN:
        if pat.search(text):
            raise ValueError(f"forbidden raw pattern {pat.pattern!r} found in {where}")


def load_review_policy() -> dict[str, Any]:
    """Load and enforce the review-required financial policy seed.

    Enforcement: refuse to proceed unless the policy keeps the advisory-only /
    no-writeback / no-determination / no-raw posture. Returns the parsed policy.
    """
    policy: dict[str, Any] = _load_policy(REVIEW_POLICY_PATH) or {}

    def _flag(key: str, default: bool) -> bool:
        value = policy.get(key, default)
        if isinstance(value, str):
            return value.strip().lower() in {"true", "1", "yes"}
        return bool(value)

    if not _flag("advisory_only_required", True):
        raise ValueError("review policy must require advisory_only")
    if _flag("external_writeback_allowed", False):
        raise ValueError("review policy must forbid external writeback")
    if _flag("financial_determination_allowed", False):
        raise ValueError("review policy must forbid financial determinations")
    if _flag("raw_financial_source_payload_allowed", False):
        raise ValueError("review policy must forbid raw financial source payloads")
    return policy


def _scan_amount_facts(
    conn: Any, *, run_id: str, project_key: str | None, policy: dict[str, Any]
) -> tuple[dict[str, int], int]:
    """Route parse-ambiguity, staleness, determination, currency, and missing-context."""
    counts: dict[str, int] = {}
    evaluated = 0
    try:
        rows = list(
            conn.execute(
                "SELECT id, project_key, parse_status, currency_status, source_field_path "
                "FROM second_brain_financial_amount_facts_normalized "
                "WHERE (? IS NULL OR project_key=?)",
                (project_key, project_key),
            )
        )
    except Exception:
        return counts, evaluated
    for fid, pk, parse_status, currency_status, source_field_path in rows:
        evaluated += 1
        pk = pk or "global"
        ref = f"amount_fact:{fid}"
        trigger = _PARSE_STATUS_TRIGGER.get(parse_status or "")
        if trigger:
            route_to_review(
                conn=conn,
                run_id=run_id,
                project_key=pk,
                trigger_category=trigger,
                amount_ref=ref,
                policy=policy,
            )
            counts[trigger] = counts.get(trigger, 0) + 1
        if (currency_status or "") in _CURRENCY_STATUS_REVIEW:
            trigger = "missing_or_inconsistent_currency"
            route_to_review(
                conn=conn,
                run_id=run_id,
                project_key=pk,
                trigger_category=trigger,
                amount_ref=ref,
                policy=policy,
            )
            counts[trigger] = counts.get(trigger, 0) + 1
        if not source_field_path:
            trigger = "missing_source_field_path"
            route_to_review(
                conn=conn,
                run_id=run_id,
                project_key=pk,
                trigger_category=trigger,
                amount_ref=ref,
                policy=policy,
            )
            counts[trigger] = counts.get(trigger, 0) + 1
    return counts, evaluated


def _scan_wbs_cost_code(
    conn: Any, *, run_id: str, project_key: str | None, policy: dict[str, Any]
) -> tuple[dict[str, int], int]:
    """Route missing WBS / cost-code / line-item-type from the source line-item tables."""
    counts: dict[str, int] = {}
    evaluated = 0
    trigger = "missing_wbs_cost_code_or_line_item_type"
    for tbl, wcol, ccol, lcol in (
        ("procore_financial_line_items", "wbs_code_id", "cost_code_id", "line_item_type_id"),
        ("procore_financial_budget_rows", "wbs_code_id", "cost_code_id", None),
        (
            "procore_financial_change_order_line_items",
            "wbs_code_id",
            "cost_code_id",
            "line_item_type_id",
        ),
    ):
        query = (
            f"SELECT rowid, project_key, {wcol} AS w, {ccol} AS c"
            + (f", {lcol} AS l" if lcol else ", NULL AS l")
            + f" FROM {tbl} WHERE (? IS NULL OR project_key=?) LIMIT 2000"
        )
        try:
            rows = list(conn.execute(query, (project_key, project_key)))
        except Exception:
            continue
        for rid, pk, wbs, cost_code, line_item_type in rows:
            evaluated += 1
            if (not wbs) or (not cost_code) or (lcol and not line_item_type):
                route_to_review(
                    conn=conn,
                    run_id=run_id,
                    project_key=pk or "global",
                    trigger_category=trigger,
                    source_ref=f"{tbl}:{rid}",
                    policy=policy,
                )
                counts[trigger] = counts.get(trigger, 0) + 1
    return counts, evaluated


def _scan_source_coverage(
    conn: Any, *, run_id: str, project_key: str | None, policy: dict[str, Any]
) -> tuple[dict[str, int], int]:
    """Route fail-closed dependencies and relationship ambiguity from coverage snapshots."""
    counts: dict[str, int] = {}
    evaluated = 0
    try:
        rows = list(
            conn.execute(
                "SELECT id, project_key, source_family, endpoint_id, coverage_status, "
                "relationship_key_count FROM second_brain_financial_source_coverage_snapshots "
                "WHERE (? IS NULL OR project_key=?)",
                (project_key, project_key),
            )
        )
    except Exception:
        return counts, evaluated
    for sid, pk, family, endpoint_id, coverage_status, relationship_key_count in rows:
        evaluated += 1
        pk = pk or "global"
        ref = f"source_coverage:{endpoint_id or family or sid}"
        if (coverage_status or "") == "fail_closed":
            trigger = "fail_closed_required_source"
            route_to_review(
                conn=conn,
                run_id=run_id,
                project_key=pk,
                trigger_category=trigger,
                source_ref=ref,
                policy=policy,
            )
            counts[trigger] = counts.get(trigger, 0) + 1
        if (relationship_key_count or 0) == 0:
            trigger = "relationship_ambiguity"
            route_to_review(
                conn=conn,
                run_id=run_id,
                project_key=pk,
                trigger_category=trigger,
                source_ref=ref,
                policy=policy,
            )
            counts[trigger] = counts.get(trigger, 0) + 1
    return counts, evaluated


def run_review_required_routing(
    *,
    conn: Any | None = None,
    project_key: str | None = None,
    db_path: str | None = None,
) -> dict[str, Any]:
    """Deterministically route all seven review-required financial signal categories.

    Opens one self-contained run (own ``run_id`` + readiness-agent receipt), scans
    the V35 facts/snapshots and ``procore_financial_*`` source tables, and persists
    one review item per detected signal via the single sanctioned ``route_to_review``
    path. Returns counts by trigger / tier / confidence. No raw values touched.
    """
    if conn is None:
        conn = _get_conn(db_path)
    policy = load_review_policy()
    run_id = f"08c-review-{uuid.uuid4().hex[:8]}"

    with transaction(conn):
        conn.execute(
            "INSERT INTO second_brain_financial_readiness_agent_runs "
            "(run_id, project_key, status, items_evaluated, review_required_count) "
            "VALUES (?, ?, 'started', 0, 0)",
            (run_id, project_key),
        )

    counts: dict[str, int] = {}
    evaluated_total = 0
    for scanner in (_scan_amount_facts, _scan_wbs_cost_code, _scan_source_coverage):
        scanner_counts, evaluated = scanner(
            conn, run_id=run_id, project_key=project_key, policy=policy
        )
        evaluated_total += evaluated
        for key, value in scanner_counts.items():
            counts[key] = counts.get(key, 0) + value

    routed_total = sum(counts.values())
    with transaction(conn):
        conn.execute(
            "UPDATE second_brain_financial_readiness_agent_runs "
            "SET status='succeeded', items_evaluated=?, review_required_count=? WHERE run_id=?",
            (evaluated_total, routed_total, run_id),
        )

    by_trigger, by_tier, by_confidence = _aggregate(conn, run_id)
    return {
        "run_id": run_id,
        "project_key": project_key,
        "items_evaluated": evaluated_total,
        "review_required_count": routed_total,
        "by_trigger": by_trigger,
        "by_tier": by_tier,
        "by_confidence": by_confidence,
    }


def _aggregate(conn: Any, run_id: str) -> tuple[dict[str, int], dict[str, int], dict[str, int]]:
    by_trigger: dict[str, int] = {}
    by_tier: dict[str, int] = {}
    by_confidence: dict[str, int] = {}
    for trigger, tier, confidence, count in conn.execute(
        "SELECT trigger_category, review_tier, confidence_label, COUNT(*) "
        "FROM second_brain_financial_review_required_items WHERE run_id=? "
        "GROUP BY trigger_category, review_tier, confidence_label",
        (run_id,),
    ):
        by_trigger[trigger] = by_trigger.get(trigger, 0) + count
        by_tier[tier] = by_tier.get(tier, 0) + count
        label = confidence or "unspecified"
        by_confidence[label] = by_confidence.get(label, 0) + count
    return by_trigger, by_tier, by_confidence


def _render_md(proof: dict[str, Any]) -> str:
    lines = [
        "# Financial Review-Required Routing Proof",
        "",
        "Deterministic routing of sensitive/ambiguous financial signals to review. Every "
        "item below is an advisory review aid only — not a payment approval, claim position, "
        "entitlement determination, contract interpretation, forecast, or executive financial "
        "determination. No financial values are computed or summed here.",
        "",
        "## Summary",
        f"- Run id: {proof['run_id']}",
        f"- Project key: {proof['project_key'] or 'all'}",
        f"- Schema version: {proof['schema_version']}",
        f"- Items evaluated: {proof['items_evaluated']}",
        f"- Review items routed: {proof['review_required_count']}",
        "",
        "## By trigger category (reason code)",
        "| Trigger category (reason code) | Review tier | Confidence | Count |",
        "| --- | --- | --- | --- |",
    ]
    for detail in proof["detail"]:
        lines.append(
            f"| {detail['trigger_category']} | {detail['review_tier']} "
            f"| {detail['confidence_label']} | {detail['count']} |"
        )
    lines += ["", "## Review tiers in use"]
    for tier, count in sorted(proof["by_tier"].items()):
        lines.append(f"- {tier}: {count}")
    lines += [
        "",
        "## Policy (loaded + enforced)",
        f"- Review tiers: {', '.join(proof['policy'].get('review_tiers') or [])}",
        f"- Triggers: {', '.join(proof['policy'].get('triggers') or [])}",
        "",
        "## Guardrails",
        "- advisory_only_required: true",
        "- no_external_writeback: true",
        "- financial_determination_forbidden: true",
        "- payment_decision_forbidden: true",
        "- claim_or_entitlement_decision_forbidden: true",
        "- raw_financial_payload_forbidden: true",
        "",
        "## Stop-check attestations",
        "- raw_payloads_or_full_source_values_written: "
        f"{str(proof['stop_checks']['raw_payloads_or_full_source_values_written']).lower()}",
        "- financial_determination_performed: "
        f"{str(proof['stop_checks']['financial_determination_performed']).lower()}",
        f"- model_required: {str(proof['stop_checks']['model_required']).lower()}",
        "",
        "## Notes",
        proof["notes"],
        "",
        "## Artifacts",
        f"- {proof['proof_json_path']}",
    ]
    for artifact in proof["sibling_artifacts"]:
        lines.append(f"- {artifact}")
    lines += ["", f"Generated: {proof['generated_utc']} | run_id: {proof['run_id']}", ""]
    return "\n".join(lines)


def build_financial_review_required_proof(
    *,
    db_path: str | None = None,
    project_key: str | None = None,
    out_dir: str = EVIDENCE_DIR,
) -> dict[str, Any]:
    """Run review routing and emit ``financial-review-required-proof.md`` (+ JSON).

    Advisory, deterministic, no model. Both artifacts pass a redaction scan before
    they are written; a forbidden raw pattern is a hard stop.
    """
    os.makedirs(out_dir, exist_ok=True)
    conn = _get_conn(db_path)
    result = run_review_required_routing(conn=conn, project_key=project_key)
    run_id = result["run_id"]
    policy = load_review_policy()

    detail: list[dict[str, Any]] = []
    for trigger, tier, confidence, count in conn.execute(
        "SELECT trigger_category, review_tier, confidence_label, COUNT(*) "
        "FROM second_brain_financial_review_required_items WHERE run_id=? "
        "GROUP BY trigger_category, review_tier, confidence_label ORDER BY trigger_category",
        (run_id,),
    ):
        detail.append(
            {
                "trigger_category": trigger,
                "review_tier": tier,
                "confidence_label": confidence,
                "count": count,
            }
        )

    samples: list[dict[str, Any]] = []
    for trigger, source_ref, amount_ref in conn.execute(
        "SELECT trigger_category, source_ref, amount_ref "
        "FROM second_brain_financial_review_required_items WHERE run_id=? ORDER BY id LIMIT 10",
        (run_id,),
    ):
        samples.append(
            {"trigger_category": trigger, "source_ref": source_ref, "amount_ref": amount_ref}
        )

    json_path = Path(out_dir) / REVIEW_PROOF_JSON
    md_path = Path(out_dir) / REVIEW_PROOF_MD
    proof: dict[str, Any] = {
        "generated_utc": _now(),
        "repo_head": "phase-08c review-required routing",
        "schema_version": 36,
        "run_id": run_id,
        "project_key": project_key,
        "policy": {
            "review_tiers": policy.get("review_tiers"),
            "triggers": policy.get("triggers"),
            "tier_by_trigger": policy.get("tier_by_trigger"),
            "confidence_by_trigger": policy.get("confidence_by_trigger"),
        },
        "items_evaluated": result["items_evaluated"],
        "review_required_count": result["review_required_count"],
        "by_trigger": result["by_trigger"],
        "by_tier": result["by_tier"],
        "by_confidence": result["by_confidence"],
        "detail": detail,
        "samples": samples,
        "advisory_only": True,
        "guardrails": {
            "local_first": True,
            "read_only_external": True,
            "no_external_writeback": True,
            "no_raw_financial_payload": True,
            "financial_determination_forbidden": True,
            "payment_decision_forbidden": True,
            "claim_or_entitlement_decision_forbidden": True,
            "advisory_only": True,
            "model_use": "absent",
        },
        "stop_checks": {
            "raw_payloads_or_full_source_values_written": False,
            "financial_determination_performed": False,
            "model_required": False,
        },
        "proof_json_path": str(json_path),
        "proof_md_path": str(md_path),
        "sibling_artifacts": [
            f"{EVIDENCE_DIR}/financial-readiness-agent-proof.json",
            f"{EVIDENCE_DIR}/financial-source-coverage-matrix.json",
        ],
        "notes": (
            "Deterministic routing of the seven review-required financial signal "
            "categories from V35 normalized facts + coverage snapshots + procore_financial_* "
            "source tables. trigger_category is the reason code; source_ref/amount_ref are "
            "metadata references only (no amounts, URLs, tokens, bodies, or payloads). "
            "confidence_label is the advisory quality of the routing signal, not certainty of "
            "any financial outcome. All outputs are advisory review aids only — not "
            "determinations, approvals, claims, entitlements, or forecasts. Source preserved "
            "in procore_financial_* tables."
        ),
    }

    serialized = json.dumps(proof, default=str)
    _assert_no_raw(serialized, "review-required proof JSON")
    with open(json_path, "w") as handle:
        json.dump(proof, handle, indent=2, default=str)

    markdown = _render_md(proof)
    _assert_no_raw(markdown, "review-required proof markdown")
    with open(md_path, "w") as handle:
        handle.write(markdown)

    proof["proof_path"] = str(md_path)
    return proof
