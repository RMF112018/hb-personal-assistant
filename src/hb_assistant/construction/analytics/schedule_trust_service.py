"""Schedule trust evaluation for Project Schedule Hub Phase 2."""

from __future__ import annotations

import json
from typing import Any

from hb_assistant.store.connection import open_connection
from hb_assistant.store.project_schedule_hub_repository import (
    MEMBERSHIP_ACCEPTED,
    MEMBERSHIP_EXCLUDED,
    MEMBERSHIP_PENDING,
    ProjectScheduleHubRepository,
)
from hb_assistant.store.schedule_identity_repository import ScheduleIdentityRepository

_OVERLAP_REVIEW_THRESHOLD = 0.35
_COUNT_DELTA_REVIEW_RATIO = 0.45


class ScheduleTrustService:
    def __init__(self, *, db_path: str) -> None:
        self._db_path = db_path
        self._identity = ScheduleIdentityRepository(db_path=db_path)
        self._hub_repo = ProjectScheduleHubRepository(db_path=db_path)

    def membership_for_version(
        self, *, project_key: str, version: dict[str, Any], identity_match: dict[str, Any] | None
    ) -> dict[str, Any]:
        version_key = str(version.get("schedule_version_key") or "")
        existing = self._hub_repo.get_membership(project_key=project_key, schedule_version_key=version_key)
        if existing:
            return existing
        status = self._default_membership_status(identity_match)
        return {
            "membership_status": status,
            "review_reason": None if status == MEMBERSHIP_ACCEPTED else (identity_match or {}).get("no_match_reason"),
        }

    def list_series_memberships(self, *, project_key: str) -> list[dict[str, Any]]:
        return self._hub_repo.list_memberships(project_key=project_key)

    def preview_import_trust(
        self,
        *,
        project_key: str,
        schedule_version_key: str,
        activity_ids: set[str],
        source_project_id: str | None,
        data_date: str | None,
        duplicate_exists: bool = False,
        confirm_supersede: bool = False,
    ) -> dict[str, Any]:
        """Best-effort pre-commit trust preview; does not persist membership."""
        warnings: list[dict[str, str]] = []
        posture = "likely_same_schedule_series"
        accepted = self._accepted_representative(project_key)

        if duplicate_exists and not confirm_supersede:
            warnings.append(
                {
                    "code": "duplicate_schedule_version",
                    "message": "This schedule version already exists. Supersede confirmation is required to replace it.",
                }
            )
            posture = "supersede_required"
        elif duplicate_exists and confirm_supersede:
            warnings.append(
                {
                    "code": "supersede_required",
                    "message": "This preview will replace the existing committed schedule version for this project.",
                }
            )
            posture = "supersede_required"

        if not accepted:
            warnings.append(
                {
                    "code": "likely_new_schedule_series",
                    "message": "No accepted schedule series exists yet for this project. Review identity after commit.",
                }
            )
            posture = "likely_new_schedule_series"
        else:
            accepted_key = str(accepted["schedule_version_key"])
            overlap = self._overlap_from_ids(activity_ids, accepted_key)
            if overlap < _OVERLAP_REVIEW_THRESHOLD:
                warnings.append(
                    {
                        "code": "low_activity_overlap",
                        "message": (
                            "Activity IDs overlap weakly with the current accepted schedule. "
                            "Review identity before accepting this file as the current update."
                        ),
                    }
                )
                posture = "identity_requires_review"
            elif overlap >= 0.7:
                posture = "likely_same_schedule_series"
            else:
                posture = "identity_requires_review"
                warnings.append(
                    {
                        "code": "identity_requires_review",
                        "message": "This file may belong to a different schedule series. Review identity before commit.",
                    }
                )

            accepted_data_date = self._data_date_for_version(accepted_key)
            if accepted_data_date and data_date and data_date < accepted_data_date:
                warnings.append(
                    {
                        "code": "data_date_out_of_sequence",
                        "message": (
                            "Data date appears earlier than the accepted schedule update. "
                            "Confirm this is the intended current snapshot."
                        ),
                    }
                )

        if source_project_id:
            procore_id = self._procore_project_id(project_key)
            if procore_id and str(source_project_id) != str(procore_id):
                warnings.append(
                    {
                        "code": "source_project_mismatch",
                        "message": "Source project ID in the file does not match the linked project record.",
                    }
                )
        else:
            warnings.append(
                {
                    "code": "source_project_unknown",
                    "message": "Source project ID was not detected in the uploaded schedule.",
                }
            )

        return {
            "posture": posture,
            "warnings": warnings,
            "accepted_schedule_version_key": (accepted or {}).get("schedule_version_key"),
            "preview_schedule_version_key": schedule_version_key,
            "limitations": [
                "Pre-commit identity match is best-effort and does not run full identity resolution.",
            ],
        }

    def _overlap_from_ids(self, left_ids: set[str], right_version_key: str) -> float:
        with open_connection(self._db_path) as conn:
            right_ids = {
                str(row[0])
                for row in conn.execute(
                    "SELECT activity_id FROM procore_ep_schedule_activities WHERE schedule_version_key=?",
                    (right_version_key,),
                ).fetchall()
            }
        if not left_ids or not right_ids:
            return 0.0
        return len(left_ids & right_ids) / max(len(left_ids), len(right_ids))

    def _data_date_for_version(self, schedule_version_key: str) -> str | None:
        from hb_assistant.store.schedule_identity_repository import parse_schedule_version_data_date

        parsed = parse_schedule_version_data_date(schedule_version_key)
        return parsed.date().isoformat() if parsed else None

    def _procore_project_id(self, project_key: str) -> str | None:
        with open_connection(self._db_path) as conn:
            row = conn.execute(
                "SELECT project_id FROM procore_ep_projects WHERE project_key=? LIMIT 1",
                (project_key,),
            ).fetchone()
        return str(row[0]) if row and row[0] else None

    def evaluate_import_guardrail(
        self,
        *,
        project_key: str,
        schedule_version_key: str,
        import_id: str,
        identity_match: dict[str, Any],
    ) -> dict[str, Any]:
        accepted = self._accepted_representative(project_key)
        evidence: dict[str, Any] = {
            "identity_match_status": identity_match.get("match_status"),
            "confidence_score": identity_match.get("confidence_score"),
        }
        review_reasons: list[str] = []
        status = MEMBERSHIP_ACCEPTED

        if int(identity_match.get("requires_review") or 0):
            status = MEMBERSHIP_PENDING
            review_reasons.append("requires_review_match")
        elif accepted:
            overlap = self._activity_overlap(schedule_version_key, str(accepted["schedule_version_key"]))
            evidence["activity_overlap_with_accepted"] = overlap
            if overlap < _OVERLAP_REVIEW_THRESHOLD:
                status = MEMBERSHIP_PENDING
                review_reasons.append("low_activity_overlap")
            count_delta = self._count_scale_delta(
                schedule_version_key, str(accepted["schedule_version_key"])
            )
            evidence.update(count_delta)
            if count_delta.get("activity_count_delta_ratio", 0) >= _COUNT_DELTA_REVIEW_RATIO:
                status = MEMBERSHIP_PENDING
                review_reasons.append("count_scale_delta")

        return self._hub_repo.upsert_membership(
            project_key=project_key,
            schedule_version_key=schedule_version_key,
            import_id=import_id,
            membership_status=status,
            review_reason=",".join(review_reasons) if review_reasons else None,
            evidence={**evidence, "review_reasons": review_reasons},
        )

    def set_series_membership(
        self,
        *,
        project_key: str,
        schedule_version_key: str,
        membership_status: str,
        reason: str | None,
        operator: str | None,
    ) -> dict[str, Any]:
        if membership_status not in {MEMBERSHIP_ACCEPTED, MEMBERSHIP_EXCLUDED, MEMBERSHIP_PENDING}:
            raise ValueError("invalid_membership_status")
        import_id = self._import_id_for_version(schedule_version_key)
        return self._hub_repo.upsert_membership(
            project_key=project_key,
            schedule_version_key=schedule_version_key,
            import_id=import_id,
            membership_status=membership_status,
            review_reason=reason,
            reviewed_by_operator=operator,
            evidence={"operator_action": membership_status},
        )

    def build_trust_envelope(
        self,
        *,
        project_key: str,
        current_choice: Any,
        versions: list[dict[str, Any]],
        accepted_identity_key: str | None,
    ) -> dict[str, Any]:
        current_match = current_choice.identity_match if current_choice else None
        membership = (
            self.membership_for_version(
                project_key=project_key,
                version=current_choice.version,
                identity_match=current_match,
            )
            if current_choice
            else None
        )
        status = "unknown"
        review_reasons: list[str] = []
        if membership:
            if membership.get("membership_status") == MEMBERSHIP_EXCLUDED:
                status = "excluded"
                review_reasons.append("excluded_from_series")
            elif membership.get("membership_status") == MEMBERSHIP_PENDING or self._requires_identity_review(current_match):
                status = "review_required"
                if membership.get("review_reason"):
                    review_reasons.extend(str(membership["review_reason"]).split(","))
                if self._requires_identity_review(current_match):
                    review_reasons.append("requires_review_match")
            else:
                status = "trusted"

        candidates = self._candidate_series(project_key, versions, accepted_identity_key)
        confidence = None
        if current_match and current_match.get("confidence_score") is not None:
            try:
                confidence = float(current_match["confidence_score"])
            except (TypeError, ValueError):
                confidence = None

        return {
            "status": status,
            "accepted_identity_key": accepted_identity_key,
            "current_identity_confidence": confidence,
            "review_reasons": sorted(set(r for r in review_reasons if r)),
            "candidate_series": candidates,
            "current_membership_status": (membership or {}).get("membership_status"),
        }

    def is_hub_eligible(
        self, *, project_key: str, version: dict[str, Any], identity_match: dict[str, Any] | None
    ) -> bool:
        if self._requires_identity_review(identity_match):
            return False
        if str((identity_match or {}).get("match_status") or "") not in {"", "resolved"}:
            return False
        membership = self.membership_for_version(
            project_key=project_key, version=version, identity_match=identity_match
        )
        return membership.get("membership_status") == MEMBERSHIP_ACCEPTED

    def enrich_review_item(self, *, project_key: str, item: dict[str, Any]) -> dict[str, Any]:
        version_key = str(item.get("schedule_version_key") or "")
        membership = self._hub_repo.get_membership(project_key=project_key, schedule_version_key=version_key)
        accepted = self._accepted_representative(project_key)
        overlap = None
        count_delta: dict[str, Any] = {}
        if accepted and version_key:
            overlap = self._activity_overlap(version_key, str(accepted["schedule_version_key"]))
            count_delta = self._count_scale_delta(version_key, str(accepted["schedule_version_key"]))
        out = dict(item)
        out["membership_status"] = (membership or {}).get("membership_status")
        out["review_reason"] = (membership or {}).get("review_reason") or item.get("no_match_reason")
        out["activity_overlap_with_accepted"] = overlap
        out["relationship_scale_delta"] = count_delta.get("relationship_count_delta_ratio")
        out["activity_count_delta_ratio"] = count_delta.get("activity_count_delta_ratio")
        if membership and membership.get("evidence_json"):
            try:
                out["membership_evidence"] = json.loads(str(membership["evidence_json"]))
            except json.JSONDecodeError:
                out["membership_evidence"] = {}
        return out

    def _candidate_series(
        self, project_key: str, versions: list[dict[str, Any]], accepted_identity_key: str | None
    ) -> list[dict[str, Any]]:
        memberships = {
            str(row["schedule_version_key"]): row
            for row in self._hub_repo.list_memberships(project_key=project_key)
        }
        out: list[dict[str, Any]] = []
        for version in versions[:12]:
            version_key = str(version.get("schedule_version_key") or "")
            match = self._identity.get_match_for_version(version_key) or {}
            membership = memberships.get(version_key) or {}
            out.append(
                {
                    "friendly_label": version.get("display_label") or version.get("source_filename_redacted"),
                    "data_date": version.get("data_date"),
                    "activity_count": version.get("activity_count"),
                    "relationship_count": version.get("relationship_count"),
                    "membership_status": membership.get("membership_status"),
                    "identity_confidence": match.get("confidence_score"),
                    "requires_review": bool(int(match.get("requires_review") or 0)),
                    "same_accepted_identity": (
                        accepted_identity_key is None
                        or str(match.get("schedule_identity_key") or "") == accepted_identity_key
                    ),
                }
            )
        return out

    def _accepted_representative(self, project_key: str) -> dict[str, Any] | None:
        memberships = self._hub_repo.list_memberships(project_key=project_key)
        for row in memberships:
            if row.get("membership_status") == MEMBERSHIP_ACCEPTED:
                return row
        identities = self._identity.list_identities(project_key=project_key, show_merged=False)
        if not identities:
            return None
        latest_key = identities[0].get("latest_schedule_version_key")
        if not latest_key:
            return None
        return {"schedule_version_key": latest_key}

    def _activity_overlap(self, left_key: str, right_key: str) -> float:
        with open_connection(self._db_path) as conn:
            left_ids = {
                str(row[0])
                for row in conn.execute(
                    "SELECT activity_id FROM procore_ep_schedule_activities WHERE schedule_version_key=?",
                    (left_key,),
                ).fetchall()
            }
            right_ids = {
                str(row[0])
                for row in conn.execute(
                    "SELECT activity_id FROM procore_ep_schedule_activities WHERE schedule_version_key=?",
                    (right_key,),
                ).fetchall()
            }
        if not left_ids or not right_ids:
            return 0.0
        return len(left_ids & right_ids) / max(len(left_ids), len(right_ids))

    def _count_scale_delta(self, left_key: str, right_key: str) -> dict[str, Any]:
        with open_connection(self._db_path) as conn:
            left = conn.execute(
                """
                SELECT COUNT(*) AS activities,
                       (SELECT COUNT(*) FROM procore_ep_schedule_relationships WHERE schedule_version_key=?)
                FROM procore_ep_schedule_activities WHERE schedule_version_key=?
                """,
                (left_key, left_key),
            ).fetchone()
            right = conn.execute(
                """
                SELECT COUNT(*) AS activities,
                       (SELECT COUNT(*) FROM procore_ep_schedule_relationships WHERE schedule_version_key=?)
                FROM procore_ep_schedule_activities WHERE schedule_version_key=?
                """,
                (right_key, right_key),
            ).fetchone()
        left_a = int(left[0] or 0)
        right_a = int(right[0] or 0)
        left_r = int(left[1] or 0)
        right_r = int(right[1] or 0)
        return {
            "activity_count_delta_ratio": abs(left_a - right_a) / max(right_a, 1),
            "relationship_count_delta_ratio": abs(left_r - right_r) / max(right_r, 1),
        }

    def _import_id_for_version(self, schedule_version_key: str) -> str | None:
        with open_connection(self._db_path) as conn:
            row = conn.execute(
                """
                SELECT import_id FROM schedule_file_imports
                WHERE schedule_version_key=? AND import_status='committed'
                ORDER BY created_at DESC LIMIT 1
                """,
                (schedule_version_key,),
            ).fetchone()
            return str(row[0]) if row else None

    @staticmethod
    def _default_membership_status(identity_match: dict[str, Any] | None) -> str:
        if not identity_match:
            return MEMBERSHIP_PENDING
        if int(identity_match.get("requires_review") or 0):
            return MEMBERSHIP_PENDING
        if str(identity_match.get("match_status") or "") in {"requires_review", "ambiguous"}:
            return MEMBERSHIP_PENDING
        return MEMBERSHIP_ACCEPTED

    @staticmethod
    def _requires_identity_review(match: dict[str, Any] | None) -> bool:
        return bool(match and int(match.get("requires_review") or 0))