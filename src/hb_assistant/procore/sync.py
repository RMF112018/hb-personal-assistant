"""Procore pilot project dry-run sync pipeline (Prompt_09).

Dry-run (default): audit prerequisite + serializable redacted plan, zero side effects.
Apply (--apply, explicit opt-in only): after audit gate, GET-only execution via
Prompt_04 client (secret at runtime), normalization, idempotent local SQLite upserts only.

All paths reuse Prompt_07 auditor (verdicts), Prompt_04 client (GET + redaction + pagination),
Prompt_05 EndpointContract (categories, review_required, deferred/excluded), Prompt_06 mapping
(pilot resolution + pending + HB/Procore ID separation + 5280), and Prompt_02 runtime secret loader.

Never writes outside caller-supplied SQLite (temp DB in tests). Never non-GET. Never secrets/bodies
in artifacts. Audit prerequisite is a hard gate (no bypass).
"""

from __future__ import annotations

import uuid
from dataclasses import dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Literal, Optional

from hb_assistant.procore.auditor import (
    EndpointAuditor,  # real Prompt_07 surface (extended in place)
)
from hb_assistant.procore.errors import (
    ProcoreMappingUnavailable,
    ProcorePendingProjectRejected,
)
from hb_assistant.procore.http_client import ProcoreHTTPClient  # type: ignore
from hb_assistant.procore.loader import (
    ProcoreProjectsError,
    load_endpoint_contract,
    load_procore_projects,
)
from hb_assistant.procore.models import ProcoreProjectsRegistry
from hb_assistant.procore.normalizers import (
    NORMALIZATION_SCHEMA_VERSION,
    normalize_daily_log_payload_block,
    normalize_meeting,
    normalize_meeting_payload_block,
    normalize_meeting_topic,
    normalize_meeting_topic_payload_block,
    normalize_observation,
    normalize_observation_comment,
    normalize_observation_payload_block,
    normalize_rfi,
    normalize_rfi_payload_block,
    normalize_rfi_reply,
    normalize_submittal,
    normalize_submittal_package,
    normalize_submittal_payload_block,
    normalize_submittal_response,
)

# Endpoint-id keyed normalizer dispatch. Each entry maps to a normalizer block
# function. Most entries return ``tuple[list[dict], ...]`` (parents + child
# categories); ``list-daily-logs`` returns ``dict[str, list[dict]]`` keyed by
# section category to accommodate the multi-section daily log payload.
RFI_ENDPOINT_ID = "list-rfis"
SUBMITTAL_ENDPOINT_ID = "list-submittals"
OBSERVATION_ENDPOINT_ID = "list-observations"
MEETING_ENDPOINT_ID = "list-meetings"
MEETING_TOPIC_ENDPOINT_ID = "list-meeting-topics"
DAILY_LOG_ENDPOINT_ID = "list-daily-logs"
NORMALIZER_DISPATCH: Dict[str, Any] = {
    RFI_ENDPOINT_ID: normalize_rfi_payload_block,
    SUBMITTAL_ENDPOINT_ID: normalize_submittal_payload_block,
    OBSERVATION_ENDPOINT_ID: normalize_observation_payload_block,
    MEETING_ENDPOINT_ID: normalize_meeting_payload_block,
    MEETING_TOPIC_ENDPOINT_ID: normalize_meeting_topic_payload_block,
    DAILY_LOG_ENDPOINT_ID: normalize_daily_log_payload_block,
}


def redact_for_evidence(obj: Any) -> Any:
    """Local evidence redactor for Prompt_09 receipts/plans (reuses Prompt_04 primitives)."""
    if isinstance(obj, dict):
        return {k: redact_for_evidence(v) for k, v in obj.items() if not _looks_like_secret(k)}
    if isinstance(obj, list):
        return [redact_for_evidence(x) for x in obj]
    if isinstance(obj, str) and any(s in obj.lower() for s in ("bearer", "token", "secret")):
        return "<redacted>"
    return obj


def _looks_like_secret(k: str) -> bool:
    return any(x in k.lower() for x in ("secret", "token", "auth", "bearer", "key"))


Mode = Literal["dry_run", "apply"]
Policy = Literal["auto", "incremental", "full"]


@dataclass
class SyncReceipt:
    """Structured receipt for both modes (redacted, safe for JSON/SQLite/evidence)."""

    sync_id: str
    mode: Mode
    pilot_project_key: str
    company_id: str  # "5280"
    started_at: str
    completed_at: Optional[str] = None
    audit_prerequisite_passed: bool = False
    audit_verdict_summary: Dict[str, int] = field(default_factory=dict)
    category_counts: Dict[str, int] = field(default_factory=dict)
    sensitivity_counts: Dict[str, int] = field(default_factory=dict)
    total_planned_requests: int = 0
    total_items_normalized: int = 0
    per_endpoint: List[Dict[str, Any]] = field(default_factory=list)
    redacted_errors: List[Dict[str, Any]] = field(default_factory=list)
    redaction_applied: bool = True
    persisted_to_sqlite: bool = False
    policy_used: str = "auto"
    sensitive_review_routing: str = "flagged per contract; no automated decisioning"
    guardrails: Dict[str, Any] = field(default_factory=dict)
    # All-project sync: one redacted per-project receipt per mapped pilot. Empty for
    # the per-project sub-receipts themselves; populated only on the aggregate.
    per_project: List[Dict[str, Any]] = field(default_factory=list)
    # Redaction-surviving project identifier ("multi" on the aggregate, the real key
    # on each per-project receipt). ``pilot_project_key`` is stripped by the evidence
    # redactor because it contains the substring "key".
    project_scope: str = ""


class ProcoreSyncCoordinator:
    """Coordinator for pilot project dry-run sync + local SQLite apply.

    All live Procore access is GET-only via Prompt_04 client (secret at call time only).
    Dry-run never touches network or DB. Apply is gated and local-only.
    """

    def __init__(
        self,
        *,
        environment: str = "prod",
        db_path: Optional[
            Path
        ] = None,  # explicit for temp DB validation; None = default PathPolicy
    ) -> None:
        self.environment = environment
        self.db_path = db_path
        self.correlation_id = str(uuid.uuid4())
        self.auditor = None  # lazy; real Prompt_07 EndpointAuditor constructed with contract + projects in the gate
        self.client: Optional[ProcoreHTTPClient] = None  # created only in apply after gate

    def _get_client(self) -> ProcoreHTTPClient:
        if self.client is None:
            self.client = ProcoreHTTPClient(
                transport=None,  # real for apply; tests inject mock
                environment=self.environment,
            )
        return self.client

    def _build_guardrails_block(self) -> Dict[str, Any]:
        return {
            "local_first": True,
            "bobby_only_mvp": True,
            "read_only_external": True,
            "no_procore_writeback": True,
            "no_post_put_patch_delete": True,
            "no_secrets_in_artifacts": True,
            "dry_run_default_explicit_apply": True,
            "audit_prerequisite_gate": True,
            "unit_tests_mocked_temp_sqlite_only": True,
            "sensitive_routes_to_review": True,
            "no_model_file_operations": True,
        }

    def _resolve_pilot_projects(self, project_key: Optional[str]) -> List[str]:
        """Return the project keys to sync. Default = mapped pilots only.

        When no explicit key is supplied, the mapping is loaded and filtered to
        ``status == "pilot"``. Pending mappings are never returned by default;
        a pending key supplied explicitly is later rejected by ``_assert_no_pending``
        unless the caller passes ``allow_pending=True``.
        """
        if project_key:
            return [project_key]
        registry = self._load_project_registry()
        return [p.hb_project_key for p in registry.projects if p.status == "pilot"]

    def _load_project_registry(self) -> ProcoreProjectsRegistry:
        """Load the real Procore projects registry. Fail closed if unavailable."""
        try:
            return load_procore_projects()
        except ProcoreProjectsError as exc:
            raise ProcoreMappingUnavailable(message=str(exc)) from exc

    def _assert_no_pending(self, pilots: List[str], *, allow_pending: bool) -> None:
        """Raise ``ProcorePendingProjectRejected`` if any selected key is pending,
        unless the caller explicitly passed ``allow_pending=True``."""
        if allow_pending:
            return
        registry = self._load_project_registry()
        pending: List[str] = []
        for key in pilots:
            mapping = registry.get(key)
            if mapping is not None and mapping.status == "pending":
                pending.append(key)
        if pending:
            raise ProcorePendingProjectRejected(
                pending_keys=pending,
                correlation_id=self.correlation_id,
            )

    def _resolve_validated_pilots(
        self, project_key: Optional[str], *, allow_pending: bool
    ) -> List[str]:
        """Resolve target pilot keys; fail closed on pending/unknown keys.

        Without ``project_key`` this is every mapped pilot. Every resolved key must
        exist in the registry; an unknown explicit key raises
        ``ProcoreMappingUnavailable`` (a clear, typed error) before any audit, so the
        auditor never receives an unmapped key (which would raise a raw ``KeyError``).
        """
        pilots = self._resolve_pilot_projects(project_key)
        self._assert_no_pending(pilots, allow_pending=allow_pending)
        registry = self._load_project_registry()
        unknown = [k for k in pilots if registry.get(k) is None]
        if unknown:
            raise ProcoreMappingUnavailable(
                message=(
                    f"unknown hb_project_key(s): {unknown!r}; run "
                    "'hb-assistant procore mapping list' to see mapped pilots"
                )
            )
        return pilots

    def plan(
        self,
        *,
        project_key: Optional[str] = None,
        endpoints: Optional[List[str]] = None,
        policy: Policy = "auto",
        allow_pending: bool = False,
        rfi_preview_payload: Optional[List[Dict[str, Any]]] = None,
        submittal_preview_payload: Optional[List[Dict[str, Any]]] = None,
        observation_preview_payload: Optional[List[Dict[str, Any]]] = None,
        meeting_preview_payload: Optional[List[Dict[str, Any]]] = None,
        meeting_topic_preview_payload: Optional[List[Dict[str, Any]]] = None,
        daily_log_preview_payload: Optional[List[Dict[str, Any]]] = None,
    ) -> Dict[str, Any]:
        """Dry-run plan. Single project when ``project_key`` is given, else every
        mapped pilot. Iterates real keys (never ``"multi"``) and returns one redacted,
        aggregated receipt carrying per-project results. Zero side effects.
        """
        pilots = self._resolve_validated_pilots(project_key, allow_pending=allow_pending)
        receipts = [
            self._plan_one(
                key,
                endpoints=endpoints,
                policy=policy,
                rfi_preview_payload=rfi_preview_payload,
                submittal_preview_payload=submittal_preview_payload,
                observation_preview_payload=observation_preview_payload,
                meeting_preview_payload=meeting_preview_payload,
                meeting_topic_preview_payload=meeting_topic_preview_payload,
                daily_log_preview_payload=daily_log_preview_payload,
            )
            for key in pilots
        ]
        return self._aggregate_receipts(
            receipts, mode="dry_run", project_key=project_key, policy=policy
        )

    def apply(
        self,
        *,
        project_key: Optional[str] = None,
        endpoints: Optional[List[str]] = None,
        policy: Policy = "auto",
        full_refresh: bool = False,
        allow_pending: bool = False,
    ) -> Dict[str, Any]:
        """Explicit opt-in apply. Single project when ``project_key`` is given, else
        every mapped pilot. Iterates real keys (never ``"multi"``); writes ONLY to
        local SQLite; returns one redacted aggregated receipt with per-project results.
        """
        pilots = self._resolve_validated_pilots(project_key, allow_pending=allow_pending)
        receipts = [
            self._apply_one(key, endpoints=endpoints, policy=policy, full_refresh=full_refresh)
            for key in pilots
        ]
        return self._aggregate_receipts(
            receipts,
            mode="apply",
            project_key=project_key,
            policy="full" if full_refresh else policy,
        )

    def _aggregate_receipts(
        self,
        receipts: List[SyncReceipt],
        *,
        mode: Mode,
        project_key: Optional[str],
        policy: str,
    ) -> Dict[str, Any]:
        """Merge per-project receipts into one redacted all-project receipt.

        ``"multi"`` is only ever a top-level display label here — it is never passed
        into project-level audit/watermark logic. Dict counts are summed, list fields
        concatenated, ``audit_prerequisite_passed`` requires every project to pass, and
        ``persisted_to_sqlite`` is true if any project wrote rows.
        """
        now = datetime.now(timezone.utc).isoformat()
        if project_key:
            top_key = project_key
        elif len(receipts) == 1:
            top_key = receipts[0].pilot_project_key
        else:
            top_key = "multi"

        aggregate = SyncReceipt(
            sync_id=str(uuid.uuid4()),
            mode=mode,
            pilot_project_key=top_key,
            project_scope=top_key,
            company_id="5280",
            started_at=receipts[0].started_at if receipts else now,
            completed_at=now,
            guardrails=self._build_guardrails_block(),
            policy_used=policy,
        )
        aggregate.audit_prerequisite_passed = bool(receipts) and all(
            r.audit_prerequisite_passed for r in receipts
        )
        for r in receipts:
            for k, v in r.audit_verdict_summary.items():
                aggregate.audit_verdict_summary[k] = aggregate.audit_verdict_summary.get(k, 0) + v
            for k, v in r.category_counts.items():
                aggregate.category_counts[k] = aggregate.category_counts.get(k, 0) + v
            for k, v in r.sensitivity_counts.items():
                aggregate.sensitivity_counts[k] = aggregate.sensitivity_counts.get(k, 0) + v
            aggregate.total_planned_requests += r.total_planned_requests
            aggregate.total_items_normalized += r.total_items_normalized
            aggregate.per_endpoint.extend(r.per_endpoint)
            aggregate.redacted_errors.extend(r.redacted_errors)
        aggregate.persisted_to_sqlite = any(r.persisted_to_sqlite for r in receipts)
        aggregate.per_project = [r.__dict__ for r in receipts]
        return redact_for_evidence(aggregate.__dict__)

    def _plan_one(
        self,
        project_key: str,
        *,
        endpoints: Optional[List[str]] = None,
        policy: Policy = "auto",
        rfi_preview_payload: Optional[List[Dict[str, Any]]] = None,
        submittal_preview_payload: Optional[List[Dict[str, Any]]] = None,
        observation_preview_payload: Optional[List[Dict[str, Any]]] = None,
        meeting_preview_payload: Optional[List[Dict[str, Any]]] = None,
        meeting_topic_preview_payload: Optional[List[Dict[str, Any]]] = None,
        daily_log_preview_payload: Optional[List[Dict[str, Any]]] = None,
    ) -> SyncReceipt:
        """Dry-run plan for a single real pilot ``project_key``. Audit gate first.

        Zero side effects. Returns the (un-redacted) receipt object; redaction +
        aggregation happen in ``_aggregate_receipts``. ``project_key`` is always a
        real mapped key — never the ``"multi"`` sentinel.
        """
        started = datetime.now(timezone.utc).isoformat()
        receipt = SyncReceipt(
            sync_id=str(uuid.uuid4()),
            mode="dry_run",
            pilot_project_key=project_key,
            project_scope=project_key,
            company_id="5280",
            started_at=started,
            guardrails=self._build_guardrails_block(),
            policy_used=policy,
        )

        # Mandatory audit prerequisite gate (single real key; never "multi").
        if self.auditor is not None and hasattr(self.auditor, "audit_endpoints_for_pilots"):
            verdict_map = self.auditor.audit_endpoints_for_pilots([project_key])  # type: ignore[attr-defined]
            verdict_summary = {
                "available": sum(1 for v in verdict_map.values() if v == "available"),
                "non_available": sum(1 for v in verdict_map.values() if v != "available"),
            }
            all_available = all(v == "available" for v in verdict_map.values())
        else:
            contract = load_endpoint_contract()
            projects = self._load_project_registry()
            auditor = EndpointAuditor(contract, projects)
            audit_receipt = auditor.build_audit_run_receipt(
                project_key,
                base_url="https://api.procore.com",
                mode="dry_run",
            )
            verdict_summary = dict((audit_receipt.breakdown or {}).get("by_verdict", {}))
            all_available = verdict_summary.get("available", 0) > 0
        receipt.audit_prerequisite_passed = bool(all_available)
        receipt.audit_verdict_summary = verdict_summary or {"available": 0}

        if not all_available:
            receipt.completed_at = datetime.now(timezone.utc).isoformat()
            # Redacted failure receipt — no further planning
            return receipt

        # Build redacted plan (counts + envelopes, no secrets, no bodies)
        plan_details: List[Dict[str, Any]] = []
        total_requests = 0
        cat_counts: Dict[str, int] = {}
        sens_counts: Dict[str, int] = {}

        contract = load_endpoint_contract()
        for ep in contract.endpoints:
            if endpoints and ep.endpoint_id not in endpoints:
                continue
            planned = 1
            total_requests += planned
            cat = ep.category or "foundation"
            cat_counts[cat] = cat_counts.get(cat, 0) + 1
            if ep.status == "sensitive_validated":
                sens_counts["review_required"] = sens_counts.get("review_required", 0) + 1

            entry: Dict[str, Any] = {
                "endpoint_id": ep.endpoint_id,
                "category": cat,
                "review_required": ep.status == "sensitive_validated",
                "planned_requests": planned,
                "supports_incremental": False,
                "live_eligible": ep.is_live_eligible,
                "verification_status": ep.verification_status,
                "endpoint_status": ep.status,
                "redacted_request_envelope": {
                    "method": "GET",
                    "path_template": ep.path_template,
                    "company_id": "5280",
                    "correlation": self.correlation_id,
                    # auth redacted by construction; no token/secret ever present
                },
            }
            if ep.endpoint_id in NORMALIZER_DISPATCH:
                entry["normalization_schema_version"] = NORMALIZATION_SCHEMA_VERSION
                entry["would_persist_children_separately"] = ep.endpoint_id in (
                    RFI_ENDPOINT_ID,
                    SUBMITTAL_ENDPOINT_ID,
                    OBSERVATION_ENDPOINT_ID,
                )
                entry["would_persist_sections_separately"] = ep.endpoint_id == DAILY_LOG_ENDPOINT_ID
            if ep.endpoint_id == RFI_ENDPOINT_ID and rfi_preview_payload is not None:
                rfi_records, reply_records = normalize_rfi_payload_block(
                    rfi_preview_payload,
                    project_key=project_key,
                    endpoint_id=ep.endpoint_id,
                    correlation_id=self.correlation_id,
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                )
                review_required_count = sum(1 for r in rfi_records if r["review_required"])
                entry["planned_rfi_record_count"] = len(rfi_records)
                entry["planned_reply_record_count"] = len(reply_records)
                entry["planned_review_required_count"] = review_required_count
            if ep.endpoint_id == DAILY_LOG_ENDPOINT_ID and daily_log_preview_payload is not None:
                from hb_assistant.procore.daily_log_selection import (
                    load_daily_log_selection,
                )

                selection_scope = load_daily_log_selection()
                records_by_category = normalize_daily_log_payload_block(
                    daily_log_preview_payload,
                    selection_scope=selection_scope,
                    project_key=project_key,
                    endpoint_id=ep.endpoint_id,
                    correlation_id=self.correlation_id,
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                )
                planned_total = sum(len(v) for v in records_by_category.values())
                planned_review_count = sum(
                    1 for v in records_by_category.values() for r in v if r.get("review_required")
                )
                planned_safety_route_count = sum(
                    1 for v in records_by_category.values() for r in v if r.get("safety_route")
                )
                entry["planned_records_by_category"] = {
                    cat: len(records) for cat, records in records_by_category.items()
                }
                entry["planned_total_record_count"] = planned_total
                entry["planned_review_required_count"] = planned_review_count
                entry["planned_safety_route_count"] = planned_safety_route_count
            if ep.endpoint_id == MEETING_ENDPOINT_ID and meeting_preview_payload is not None:
                (meeting_records,) = normalize_meeting_payload_block(
                    meeting_preview_payload,
                    project_key=project_key,
                    endpoint_id=ep.endpoint_id,
                    correlation_id=self.correlation_id,
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                )
                meeting_review_count = sum(1 for r in meeting_records if r["review_required"])
                entry["planned_meeting_record_count"] = len(meeting_records)
                entry["planned_review_required_count"] = meeting_review_count
            if (
                ep.endpoint_id == MEETING_TOPIC_ENDPOINT_ID
                and meeting_topic_preview_payload is not None
            ):
                (topic_records,) = normalize_meeting_topic_payload_block(
                    meeting_topic_preview_payload,
                    project_key=project_key,
                    endpoint_id=ep.endpoint_id,
                    correlation_id=self.correlation_id,
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                )
                topic_review_count = sum(1 for r in topic_records if r["review_required"])
                topic_safety_count = sum(1 for r in topic_records if r.get("safety_route"))
                entry["planned_meeting_topic_record_count"] = len(topic_records)
                entry["planned_review_required_count"] = topic_review_count
                entry["planned_safety_route_count"] = topic_safety_count
            if (
                ep.endpoint_id == OBSERVATION_ENDPOINT_ID
                and observation_preview_payload is not None
            ):
                observation_records, comment_records = normalize_observation_payload_block(
                    observation_preview_payload,
                    project_key=project_key,
                    endpoint_id=ep.endpoint_id,
                    correlation_id=self.correlation_id,
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                )
                parent_review_count = sum(1 for r in observation_records if r["review_required"])
                safety_route_count = sum(1 for r in observation_records if r.get("safety_route"))
                entry["planned_observation_record_count"] = len(observation_records)
                entry["planned_comment_record_count"] = len(comment_records)
                # Every comment is always review-required; parents contribute
                # per their heuristic.
                entry["planned_review_required_count"] = parent_review_count + len(comment_records)
                entry["planned_safety_route_count"] = safety_route_count
            if ep.endpoint_id == SUBMITTAL_ENDPOINT_ID and submittal_preview_payload is not None:
                (
                    submittal_records,
                    response_records,
                    package_records,
                ) = normalize_submittal_payload_block(
                    submittal_preview_payload,
                    project_key=project_key,
                    endpoint_id=ep.endpoint_id,
                    correlation_id=self.correlation_id,
                    fetched_at=datetime.now(timezone.utc).isoformat(),
                )
                parent_review_count = sum(1 for r in submittal_records if r["review_required"])
                entry["planned_submittal_record_count"] = len(submittal_records)
                entry["planned_response_record_count"] = len(response_records)
                entry["planned_package_record_count"] = len(package_records)
                # All response + package records are always review_required by
                # construction; the parent count is the meaningful signal.
                entry["planned_review_required_count"] = (
                    parent_review_count + len(response_records) + len(package_records)
                )
            plan_details.append(entry)

        receipt.total_planned_requests = total_requests
        receipt.category_counts = cat_counts
        receipt.sensitivity_counts = sens_counts
        receipt.per_endpoint = plan_details
        receipt.completed_at = datetime.now(timezone.utc).isoformat()
        return receipt

    def _apply_one(
        self,
        project_key: str,
        *,
        endpoints: Optional[List[str]] = None,
        policy: Policy = "auto",
        full_refresh: bool = False,
    ) -> SyncReceipt:
        """Apply sync for a single real pilot ``project_key``. Re-evaluates the audit
        gate, then GET-only fetch + idempotent local SQLite upserts for that project.
        Never external writeback. Never non-GET. Returns the (un-redacted) receipt
        object; redaction + aggregation happen in ``_aggregate_receipts``.
        """
        # Local import to avoid potential cycles (pattern used elsewhere e.g. vault_writer)
        from hb_assistant.store.repositories import (  # type: ignore
            get_procore_sync_watermark,
            set_procore_sync_watermark,
            upsert_procore_synced_entity,
        )

        started = datetime.now(timezone.utc).isoformat()
        receipt = SyncReceipt(
            sync_id=str(uuid.uuid4()),
            mode="apply",
            pilot_project_key=project_key,
            project_scope=project_key,
            company_id="5280",
            started_at=started,
            guardrails=self._build_guardrails_block(),
            policy_used="full" if full_refresh else policy,
        )

        # Resolve the real Procore project id for per-project request targeting.
        mapping = self._load_project_registry().get(project_key)
        procore_project_id = mapping.procore_project_id if mapping else project_key

        if self.auditor is not None and hasattr(self.auditor, "audit_endpoints_for_pilots"):
            verdict_map = self.auditor.audit_endpoints_for_pilots([project_key])  # type: ignore[attr-defined]
            verdict_summary = {
                "available": sum(1 for v in verdict_map.values() if v == "available"),
                "non_available": sum(1 for v in verdict_map.values() if v != "available"),
            }
            all_available = all(v == "available" for v in verdict_map.values())
        else:
            contract = load_endpoint_contract()
            projects = self._load_project_registry()
            auditor = EndpointAuditor(contract, projects)
            audit_receipt = auditor.build_audit_run_receipt(
                project_key,
                base_url="https://api.procore.com",
                mode="dry_run",
            )
            verdict_summary = dict((audit_receipt.breakdown or {}).get("by_verdict", {}))
            all_available = verdict_summary.get("available", 0) > 0
        receipt.audit_prerequisite_passed = bool(all_available)
        receipt.audit_verdict_summary = verdict_summary or {"available": 0}

        if not all_available:
            receipt.completed_at = datetime.now(timezone.utc).isoformat()
            receipt.redacted_errors.append(
                {"error": "audit_prerequisite_failed", "correlation": self.correlation_id}
            )
            return receipt

        client = self._get_client()  # Prompt_04, secret at this moment only

        contract = load_endpoint_contract()
        total_items = 0
        errors: List[Dict[str, Any]] = []

        for ep in contract.endpoints:
            if endpoints and ep.endpoint_id not in endpoints:
                continue
            if not ep.is_live_eligible:
                receipt.per_endpoint.append(
                    {
                        "endpoint_id": ep.endpoint_id,
                        "items_written": 0,
                        "status": "skipped_not_live_eligible",
                        "verification_status": ep.verification_status,
                        "endpoint_status": ep.status,
                    }
                )
                continue
            try:
                # Watermark / incremental decision (simplified MVP; full in later iteration)
                watermark = None
                if not full_refresh and policy != "full":
                    watermark = get_procore_sync_watermark(
                        self.db_path, ep.endpoint_id, project_key
                    )

                # Execute via Prompt_04 client (GET + pagination + retry + redaction inside)
                items = client.paginate(
                    path=ep.path_template.format(company_id="5280", project_id=procore_project_id),
                    params={"updated_after": watermark} if watermark else None,
                )

                fetched_at = datetime.now(timezone.utc).isoformat()
                if ep.endpoint_id == RFI_ENDPOINT_ID:
                    parent_written = 0
                    reply_written = 0
                    for item in items:
                        rfi_record = normalize_rfi(
                            item,
                            project_key=project_key,
                            endpoint_id=ep.endpoint_id,
                            correlation_id=self.correlation_id,
                            fetched_at=fetched_at,
                        )
                        upsert_procore_synced_entity(
                            self.db_path, rfi_record, correlation=self.correlation_id
                        )
                        parent_written += 1
                        total_items += 1
                        for raw_reply in item.get("replies") or []:
                            if not isinstance(raw_reply, dict):
                                continue
                            reply_record = normalize_rfi_reply(
                                raw_reply,
                                parent_procore_id=rfi_record["entity_stable_key"],
                                project_key=project_key,
                                endpoint_id=ep.endpoint_id,
                                correlation_id=self.correlation_id,
                                fetched_at=fetched_at,
                            )
                            upsert_procore_synced_entity(
                                self.db_path,
                                reply_record,
                                correlation=self.correlation_id,
                            )
                            reply_written += 1
                            total_items += 1
                    items_written = parent_written + reply_written
                    endpoint_entry: Dict[str, Any] = {
                        "endpoint_id": ep.endpoint_id,
                        "items_written": items_written,
                        "rfi_records_written": parent_written,
                        "reply_records_written": reply_written,
                        "status": "success",
                    }
                elif ep.endpoint_id == DAILY_LOG_ENDPOINT_ID:
                    from hb_assistant.procore.daily_log_selection import (
                        load_daily_log_selection,
                    )

                    selection_scope = load_daily_log_selection()
                    records_by_category = normalize_daily_log_payload_block(
                        list(items),
                        selection_scope=selection_scope,
                        project_key=project_key,
                        endpoint_id=ep.endpoint_id,
                        correlation_id=self.correlation_id,
                        fetched_at=fetched_at,
                    )
                    counts_by_category: Dict[str, int] = {}
                    safety_routed = 0
                    review_required_written = 0
                    for category, records in records_by_category.items():
                        for record in records:
                            upsert_procore_synced_entity(
                                self.db_path,
                                record,
                                correlation=self.correlation_id,
                            )
                            counts_by_category[category] = counts_by_category.get(category, 0) + 1
                            total_items += 1
                            if record.get("safety_route"):
                                safety_routed += 1
                            if record.get("review_required"):
                                review_required_written += 1
                    items_written = sum(counts_by_category.values())
                    endpoint_entry = {
                        "endpoint_id": ep.endpoint_id,
                        "items_written": items_written,
                        "records_by_category": counts_by_category,
                        "review_required_count": review_required_written,
                        "safety_route_count": safety_routed,
                        "status": "success",
                    }
                elif ep.endpoint_id == MEETING_ENDPOINT_ID:
                    meeting_written = 0
                    for item in items:
                        meeting_record = normalize_meeting(
                            item,
                            project_key=project_key,
                            endpoint_id=ep.endpoint_id,
                            correlation_id=self.correlation_id,
                            fetched_at=fetched_at,
                        )
                        upsert_procore_synced_entity(
                            self.db_path,
                            meeting_record,
                            correlation=self.correlation_id,
                        )
                        meeting_written += 1
                        total_items += 1
                    items_written = meeting_written
                    endpoint_entry = {
                        "endpoint_id": ep.endpoint_id,
                        "items_written": items_written,
                        "meeting_records_written": meeting_written,
                        "status": "success",
                    }
                elif ep.endpoint_id == MEETING_TOPIC_ENDPOINT_ID:
                    topic_written = 0
                    safety_routed = 0
                    for item in items:
                        topic_record = normalize_meeting_topic(
                            item,
                            project_key=project_key,
                            endpoint_id=ep.endpoint_id,
                            correlation_id=self.correlation_id,
                            fetched_at=fetched_at,
                        )
                        upsert_procore_synced_entity(
                            self.db_path,
                            topic_record,
                            correlation=self.correlation_id,
                        )
                        topic_written += 1
                        total_items += 1
                        if topic_record.get("safety_route"):
                            safety_routed += 1
                    items_written = topic_written
                    endpoint_entry = {
                        "endpoint_id": ep.endpoint_id,
                        "items_written": items_written,
                        "meeting_topic_records_written": topic_written,
                        "safety_route_count": safety_routed,
                        "status": "success",
                    }
                elif ep.endpoint_id == OBSERVATION_ENDPOINT_ID:
                    observation_written = 0
                    comment_written = 0
                    safety_routed = 0
                    for item in items:
                        observation_record = normalize_observation(
                            item,
                            project_key=project_key,
                            endpoint_id=ep.endpoint_id,
                            correlation_id=self.correlation_id,
                            fetched_at=fetched_at,
                        )
                        upsert_procore_synced_entity(
                            self.db_path,
                            observation_record,
                            correlation=self.correlation_id,
                        )
                        observation_written += 1
                        total_items += 1
                        if observation_record.get("safety_route"):
                            safety_routed += 1
                        parent_key = observation_record["entity_stable_key"]
                        for raw_comment in item.get("comments") or []:
                            if not isinstance(raw_comment, dict):
                                continue
                            comment_record = normalize_observation_comment(
                                raw_comment,
                                parent_observation_stable_key=parent_key,
                                project_key=project_key,
                                endpoint_id=ep.endpoint_id,
                                correlation_id=self.correlation_id,
                                fetched_at=fetched_at,
                            )
                            upsert_procore_synced_entity(
                                self.db_path,
                                comment_record,
                                correlation=self.correlation_id,
                            )
                            comment_written += 1
                            total_items += 1
                    items_written = observation_written + comment_written
                    endpoint_entry = {
                        "endpoint_id": ep.endpoint_id,
                        "items_written": items_written,
                        "observation_records_written": observation_written,
                        "comment_records_written": comment_written,
                        "safety_route_count": safety_routed,
                        "status": "success",
                    }
                elif ep.endpoint_id == SUBMITTAL_ENDPOINT_ID:
                    submittal_written = 0
                    response_written = 0
                    package_written = 0
                    for item in items:
                        submittal_record = normalize_submittal(
                            item,
                            project_key=project_key,
                            endpoint_id=ep.endpoint_id,
                            correlation_id=self.correlation_id,
                            fetched_at=fetched_at,
                        )
                        upsert_procore_synced_entity(
                            self.db_path,
                            submittal_record,
                            correlation=self.correlation_id,
                        )
                        submittal_written += 1
                        total_items += 1
                        parent_key = submittal_record["entity_stable_key"]
                        for raw_response in item.get("responses") or []:
                            if not isinstance(raw_response, dict):
                                continue
                            response_record = normalize_submittal_response(
                                raw_response,
                                parent_procore_id=parent_key,
                                project_key=project_key,
                                endpoint_id=ep.endpoint_id,
                                correlation_id=self.correlation_id,
                                fetched_at=fetched_at,
                            )
                            upsert_procore_synced_entity(
                                self.db_path,
                                response_record,
                                correlation=self.correlation_id,
                            )
                            response_written += 1
                            total_items += 1
                        for raw_package in item.get("packages") or []:
                            if not isinstance(raw_package, dict):
                                continue
                            package_record = normalize_submittal_package(
                                raw_package,
                                parent_procore_id=parent_key,
                                project_key=project_key,
                                endpoint_id=ep.endpoint_id,
                                correlation_id=self.correlation_id,
                                fetched_at=fetched_at,
                            )
                            upsert_procore_synced_entity(
                                self.db_path,
                                package_record,
                                correlation=self.correlation_id,
                            )
                            package_written += 1
                            total_items += 1
                    items_written = submittal_written + response_written + package_written
                    endpoint_entry = {
                        "endpoint_id": ep.endpoint_id,
                        "items_written": items_written,
                        "submittal_records_written": submittal_written,
                        "response_records_written": response_written,
                        "package_records_written": package_written,
                        "status": "success",
                    }
                else:
                    items_written = 0
                    for item in items:
                        normalized = self._normalize(ep, item, project_key)
                        upsert_procore_synced_entity(
                            self.db_path, normalized, correlation=self.correlation_id
                        )
                        items_written += 1
                        total_items += 1
                    endpoint_entry = {
                        "endpoint_id": ep.endpoint_id,
                        "items_written": items_written,
                        "status": "success",
                    }

                # Update watermark (safe, redacted)
                new_watermark = datetime.now(timezone.utc).isoformat()
                set_procore_sync_watermark(self.db_path, ep.endpoint_id, project_key, new_watermark)

                receipt.per_endpoint.append(endpoint_entry)
            except Exception as exc:  # noqa: BLE001
                redacted = redact_for_evidence({"endpoint": ep.endpoint_id, "error": str(exc)})
                errors.append(redacted)
                receipt.per_endpoint.append(
                    {
                        "endpoint_id": ep.endpoint_id,
                        "items_written": 0,
                        "status": "error",
                    }
                )

        receipt.total_items_normalized = total_items
        receipt.redacted_errors = errors
        receipt.persisted_to_sqlite = True
        receipt.completed_at = datetime.now(timezone.utc).isoformat()
        return receipt

    def _normalize(self, ep: Any, raw: Dict[str, Any], project_key: str) -> Dict[str, Any]:
        """Thin normalization. Redact aggressively. Carry review flags + traceability."""
        redacted_raw = redact_for_evidence(raw)
        return {
            "source_project_key": project_key,
            "endpoint_id": ep.endpoint_id,
            "entity_stable_key": str(raw.get("id") or raw.get("uid") or hash(str(redacted_raw))),
            "category": ep.category or "foundation",
            "review_required": ep.status == "sensitive_validated",
            "canonical_fields": {
                k: v
                for k, v in redacted_raw.items()
                if k in ("number", "title", "status", "updated_at")
            },
            "fetched_at": datetime.now(timezone.utc).isoformat(),
            "correlation_id": self.correlation_id,
            "redaction_applied": True,
        }


# Convenience CLI-facing entry (thin wrapper)
def run_sync(
    *,
    project_key: Optional[str] = None,
    dry_run: bool = True,
    apply: bool = False,
    full_refresh: bool = False,
    db_path: Optional[Path] = None,
    json_output: bool = True,
    allow_pending: bool = False,
    endpoints: Optional[List[str]] = None,
    rfi_preview_payload: Optional[List[Dict[str, Any]]] = None,
    submittal_preview_payload: Optional[List[Dict[str, Any]]] = None,
    observation_preview_payload: Optional[List[Dict[str, Any]]] = None,
    meeting_preview_payload: Optional[List[Dict[str, Any]]] = None,
    meeting_topic_preview_payload: Optional[List[Dict[str, Any]]] = None,
    daily_log_preview_payload: Optional[List[Dict[str, Any]]] = None,
) -> Dict[str, Any]:
    """Entry for CLI `procore sync`. Dry-run default. --apply explicit only.

    ``allow_pending=True`` is required to target a project whose mapping
    status is ``pending``; default behavior is fail-closed.

    ``endpoints`` filters the contract to a subset (e.g. ``["list-rfis"]``).
    ``rfi_preview_payload`` is consumed by ``plan()`` only and lets the
    evidence-generation flow surface fixture-derived record counts in the
    dry-run receipt without coupling production planning to fixtures.
    """
    if apply and dry_run:
        dry_run = False  # --apply wins when both present (documented guard in CLI)

    coord = ProcoreSyncCoordinator(db_path=db_path)
    if dry_run or not apply:
        plan = coord.plan(
            project_key=project_key,
            endpoints=endpoints,
            policy="full" if full_refresh else "auto",
            allow_pending=allow_pending,
            rfi_preview_payload=rfi_preview_payload,
            submittal_preview_payload=submittal_preview_payload,
            observation_preview_payload=observation_preview_payload,
            meeting_preview_payload=meeting_preview_payload,
            meeting_topic_preview_payload=meeting_topic_preview_payload,
            daily_log_preview_payload=daily_log_preview_payload,
        )
        return plan  # type: ignore[return-value]
    else:
        receipt = coord.apply(
            project_key=project_key,
            endpoints=endpoints,
            full_refresh=full_refresh,
            policy="full" if full_refresh else "auto",
            allow_pending=allow_pending,
        )
        return receipt  # type: ignore[return-value]
