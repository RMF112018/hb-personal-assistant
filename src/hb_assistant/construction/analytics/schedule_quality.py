"""Deterministic schedule quality checks."""

from __future__ import annotations

from typing import Any

from .schedule_graph import orphan_relationship_ids


def run_quality_checks(
    *,
    project_key: str,
    schedule_version_key: str,
    import_id: str,
    activities: list[dict[str, Any]],
    relationships: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    findings: list[dict[str, Any]] = []
    activity_ids = {str(a.get("activity_id")) for a in activities if a.get("activity_id")}

    for act in activities:
        act_id = act.get("activity_id")
        if not act.get("start_date") and not act.get("finish_date"):
            findings.append(
                _finding(
                    project_key=project_key,
                    schedule_version_key=schedule_version_key,
                    import_id=import_id,
                    finding_type="missing_dates",
                    severity="warning",
                    activity_id=act_id,
                    finding_code="activity_missing_dates",
                    finding_summary="Activity has no start or finish date",
                )
            )
        try:
            if act.get("total_float") is not None and float(act["total_float"]) < 0:
                findings.append(
                    _finding(
                        project_key=project_key,
                        schedule_version_key=schedule_version_key,
                        import_id=import_id,
                        finding_type="negative_float",
                        severity="info",
                        activity_id=act_id,
                        finding_code="negative_total_float",
                        finding_summary="Activity reports negative total float",
                    )
                )
        except (TypeError, ValueError):
            pass

    for orphan in orphan_relationship_ids(relationships, activity_ids):
        findings.append(
            _finding(
                project_key=project_key,
                schedule_version_key=schedule_version_key,
                import_id=import_id,
                finding_type="orphan_relationship",
                severity="warning",
                finding_code="orphan_relationship",
                finding_summary=f"Relationship references missing activity: {orphan}",
                requires_review=1,
            )
        )

    if not activities:
        findings.append(
            _finding(
                project_key=project_key,
                schedule_version_key=schedule_version_key,
                import_id=import_id,
                finding_type="empty_schedule",
                severity="error",
                finding_code="no_activities",
                finding_summary="Schedule version contains no activities",
                requires_review=1,
            )
        )

    return findings


def _finding(**kwargs: Any) -> dict[str, Any]:
    return {
        "project_key": kwargs["project_key"],
        "schedule_version_key": kwargs["schedule_version_key"],
        "import_id": kwargs.get("import_id"),
        "finding_type": kwargs["finding_type"],
        "severity": kwargs["severity"],
        "activity_id": kwargs.get("activity_id"),
        "relationship_id": kwargs.get("relationship_id"),
        "wbs_id": kwargs.get("wbs_id"),
        "finding_code": kwargs["finding_code"],
        "finding_summary": kwargs["finding_summary"],
        "evidence_json": None,
        "requires_operator_review": kwargs.get("requires_review", 0),
    }