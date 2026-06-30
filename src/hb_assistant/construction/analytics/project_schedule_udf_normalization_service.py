"""Read-through UDF normalization and schedule-dimension payloads for Project Schedule Hub."""

from __future__ import annotations

from collections import defaultdict
from datetime import date, datetime, timedelta
from typing import Any

from hb_assistant.store.connection import open_connection
from hb_assistant.store.schedule_activity_repository import ScheduleActivityRepository

from .project_schedule_canonical_metrics import ProjectScheduleCanonicalMetricService
from .project_schedule_summary_service import _date_str, _parse_date
from .project_schedule_visualization_metric_contract import NON_CAUSATION_CAVEAT

UDF_FIELD_ALIASES: dict[str, tuple[str, ...]] = {
    "old_id": ("OLD ID",),
    "phase": ("PHASE",),
    "floor": ("FLOOR",),
    "sector_area": ("SECTOR / AREA",),
    "subcontractor": ("SUBCONTRACTOR",),
    "cost_code": ("Cost Code",),
    "filter_out": ("Filter Out",),
    "start_previous_status": ("Start (Previous Status)", "Start Previous Status"),
    "finish_previous_status": ("Finish (Previous Status)", "Finish Previous Status"),
    "update_notes_1": ("Update Notes - 1",),
    "update_notes_2": ("Update Notes - 2",),
    "update_notes": ("Update Notes",),
    "schedule_review_comments": ("Schedule Review Comments",),
}

REQUIRED_INTERNAL_FIELDS: tuple[str, ...] = tuple(UDF_FIELD_ALIASES.keys())

ALIAS_TO_INTERNAL: dict[str, str] = {}
for _field, _aliases in UDF_FIELD_ALIASES.items():
    for _alias in _aliases:
        ALIAS_TO_INTERNAL[_alias] = _field

UDF_DEPENDENT_METRICS: frozenset[str] = frozenset(
    {
        "delay_analysis",
        "window_start_accuracy",
        "window_finish_accuracy",
        "should_have_finished_status",
        "critical_issues_category_model",
    }
)

_FILTER_TRUE = frozenset({"y", "yes", "true", "1"})
_FILTER_FALSE = frozenset({"n", "no", "false", "0"})

_CRITICAL_ISSUE_CATEGORIES: tuple[tuple[str, str], ...] = (
    ("negative_float_and_critical_path_erosion", "Negative float and critical path erosion"),
    ("schedule_compression_on_critical_path", "Schedule compression on critical path"),
    ("logic_and_quality_findings", "Logic and quality findings"),
    ("execution_and_status_gaps", "Execution and status gaps"),
    ("review_and_external_flags", "Review and external flags"),
)


class ProjectScheduleUdfNormalizationService:
    """Normalize named P6 UDFs into stable queryable dimensions without mutating raw storage."""

    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._activity_repo = ScheduleActivityRepository(db_path=db_path)
        self._canonical = ProjectScheduleCanonicalMetricService(db_path=db_path)

    def get_udf_name_inventory(
        self,
        *,
        project_key: str | None = None,
        version_key: str | None = None,
    ) -> dict[str, Any]:
        rows = self._fetch_udf_rows(project_key=project_key, version_key=version_key)
        counts: dict[str, int] = defaultdict(int)
        for row in rows:
            name = str(row.get("udf_type_name") or "").strip()
            if name:
                counts[name] += 1
        return {
            "available": True,
            "project_key": project_key,
            "version_key": version_key,
            "udf_names": [
                {"udf_type_name": name, "row_count": count}
                for name, count in sorted(counts.items())
            ],
            "total_rows": len(rows),
            "backend_derived": True,
        }

    def get_udf_availability(self, project_key: str, version_key: str) -> dict[str, Any]:
        rows = self._fetch_udf_rows(project_key=project_key, version_key=version_key)
        inventory = {str(r.get("udf_type_name") or "").strip() for r in rows}
        fields: dict[str, Any] = {}
        for field, aliases in UDF_FIELD_ALIASES.items():
            discovered = [alias for alias in aliases if alias in inventory]
            ambiguous_aliases = self._ambiguous_aliases(rows, aliases)
            if len(discovered) > 1 and field not in {"update_notes", "update_notes_1", "update_notes_2"}:
                status = "ambiguous"
            elif discovered:
                status = "discovered"
            else:
                status = "missing"
            fields[field] = {
                "status": status,
                "discovered_aliases": discovered,
                "expected_aliases": list(aliases),
                "ambiguous_aliases": ambiguous_aliases,
            }
        return {
            "available": True,
            "project_key": project_key,
            "version_key": version_key,
            "fields": fields,
            "backend_derived": True,
        }

    def get_udf_sparsity_summary(self, project_key: str, version_key: str) -> dict[str, Any]:
        activity_count = self._activity_repo.count_activities(version_key)
        normalized = self.get_normalized_activity_dimensions(
            project_key=project_key,
            version_key=version_key,
        )
        records = normalized["records"]
        field_stats: dict[str, Any] = {}
        for field in REQUIRED_INTERNAL_FIELDS:
            non_null = sum(1 for rec in records if rec.get(field) not in (None, ""))
            blank = len(records) - non_null
            coverage = (non_null / activity_count) if activity_count else 0.0
            field_stats[field] = {
                "non_null_count": non_null,
                "blank_count": blank,
                "coverage_ratio": round(coverage, 4),
                "sparse": coverage < 0.5 if activity_count else True,
            }
        return {
            "available": True,
            "project_key": project_key,
            "version_key": version_key,
            "activity_count": activity_count,
            "normalized_record_count": len(records),
            "field_stats": field_stats,
            "warnings": [
                f"{field} coverage below 50%"
                for field, stats in field_stats.items()
                if stats["sparse"] and activity_count > 0
            ],
            "backend_derived": True,
        }

    def get_udf_join_proof(self, project_key: str, version_key: str) -> dict[str, Any]:
        udf_rows = self._fetch_udf_rows(project_key=project_key, version_key=version_key)
        activity_ids = self._activity_ids(version_key)
        joined = 0
        orphan_examples: list[dict[str, Any]] = []
        for row in udf_rows:
            aid = str(row.get("activity_id") or "")
            if aid in activity_ids:
                joined += 1
            elif len(orphan_examples) < 5:
                orphan_examples.append(
                    {
                        "activity_id": aid,
                        "udf_type_name": row.get("udf_type_name"),
                        "udf_value": row.get("udf_value"),
                    }
                )
        total_udf = len(udf_rows)
        join_rate = (joined / total_udf) if total_udf else 1.0
        activities_with_udf = len({str(r.get("activity_id")) for r in udf_rows if str(r.get("activity_id")) in activity_ids})
        return {
            "available": True,
            "project_key": project_key,
            "version_key": version_key,
            "activity_count": len(activity_ids),
            "udf_row_count": total_udf,
            "joined_udf_row_count": joined,
            "join_failure_count": total_udf - joined,
            "join_success_rate": round(join_rate, 4),
            "activities_with_udf_count": activities_with_udf,
            "orphan_udf_examples": orphan_examples,
            "deterministic_join_proven": total_udf == 0 or join_rate == 1.0,
            "backend_derived": True,
        }

    def get_normalized_activity_dimensions(
        self,
        *,
        project_key: str,
        version_key: str,
        activity_ids: list[str] | None = None,
    ) -> dict[str, Any]:
        udf_rows = self._fetch_udf_rows(project_key=project_key, version_key=version_key)
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in udf_rows:
            aid = str(row.get("activity_id") or "")
            if activity_ids is not None and aid not in activity_ids:
                continue
            grouped[aid].append(row)

        if activity_ids is not None:
            target_ids = activity_ids
        else:
            target_ids = sorted(set(self._activity_ids(version_key)) | set(grouped.keys()))

        records: list[dict[str, Any]] = []
        for aid in target_ids:
            records.append(self._normalize_activity_record(project_key, version_key, aid, grouped.get(aid, [])))

        return {
            "available": True,
            "project_key": project_key,
            "version_key": version_key,
            "records": records,
            "backend_derived": True,
        }

    def get_udf_metric_readiness(self, project_key: str, version_key: str) -> dict[str, Any]:
        join_proof = self.get_udf_join_proof(project_key, version_key)
        availability = self.get_udf_availability(project_key, version_key)
        sparsity = self.get_udf_sparsity_summary(project_key, version_key)
        activity_count = join_proof["activity_count"]
        metrics: dict[str, Any] = {}

        def _field_ready(*fields: str) -> tuple[bool, list[str]]:
            blockers: list[str] = []
            for field in fields:
                status = availability["fields"][field]["status"]
                if status == "missing":
                    blockers.append(f"udf_field_missing:{field}")
                elif status == "ambiguous":
                    blockers.append(f"udf_field_ambiguous:{field}")
            if activity_count == 0:
                blockers.append("no_schedule_activities")
            if not join_proof["deterministic_join_proven"]:
                blockers.append("udf_join_not_deterministic")
            return (not blockers, blockers)

        ready, blockers = _field_ready("filter_out", "start_previous_status")
        metrics["window_start_accuracy"] = {
            "ready": ready and activity_count > 0,
            "blockers": blockers,
            "partial_dimension_support": any(
                availability["fields"][f]["status"] == "missing"
                for f in ("filter_out", "start_previous_status")
            ),
        }

        ready, blockers = _field_ready("filter_out", "finish_previous_status")
        metrics["window_finish_accuracy"] = {
            "ready": ready and activity_count > 0,
            "blockers": blockers,
            "partial_dimension_support": any(
                availability["fields"][f]["status"] == "missing"
                for f in ("filter_out", "finish_previous_status")
            ),
        }

        ready, blockers = _field_ready("filter_out")
        metrics["should_have_finished_status"] = {
            "ready": activity_count > 0 and join_proof["deterministic_join_proven"],
            "blockers": blockers if activity_count == 0 else [b for b in blockers if b != "udf_field_missing:filter_out"],
            "partial_dimension_support": availability["fields"]["filter_out"]["status"] == "missing",
        }

        ready, blockers = _field_ready("phase", "floor", "sector_area", "subcontractor")
        has_diff = self._has_prior_update_diff(project_key, version_key)
        metrics["delay_analysis"] = {
            "ready": has_diff and join_proof["deterministic_join_proven"],
            "blockers": ([] if has_diff else ["prior_update_diff_unavailable"]) + blockers,
            "partial_dimension_support": any(
                availability["fields"][f]["status"] in {"missing", "ambiguous"}
                for f in ("phase", "floor", "sector_area", "subcontractor", "update_notes", "schedule_review_comments")
            ),
            "caveats": [NON_CAUSATION_CAVEAT],
        }

        metrics["critical_issues_category_model"] = {
            "ready": activity_count > 0 and join_proof["deterministic_join_proven"],
            "blockers": [] if activity_count > 0 else ["no_schedule_activities"],
            "partial_dimension_support": any(
                availability["fields"][f]["status"] == "missing"
                for f in ("update_notes", "schedule_review_comments", "subcontractor", "cost_code", "phase", "floor")
            ),
            "caveats": [NON_CAUSATION_CAVEAT],
        }

        return {
            "available": True,
            "project_key": project_key,
            "version_key": version_key,
            "metrics": metrics,
            "join_proof": join_proof,
            "sparsity_warnings": sparsity.get("warnings", []),
            "backend_derived": True,
        }

    def build_metric_payload(
        self,
        *,
        metric_key: str,
        project_key: str,
        version_key: str,
        as_of_date: date,
        data_date: date | None = None,
    ) -> dict[str, Any]:
        builders = {
            "window_start_accuracy": self._window_start_accuracy_payload,
            "window_finish_accuracy": self._window_finish_accuracy_payload,
            "should_have_finished_status": self._should_have_finished_status_payload,
            "delay_analysis": self._delay_analysis_payload,
            "critical_issues_category_model": self._critical_issues_category_model_payload,
        }
        if metric_key not in builders:
            raise ValueError("unsupported_udf_metric_key")
        return builders[metric_key](
            project_key=project_key,
            version_key=version_key,
            as_of_date=as_of_date,
            data_date=data_date,
        )

    def get_should_have_finished_activity_cues(
        self,
        *,
        project_key: str,
        version_key: str,
        as_of_date: date,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        payload = self.build_metric_payload(
            metric_key="should_have_finished_status",
            project_key=project_key,
            version_key=version_key,
            as_of_date=as_of_date,
        )
        if not payload.get("available"):
            return []
        confidence = (
            "partial_dimension_support"
            if payload.get("partial_dimension_support")
            else "production_backed"
        )
        at_risk_float_days = 5
        dimensions = {
            rec["activity_id"]: rec
            for rec in self.get_normalized_activity_dimensions(
                project_key=project_key,
                version_key=version_key,
            )["records"]
        }
        cues: list[dict[str, Any]] = []
        cpm_run = self._canonical.selected_cpm_run(version_key)
        cpm_flags: dict[str, dict[str, Any]] = {}
        if cpm_run:
            with open_connection(self._db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT activity_id, computed_total_float
                    FROM schedule_cpm_activity_results
                    WHERE schedule_version_key=? AND cpm_run_id=?
                    """,
                    (version_key, cpm_run["cpm_run_id"]),
                ).fetchall()
                cpm_flags = {str(r["activity_id"]): dict(r) for r in rows}
        with open_connection(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT activity_id, activity_name, wbs_code, planned_finish, early_finish,
                       actual_finish, total_float, derived_total_float_days, explicit_total_float_days
                FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                """,
                (version_key,),
            ).fetchall()
        for row in rows:
            aid = str(row["activity_id"])
            dim = dimensions.get(aid, {})
            if dim.get("filter_out_parsed") is True:
                continue
            due = _parse_date(row["planned_finish"]) or _parse_date(row["early_finish"])
            if not due or due > as_of_date:
                continue
            if _parse_date(row["actual_finish"]) is not None:
                continue
            float_days = self._activity_float(row, cpm_flags.get(aid))
            if float_days is not None and float_days < 0:
                status = "delayed"
            elif float_days is not None and float_days <= at_risk_float_days:
                status = "at_risk"
            else:
                continue
            cues.append(
                {
                    "activity_id": aid,
                    "activity_name": row["activity_name"],
                    "wbs_code": row["wbs_code"],
                    "status": status,
                    "confidence": confidence,
                    "partial_dimension_support": payload.get("partial_dimension_support", False),
                    "phase": dim.get("phase"),
                    "floor": dim.get("floor"),
                    "sector_area": dim.get("sector_area"),
                    "subcontractor": dim.get("subcontractor"),
                    "cost_code": dim.get("cost_code"),
                    "cue_summary": f"Activity due by data date is {status.replace('_', ' ')} and needs PM review.",
                    "data_quality_notes": payload.get("data_quality_notes", []),
                }
            )
        cues.sort(key=lambda cue: (0 if cue.get("status") == "delayed" else 1, str(cue.get("activity_id"))))
        return cues[: max(1, min(limit, 100))]

    def get_window_start_activity_cues(
        self,
        *,
        project_key: str,
        version_key: str,
        as_of_date: date,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        payload = self.build_metric_payload(
            metric_key="window_start_accuracy",
            project_key=project_key,
            version_key=version_key,
            as_of_date=as_of_date,
        )
        if not payload.get("available"):
            return []
        confidence = (
            "partial_dimension_support"
            if payload.get("partial_dimension_support")
            else "production_backed"
        )
        lookback, lookahead = 7, 21
        window_start = as_of_date - timedelta(days=lookback)
        window_end = as_of_date + timedelta(days=lookahead)
        dimensions = {
            rec["activity_id"]: rec
            for rec in self.get_normalized_activity_dimensions(
                project_key=project_key,
                version_key=version_key,
            )["records"]
        }
        cues: list[dict[str, Any]] = []
        with open_connection(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT activity_id, activity_name, wbs_code, planned_start, start_date, actual_start
                FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                """,
                (version_key,),
            ).fetchall()
        for row in rows:
            aid = str(row["activity_id"])
            dim = dimensions.get(aid, {})
            if dim.get("filter_out_parsed") is True:
                continue
            planned = _parse_date(row["planned_start"]) or _parse_date(row["start_date"])
            if not planned or planned < window_start or planned > window_end:
                continue
            actual = _parse_date(row["actual_start"])
            if actual is None:
                signal_type = "did_not_start"
            elif actual > planned:
                signal_type = "late_start"
            else:
                continue
            cues.append(
                {
                    "activity_id": aid,
                    "activity_name": row["activity_name"],
                    "wbs_code": row["wbs_code"],
                    "signal_type": signal_type,
                    "confidence": confidence,
                    "partial_dimension_support": payload.get("partial_dimension_support", False),
                    "phase": dim.get("phase"),
                    "cue_summary": f"Planned start in window but activity {signal_type.replace('_', ' ')}.",
                    "data_quality_notes": payload.get("data_quality_notes", []),
                }
            )
        cues.sort(
            key=lambda cue: (
                0 if cue.get("signal_type") == "did_not_start" else 1,
                str(cue.get("activity_id")),
            )
        )
        return cues[: max(1, min(limit, 100))]

    def get_window_finish_activity_cues(
        self,
        *,
        project_key: str,
        version_key: str,
        as_of_date: date,
        limit: int = 25,
    ) -> list[dict[str, Any]]:
        payload = self.build_metric_payload(
            metric_key="window_finish_accuracy",
            project_key=project_key,
            version_key=version_key,
            as_of_date=as_of_date,
        )
        if not payload.get("available"):
            return []
        confidence = (
            "partial_dimension_support"
            if payload.get("partial_dimension_support")
            else "production_backed"
        )
        lookback, lookahead = 7, 21
        window_start = as_of_date - timedelta(days=lookback)
        window_end = as_of_date + timedelta(days=lookahead)
        dimensions = {
            rec["activity_id"]: rec
            for rec in self.get_normalized_activity_dimensions(
                project_key=project_key,
                version_key=version_key,
            )["records"]
        }
        cues: list[dict[str, Any]] = []
        with open_connection(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT activity_id, activity_name, wbs_code, planned_finish, finish_date, actual_finish
                FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                """,
                (version_key,),
            ).fetchall()
        for row in rows:
            aid = str(row["activity_id"])
            dim = dimensions.get(aid, {})
            if dim.get("filter_out_parsed") is True:
                continue
            planned = _parse_date(row["planned_finish"]) or _parse_date(row["finish_date"])
            if not planned or planned < window_start or planned > window_end:
                continue
            actual = _parse_date(row["actual_finish"])
            if actual is None:
                signal_type = "did_not_finish"
            elif actual > planned:
                signal_type = "late_finish"
            else:
                continue
            cues.append(
                {
                    "activity_id": aid,
                    "activity_name": row["activity_name"],
                    "wbs_code": row["wbs_code"],
                    "signal_type": signal_type,
                    "confidence": confidence,
                    "partial_dimension_support": payload.get("partial_dimension_support", False),
                    "phase": dim.get("phase"),
                    "cue_summary": f"Planned finish in window but activity {signal_type.replace('_', ' ')}.",
                    "data_quality_notes": payload.get("data_quality_notes", []),
                }
            )
        cues.sort(
            key=lambda cue: (
                0 if cue.get("signal_type") == "did_not_finish" else 1,
                str(cue.get("activity_id")),
            )
        )
        return cues[: max(1, min(limit, 100))]

    def _window_start_accuracy_payload(
        self,
        *,
        project_key: str,
        version_key: str,
        as_of_date: date,
        data_date: date | None,
    ) -> dict[str, Any]:
        readiness = self.get_udf_metric_readiness(project_key, version_key)["metrics"]["window_start_accuracy"]
        effective_date = data_date or as_of_date
        lookback = 7
        lookahead = 21
        window_start = effective_date - timedelta(days=lookback)
        window_end = effective_date + timedelta(days=lookahead)
        dimensions = {
            rec["activity_id"]: rec
            for rec in self.get_normalized_activity_dimensions(
                project_key=project_key,
                version_key=version_key,
            )["records"]
        }
        on_time = late = did_not_start = excluded = 0
        notes: list[str] = []
        with open_connection(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT activity_id, planned_start, start_date, actual_start
                FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                """,
                (version_key,),
            ).fetchall()
        for row in rows:
            aid = str(row["activity_id"])
            dim = dimensions.get(aid, {})
            filter_parsed = dim.get("filter_out_parsed")
            if filter_parsed is True:
                excluded += 1
                continue
            if filter_parsed is None and dim.get("filter_out") not in (None, ""):
                notes.append(f"filter_out ambiguous for activity {aid}; not excluded")
            planned = _parse_date(row["planned_start"]) or _parse_date(row["start_date"])
            if not planned or planned < window_start or planned > window_end:
                continue
            actual = _parse_date(row["actual_start"])
            if actual is None:
                did_not_start += 1
            elif actual <= planned:
                on_time += 1
            else:
                late += 1
        total = on_time + late + did_not_start
        ratio = (on_time / total) if total else None
        partial = readiness.get("partial_dimension_support", False)
        if total == 0:
            return {
                "available": False,
                "reason": "no_activities_in_window",
                "readiness": readiness,
                "points": [],
                "partial_dimension_support": partial,
                "dimension_coverage": self._dimension_coverage(dimensions),
                "data_quality_notes": notes + ["No planned starts fell in the configured window."],
            }
        return {
            "available": True,
            "readiness": readiness,
            "partial_dimension_support": partial,
            "dimension_coverage": self._dimension_coverage(dimensions),
            "points": [
                {
                    "data_date": _date_str(effective_date),
                    "window_start": window_start.isoformat(),
                    "window_end": window_end.isoformat(),
                    "planned_start_basis": "planned_start_or_start_date",
                    "on_time_count": on_time,
                    "late_count": late,
                    "did_not_start_count": did_not_start,
                    "excluded_by_filter_out_count": excluded,
                    "accuracy_ratio": round(ratio, 4) if ratio is not None else None,
                }
            ],
            "summary": {"activity_count_basis": "activity_count", "backend_derived": True},
            "data_quality_notes": notes,
        }

    def _window_finish_accuracy_payload(
        self,
        *,
        project_key: str,
        version_key: str,
        as_of_date: date,
        data_date: date | None,
    ) -> dict[str, Any]:
        readiness = self.get_udf_metric_readiness(project_key, version_key)["metrics"]["window_finish_accuracy"]
        effective_date = data_date or as_of_date
        lookback = 7
        lookahead = 21
        window_start = effective_date - timedelta(days=lookback)
        window_end = effective_date + timedelta(days=lookahead)
        dimensions = {
            rec["activity_id"]: rec
            for rec in self.get_normalized_activity_dimensions(
                project_key=project_key,
                version_key=version_key,
            )["records"]
        }
        on_time = late = did_not_finish = excluded = 0
        notes: list[str] = []
        with open_connection(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT activity_id, planned_finish, finish_date, actual_finish
                FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                """,
                (version_key,),
            ).fetchall()
        for row in rows:
            aid = str(row["activity_id"])
            dim = dimensions.get(aid, {})
            filter_parsed = dim.get("filter_out_parsed")
            if filter_parsed is True:
                excluded += 1
                continue
            if filter_parsed is None and dim.get("filter_out") not in (None, ""):
                notes.append(f"filter_out ambiguous for activity {aid}; not excluded")
            planned = _parse_date(row["planned_finish"]) or _parse_date(row["finish_date"])
            if not planned or planned < window_start or planned > window_end:
                continue
            actual = _parse_date(row["actual_finish"])
            if actual is None:
                did_not_finish += 1
            elif actual <= planned:
                on_time += 1
            else:
                late += 1
        total = on_time + late + did_not_finish
        ratio = (on_time / total) if total else None
        partial = readiness.get("partial_dimension_support", False)
        if total == 0:
            return {
                "available": False,
                "reason": "no_activities_in_window",
                "readiness": readiness,
                "points": [],
                "partial_dimension_support": partial,
                "dimension_coverage": self._dimension_coverage(dimensions),
                "data_quality_notes": notes + ["No planned finishes fell in the configured window."],
            }
        return {
            "available": True,
            "readiness": readiness,
            "partial_dimension_support": partial,
            "dimension_coverage": self._dimension_coverage(dimensions),
            "points": [
                {
                    "data_date": _date_str(effective_date),
                    "window_start": window_start.isoformat(),
                    "window_end": window_end.isoformat(),
                    "planned_finish_basis": "planned_finish_or_finish_date",
                    "finished_on_time_count": on_time,
                    "finished_late_count": late,
                    "did_not_finish_count": did_not_finish,
                    "excluded_by_filter_out_count": excluded,
                    "accuracy_ratio": round(ratio, 4) if ratio is not None else None,
                }
            ],
            "summary": {"activity_count_basis": "activity_count", "backend_derived": True},
            "data_quality_notes": notes,
        }

    def _should_have_finished_status_payload(
        self,
        *,
        project_key: str,
        version_key: str,
        as_of_date: date,
        data_date: date | None,
    ) -> dict[str, Any]:
        readiness = self.get_udf_metric_readiness(project_key, version_key)["metrics"]["should_have_finished_status"]
        effective_date = data_date or as_of_date
        at_risk_float_days = 5
        dimensions = {
            rec["activity_id"]: rec
            for rec in self.get_normalized_activity_dimensions(
                project_key=project_key,
                version_key=version_key,
            )["records"]
        }
        counts = {"on_track": 0, "at_risk": 0, "delayed": 0}
        cpm_run = self._canonical.selected_cpm_run(version_key)
        cpm_flags: dict[str, dict[str, Any]] = {}
        if cpm_run:
            with open_connection(self._db_path) as conn:
                rows = conn.execute(
                    """
                    SELECT activity_id, computed_critical_flag, computed_near_critical_flag,
                           computed_total_float
                    FROM schedule_cpm_activity_results
                    WHERE schedule_version_key=? AND cpm_run_id=?
                    """,
                    (version_key, cpm_run["cpm_run_id"]),
                ).fetchall()
                cpm_flags = {str(r["activity_id"]): dict(r) for r in rows}
        with open_connection(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT activity_id, planned_finish, early_finish, actual_finish,
                       percent_complete, activity_status, total_float,
                       derived_total_float_days, explicit_total_float_days
                FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                """,
                (version_key,),
            ).fetchall()
        for row in rows:
            aid = str(row["activity_id"])
            dim = dimensions.get(aid, {})
            if dim.get("filter_out_parsed") is True:
                continue
            due = _parse_date(row["planned_finish"]) or _parse_date(row["early_finish"])
            if not due or due > effective_date:
                continue
            actual = _parse_date(row["actual_finish"])
            if actual is not None:
                continue
            float_days = self._activity_float(row, cpm_flags.get(aid))
            if float_days is not None and float_days < 0:
                counts["delayed"] += 1
            elif float_days is not None and float_days <= at_risk_float_days:
                counts["at_risk"] += 1
            else:
                counts["on_track"] += 1
        total = sum(counts.values())
        if total == 0:
            return {
                "available": False,
                "reason": "no_due_unfinished_activities",
                "readiness": readiness,
                "points": [],
                "partial_dimension_support": readiness.get("partial_dimension_support", False),
                "dimension_coverage": self._dimension_coverage(dimensions),
                "data_quality_notes": ["No unfinished activities were due on or before the data date."],
            }
        return {
            "available": True,
            "readiness": readiness,
            "partial_dimension_support": readiness.get("partial_dimension_support", False),
            "dimension_coverage": self._dimension_coverage(dimensions),
            "points": [
                {
                    "data_date": _date_str(effective_date),
                    "basis": "planned_finish_or_early_finish",
                    "status": status,
                    "activity_count": count,
                }
                for status, count in counts.items()
                if count > 0
            ],
            "summary": {
                "total_due_unfinished": total,
                "backend_derived": True,
                "review_cue_only": True,
            },
            "data_quality_notes": [
                "Classification is a PM review cue only; it does not infer responsibility or causation."
            ],
        }

    def _delay_analysis_payload(
        self,
        *,
        project_key: str,
        version_key: str,
        as_of_date: date,
        data_date: date | None,
    ) -> dict[str, Any]:
        readiness = self.get_udf_metric_readiness(project_key, version_key)["metrics"]["delay_analysis"]
        if not readiness.get("ready"):
            return {
                "available": False,
                "reason": readiness["blockers"][0] if readiness["blockers"] else "delay_analysis_not_ready",
                "readiness": readiness,
                "points": [],
                "partial_dimension_support": readiness.get("partial_dimension_support", False),
                "caveats": [NON_CAUSATION_CAVEAT],
                "data_quality_notes": ["Delay analysis requires prior-update diff evidence and normalized UDF dimensions."],
            }
        prior_key = self._prior_version_key(project_key, version_key)
        dimensions = {
            rec["activity_id"]: rec
            for rec in self.get_normalized_activity_dimensions(
                project_key=project_key,
                version_key=version_key,
            )["records"]
        }
        delays = gains = 0
        net_movement = 0
        with open_connection(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT activity_id, change_type, day_delta, wbs_code
                FROM schedule_version_diff_detail_facts
                WHERE to_schedule_version_key=?
                  AND from_schedule_version_key=?
                  AND change_domain='activity'
                  AND field_name IN ('finish_date', 'planned_finish')
                """,
                (version_key, prior_key),
            ).fetchall()
        for row in rows:
            delta = int(row["day_delta"] or 0)
            net_movement += delta
            if delta > 0:
                delays += 1
            elif delta < 0:
                gains += 1
        primary_phase = None
        for rec in dimensions.values():
            if rec.get("phase"):
                primary_phase = rec["phase"]
                break
        return {
            "available": True,
            "readiness": readiness,
            "partial_dimension_support": readiness.get("partial_dimension_support", False),
            "dimension_coverage": self._dimension_coverage(dimensions),
            "points": [
                {
                    "period": _date_str(data_date or as_of_date),
                    "data_date": _date_str(data_date or as_of_date),
                    "schedule_end_date": None,
                    "delays": delays,
                    "gains": gains,
                    "planned_movement": net_movement,
                    "net_movement": net_movement,
                    "candidate_driver": "prior_update_finish_movement",
                    "primary_wbs_phase": primary_phase,
                }
            ],
            "summary": {"review_cue_only": True, "backend_derived": True},
            "caveats": [NON_CAUSATION_CAVEAT],
            "data_quality_notes": [
                "Candidate driver wording is advisory and not a causation or entitlement finding."
            ],
        }

    def _critical_issues_category_model_payload(
        self,
        *,
        project_key: str,
        version_key: str,
        as_of_date: date,
        data_date: date | None,
    ) -> dict[str, Any]:
        del as_of_date, data_date
        readiness = self.get_udf_metric_readiness(project_key, version_key)["metrics"]["critical_issues_category_model"]
        dimensions = {
            rec["activity_id"]: rec
            for rec in self.get_normalized_activity_dimensions(
                project_key=project_key,
                version_key=version_key,
            )["records"]
        }
        category_counts: dict[str, int] = {key: 0 for key, _ in _CRITICAL_ISSUE_CATEGORIES}
        cpm_run = self._canonical.selected_cpm_run(version_key)
        with open_connection(self._db_path) as conn:
            if cpm_run:
                neg_float = conn.execute(
                    """
                    SELECT COUNT(*) FROM schedule_cpm_activity_results
                    WHERE schedule_version_key=? AND cpm_run_id=?
                      AND computed_total_float < 0
                    """,
                    (version_key, cpm_run["cpm_run_id"]),
                ).fetchone()[0]
                category_counts["negative_float_and_critical_path_erosion"] = int(neg_float or 0)
            quality_count = conn.execute(
                """
                SELECT COUNT(*) FROM schedule_quality_findings qf
                JOIN schedule_quality_evaluation_runs er ON er.evaluation_run_id = qf.evaluation_run_id
                WHERE er.schedule_version_key=? AND er.is_latest=1
                """,
                (version_key,),
            ).fetchone()[0]
            category_counts["logic_and_quality_findings"] = int(quality_count or 0)
            open_due = conn.execute(
                """
                SELECT COUNT(*) FROM procore_ep_schedule_activities
                WHERE schedule_version_key=?
                  AND (actual_finish IS NULL OR TRIM(actual_finish)='')
                  AND COALESCE(planned_finish, finish_date, early_finish) < date('now')
                """,
                (version_key,),
            ).fetchone()[0]
            category_counts["execution_and_status_gaps"] = int(open_due or 0)
            review_flags = sum(
                1
                for rec in dimensions.values()
                if rec.get("schedule_review_comments") or rec.get("update_notes")
            )
            category_counts["review_and_external_flags"] = review_flags
        points = [
            {
                "category": key,
                "category_label": label,
                "severity": "review",
                "candidate_count": category_counts[key],
                "drilldown_basis": "normalized_udf_and_schedule_facts",
                "review_item_eligible": False,
            }
            for key, label in _CRITICAL_ISSUE_CATEGORIES
        ]
        total_candidates = sum(category_counts.values())
        return {
            "available": total_candidates > 0 or readiness.get("ready"),
            "readiness": readiness,
            "partial_dimension_support": readiness.get("partial_dimension_support", False),
            "dimension_coverage": self._dimension_coverage(dimensions),
            "points": points,
            "summary": {
                "category_count": len(_CRITICAL_ISSUE_CATEGORIES),
                "total_candidate_count": total_candidates,
                "review_item_eligible": False,
                "backend_derived": True,
            },
            "caveats": [NON_CAUSATION_CAVEAT],
            "data_quality_notes": [
                "Issue categories are review cues only; Phase 8B does not create review items or infer responsibility."
            ],
        }

    def _normalize_activity_record(
        self,
        project_key: str,
        version_key: str,
        activity_id: str,
        rows: list[dict[str, Any]],
    ) -> dict[str, Any]:
        by_name: dict[str, list[dict[str, Any]]] = defaultdict(list)
        raw_sources: list[dict[str, Any]] = []
        for row in rows:
            name = str(row.get("udf_type_name") or "").strip()
            raw_sources.append(
                {
                    "udf_type_name": name,
                    "udf_value": row.get("udf_value"),
                    "udf_data_type": row.get("udf_data_type"),
                    "source_object_id": row.get("source_object_id"),
                }
            )
            if name:
                by_name[name].append(row)

        field_values: dict[str, Any] = {field: None for field in REQUIRED_INTERNAL_FIELDS}
        alias_notes: list[str] = []
        sparsity_flags: list[str] = []
        ambiguous_fields: list[str] = []

        for field, aliases in UDF_FIELD_ALIASES.items():
            if field in {"update_notes", "update_notes_1", "update_notes_2"}:
                continue
            matched: list[str] = []
            for alias in aliases:
                alias_rows = by_name.get(alias, [])
                if len(alias_rows) > 1:
                    ambiguous_fields.append(field)
                    alias_notes.append(f"duplicate rows for {alias} on {activity_id}")
                elif len(alias_rows) == 1:
                    value = str(alias_rows[0].get("udf_value") or "").strip() or None
                    if value is not None:
                        matched.append(value)
            if len(matched) > 1:
                ambiguous_fields.append(field)
                alias_notes.append(f"conflicting alias values for {field} on {activity_id}")
            elif len(matched) == 1:
                field_values[field] = matched[0]
            else:
                sparsity_flags.append(field)

        notes_primary = self._first_value(by_name, "Update Notes")
        notes_1 = self._first_value(by_name, "Update Notes - 1")
        notes_2 = self._first_value(by_name, "Update Notes - 2")
        field_values["update_notes_1"] = notes_1
        field_values["update_notes_2"] = notes_2
        field_values["update_notes"] = notes_primary or notes_1 or notes_2

        filter_raw = field_values.get("filter_out")
        filter_parsed = self._parse_filter_out(filter_raw)
        if filter_raw and filter_parsed is None:
            alias_notes.append(f"filter_out value not safely parsed: {filter_raw}")

        confidence = "high"
        if ambiguous_fields:
            confidence = "ambiguous"
        elif sparsity_flags and len(sparsity_flags) == len(REQUIRED_INTERNAL_FIELDS):
            confidence = "missing"

        source_object_id = None
        if rows:
            source_object_id = rows[0].get("source_object_id")

        return {
            "project_key": project_key,
            "version_key": version_key,
            "activity_id": activity_id,
            "source_object_id": source_object_id,
            **field_values,
            "filter_out_parsed": filter_parsed,
            "raw_udf_sources": raw_sources,
            "normalization_confidence": confidence,
            "sparsity_flags": sparsity_flags,
            "alias_notes": alias_notes,
        }

    @staticmethod
    def _first_value(by_name: dict[str, list[dict[str, Any]]], alias: str) -> str | None:
        rows = by_name.get(alias, [])
        if not rows:
            return None
        return str(rows[0].get("udf_value") or "").strip() or None

    @staticmethod
    def _parse_filter_out(value: str | None) -> bool | None:
        if value is None:
            return None
        normalized = str(value).strip().lower()
        if not normalized:
            return None
        if normalized in _FILTER_TRUE:
            return True
        if normalized in _FILTER_FALSE:
            return False
        return None

    @staticmethod
    def _ambiguous_aliases(rows: list[dict[str, Any]], aliases: tuple[str, ...]) -> list[str]:
        counts: dict[str, int] = defaultdict(int)
        for row in rows:
            name = str(row.get("udf_type_name") or "").strip()
            if name in aliases:
                key = f"{row.get('activity_id')}::{name}"
                counts[key] += 1
        return sorted({name.split("::", 1)[1] for key, count in counts.items() if count > 1 for name in [key]})

    def _fetch_udf_rows(
        self,
        *,
        project_key: str | None,
        version_key: str | None,
    ) -> list[dict[str, Any]]:
        clauses: list[str] = []
        params: list[Any] = []
        if project_key:
            clauses.append("project_key=?")
            params.append(project_key)
        if version_key:
            clauses.append("schedule_version_key=?")
            params.append(version_key)
        where = f"WHERE {' AND '.join(clauses)}" if clauses else ""
        with open_connection(self._db_path) as conn:
            rows = conn.execute(
                f"""
                SELECT project_key, schedule_version_key, import_id, activity_id,
                       udf_type_name, udf_data_type, udf_value, source_object_id
                FROM procore_ep_schedule_udf_values
                {where}
                ORDER BY activity_id, udf_type_name
                """,
                tuple(params),
            ).fetchall()
        return [dict(row) for row in rows]

    def _activity_ids(self, version_key: str) -> set[str]:
        with open_connection(self._db_path) as conn:
            rows = conn.execute(
                "SELECT activity_id FROM procore_ep_schedule_activities WHERE schedule_version_key=?",
                (version_key,),
            ).fetchall()
        return {str(row["activity_id"]) for row in rows}

    def _dimension_coverage(self, dimensions: dict[str, dict[str, Any]]) -> dict[str, float]:
        if not dimensions:
            return {field: 0.0 for field in REQUIRED_INTERNAL_FIELDS}
        total = len(dimensions)
        coverage: dict[str, float] = {}
        for field in REQUIRED_INTERNAL_FIELDS:
            non_null = sum(1 for rec in dimensions.values() if rec.get(field) not in (None, ""))
            coverage[field] = round(non_null / total, 4)
        return coverage

    def _has_prior_update_diff(self, project_key: str, version_key: str) -> bool:
        prior = self._prior_version_key(project_key, version_key)
        if not prior:
            return False
        with open_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT COUNT(*) FROM schedule_version_diff_detail_facts
                WHERE project_key=? AND to_schedule_version_key=? AND from_schedule_version_key=?
                """,
                (project_key, version_key, prior),
            ).fetchone()
        return int(row[0] or 0) > 0

    def _prior_version_key(self, project_key: str, version_key: str) -> str | None:
        with open_connection(self._db_path) as conn:
            rows = conn.execute(
                """
                SELECT schedule_version_key, created_at
                FROM schedule_file_imports
                WHERE project_key=? AND import_status='committed'
                ORDER BY created_at
                """,
                (project_key,),
            ).fetchall()
        keys = [str(r["schedule_version_key"]) for r in rows]
        if version_key not in keys:
            return None
        idx = keys.index(version_key)
        return keys[idx - 1] if idx > 0 else None

    @staticmethod
    def _activity_float(row: Any, cpm: dict[str, Any] | None) -> float | None:
        if cpm and cpm.get("computed_total_float") is not None:
            try:
                return float(cpm["computed_total_float"])
            except (TypeError, ValueError):
                pass
        for key in ("total_float", "derived_total_float_days", "explicit_total_float_days"):
            raw = row[key]
            if raw is not None and str(raw).strip() != "":
                try:
                    return float(raw)
                except (TypeError, ValueError):
                    continue
        return None
