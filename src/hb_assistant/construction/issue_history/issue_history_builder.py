"""Phase 07D Prompt 07 — project issue-history materialization.

Materializes `project_issue_history_items` (V25, shipped empty in Prompt 02) by grouping the
unified cross-source relationship candidates into per-issue families using DETERMINISTIC and
STRONG-HEURISTIC relationships only. Weak / model-proposed / sensitive-high-impact edges are
excluded from grouping entirely (never grouped, never auto-promoted).

An issue family is one per distinct anchor source record `(source_family, source_record_ref)`
that has at least one eligible edge — a bounded, deterministic unit (an RFI / change order /
commitment and its directly-related records and entities), not a transitive connected component
(which would collapse the project into mega-families through shared entities such as vendor,
created_by, or category).

`latest_activity_utc` / `age_days` / `status` are best-effort honest: the anchor procore record
is resolved against `procore_live_records` (by a reconstructed record_key) for a real source
`updated_at_utc` + a normalized status token. When the anchor is non-procore or carries no source
timestamp, activity is left NULL / unknown and flagged in `stale_unknown_flags_json` — never
fabricated or overstated.

Guardrails: local-first, read-only against external systems; record refs are local stable
identifiers / existing hashes; no raw email/document/calendar content, raw status payload, signed/
download URL, token, secret, prompt, or response is read or persisted; outputs are advisory and
emit no final legal/contractual/claim/safety/financial determination.
"""

from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from typing import Any, Optional

from hb_assistant.construction.relationships.contracts import load_phase_07d_contract
from hb_assistant.construction.store.repositories import ConstructionStore
from hb_assistant.normalize.redaction import hash_value
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

_ISSUE_HISTORY_GUARDRAILS: dict[str, Any] = {
    "external_systems": "read_only",
    "writeback": "none",
    "writes": "local_sqlite_project_issue_history_items_only",
    "no_raw_content": True,
    "refs_are_local_ids_or_hashes": True,
    "advisory_only": True,
    "no_final_determinations": True,
    "auto_promotion": False,
    "grouping": "deterministic_and_strong_heuristic_only",
}

# Eligible confidence classes for issue-family grouping (excludes weak/model/human/rejected/stale).
_ELIGIBLE_CONFIDENCE_CLASSES = frozenset({"deterministic", "strong_heuristic"})

# Bounded, safe status vocabulary; anything else collapses to "other"/"unknown".
_KNOWN_STATUS = frozenset(
    {
        "open",
        "closed",
        "approved",
        "draft",
        "void",
        "pending",
        "none",
        "rejected",
        "in_review",
        "submitted",
        "answered",
        "overdue",
        "mixed",
    }
)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    if not value:
        return None
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


def _normalize_status(raw: Any) -> str:
    """Map a source status to a bounded safe token. Never persists the raw payload — Procore
    statuses can arrive as messy dict-strings (e.g. ``{'id': 20577, 'name': 'Open', ...}``)."""
    if raw is None:
        return "unknown"
    s = str(raw).strip()
    if not s:
        return "unknown"
    if s.startswith("{"):
        m = re.search(r"'mapped_to_status'\s*:\s*'([^']+)'", s) or re.search(
            r"'name'\s*:\s*'([^']+)'", s
        )
        s = m.group(1) if m else "other"
    s = s.lower().replace(" ", "_")
    if s in _KNOWN_STATUS:
        return s
    if len(s) <= 20 and s.replace("_", "").replace("-", "").isalnum():
        return s
    return "other"


def _procore_record_key(rec: dict[str, Any]) -> str:
    """Reconstruct the substrate record_key `project|endpoint|parent|id` for a live record."""
    return "|".join(
        [
            str(rec.get("project_key") or ""),
            str(rec.get("endpoint_id") or ""),
            str(rec.get("parent_procore_id") or ""),
            str(rec.get("procore_record_id") or ""),
        ]
    )


class IssueHistoryBuilder:
    """Materialize project issue-history families from the V25 substrate."""

    def __init__(self, store: Optional[ConstructionStore] = None) -> None:
        self._store = store or ConstructionStore()
        contract = load_phase_07d_contract("project_issue_history_contract")
        self._contract_version = contract.get("version")

    # -- helpers -------------------------------------------------------------

    def _eligible_candidates(self, project_key: str) -> list[dict[str, Any]]:
        return [
            c
            for c in self._store.list_cross_source_relationship_candidates(
                project_key=project_key, limit=100000
            )
            if c.get("confidence_class") in _ELIGIBLE_CONFIDENCE_CLASSES
            and not c.get("sensitive_high_impact")
            and not c.get("model_proposed")
        ]

    def _discover_projects(self, project_filter: Optional[str]) -> list[str]:
        if project_filter is not None:
            return [project_filter]
        keys: set[str] = set()
        for c in self._store.list_cross_source_relationship_candidates(limit=100000):
            pk = c.get("project_key")
            if pk:
                keys.add(str(pk))
        return sorted(keys)

    def _procore_activity_map(self, project_key: str) -> dict[str, tuple[Optional[str], str]]:
        """{record_key: (updated_at_utc, normalized_status)} for the project's live records."""
        out: dict[str, tuple[Optional[str], str]] = {}
        for rec in self._store.list_procore_live_records(project_key=project_key):
            out[_procore_record_key(rec)] = (
                rec.get("updated_at_utc") or None,
                _normalize_status(rec.get("status")),
            )
        return out

    # -- public API ----------------------------------------------------------

    def build(
        self,
        *,
        dry_run: bool = True,
        project_filter: Optional[str] = None,
        now_utc: Optional[datetime] = None,
    ) -> dict[str, Any]:
        """Materialize per-issue families. Dry-run plans counts and writes nothing; --apply
        upserts one `project_issue_history_items` row per anchor source record."""
        mode = "apply" if not dry_run else "dry_run"
        now = now_utc or datetime.now(timezone.utc)
        projects = self._discover_projects(project_filter)

        families_planned = 0
        families_written = 0
        review_required_total = 0
        resolved_activity = 0
        unresolved_activity = 0
        by_confidence: dict[str, int] = {}
        by_status: dict[str, int] = {}
        by_issue_kind: dict[str, int] = {}

        for project_key in projects:
            activity = self._procore_activity_map(project_key)
            # Group eligible edges by anchor source record.
            groups: dict[tuple[str, str], list[dict[str, Any]]] = {}
            for c in self._eligible_candidates(project_key):
                key = (str(c.get("source_family")), str(c.get("source_record_ref")))
                groups.setdefault(key, []).append(c)

            for (source_family, source_ref), edges in sorted(groups.items()):
                families_planned += 1
                item = self._build_item(
                    project_key, source_family, source_ref, edges, activity, now
                )
                by_confidence[item["confidence_class"]] = (
                    by_confidence.get(item["confidence_class"], 0) + 1
                )
                by_status[item["status"]] = by_status.get(item["status"], 0) + 1
                if item["issue_kind"]:
                    by_issue_kind[item["issue_kind"]] = by_issue_kind.get(item["issue_kind"], 0) + 1
                if item["review_required"]:
                    review_required_total += 1
                if item["latest_activity_utc"] is not None:
                    resolved_activity += 1
                else:
                    unresolved_activity += 1
                if not dry_run:
                    self._store.upsert_project_issue_history_item(
                        issue_family_id=item["issue_family_id"],
                        project_key=project_key,
                        status=item["status"],
                        source_families_json=item["source_families_json"],
                        confidence_class=item["confidence_class"],
                        issue_kind=item["issue_kind"],
                        age_days=item["age_days"],
                        latest_activity_utc=item["latest_activity_utc"],
                        evidence_trail_id=item["evidence_trail_id"],
                        review_required=item["review_required"],
                        stale_unknown_flags_json=item["stale_unknown_flags_json"],
                    )
                    families_written += 1

        return {
            "command": "construction-agent issue-history build",
            "mode": mode,
            "ok": True,
            "schema_version": LATEST_SCHEMA_VERSION,
            "contract_version": self._contract_version,
            "project_filter": project_filter,
            "summary": {
                "projects": projects,
                "families_planned": families_planned,
                "families_written": families_written,
                "review_required": review_required_total,
                "resolved_activity": resolved_activity,
                "unresolved_activity": unresolved_activity,
                "by_confidence_class": dict(sorted(by_confidence.items())),
                "by_status": dict(sorted(by_status.items())),
                "by_issue_kind": dict(sorted(by_issue_kind.items())),
            },
            "guardrails": _ISSUE_HISTORY_GUARDRAILS,
        }

    def _build_item(
        self,
        project_key: str,
        source_family: str,
        source_ref: str,
        edges: list[dict[str, Any]],
        activity: dict[str, tuple[Optional[str], str]],
        now: datetime,
    ) -> dict[str, Any]:
        issue_family_id = (
            hash_value(f"issue|{project_key}|{source_family}|{source_ref}") or source_ref
        )
        all_deterministic = all(e.get("confidence_class") == "deterministic" for e in edges)
        confidence_class = "deterministic" if all_deterministic else "strong_heuristic"
        review_required = (confidence_class != "deterministic") or any(
            e.get("review_required") for e in edges
        )
        families = {source_family}
        for e in edges:
            families.add(str(e.get("target_family")))
        evidence_trail_id = next(
            (e.get("evidence_trail_id") for e in edges if e.get("evidence_trail_id")), None
        )

        # issue_kind: procore endpoint segment of the record_key, else the source record type.
        issue_kind: Optional[str]
        if source_family == "procore" and source_ref.count("|") >= 3:
            issue_kind = source_ref.split("|")[1] or None
        else:
            issue_kind = str(edges[0].get("source_record_type")) if edges else None

        # Activity / status: resolve the procore anchor against live records.
        latest_activity_utc: Optional[str] = None
        status = "unknown"
        age_days = 0
        flags: dict[str, Any] = {}
        resolved = activity.get(source_ref) if source_family == "procore" else None
        if resolved is not None:
            latest_activity_utc, status = resolved
            if latest_activity_utc is None:
                flags["no_source_activity_timestamp"] = True
            else:
                dt = _parse_dt(latest_activity_utc)
                age_days = max(0, (now - dt).days) if dt is not None else 0
                if dt is None:
                    latest_activity_utc = None
                    flags["no_source_activity_timestamp"] = True
            if status in ("unknown", "none"):
                flags["status_unresolved"] = True
        else:
            flags["no_source_activity_timestamp"] = True
            flags["status_unresolved"] = True

        return {
            "issue_family_id": issue_family_id,
            "issue_kind": issue_kind,
            "status": status,
            "age_days": age_days,
            "latest_activity_utc": latest_activity_utc,
            "source_families_json": json.dumps(sorted(families), sort_keys=True),
            "evidence_trail_id": evidence_trail_id,
            "confidence_class": confidence_class,
            "review_required": review_required,
            "stale_unknown_flags_json": json.dumps(flags, sort_keys=True) if flags else None,
        }


def project_issue_history_status(
    store: Optional[ConstructionStore] = None, *, project_filter: Optional[str] = None
) -> dict[str, Any]:
    """Read-only coverage report over the V25 project issue-history table."""
    store = store or ConstructionStore()
    items = store.list_project_issue_history_items(project_key=project_filter, limit=100000)
    by_status: dict[str, int] = {}
    by_issue_kind: dict[str, int] = {}
    by_confidence: dict[str, int] = {}
    review_required = 0
    resolved_activity = 0
    for it in items:
        by_status[str(it["status"])] = by_status.get(str(it["status"]), 0) + 1
        if it.get("issue_kind"):
            by_issue_kind[str(it["issue_kind"])] = by_issue_kind.get(str(it["issue_kind"]), 0) + 1
        by_confidence[str(it["confidence_class"])] = (
            by_confidence.get(str(it["confidence_class"]), 0) + 1
        )
        if it["review_required"]:
            review_required += 1
        if it.get("latest_activity_utc") is not None:
            resolved_activity += 1
    return {
        "command": "construction-agent issue-history status",
        "ok": True,
        "schema_version": LATEST_SCHEMA_VERSION,
        "project_filter": project_filter,
        "summary": {
            "items": len(items),
            "review_required": review_required,
            "resolved_activity": resolved_activity,
            "by_status": dict(sorted(by_status.items())),
            "by_issue_kind": dict(sorted(by_issue_kind.items())),
            "by_confidence_class": dict(sorted(by_confidence.items())),
        },
        "guardrails": _ISSUE_HISTORY_GUARDRAILS,
    }
