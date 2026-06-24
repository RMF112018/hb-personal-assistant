"""DB-backed DCMA / GAO / AACE schedule quality assessment engine."""

from __future__ import annotations

import json
from dataclasses import dataclass, field
from decimal import Decimal
from typing import Any

from hb_assistant.store.schedule_activity_repository import ScheduleActivityRepository
from hb_assistant.store.schedule_mapping_repository import ScheduleMappingRepository

from .schedule_critical_path_analytics import (
    METRIC_STATUS_AVAILABLE_XER_DRIVING,
    METRIC_STATUS_AVAILABLE_XER_TOTFLOAT,
    METRIC_STATUS_PARTIAL_XER_FLOAT,
    compute_msp_critical_slack_analytics,
    compute_source_critical_path_analytics,
    resolve_analytics_status,
)
from .schedule_float_derivation import supports_finish_float_derivation
from .schedule_graph import orphan_relationship_ids
from .schedule_quality_normalization import (
    calendar_hours_per_day,
    cost_resource_posture,
    is_logic_excluded_activity,
    normalize_duration_days,
    normalize_lag_result,
    normalize_relationship_type,
    relationship_type_distribution,
)
from .schedule_quality_profiles import (
    DCMA_METRIC_SPECS,
    DISCLAIMER_VERSION,
    SOURCE_EXPORT_METRIC_SPECS,
    SUPPLEMENTAL_METRIC_SPECS,
    AssessmentProfile,
    get_profile,
)

HIGH_FLOAT_DAYS = 44.0
HIGH_DURATION_DAYS = 44.0
EXCESSIVE_LAG_DAYS = 44.0
MAX_EVIDENCE_IDS = 10
EXCESSIVE_LAG_DAYS_DECIMAL = Decimal(str(EXCESSIVE_LAG_DAYS))

METRIC_STATUS_MEASURED = "measured"
METRIC_STATUS_PASS = "passed_threshold"
METRIC_STATUS_WARN = "warning_threshold"
METRIC_STATUS_FAIL = "failed_threshold"
METRIC_STATUS_NOT_MEASURABLE = "not_measurable_missing_data"
METRIC_STATUS_NA = "not_applicable"
METRIC_STATUS_DERIVED_FINISH_FLOAT = "measured_from_derived_finish_float"
METRIC_STATUS_PARTIAL_CRITICAL_FLOAT = "partially_measurable_critical_float_available"
METRIC_STATUS_NOT_MEASURABLE_LONGEST_PATH = "not_measurable_missing_longest_path_data"
METRIC_STATUS_NOT_MEASURABLE_RECALC = "not_measurable_requires_recalculation"
METRIC_STATUS_XER_DRIVING_PATH = "measured_from_xer_driving_path"
METRIC_STATUS_MSP_CRITICAL = "measured_from_msp_critical_flag"
METRIC_STATUS_EXPLICIT_FLOAT = "measured_from_explicit_source_float"
METRIC_STATUS_SOURCE_EXPORT_PROXY = "measured_from_source_export_proxy"

MEASURED_STATUSES = (
    METRIC_STATUS_PASS,
    METRIC_STATUS_WARN,
    METRIC_STATUS_FAIL,
    METRIC_STATUS_MEASURED,
    METRIC_STATUS_DERIVED_FINISH_FLOAT,
    METRIC_STATUS_PARTIAL_CRITICAL_FLOAT,
    METRIC_STATUS_XER_DRIVING_PATH,
    METRIC_STATUS_MSP_CRITICAL,
    METRIC_STATUS_EXPLICIT_FLOAT,
)


@dataclass
class EvaluationContext:
    project_key: str
    schedule_version_key: str
    schedule_table_id: str | None
    import_id: str | None
    evaluation_run_id: str
    assessment_profile: AssessmentProfile
    data_date: str | None = None
    activities: list[dict[str, Any]] = field(default_factory=list)
    relationships: list[dict[str, Any]] = field(default_factory=list)
    wbs_nodes: list[dict[str, Any]] = field(default_factory=list)
    calendars: list[dict[str, Any]] = field(default_factory=list)
    prior_diff: dict[str, Any] | None = None
    import_meta: dict[str, Any] | None = None
    schedule_options: dict[str, Any] | None = None
    code_assignments: list[dict[str, Any]] = field(default_factory=list)
    udf_values: list[dict[str, Any]] = field(default_factory=list)


def _parse_threshold(value: Any) -> float:
    if value is None or str(value).strip() == "":
        return 0.0
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def _decimal_evidence_value(value: Decimal | None) -> str | None:
    if value is None:
        return None
    return format(value.normalize(), "f")


@dataclass
class EvaluationResult:
    metrics: list[dict[str, Any]]
    findings: list[dict[str, Any]]
    scorecard: dict[str, Any]


class ScheduleQualityDataLoader:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._activity_repo = ScheduleActivityRepository(db_path=db_path)
        self._mapping_repo = ScheduleMappingRepository(db_path=db_path)

    def load(self, schedule_version_key: str) -> dict[str, Any]:
        total = self._activity_repo.count_activities(schedule_version_key)
        activities = self._activity_repo.list_activities(
            schedule_version_key, limit=max(total, 1), offset=0
        )
        relationships = self._activity_repo.list_relationships(schedule_version_key)
        import_meta = self._activity_repo.get_version_summary(schedule_version_key)
        wbs_nodes = self._load_table("procore_ep_schedule_wbs_nodes", schedule_version_key)
        calendars = self._load_table("procore_ep_schedule_calendars", schedule_version_key)
        code_assignments = self._load_table(
            "procore_ep_schedule_activity_code_assignments", schedule_version_key
        )
        udf_values = self._load_table("procore_ep_schedule_udf_values", schedule_version_key)
        schedule_table_id = None
        data_date = None
        if activities:
            schedule_table_id = activities[0].get("schedule_table_id")
        if import_meta:
            parts = str(schedule_version_key).split("|")
            data_date = parts[2] if len(parts) >= 3 else None
        prior_diff = self._latest_diff(schedule_version_key)
        schedule_options = None
        if import_meta:
            schedule_options = {
                "compute_total_float_type": import_meta.get("compute_total_float_type"),
                "critical_activity_path_type": import_meta.get("critical_activity_path_type"),
                "critical_activity_float_threshold": _parse_threshold(
                    import_meta.get("critical_activity_float_threshold")
                ),
                "calculate_float_based_on_finish_date": import_meta.get(
                    "calculate_float_based_on_finish_date"
                ),
                "critical_path_type": import_meta.get("critical_path_type"),
                "critical_float_threshold": import_meta.get("critical_float_threshold"),
            }
        return {
            "activities": activities,
            "relationships": relationships,
            "wbs_nodes": wbs_nodes,
            "calendars": calendars,
            "import_meta": import_meta,
            "schedule_options": schedule_options,
            "schedule_table_id": schedule_table_id,
            "data_date": data_date,
            "prior_diff": prior_diff,
            "code_assignments": code_assignments,
            "udf_values": udf_values,
        }

    def _load_table(self, table: str, schedule_version_key: str) -> list[dict[str, Any]]:
        from hb_assistant.store.connection import get_connection

        conn = get_connection(self._db_path)
        cur = conn.execute(
            f"SELECT * FROM {table} WHERE schedule_version_key=?",
            (schedule_version_key,),
        )
        rows = [dict(r) for r in cur.fetchall()]
        conn.close()
        return rows

    def _latest_diff(self, schedule_version_key: str) -> dict[str, Any] | None:
        from hb_assistant.store.connection import get_connection

        conn = get_connection(self._db_path)
        cur = conn.execute(
            """
            SELECT * FROM schedule_version_diffs
            WHERE to_schedule_version_key=? ORDER BY created_at DESC LIMIT 1
            """,
            (schedule_version_key,),
        )
        row = cur.fetchone()
        conn.close()
        return dict(row) if row else None


class ScheduleQualityAssessmentEngine:
    def evaluate(self, ctx: EvaluationContext) -> EvaluationResult:
        profile = ctx.assessment_profile
        metrics: list[dict[str, Any]] = []
        findings: list[dict[str, Any]] = []

        for code in profile.dcma_metrics:
            metric, metric_findings = self._evaluate_dcma_metric(ctx, code)
            metrics.append(metric)
            findings.extend(metric_findings)

        metrics.extend(self._evaluate_source_export_metrics(ctx))
        metrics.extend(self._evaluate_supplemental_metrics(ctx))

        gao_summary: dict[str, dict[str, Any]] = {}
        for category in profile.gao_categories:
            summary, cat_findings = self._evaluate_gao_category(ctx, category)
            gao_summary[category] = summary
            findings.extend(cat_findings)

        for category in profile.aace_categories:
            if category in gao_summary:
                continue
            summary, cat_findings = self._evaluate_aace_category(ctx, category)
            gao_summary[category] = summary
            findings.extend(cat_findings)

        scorecard = self._build_scorecard(ctx, metrics, findings, gao_summary)
        return EvaluationResult(metrics=metrics, findings=findings, scorecard=scorecard)

    def _evaluate_dcma_metric(
        self, ctx: EvaluationContext, code: str
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        spec = DCMA_METRIC_SPECS[code]
        evaluators = {
            "dcma_logic": self._metric_logic,
            "dcma_leads": self._metric_leads,
            "dcma_lags": self._metric_lags,
            "dcma_relationship_types": self._metric_rel_types,
            "dcma_hard_constraints": self._metric_constraints,
            "dcma_high_float": self._metric_high_float,
            "dcma_negative_float": self._metric_negative_float,
            "dcma_high_duration": self._metric_high_duration,
            "dcma_invalid_dates": self._metric_invalid_dates,
            "dcma_resources_cost_loading": self._metric_cost_loading,
            "dcma_missed_tasks": self._metric_missed_tasks,
            "dcma_critical_path_test": self._metric_critical_path_test,
            "dcma_cpli": self._metric_cpli,
            "dcma_bei": self._metric_bei,
        }
        return evaluators[code](ctx, code, spec)

    def _evaluate_source_export_metrics(
        self, ctx: EvaluationContext
    ) -> list[dict[str, Any]]:
        source_fmt = self._import_source_format(ctx)
        if source_fmt == "primavera_xer":
            spec = SOURCE_EXPORT_METRIC_SPECS["source_critical_path_available"]
            metric, _ = self._metric_source_critical_path_available(
                ctx,
                "source_critical_path_available",
                spec,
            )
            return [metric]
        if source_fmt == "ms_project_xml":
            spec = SOURCE_EXPORT_METRIC_SPECS["source_msp_critical_slack_available"]
            metric, _ = self._metric_source_msp_critical_slack_available(
                ctx,
                "source_msp_critical_slack_available",
                spec,
            )
            return [metric]
        return []

    def _evaluate_supplemental_metrics(
        self, ctx: EvaluationContext
    ) -> list[dict[str, Any]]:
        supplemental: list[dict[str, Any]] = []
        source_fmt = self._import_source_format(ctx)
        if source_fmt != "primavera_xer":
            return supplemental
        driving = [a for a in ctx.activities if a.get("source_driving_path_flag")]
        if not driving:
            return supplemental
        spec = SUPPLEMENTAL_METRIC_SPECS["source_driving_path_integrity_proxy"]
        metric, _ = self._metric_source_driving_path_integrity_proxy(
            ctx,
            "source_driving_path_integrity_proxy",
            spec,
            driving,
        )
        supplemental.append(metric)
        return supplemental

    def _metric_source_critical_path_available(
        self,
        ctx: EvaluationContext,
        code: str,
        spec: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        analytics = compute_source_critical_path_analytics(
            ctx.import_meta,
            ctx.activities,
            schedule_options=ctx.schedule_options,
        )
        status = resolve_analytics_status(analytics)
        critical_count = int(analytics.get("source_critical_activity_count") or 0)
        coverage_denom = int(analytics.get("source_critical_coverage_denominator") or 0)
        return (
            self._base_metric(
                ctx,
                code=code,
                spec=spec,
                status=status,
                numerator=critical_count,
                denominator=coverage_denom or len(ctx.activities),
                value=critical_count,
                metric_family="source_export",
                not_measurable_reason=(
                    None
                    if status
                    in (
                        METRIC_STATUS_AVAILABLE_XER_DRIVING,
                        METRIC_STATUS_AVAILABLE_XER_TOTFLOAT,
                        METRIC_STATUS_PARTIAL_XER_FLOAT,
                    )
                    else "no source-export critical path basis recognized"
                ),
                evidence={
                    **analytics,
                    "display_name_override": "Source critical path analytics",
                    "not_a_dcma_critical_path_test": True,
                },
            ),
            [],
        )

    def _metric_source_msp_critical_slack_available(
        self,
        ctx: EvaluationContext,
        code: str,
        spec: dict[str, Any],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        analytics = compute_msp_critical_slack_analytics(ctx.activities)
        status = resolve_analytics_status(analytics)
        consistent = int(analytics.get("consistent_critical_slack_count") or 0)
        eligible = int(analytics.get("eligible_evidence_activity_count") or 0)
        return (
            self._base_metric(
                ctx,
                code=code,
                spec=spec,
                status=status,
                numerator=consistent,
                denominator=eligible,
                value=analytics.get("consistency_ratio"),
                metric_family="source_export",
                not_measurable_reason=None
                if eligible
                else "no MSP critical/slack source-export evidence",
                evidence={
                    **analytics,
                    "display_name_override": "MSP source critical/slack consistency",
                },
            ),
            [],
        )

    def _base_metric(
        self,
        ctx: EvaluationContext,
        *,
        code: str,
        spec: dict[str, Any],
        status: str,
        numerator: Any = None,
        denominator: Any = None,
        value: Any = None,
        not_measurable_reason: str | None = None,
        evidence: dict[str, Any] | None = None,
        related_codes: list[str] | None = None,
        metric_family: str = "dcma",
    ) -> dict[str, Any]:
        return {
            "evaluation_run_id": ctx.evaluation_run_id,
            "project_key": ctx.project_key,
            "schedule_version_key": ctx.schedule_version_key,
            "metric_code": code,
            "metric_name": spec["metric_name"],
            "metric_family": metric_family,
            "numerator": str(numerator) if numerator is not None else None,
            "denominator": str(denominator) if denominator is not None else None,
            "value": str(value) if value is not None else None,
            "unit": spec.get("unit"),
            "threshold_warning": str(spec["threshold_warning"])
            if spec.get("threshold_warning") is not None
            else None,
            "threshold_fail": str(spec["threshold_fail"])
            if spec.get("threshold_fail") is not None
            else None,
            "status": status,
            "not_measurable_reason": not_measurable_reason,
            "evidence_json": json.dumps(evidence or {}),
            "related_finding_codes_json": json.dumps(related_codes or []),
        }

    def _status_from_ratio(
        self, ratio: float, spec: dict[str, Any], *, higher_is_better: bool = False
    ) -> str:
        if spec.get("threshold_fail") is None:
            return METRIC_STATUS_MEASURED
        warn = float(spec["threshold_warning"])
        fail = float(spec["threshold_fail"])
        if higher_is_better:
            if ratio >= warn:
                return METRIC_STATUS_PASS
            if ratio >= fail:
                return METRIC_STATUS_WARN
            return METRIC_STATUS_FAIL
        if ratio <= warn:
            return METRIC_STATUS_PASS
        if ratio <= fail:
            return METRIC_STATUS_WARN
        return METRIC_STATUS_FAIL

    def _metric_logic(
        self, ctx: EvaluationContext, code: str, spec: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        acts = ctx.activities
        rels = ctx.relationships
        findings: list[dict[str, Any]] = []
        if not acts:
            return (
                self._base_metric(
                    ctx,
                    code=code,
                    spec=spec,
                    status=METRIC_STATUS_NOT_MEASURABLE,
                    not_measurable_reason="no activities in canonical store",
                ),
                findings,
            )
        if not rels:
            return (
                self._base_metric(
                    ctx,
                    code=code,
                    spec=spec,
                    status=METRIC_STATUS_NOT_MEASURABLE,
                    not_measurable_reason="no relationships in canonical store",
                ),
                findings,
            )

        activity_ids = {str(a["activity_id"]) for a in acts if a.get("activity_id")}
        assessed: list[dict[str, Any]] = []
        excluded = 0
        exclusion_reasons: dict[str, int] = {}
        for act in acts:
            skip, reason = is_logic_excluded_activity(act)
            if skip:
                excluded += 1
                if reason:
                    exclusion_reasons[reason] = exclusion_reasons.get(reason, 0) + 1
                continue
            assessed.append(act)

        preds_by_succ: dict[str, set[str]] = {}
        succs_by_pred: dict[str, set[str]] = {}
        rel_keys: set[str] = set()
        duplicate_relationship_count = 0
        self_relationship_count = 0
        for rel in rels:
            pred = str(rel.get("predecessor_activity_id") or "")
            succ = str(rel.get("successor_activity_id") or "")
            if pred and pred == succ:
                self_relationship_count += 1
            key = f"{pred}|{succ}|{normalize_relationship_type(rel.get('relationship_type'))}"
            if key in rel_keys:
                duplicate_relationship_count += 1
            rel_keys.add(key)
            if succ:
                preds_by_succ.setdefault(succ, set()).add(pred)
            if pred:
                succs_by_pred.setdefault(pred, set()).add(succ)

        open_start_count = 0
        open_finish_count = 0
        for act in assessed:
            aid = str(act.get("activity_id") or "")
            if not preds_by_succ.get(aid):
                open_start_count += 1
            if not succs_by_pred.get(aid):
                open_finish_count += 1

        orphans = orphan_relationship_ids(rels, activity_ids)
        invalid_relationship_reference_count = len(orphans)
        for o in orphans[:MAX_EVIDENCE_IDS]:
            findings.append(
                self._finding(
                    ctx,
                    finding_code="orphan_relationship",
                    severity="warning",
                    finding_type="logic",
                    category="dcma",
                    metric_code=code,
                    summary=f"Relationship references missing activity: {o}",
                    requires_review=1,
                )
            )

        logic_defects = (
            open_start_count
            + open_finish_count
            + invalid_relationship_reference_count
            + duplicate_relationship_count
            + self_relationship_count
        )
        denom = len(assessed) if assessed else len(acts)
        ratio = logic_defects / denom if denom else 0.0
        evidence = {
            "open_start_count": open_start_count,
            "open_finish_count": open_finish_count,
            "invalid_relationship_reference_count": invalid_relationship_reference_count,
            "duplicate_relationship_count": duplicate_relationship_count,
            "self_relationship_count": self_relationship_count,
            "excluded_activity_count": excluded,
            "exclusion_reasons": exclusion_reasons,
        }
        return (
            self._base_metric(
                ctx,
                code=code,
                spec=spec,
                status=self._status_from_ratio(ratio, spec),
                numerator=logic_defects,
                denominator=denom,
                value=round(ratio, 4),
                evidence=evidence,
                related_codes=["orphan_relationship", "open_start", "open_finish"],
            ),
            findings,
        )

    def _metric_leads(
        self, ctx: EvaluationContext, code: str, spec: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        return self._lag_metric(ctx, code, spec, negative_only=True)

    def _metric_lags(
        self, ctx: EvaluationContext, code: str, spec: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        return self._lag_metric(ctx, code, spec, negative_only=False, excessive_only=True)

    def _lag_metric(
        self,
        ctx: EvaluationContext,
        code: str,
        spec: dict[str, Any],
        *,
        negative_only: bool = False,
        excessive_only: bool = False,
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        rels = ctx.relationships
        findings: list[dict[str, Any]] = []
        if not rels:
            return (
                self._base_metric(
                    ctx,
                    code=code,
                    spec=spec,
                    status=METRIC_STATUS_NOT_MEASURABLE,
                    not_measurable_reason="no relationships in canonical store",
                ),
                findings,
            )
        bad = 0
        normalized_count = 0
        assumed_day_count = 0
        skipped_unparseable_count = 0
        unit_distribution: dict[str, int] = {}
        conversion_status_distribution = {
            "known_unit": 0,
            "assumed_days": 0,
            "unparseable": 0,
        }
        max_positive_lag_days: Decimal | None = None
        min_negative_lag_days: Decimal | None = None
        finding_samples: list[dict[str, Any]] = []
        for rel in rels:
            result = normalize_lag_result(rel.get("lag_value"), rel.get("lag_unit"))
            unit_key = result.source_unit_label or "(missing)"
            unit_distribution[unit_key] = unit_distribution.get(unit_key, 0) + 1
            conversion_status_distribution[result.conversion_status] += 1
            if result.conversion_status == "known_unit":
                normalized_count += 1
            elif result.conversion_status == "assumed_days":
                assumed_day_count += 1
            else:
                skipped_unparseable_count += 1
                continue
            lag_days = result.normalized_days
            if lag_days is None:
                skipped_unparseable_count += 1
                continue
            if lag_days > 0 and (
                max_positive_lag_days is None or lag_days > max_positive_lag_days
            ):
                max_positive_lag_days = lag_days
            if lag_days < 0 and (
                min_negative_lag_days is None or lag_days < min_negative_lag_days
            ):
                min_negative_lag_days = lag_days
            hit = False
            if negative_only and lag_days < 0 or excessive_only and lag_days > EXCESSIVE_LAG_DAYS_DECIMAL:
                hit = True
            if hit:
                bad += 1
                relationship_id = (
                    rel.get("relationship_id")
                    or rel.get("source_relationship_object_id")
                    or rel.get("relationship_row_id")
                    or (
                        f"{rel.get('predecessor_activity_id')}->"
                        f"{rel.get('successor_activity_id')}"
                    )
                )
                finding_evidence = {
                    "relationship_id": relationship_id,
                    "predecessor_activity_id": rel.get("predecessor_activity_id"),
                    "successor_activity_id": rel.get("successor_activity_id"),
                    "raw_lag_value": rel.get("lag_value"),
                    "raw_lag_unit": rel.get("lag_unit"),
                    "normalized_lag_days": _decimal_evidence_value(lag_days),
                    "conversion_status": result.conversion_status,
                }
                if len(finding_samples) < MAX_EVIDENCE_IDS:
                    finding_samples.append(finding_evidence)
                findings.append(
                    self._finding(
                        ctx,
                        finding_code="lag_out_of_range",
                        severity="warning",
                        finding_type="lags",
                        category="dcma",
                        metric_code=code,
                        relationship_id=relationship_id,
                        summary=(
                            "Relationship lag value "
                            f"{_decimal_evidence_value(lag_days)} days is out of expected range"
                        ),
                        evidence=finding_evidence,
                    )
                )
        ratio = bad / len(rels)
        evidence = {
            "total_relationships_assessed": len(rels),
            "lag_values_normalized_count": normalized_count,
            "assumed_day_count": assumed_day_count,
            "skipped_unparseable_count": skipped_unparseable_count,
            "unit_distribution": unit_distribution,
            "conversion_status_distribution": conversion_status_distribution,
            "observed_units": sorted(unit_distribution)[:MAX_EVIDENCE_IDS],
            "max_positive_lag_days": _decimal_evidence_value(max_positive_lag_days),
            "min_negative_lag_days": _decimal_evidence_value(min_negative_lag_days),
            "excessive_lag_threshold_days": _decimal_evidence_value(
                EXCESSIVE_LAG_DAYS_DECIMAL
            ),
            "finding_samples": finding_samples,
        }
        return (
            self._base_metric(
                ctx,
                code=code,
                spec=spec,
                status=self._status_from_ratio(ratio, spec),
                numerator=bad,
                denominator=len(rels),
                value=round(ratio, 4),
                evidence=evidence,
            ),
            findings,
        )

    def _metric_rel_types(
        self, ctx: EvaluationContext, code: str, spec: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        rels = ctx.relationships
        if not rels:
            return (
                self._base_metric(
                    ctx,
                    code=code,
                    spec=spec,
                    status=METRIC_STATUS_NOT_MEASURABLE,
                    not_measurable_reason="no relationships in canonical store",
                ),
                [],
            )
        distribution = relationship_type_distribution(rels)
        fs_count = distribution.get("FS", 0)
        ratio = fs_count / len(rels)
        return (
            self._base_metric(
                ctx,
                code=code,
                spec=spec,
                status=self._status_from_ratio(ratio, spec, higher_is_better=True),
                numerator=fs_count,
                denominator=len(rels),
                value=round(ratio, 4),
                evidence={
                    "distribution": distribution,
                    "numerator_basis": "fs_relationship_count",
                    "denominator_basis": "all_relationships",
                },
            ),
            [],
        )

    def _metric_constraints(
        self, ctx: EvaluationContext, code: str, spec: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        acts = ctx.activities
        if not acts:
            return (
                self._base_metric(
                    ctx,
                    code=code,
                    spec=spec,
                    status=METRIC_STATUS_NOT_MEASURABLE,
                    not_measurable_reason="no activities in canonical store",
                ),
                [],
            )
        hard = [a for a in acts if a.get("constraint_type")]
        if not hard and not any(a.get("calendar_id") for a in acts):
            return (
                self._base_metric(
                    ctx,
                    code=code,
                    spec=spec,
                    status=METRIC_STATUS_NOT_MEASURABLE,
                    not_measurable_reason="no constraint fields populated in canonical store",
                ),
                [],
            )
        ratio = len(hard) / len(acts)
        return (
            self._base_metric(
                ctx,
                code=code,
                spec=spec,
                status=self._status_from_ratio(ratio, spec),
                numerator=len(hard),
                denominator=len(acts),
                value=round(ratio, 4),
            ),
            [],
        )

    def _metric_high_float(
        self, ctx: EvaluationContext, code: str, spec: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        return self._float_metric(ctx, code, spec, mode="high")

    def _metric_negative_float(
        self, ctx: EvaluationContext, code: str, spec: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        return self._float_metric(ctx, code, spec, mode="negative")

    def _import_source_format(self, ctx: EvaluationContext) -> str:
        if ctx.import_meta:
            return str(ctx.import_meta.get("source_format") or "")
        return ""

    def _coding_coverage(self, ctx: EvaluationContext) -> dict[str, int]:
        coded = {
            str(c["activity_id"])
            for c in ctx.code_assignments
            if c.get("activity_id") is not None
        }
        udf_coded = {
            str(u["activity_id"]) for u in ctx.udf_values if u.get("activity_id") is not None
        }
        direct_cost_code = sum(1 for a in ctx.activities if a.get("cost_code"))
        return {
            "schedule_coding_coverage_count": len(coded),
            "udf_coverage_count": len(udf_coded),
            "activity_code_coverage_count": len(coded) or direct_cost_code,
            "code_assignment_row_count": len(ctx.code_assignments),
            "udf_row_count": len(ctx.udf_values),
        }

    def _activity_percent_complete(self, activity: dict[str, Any]) -> float | None:
        pc = activity.get("percent_complete")
        if pc is None or str(pc).strip() == "":
            return None
        try:
            return float(pc)
        except (TypeError, ValueError):
            return None

    def _is_completed_activity(self, activity: dict[str, Any]) -> bool:
        status = str(activity.get("activity_status") or "")
        if status == "TK_Complete":
            return True
        pct = self._activity_percent_complete(activity)
        return pct is not None and pct >= 100.0

    def _is_started_activity(self, activity: dict[str, Any]) -> bool:
        status = str(activity.get("activity_status") or "")
        if status in {"TK_Active", "TK_Complete"}:
            return True
        pct = self._activity_percent_complete(activity)
        return pct is not None and pct > 0.0

    def _canonical_actual_start(self, activity: dict[str, Any]) -> str | None:
        raw = activity.get("actual_start")
        return str(raw) if raw else None

    def _canonical_actual_finish(self, activity: dict[str, Any]) -> str | None:
        raw = activity.get("actual_finish")
        return str(raw) if raw else None

    def _explicit_float_days(self, activity: dict[str, Any]) -> float | None:
        raw = activity.get("explicit_total_float_days")
        if raw is None or str(raw).strip() == "":
            return None
        try:
            return float(raw)
        except (TypeError, ValueError):
            return None

    def _activity_float_days(
        self, activity: dict[str, Any]
    ) -> tuple[float | None, bool, str]:
        explicit = self._explicit_float_days(activity)
        if explicit is not None:
            return explicit, False, "explicit"
        if activity.get("derived_float_basis"):
            try:
                return float(activity["derived_total_float_days"]), True, "derived"
            except (TypeError, ValueError):
                pass
        if activity.get("total_float") is not None:
            try:
                return float(activity["total_float"]), False, "export"
            except (TypeError, ValueError):
                pass
        return None, False, "missing"

    def _is_p6_derived_only(self, ctx: EvaluationContext) -> bool:
        fmt = self._import_source_format(ctx)
        if fmt and fmt != "primavera_pmxml":
            return False
        if any(a.get("critical_path_source") == "xer_driving_path_flag" for a in ctx.activities):
            return False
        if any(a.get("critical_path_source") == "msp_critical_flag" for a in ctx.activities):
            return False
        return supports_finish_float_derivation(ctx.schedule_options) or any(
            a.get("derived_float_basis") for a in ctx.activities
        )

    def _float_metric(
        self, ctx: EvaluationContext, code: str, spec: dict[str, Any], *, mode: str
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        floats: list[float] = []
        derived_used = False
        explicit_used = False
        for a in ctx.activities:
            val, is_derived, source_kind = self._activity_float_days(a)
            if val is not None:
                floats.append(val)
                derived_used = derived_used or is_derived
                explicit_used = explicit_used or source_kind == "explicit"
        if not floats:
            return (
                self._base_metric(
                    ctx,
                    code=code,
                    spec=spec,
                    status=METRIC_STATUS_NOT_MEASURABLE,
                    not_measurable_reason="no derived or export float values in canonical store",
                ),
                [],
            )
        if mode == "high":
            bad = sum(1 for f in floats if f > HIGH_FLOAT_DAYS)
        else:
            bad = sum(1 for f in floats if f < 0)
        ratio = bad / len(floats)
        threshold_status = self._status_from_ratio(ratio, spec)
        if explicit_used and not derived_used:
            status = METRIC_STATUS_EXPLICIT_FLOAT
        elif derived_used:
            status = METRIC_STATUS_DERIVED_FINISH_FLOAT
        else:
            status = threshold_status
        return (
            self._base_metric(
                ctx,
                code=code,
                spec=spec,
                status=status,
                numerator=bad,
                denominator=len(floats),
                value=round(ratio, 4),
                evidence={
                    "method": (
                        "explicit_source_float"
                        if explicit_used and not derived_used
                        else "derived_finish_float"
                        if derived_used
                        else "export_total_float"
                    ),
                    "float_basis": "remaining_late_finish_minus_remaining_early_finish"
                    if derived_used
                    else "xer_or_msp_explicit"
                    if explicit_used
                    else None,
                    "threshold_status": threshold_status,
                    "schedule_options_snapshot": ctx.schedule_options or {},
                },
            ),
            [],
        )

    def _metric_high_duration(
        self, ctx: EvaluationContext, code: str, spec: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        source_format = self._import_source_format(ctx)
        normalized: list[dict[str, Any]] = []
        for act in ctx.activities:
            if act.get("duration_original") is None:
                continue
            hpd = calendar_hours_per_day(ctx.calendars, act.get("calendar_id"))
            days = normalize_duration_days(
                duration_value=act.get("duration_original"),
                duration_unit=act.get("duration_unit"),
                hours_per_day=hpd,
                source_format=source_format or None,
            )
            if days is None:
                continue
            normalized.append(
                {
                    "activity_id": act.get("activity_id"),
                    "duration_raw": act.get("duration_original"),
                    "duration_unit": act.get("duration_unit") or (
                        "hour" if source_format == "primavera_xer" else None
                    ),
                    "calendar_id": act.get("calendar_id"),
                    "hours_per_day": hpd,
                    "hours_per_day_source": "calendar" if act.get("calendar_id") else "default_8h",
                    "duration_normalized_days": days,
                    "threshold_days": HIGH_DURATION_DAYS,
                }
            )
        if not normalized:
            return (
                self._base_metric(
                    ctx,
                    code=code,
                    spec=spec,
                    status=METRIC_STATUS_NOT_MEASURABLE,
                    not_measurable_reason="no duration values in canonical store",
                ),
                [],
            )
        bad_items = [n for n in normalized if n["duration_normalized_days"] > HIGH_DURATION_DAYS]
        ratio = len(bad_items) / len(normalized)
        return (
            self._base_metric(
                ctx,
                code=code,
                spec=spec,
                status=self._status_from_ratio(ratio, spec),
                numerator=len(bad_items),
                denominator=len(normalized),
                value=round(ratio, 4),
                evidence={
                    "method": "normalized_working_days",
                    "numerator_basis": "activities_exceeding_duration_threshold",
                    "denominator_basis": "activities_with_duration",
                    "threshold_days": HIGH_DURATION_DAYS,
                    "source_format": source_format or None,
                    "sample_failures": bad_items[:MAX_EVIDENCE_IDS],
                },
            ),
            [],
        )

    def _metric_invalid_dates(
        self, ctx: EvaluationContext, code: str, spec: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        findings: list[dict[str, Any]] = []
        subcategory_defs = {
            "completed_missing_actual_finish": "completed_activities",
            "started_missing_actual_start": "started_activities",
            "actual_finish_before_start": "activities_with_actual_dates",
            "actual_start_after_data_date": "activities_with_actual_start",
            "actual_finish_after_data_date": "activities_with_actual_finish",
            "early_late_ordering": "activities_with_early_late_dates",
        }
        subcategories: dict[str, dict[str, Any]] = {
            key: {"findings": 0, "denominator": 0, "denominator_basis": basis}
            for key, basis in subcategory_defs.items()
        }
        seen: dict[str, set[str]] = {key: set() for key in subcategory_defs}

        def _record(
            subcategory: str,
            *,
            activity_id: str | None,
            finding_code: str,
            severity: str,
            summary: str,
        ) -> None:
            aid = str(activity_id) if activity_id is not None else ""
            if aid and aid in seen[subcategory]:
                return
            if aid:
                seen[subcategory].add(aid)
            subcategories[subcategory]["findings"] += 1
            findings.append(
                self._finding(
                    ctx,
                    finding_code=finding_code,
                    severity=severity,
                    finding_type="invalid_dates",
                    category="dcma",
                    metric_code=code,
                    activity_id=activity_id,
                    summary=summary,
                )
            )

        for act in ctx.activities:
            aid = act.get("activity_id")
            actual_start = self._canonical_actual_start(act)
            actual_finish = self._canonical_actual_finish(act)

            if self._is_completed_activity(act):
                subcategories["completed_missing_actual_finish"]["denominator"] += 1
                if not actual_finish:
                    _record(
                        "completed_missing_actual_finish",
                        activity_id=aid,
                        finding_code="completed_missing_actual_finish",
                        severity="warning",
                        summary="Completed activity missing actual finish",
                    )

            if self._is_started_activity(act):
                subcategories["started_missing_actual_start"]["denominator"] += 1
                if not actual_start:
                    _record(
                        "started_missing_actual_start",
                        activity_id=aid,
                        finding_code="started_missing_actual_start",
                        severity="warning",
                        summary="Started activity missing actual start",
                    )

            if actual_start and actual_finish:
                subcategories["actual_finish_before_start"]["denominator"] += 1
                if actual_finish < actual_start:
                    _record(
                        "actual_finish_before_start",
                        activity_id=aid,
                        finding_code="actual_finish_before_start",
                        severity="critical",
                        summary="Actual finish precedes actual start",
                    )

            if ctx.data_date and actual_start:
                subcategories["actual_start_after_data_date"]["denominator"] += 1
                if actual_start > str(ctx.data_date):
                    _record(
                        "actual_start_after_data_date",
                        activity_id=aid,
                        finding_code="actual_start_after_data_date",
                        severity="warning",
                        summary="Actual start is after schedule data date",
                    )

            if ctx.data_date and actual_finish:
                subcategories["actual_finish_after_data_date"]["denominator"] += 1
                if actual_finish > str(ctx.data_date):
                    _record(
                        "actual_finish_after_data_date",
                        activity_id=aid,
                        finding_code="actual_finish_after_data_date",
                        severity="warning",
                        summary="Actual finish is after schedule data date",
                    )

            early_start = act.get("early_start")
            late_start = act.get("late_start")
            if early_start and late_start:
                subcategories["early_late_ordering"]["denominator"] += 1
                if str(early_start) > str(late_start):
                    _record(
                        "early_late_ordering",
                        activity_id=aid,
                        finding_code="early_late_ordering",
                        severity="warning",
                        summary="Early start is after late start",
                    )

        if not ctx.activities:
            return (
                self._base_metric(
                    ctx,
                    code=code,
                    spec=spec,
                    status=METRIC_STATUS_NOT_MEASURABLE,
                    not_measurable_reason="no date fields in canonical store",
                ),
                findings,
            )

        total_findings = sum(s["findings"] for s in subcategories.values())
        primary_key = max(
            subcategory_defs,
            key=lambda k: (
                subcategories[k]["findings"],
                subcategories[k]["denominator"],
            ),
        )
        primary = subcategories[primary_key]
        primary_findings = int(primary["findings"])
        primary_denominator = int(primary["denominator"]) or len(ctx.activities)
        ratio = (
            primary_findings / primary_denominator if primary_denominator else 0.0
        )
        if primary_findings > primary_denominator:
            primary_findings = primary_denominator
            ratio = 1.0

        measurable = any(s["denominator"] > 0 for s in subcategories.values())
        status = (
            self._status_from_ratio(ratio, spec)
            if measurable and primary_denominator
            else METRIC_STATUS_MEASURED
        )

        return (
            self._base_metric(
                ctx,
                code=code,
                spec=spec,
                status=status,
                numerator=primary_findings,
                denominator=primary_denominator,
                value=round(ratio, 4) if primary_denominator else 0.0,
                evidence={
                    "display_mode": "finding_count",
                    "method": "subcategory_date_checks",
                    "subcategories": subcategories,
                    "total_findings": total_findings,
                    "primary_subcategory": primary_key,
                    "primary_denominator": primary_denominator,
                    "primary_denominator_basis": primary["denominator_basis"],
                    "numerator_basis": "primary_subcategory_findings",
                    "denominator_basis": primary["denominator_basis"],
                },
            ),
            findings,
        )

    def _metric_cost_loading(
        self, ctx: EvaluationContext, code: str, spec: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        acts = ctx.activities
        if not acts:
            return (
                self._base_metric(
                    ctx,
                    code=code,
                    spec=spec,
                    status=METRIC_STATUS_NOT_MEASURABLE,
                    not_measurable_reason="no activities in canonical store",
                ),
                [],
            )
        posture = cost_resource_posture(ctx.import_meta)
        coding = self._coding_coverage(ctx)
        resource_loaded = sum(
            1 for a in acts if a.get("resource_id") or a.get("resource_name")
        )
        cost_loaded = sum(1 for a in acts if a.get("cost_loaded_amount"))
        import_meta = ctx.import_meta or {}
        evidence = {
            "schedule_posture": posture,
            "activity_code_coverage_count": coding["activity_code_coverage_count"],
            "schedule_coding_coverage_count": coding["schedule_coding_coverage_count"],
            "udf_coverage_count": coding["udf_coverage_count"],
            "code_assignment_row_count": coding["code_assignment_row_count"],
            "udf_row_count": coding["udf_row_count"],
            "import_code_count": import_meta.get("code_count"),
            "import_udf_count": import_meta.get("udf_count"),
            "resource_loading_count": resource_loaded,
            "cost_loading_count": cost_loaded,
        }
        if posture in {"not_cost_loaded", "unknown"}:
            return (
                self._base_metric(
                    ctx,
                    code=code,
                    spec=spec,
                    status=METRIC_STATUS_NA,
                    numerator=0,
                    denominator=len(acts),
                    value=0.0,
                    not_measurable_reason="schedule is not cost- or resource-loaded",
                    evidence=evidence,
                ),
                [],
            )
        loaded = max(resource_loaded, cost_loaded)
        ratio = loaded / len(acts)
        return (
            self._base_metric(
                ctx,
                code=code,
                spec=spec,
                status=self._status_from_ratio(ratio, spec, higher_is_better=True),
                numerator=loaded,
                denominator=len(acts),
                value=round(ratio, 4),
                evidence=evidence,
            ),
            [],
        )

    def _metric_missed_tasks(
        self, ctx: EvaluationContext, code: str, spec: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        return (
            self._base_metric(
                ctx,
                code=code,
                spec=spec,
                status=METRIC_STATUS_NOT_MEASURABLE,
                not_measurable_reason="baseline schedule data not available in canonical store",
            ),
            [],
        )

    def _driving_path_proxy_stats(
        self, ctx: EvaluationContext, driving: list[dict[str, Any]]
    ) -> dict[str, Any]:
        threshold = _parse_threshold(
            (ctx.import_meta or {}).get("critical_float_threshold")
            or (ctx.schedule_options or {}).get("critical_activity_float_threshold")
        )
        mismatches = 0
        checked = 0
        non_driving_zero = 0
        eligible_by_status: dict[str, int] = {}
        for a in ctx.activities:
            tf = self._explicit_float_days(a)
            if tf is None:
                continue
            if a.get("source_driving_path_flag"):
                checked += 1
                status = str(a.get("activity_status") or "unknown")
                eligible_by_status[status] = eligible_by_status.get(status, 0) + 1
                if tf > threshold + 0.01:
                    mismatches += 1
            elif tf <= threshold + 0.01 and tf >= -0.01:
                non_driving_zero += 1
        driving_count = len(driving)
        ratio = mismatches / checked if checked else 0.0
        return {
            "method": "source_export_proxy",
            "critical_path_source": "xer_driving_path_flag",
            "cpm_recalculation": "not_implemented",
            "dcma_critical_path_test": "not_applicable",
            "caveat": "not a DCMA critical path test; CPM recalculation not implemented",
            "source_driving_path_available": driving_count > 0,
            "driving_path_activity_count": driving_count,
            "driving_path_count": driving_count,
            "eligible_driving_path_activity_count": checked,
            "eligible_denominator_basis": "driving_path_flag_with_explicit_float",
            "eligible_by_activity_status": eligible_by_status,
            "explicit_float_checked": checked,
            "driving_path_float_consistency_violation_count": mismatches,
            "proxy_violation_count": mismatches,
            "non_driving_near_zero_float_count": non_driving_zero,
            "numerator_basis": "driving_path_float_consistency_violations",
            "denominator_basis": "driving_path_flag_with_explicit_float",
            "threshold_status": self._status_from_ratio(
                ratio,
                SUPPLEMENTAL_METRIC_SPECS["source_driving_path_integrity_proxy"],
            )
            if checked
            else METRIC_STATUS_NOT_MEASURABLE,
            "float_threshold": threshold,
            "ratio": round(ratio, 4) if checked else None,
        }

    def _metric_source_driving_path_integrity_proxy(
        self,
        ctx: EvaluationContext,
        code: str,
        spec: dict[str, Any],
        driving: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        stats = self._driving_path_proxy_stats(ctx, driving)
        checked = int(stats["eligible_driving_path_activity_count"])
        if checked == 0:
            return (
                self._base_metric(
                    ctx,
                    code=code,
                    spec=spec,
                    status=METRIC_STATUS_NOT_MEASURABLE,
                    not_measurable_reason="no explicit float on driving-path activities",
                    metric_family="supplemental",
                    evidence=stats,
                ),
                [],
            )
        mismatches = int(stats["driving_path_float_consistency_violation_count"])
        return (
            self._base_metric(
                ctx,
                code=code,
                spec=spec,
                status=METRIC_STATUS_SOURCE_EXPORT_PROXY,
                numerator=mismatches,
                denominator=checked,
                value=stats["ratio"],
                metric_family="supplemental",
                evidence={
                    **stats,
                    "display_name_override": "Source driving path integrity (proxy)",
                },
            ),
            [],
        )

    def _metric_critical_path_msp_critical(
        self,
        ctx: EvaluationContext,
        code: str,
        spec: dict[str, Any],
        critical: list[dict[str, Any]],
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        mismatches = 0
        checked = 0
        for a in critical:
            tf = self._explicit_float_days(a)
            if tf is None:
                continue
            checked += 1
            if tf > 0.01:
                mismatches += 1
        if checked == 0:
            return (
                self._base_metric(
                    ctx,
                    code=code,
                    spec=spec,
                    status=METRIC_STATUS_NOT_MEASURABLE,
                    not_measurable_reason="no explicit slack on MSP critical tasks",
                ),
                [],
            )
        ratio = mismatches / checked
        return (
            self._base_metric(
                ctx,
                code=code,
                spec=spec,
                status=METRIC_STATUS_MSP_CRITICAL,
                numerator=mismatches,
                denominator=checked,
                value=round(ratio, 4),
                evidence={
                    "method": "msp_critical_slack_consistency",
                    "critical_path_source": "msp_critical_flag",
                    "critical_flag_count": len(critical),
                    "threshold_status": self._status_from_ratio(ratio, spec),
                },
            ),
            [],
        )

    def _metric_critical_path_test(
        self, ctx: EvaluationContext, code: str, spec: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        source_fmt = self._import_source_format(ctx)
        if source_fmt in {"primavera_xer", "ms_project_xml"}:
            return (
                self._base_metric(
                    ctx,
                    code=code,
                    spec=spec,
                    status=METRIC_STATUS_NOT_MEASURABLE_RECALC,
                    not_measurable_reason=(
                        "CPM recalculation not implemented; source-export critical path "
                        "data is available separately"
                    ),
                    evidence={
                        "method": "requires_cpm_recalculation",
                        "cpm_recalculation": "not_implemented",
                        "source_format": source_fmt,
                    },
                ),
                [],
            )
        if self._is_p6_derived_only(ctx):
            return (
                self._base_metric(
                    ctx,
                    code=code,
                    spec=spec,
                    status=METRIC_STATUS_NOT_MEASURABLE_RECALC,
                    not_measurable_reason=(
                        "derived finish float cannot validate DCMA critical path test; "
                        "full Primavera recalculation or authoritative export flags required"
                    ),
                    evidence={"method": "derived_finish_float_non_authoritative"},
                ),
                [],
            )
        has_float = any(a.get("total_float") is not None for a in ctx.activities)
        has_critical = any(a.get("is_critical") for a in ctx.activities)
        if not has_float and not has_critical:
            return (
                self._base_metric(
                    ctx,
                    code=code,
                    spec=spec,
                    status=METRIC_STATUS_NOT_MEASURABLE,
                    not_measurable_reason="no float or critical-path flags in export",
                ),
                [],
            )
        mismatches = 0
        checked = 0
        for a in ctx.activities:
            try:
                tf = float(a["total_float"]) if a.get("total_float") is not None else None
            except (TypeError, ValueError):
                tf = None
            if tf is None:
                continue
            checked += 1
            critical = bool(a.get("is_critical"))
            if critical and tf > 0.01:
                mismatches += 1
            if not critical and tf <= 0.01 and tf >= -0.01:
                mismatches += 1
        if checked == 0:
            return (
                self._base_metric(
                    ctx,
                    code=code,
                    spec=spec,
                    status=METRIC_STATUS_NOT_MEASURABLE,
                    not_measurable_reason="no comparable float values for critical path test",
                ),
                [],
            )
        ratio = mismatches / checked
        return (
            self._base_metric(
                ctx,
                code=code,
                spec=spec,
                status=self._status_from_ratio(ratio, spec),
                numerator=mismatches,
                denominator=checked,
                value=round(ratio, 4),
                evidence={"method": "export_flags_only"},
            ),
            [],
        )

    def _metric_cpli(
        self, ctx: EvaluationContext, code: str, spec: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        return (
            self._base_metric(
                ctx,
                code=code,
                spec=spec,
                status=METRIC_STATUS_NOT_MEASURABLE,
                not_measurable_reason="baseline and critical-path length data not available",
            ),
            [],
        )

    def _metric_bei(
        self, ctx: EvaluationContext, code: str, spec: dict[str, Any]
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        return (
            self._base_metric(
                ctx,
                code=code,
                spec=spec,
                status=METRIC_STATUS_NOT_MEASURABLE,
                not_measurable_reason="baseline execution data not available",
            ),
            [],
        )

    def _evaluate_gao_category(
        self, ctx: EvaluationContext, category: str
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        findings: list[dict[str, Any]] = []
        posture = "pass"
        reason = None

        if category == "capturing_all_activities":
            if not ctx.activities:
                posture = "fail"
                findings.append(
                    self._finding(
                        ctx,
                        finding_code="no_activities",
                        severity="critical",
                        finding_type="completeness",
                        category="gao",
                        summary="Schedule version contains no activities",
                        requires_review=1,
                    )
                )
        elif category == "sequencing_all_activities":
            if ctx.activities and not ctx.relationships:
                posture = "warn"
                reason = "activities present but no relationships"
        elif category == "duration_reasonableness":
            if not any(a.get("duration_original") for a in ctx.activities):
                posture = "not_measurable"
                reason = "no duration fields"
        elif category == "resource_cost_loading":
            schedule_posture = cost_resource_posture(ctx.import_meta)
            coding = self._coding_coverage(ctx)
            import_meta = ctx.import_meta or {}
            coding_payload = {
                "schedule_posture": schedule_posture,
                "activity_code_coverage_count": coding["activity_code_coverage_count"],
                "schedule_coding_coverage_count": coding["schedule_coding_coverage_count"],
                "udf_coverage_count": coding["udf_coverage_count"],
                "code_assignment_row_count": coding["code_assignment_row_count"],
                "udf_row_count": coding["udf_row_count"],
                "import_code_count": import_meta.get("code_count"),
                "import_udf_count": import_meta.get("udf_count"),
            }
            if schedule_posture in {"not_cost_loaded", "unknown"}:
                posture = "not_cost_resource_loaded"
                reason = json.dumps(coding_payload)
            elif not any(
                a.get("cost_loaded_amount") or a.get("resource_id") for a in ctx.activities
            ):
                posture = "not_measurable"
                reason = "no resource or cost loading fields"
        elif category == "horizontal_vertical_traceability":
            missing_wbs = sum(1 for a in ctx.activities if not a.get("wbs_code"))
            if ctx.activities and missing_wbs / len(ctx.activities) > 0.25:
                posture = "warn"
                findings.append(
                    self._finding(
                        ctx,
                        finding_code="missing_wbs_reference",
                        severity="warning",
                        finding_type="traceability",
                        category="gao",
                        summary=f"{missing_wbs} activities missing WBS reference",
                    )
                )
        elif category == "critical_path_validity":
            source_fmt = self._import_source_format(ctx)
            if source_fmt == "primavera_xer":
                analytics = compute_source_critical_path_analytics(
                    ctx.import_meta,
                    ctx.activities,
                    schedule_options=ctx.schedule_options,
                )
                driving_count = int(analytics.get("source_driving_path_count") or 0)
                if analytics.get("source_critical_basis") != "missing" or driving_count > 0:
                    posture = "xer_export_critical_path_analytics"
                    reason = json.dumps(
                        {
                            **analytics,
                            "longest_path_driving_path": {
                                "posture": "xer_export_critical_path_analytics",
                                "reason": "XER export critical path metadata; not forensic delay analysis",
                            },
                        }
                    )
                else:
                    posture = "not_measurable"
                    reason = "no XER critical path export data"
            elif source_fmt == "ms_project_xml" and any(
                a.get("source_critical_flag") for a in ctx.activities
            ):
                posture = METRIC_STATUS_MSP_CRITICAL
                reason = json.dumps(
                    {
                        "critical_path_source": "msp_critical_flag",
                        "critical_flag_count": sum(
                            1 for a in ctx.activities if a.get("source_critical_flag")
                        ),
                        "posture": "msp_export_critical",
                    }
                )
            else:
                derivable = [a for a in ctx.activities if a.get("derived_float_basis")]
                critical_by_threshold = [
                    a for a in ctx.activities if a.get("derived_is_critical_by_float_threshold")
                ]
                has_longest = any(a.get("is_longest_path") for a in ctx.activities)
                if derivable and supports_finish_float_derivation(ctx.schedule_options):
                    posture = METRIC_STATUS_PARTIAL_CRITICAL_FLOAT
                    reason = json.dumps(
                        {
                            "critical_float_classification": {
                                "posture": METRIC_STATUS_PARTIAL_CRITICAL_FLOAT,
                                "derivable_count": len(derivable),
                                "critical_by_float_threshold_count": len(critical_by_threshold),
                            },
                            "longest_path_driving_path": {
                                "posture": METRIC_STATUS_NOT_MEASURABLE_LONGEST_PATH
                                if not has_longest
                                else "export_flags_only",
                                "reason": "no longest-path or driving-path export flags"
                                if not has_longest
                                else "longest-path flags present; not authoritative CPM",
                            },
                        }
                    )
                elif not any(a.get("is_critical") for a in ctx.activities) and not any(
                    a.get("total_float") is not None for a in ctx.activities
                ):
                    posture = "not_measurable"
                    reason = "no critical path or float export data"
        elif category == "float_reasonableness":
            if not any(a.get("derived_float_basis") for a in ctx.activities) and not any(
                a.get("total_float") is not None for a in ctx.activities
            ):
                posture = "not_measurable"
                reason = "no derived or export float data"
        elif category == "schedule_risk_readiness":
            posture = "pass" if ctx.activities else "fail"
        elif category == "update_status_integrity":
            bad = sum(
                1
                for a in ctx.activities
                if (a.get("percent_complete") or 0) and not a.get("actual_start")
            )
            if bad:
                posture = "warn"
        elif category == "baseline_maintenance":
            posture = "not_measurable"
            reason = "no baseline data in canonical store"
        elif category == "source_validation":
            if not ctx.import_meta:
                posture = "warn"
                reason = "missing import metadata"
        elif category == "data_date_integrity":
            if not ctx.data_date:
                posture = "warn"
                reason = "data date not recorded"
        elif category == "version_over_version_churn":
            if ctx.prior_diff:
                try:
                    churn = float(ctx.prior_diff.get("logic_churn_rate") or 0)
                    if churn > 0.25:
                        posture = "warn"
                        findings.append(
                            self._finding(
                                ctx,
                                finding_code="logic_churn_elevated",
                                severity="advisory",
                                finding_type="churn",
                                category="gao",
                                summary="Logic churn elevated versus prior version",
                            )
                        )
                except (TypeError, ValueError):
                    pass
            else:
                posture = "not_measurable"
                reason = "no prior version diff available"

        return (
            {
                "category": category,
                "posture": posture,
                "reason": reason,
                "finding_count": len([f for f in findings if f.get("category") == "gao"]),
            },
            findings,
        )

    def _evaluate_aace_category(
        self, ctx: EvaluationContext, category: str
    ) -> tuple[dict[str, Any], list[dict[str, Any]]]:
        return self._evaluate_gao_category(ctx, category)

    def _build_scorecard(
        self,
        ctx: EvaluationContext,
        metrics: list[dict[str, Any]],
        findings: list[dict[str, Any]],
        gao_summary: dict[str, dict[str, Any]],
    ) -> dict[str, Any]:
        dcma = [m for m in metrics if m["metric_family"] == "dcma"]
        measured = [m for m in dcma if m["status"] in MEASURED_STATUSES]
        not_measurable = [
            m
            for m in dcma
            if m["status"]
            in (
                METRIC_STATUS_NOT_MEASURABLE,
                METRIC_STATUS_NA,
                METRIC_STATUS_NOT_MEASURABLE_RECALC,
                METRIC_STATUS_NOT_MEASURABLE_LONGEST_PATH,
            )
        ]

        def _threshold_status(metric: dict[str, Any]) -> str:
            if metric["status"] == METRIC_STATUS_DERIVED_FINISH_FLOAT:
                try:
                    ev = json.loads(metric.get("evidence_json") or "{}")
                except json.JSONDecodeError:
                    ev = {}
                return str(ev.get("threshold_status") or METRIC_STATUS_MEASURED)
            return str(metric["status"])

        pass_c = sum(1 for m in measured if _threshold_status(m) == METRIC_STATUS_PASS)
        warn_c = sum(1 for m in measured if _threshold_status(m) == METRIC_STATUS_WARN)
        fail_c = sum(1 for m in measured if _threshold_status(m) == METRIC_STATUS_FAIL)

        score = None
        grade = "insufficient_data"
        scorable = [
            m
            for m in measured
            if _threshold_status(m)
            in (METRIC_STATUS_PASS, METRIC_STATUS_WARN, METRIC_STATUS_FAIL)
        ]
        if len(scorable) >= 5:
            points = sum(
                1.0
                if _threshold_status(m) == METRIC_STATUS_PASS
                else 0.5
                if _threshold_status(m) == METRIC_STATUS_WARN
                else 0.0
                for m in scorable
            )
            score = round(100.0 * points / len(scorable), 1)
            if score >= 90:
                grade = "A"
            elif score >= 80:
                grade = "B"
            elif score >= 70:
                grade = "C"
            elif score >= 60:
                grade = "D"
            else:
                grade = "F"

        sev_counts: dict[str, int] = {"critical": 0, "warning": 0, "advisory": 0}
        for f in findings:
            sev = str(f.get("severity", "advisory"))
            if sev in sev_counts:
                sev_counts[sev] += 1

        expected_not_measurable = {
            "dcma_cpli",
            "dcma_bei",
            "dcma_missed_tasks",
            "dcma_critical_path_test",
        }
        has_expected_gaps = any(
            m["metric_code"] in expected_not_measurable
            and m["status"]
            in (
                METRIC_STATUS_NOT_MEASURABLE,
                METRIC_STATUS_NOT_MEASURABLE_RECALC,
                METRIC_STATUS_NOT_MEASURABLE_LONGEST_PATH,
                METRIC_STATUS_NA,
            )
            for m in dcma
        )
        completion_posture = "completed"
        if has_expected_gaps and len(measured) >= 5:
            completion_posture = "completed_with_limitations"

        has_critical_path_recalc = any(
            m["metric_code"] == "dcma_critical_path_test"
            and m["status"] == METRIC_STATUS_NOT_MEASURABLE_RECALC
            for m in dcma
        )
        has_source_critical_analytics = any(
            m.get("metric_code") == "source_critical_path_available"
            and m.get("status")
            in (
                METRIC_STATUS_AVAILABLE_XER_DRIVING,
                METRIC_STATUS_AVAILABLE_XER_TOTFLOAT,
                METRIC_STATUS_PARTIAL_XER_FLOAT,
            )
            for m in metrics
        )
        source_fmt = self._import_source_format(ctx)
        if has_source_critical_analytics:
            critical_path_analytics = "available_source_export_critical_path"
        elif source_fmt == "primavera_xer":
            critical_path_analytics = "unavailable_requires_cpm_recalculation"
        elif source_fmt == "ms_project_xml":
            critical_path_analytics = "available_msp_critical_slack"
        elif has_critical_path_recalc:
            critical_path_analytics = "unavailable_requires_cpm_recalculation"
        else:
            critical_path_analytics = "available_export_flags_only"
        critical_blockers = any(f.get("severity") == "critical" for f in findings)
        cost_weighting = "blocked"
        if completion_posture == "completed_with_limitations" and not critical_blockers:
            cost_weighting = "ready_with_quality_penalty"
        elif completion_posture == "completed" and grade not in ("insufficient_data", "F") and fail_c == 0:
            cost_weighting = "ready"

        readiness = {
            "completion_posture": completion_posture,
            "cost_mapping": "ready" if ctx.activities else "not_ready",
            "cost_weighting": cost_weighting,
            "critical_path_analytics": critical_path_analytics,
            "cpm_recalculation": "not_implemented",
            "baseline_analytics": "unavailable_missing_baseline",
            "true_cost_loaded_analytics": (
                "unavailable_not_cost_loaded"
                if cost_resource_posture(ctx.import_meta) in {"not_cost_loaded", "unknown"}
                else (
                    "partially_available"
                    if cost_resource_posture(ctx.import_meta) == "partially_resource_loaded"
                    else "available"
                )
            ),
            "blockers": [],
            "cost_mapping_ready": bool(ctx.activities),
            "cost_weighting_ready": cost_weighting in {"ready", "ready_with_quality_penalty"},
            "forecast_context_ready": score is not None and score >= 60,
        }
        if cost_weighting == "blocked":
            readiness["blockers"].append("quality_scorecard_incomplete_or_failed")
        elif cost_weighting == "ready_with_quality_penalty":
            readiness["blockers"] = []

        return {
            "evaluation_run_id": ctx.evaluation_run_id,
            "project_key": ctx.project_key,
            "schedule_version_key": ctx.schedule_version_key,
            "assessment_profile": ctx.assessment_profile.profile_id,
            "completion_posture": completion_posture,
            "quality_score": str(score) if score is not None else None,
            "quality_grade": grade,
            "dcma_measured_count": len(measured),
            "dcma_not_measurable_count": len(not_measurable),
            "dcma_pass_count": pass_c,
            "dcma_warn_count": warn_c,
            "dcma_fail_count": fail_c,
            "gao_category_summary_json": json.dumps(gao_summary),
            "finding_counts_json": json.dumps(sev_counts),
            "downstream_readiness_json": json.dumps(readiness),
            "disclaimer_version": DISCLAIMER_VERSION,
        }

    def _finding(self, ctx: EvaluationContext, **kwargs: Any) -> dict[str, Any]:
        return {
            "project_key": ctx.project_key,
            "schedule_version_key": ctx.schedule_version_key,
            "import_id": ctx.import_id,
            "evaluation_run_id": ctx.evaluation_run_id,
            "assessment_profile": ctx.assessment_profile.profile_id,
            "metric_code": kwargs.get("metric_code"),
            "category": kwargs.get("category", "dcma"),
            "finding_type": kwargs["finding_type"],
            "severity": kwargs["severity"],
            "activity_id": kwargs.get("activity_id"),
            "relationship_id": kwargs.get("relationship_id"),
            "wbs_id": kwargs.get("wbs_id"),
            "finding_code": kwargs["finding_code"],
            "finding_summary": kwargs["summary"],
            "evidence_json": json.dumps(kwargs.get("evidence") or {}),
            "requires_operator_review": kwargs.get("requires_review", 0),
        }

    @staticmethod
    def _rel_type_counts(rels: list[dict[str, Any]]) -> dict[str, int]:
        return relationship_type_distribution(rels)


def run_evaluation_for_run(
    *,
    db_path: str,
    evaluation_run_id: str,
    project_key: str,
    schedule_version_key: str,
    schedule_table_id: str | None,
    import_id: str | None,
    profile_id: str | None = None,
) -> EvaluationResult:
    profile = get_profile(profile_id)
    loader = ScheduleQualityDataLoader(db_path=db_path)
    data = loader.load(schedule_version_key)
    ctx = EvaluationContext(
        project_key=project_key,
        schedule_version_key=schedule_version_key,
        schedule_table_id=schedule_table_id or data.get("schedule_table_id"),
        import_id=import_id,
        evaluation_run_id=evaluation_run_id,
        assessment_profile=profile,
        data_date=data.get("data_date"),
        activities=data["activities"],
        relationships=data["relationships"],
        wbs_nodes=data["wbs_nodes"],
        calendars=data["calendars"],
        prior_diff=data.get("prior_diff"),
        import_meta=data.get("import_meta"),
        schedule_options=data.get("schedule_options"),
        code_assignments=data.get("code_assignments") or [],
        udf_values=data.get("udf_values") or [],
    )
    return ScheduleQualityAssessmentEngine().evaluate(ctx)
