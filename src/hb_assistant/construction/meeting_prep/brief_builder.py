"""Phase 07D Prompt 06 — meeting-prep brief materialization.

Materializes source-linked, review-controlled meeting-prep briefs into the two V25 tables
``meeting_prep_brief_runs`` + ``meeting_prep_brief_sections`` (shipped empty in Prompt 02). One
brief run per project, with the eight policy sections (``meeting_prep_brief_policy.seed.yaml``):
meeting_context, project_context, open_items, aging_items, recent_activity,
risk_exposure_watchlist, review_required_warnings, confidence_and_stale_unknown_warnings.

Each section carries a redacted bounded summary (counts / enums / local identifiers only), a
confidence label, an optional evidence-trail ref, a review-required flag, and stale/unknown
flags. Sections sourced from not-yet-implemented prompts (aging — Prompt 07/09; risk — Prompt 08)
are emitted as honest *deferred* placeholders with a ``deferred_source`` flag, never fabricated.

Gating: per ``require_prerequisite_gates`` the brief refuses to materialize sections unless the
Phase 07D meeting-prep prerequisite gates report ``meeting_prep_readiness.ready`` (Prompt 05). A
blocked run is a valid, honest outcome (status='blocked', zero sections) — not an error.

Guardrails: local-first, read-only against external systems; record refs are local stable
identifiers / existing hashes; no raw email/document/calendar content, signed/download URL,
token, secret, prompt, or model response is read or persisted; weak/model/sensitive/high-impact
relationships stay review-required and are never auto-promoted; outputs are advisory and emit no
final legal/contractual/claim/safety/financial determination.
"""

from __future__ import annotations

import json
from datetime import datetime, timedelta, timezone
from typing import Any, Optional

from hb_assistant.construction.relationships.contracts import (
    load_phase_07d_contract,
    load_phase_07d_seed,
)
from hb_assistant.construction.store.repositories import ConstructionStore
from hb_assistant.normalize.redaction import hash_value
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

_BRIEF_GUARDRAILS: dict[str, Any] = {
    "external_systems": "read_only",
    "writeback": "none",
    "writes": "local_sqlite_brief_runs_and_sections_only",
    "no_raw_content": True,
    "refs_are_local_ids_or_hashes": True,
    "advisory_only": True,
    "no_final_determinations": True,
    "prerequisite_gated": True,
    "auto_promotion": False,
}

# Confidence classes that mark a candidate as weak / model-proposed / stale for the
# confidence-and-stale warnings section (mirrors the substrate vocabulary).
_WEAK_CONFIDENCE_CLASSES = frozenset({"weak_heuristic", "model_proposed", "stale_or_unresolved"})

_SECTION_KINDS: tuple[str, ...] = (
    "meeting_context",
    "project_context",
    "open_items",
    "aging_items",
    "recent_activity",
    "risk_exposure_watchlist",
    "review_required_warnings",
    "confidence_and_stale_unknown_warnings",
)


def _parse_dt(value: Optional[str]) -> Optional[datetime]:
    """Parse an ISO timestamp into an aware UTC datetime; None on any failure."""
    if not value:
        return None
    text = value[:-1] + "+00:00" if value.endswith("Z") else value
    try:
        dt = datetime.fromisoformat(text)
    except ValueError:
        return None
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt


class MeetingPrepBriefBuilder:
    """Build per-project meeting-prep briefs from the live local substrate (V25)."""

    def __init__(self, store: Optional[ConstructionStore] = None) -> None:
        self._store = store or ConstructionStore()
        contract = load_phase_07d_contract("meeting_prep_brief_contract")
        self._contract_version = contract.get("version")
        policy = load_phase_07d_seed("meeting_prep_brief_policy")
        self._policy_version = policy.get("version")
        self._lookahead_default = int(policy.get("lookahead_days_default", 7))
        self._require_gates = bool(policy.get("require_prerequisite_gates", True))

    # -- prerequisite readiness ---------------------------------------------

    def _readiness(self, injected: Optional[dict[str, Any]]) -> dict[str, Any]:
        if injected is not None:
            return injected
        from hb_assistant.construction.data_quality import evaluate_data_quality_gates

        report = evaluate_data_quality_gates(
            db_path=getattr(self._store, "_db_path", None), persist=False
        )
        return report["phase_go_nogo"]["07D"]["meeting_prep_readiness"]

    # -- project discovery ---------------------------------------------------

    def _discover_projects(self, project_filter: Optional[str]) -> list[str]:
        if project_filter is not None:
            return [project_filter]
        keys: set[str] = set()
        for c in self._store.list_cross_source_relationship_candidates(limit=100000):
            pk = c.get("project_key")
            if pk:
                keys.add(str(pk))
        for r in self._store.list_cross_source_relationships(limit=100000):
            pk = r.get("project_key")
            if pk:
                keys.add(str(pk))
        return sorted(keys)

    # -- public API ----------------------------------------------------------

    def build(
        self,
        *,
        dry_run: bool = True,
        project_filter: Optional[str] = None,
        lookahead_days: Optional[int] = None,
        now_utc: Optional[datetime] = None,
        readiness: Optional[dict[str, Any]] = None,
    ) -> dict[str, Any]:
        """Materialize meeting-prep briefs. Dry-run plans counts and writes nothing; --apply
        upserts one brief run + its sections per project. Refuses (status='blocked', zero
        sections) when prerequisite gates are required and readiness is not met."""
        mode = "apply" if not dry_run else "dry_run"
        lookahead = int(lookahead_days) if lookahead_days is not None else self._lookahead_default
        now = now_utc or datetime.now(timezone.utc)
        readiness_block = self._readiness(readiness)
        ready = bool(readiness_block.get("ready"))
        gate_blocked = self._require_gates and not ready

        projects = self._discover_projects(project_filter)
        runs_planned = 0
        runs_written = 0
        sections_planned = 0
        sections_written = 0
        review_required_total = 0
        by_section_kind: dict[str, int] = {}

        for project_key in projects:
            runs_planned += 1
            brief_run_id = hash_value(f"meeting_prep|{project_key}|{lookahead}") or project_key
            if gate_blocked:
                if not dry_run:
                    self._store.upsert_meeting_prep_brief_run(
                        brief_run_id=brief_run_id,
                        project_key=project_key,
                        mode=mode,
                        lookahead_days=lookahead,
                        status="blocked",
                        sections_written=0,
                        review_required_count=0,
                    )
                    runs_written += 1
                continue

            sections = self._build_sections(project_key, lookahead, now)
            sections_planned += len(sections)
            run_review_count = sum(1 for s in sections if s["review_required"])
            for s in sections:
                by_section_kind[s["section_kind"]] = by_section_kind.get(s["section_kind"], 0) + 1
            review_required_total += run_review_count
            if not dry_run:
                first_event = next(
                    (s.get("_event_index_id") for s in sections if s.get("_event_index_id")),
                    None,
                )
                self._store.upsert_meeting_prep_brief_run(
                    brief_run_id=brief_run_id,
                    project_key=project_key,
                    mode=mode,
                    lookahead_days=lookahead,
                    status="materialized",
                    event_index_id=first_event,
                    sections_written=len(sections),
                    review_required_count=run_review_count,
                )
                runs_written += 1
                for s in sections:
                    section_id = (
                        hash_value(f"{brief_run_id}|{s['section_kind']}") or s["section_kind"]
                    )
                    self._store.upsert_meeting_prep_brief_section(
                        section_id=section_id,
                        brief_run_id=brief_run_id,
                        section_kind=s["section_kind"],
                        section_redacted=s["section_redacted"],
                        confidence_class=s["confidence_class"],
                        evidence_trail_id=s["evidence_trail_id"],
                        review_required=s["review_required"],
                        stale_unknown_flags_json=s["stale_unknown_flags_json"],
                    )
                    sections_written += 1

        return {
            "command": "construction-agent meeting-prep build",
            "mode": mode,
            "ok": True,
            "schema_version": LATEST_SCHEMA_VERSION,
            "contract_version": self._contract_version,
            "policy_version": self._policy_version,
            "lookahead_days": lookahead,
            "project_filter": project_filter,
            "prerequisite_readiness": {
                "ready": ready,
                "blocked_by": list(readiness_block.get("blocked_by", [])),
                "auto_readiness_allowed": bool(
                    readiness_block.get("auto_readiness_allowed", False)
                ),
            },
            "summary": {
                "projects": projects,
                "runs_planned": runs_planned,
                "runs_written": runs_written,
                "sections_planned": sections_planned,
                "sections_written": sections_written,
                "review_required": review_required_total,
                "blocked": gate_blocked,
                "by_section_kind": dict(sorted(by_section_kind.items())),
            },
            "guardrails": _BRIEF_GUARDRAILS,
        }

    # -- section builders ----------------------------------------------------

    def _build_sections(
        self, project_key: str, lookahead: int, now: datetime
    ) -> list[dict[str, Any]]:
        candidates = self._store.list_cross_source_relationship_candidates(
            project_key=project_key, limit=100000
        )
        relationships = self._store.list_cross_source_relationships(
            project_key=project_key, limit=100000
        )
        evidence_trails = self._store.list_source_evidence_trails(
            project_key=project_key, limit=100000
        )
        return [
            self._section_meeting_context(project_key, lookahead, now),
            self._section_project_context(project_key),
            self._section_open_items(candidates),
            self._section_deferred(
                "aging_items", "project_issue_history_items", "07D_prompt_07_09"
            ),
            self._section_recent_activity(relationships),
            self._section_deferred(
                "risk_exposure_watchlist", "project_risk_digest_items", "07D_prompt_08"
            ),
            self._section_review_required_warnings(candidates),
            self._section_confidence_stale_warnings(candidates, evidence_trails),
        ]

    @staticmethod
    def _section(
        kind: str,
        payload: dict[str, Any],
        confidence_class: str,
        *,
        evidence_trail_id: Optional[str] = None,
        review_required: bool = False,
        stale_unknown: Optional[dict[str, Any]] = None,
        event_index_id: Optional[str] = None,
    ) -> dict[str, Any]:
        return {
            "section_kind": kind,
            "section_redacted": json.dumps(payload, sort_keys=True),
            "confidence_class": confidence_class,
            "evidence_trail_id": evidence_trail_id,
            "review_required": review_required,
            "stale_unknown_flags_json": (
                json.dumps(stale_unknown, sort_keys=True) if stale_unknown else None
            ),
            "_event_index_id": event_index_id,
        }

    def _section_meeting_context(
        self, project_key: str, lookahead: int, now: datetime
    ) -> dict[str, Any]:
        horizon = now + timedelta(days=lookahead)
        matched_ids: list[str] = []
        unmatched = 0
        first_event: Optional[str] = None
        for ev in self._store.list_calendar_event_index(limit=100000):
            if ev.get("is_cancelled"):
                continue
            start = _parse_dt(ev.get("start_datetime_utc"))
            if start is None or not (now <= start <= horizon):
                continue
            first_event = first_event or ev.get("event_index_id")
            if ev.get("project_key") == project_key:
                matched_ids.append(str(ev.get("event_index_id")))
            else:
                unmatched += 1
        payload = {
            "lookahead_days": lookahead,
            "project_matched_meetings": len(matched_ids),
            "unmatched_upcoming_meetings": unmatched,
            "matched_event_refs": matched_ids[:25],
        }
        if matched_ids:
            return self._section(
                "meeting_context",
                payload,
                "strong_heuristic",
                event_index_id=first_event,
            )
        return self._section(
            "meeting_context",
            payload,
            "stale_or_unresolved",
            review_required=unmatched > 0,
            stale_unknown={
                "no_project_matched_meetings": True,
                "unmatched_upcoming_present": unmatched > 0,
            },
            event_index_id=first_event,
        )

    def _section_project_context(self, project_key: str) -> dict[str, Any]:
        identity = self._store.get_project_identity(project_key)
        if identity is None:
            return self._section(
                "project_context",
                {"project_key": project_key, "identity_resolved": False},
                "stale_or_unresolved",
                review_required=True,
                stale_unknown={"unknown_project_identity": True},
            )
        # Copy only safe normalized/enum fields — never project_name_raw.
        return self._section(
            "project_context",
            {
                "project_key": project_key,
                "identity_resolved": True,
                "project_name_normalized": identity.get("project_name_normalized"),
                "project_stage": identity.get("project_stage"),
                "is_active": bool(identity.get("is_active")),
                "match_status": identity.get("match_status"),
            },
            "deterministic",
        )

    def _section_open_items(self, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        by_type: dict[str, int] = {}
        by_class: dict[str, int] = {}
        deterministic = 0
        evidence_trail_id: Optional[str] = None
        for c in candidates:
            by_type[str(c.get("relationship_type"))] = (
                by_type.get(str(c.get("relationship_type")), 0) + 1
            )
            by_class[str(c.get("confidence_class"))] = (
                by_class.get(str(c.get("confidence_class")), 0) + 1
            )
            if c.get("deterministic"):
                deterministic += 1
            evidence_trail_id = evidence_trail_id or c.get("evidence_trail_id")
        payload = {
            "total_candidates": len(candidates),
            "by_relationship_type": dict(sorted(by_type.items())),
            "by_confidence_class": dict(sorted(by_class.items())),
        }
        if not candidates:
            cls = "stale_or_unresolved"
        elif deterministic > 0:
            cls = "deterministic"
        else:
            cls = "weak_heuristic"
        return self._section("open_items", payload, cls, evidence_trail_id=evidence_trail_id)

    def _section_recent_activity(self, relationships: list[dict[str, Any]]) -> dict[str, Any]:
        by_family: dict[str, int] = {}
        by_type: dict[str, int] = {}
        evidence_trail_id: Optional[str] = None
        for r in relationships:
            by_family[str(r.get("source_family"))] = (
                by_family.get(str(r.get("source_family")), 0) + 1
            )
            by_type[str(r.get("relationship_type"))] = (
                by_type.get(str(r.get("relationship_type")), 0) + 1
            )
            evidence_trail_id = evidence_trail_id or r.get("evidence_trail_id")
        payload = {
            "promoted_relationships": len(relationships),
            "by_source_family": dict(sorted(by_family.items())),
            "by_relationship_type": dict(sorted(by_type.items())),
        }
        cls = "deterministic" if relationships else "stale_or_unresolved"
        return self._section("recent_activity", payload, cls, evidence_trail_id=evidence_trail_id)

    def _section_review_required_warnings(self, candidates: list[dict[str, Any]]) -> dict[str, Any]:
        flagged = [c for c in candidates if c.get("review_required")]
        by_type: dict[str, int] = {}
        for c in flagged:
            by_type[str(c.get("relationship_type"))] = (
                by_type.get(str(c.get("relationship_type")), 0) + 1
            )
        payload = {
            "review_required_count": len(flagged),
            "by_relationship_type": dict(sorted(by_type.items())),
        }
        return self._section(
            "review_required_warnings",
            payload,
            "deterministic",
            review_required=len(flagged) > 0,
            stale_unknown={"items_pending_human_review": len(flagged)} if flagged else None,
        )

    def _section_confidence_stale_warnings(
        self, candidates: list[dict[str, Any]], evidence_trails: list[dict[str, Any]]
    ) -> dict[str, Any]:
        weak = sum(1 for c in candidates if c.get("confidence_class") in _WEAK_CONFIDENCE_CLASSES)
        model = sum(1 for c in candidates if c.get("model_proposed"))
        stale_trails = sum(1 for t in evidence_trails if t.get("stale_unknown_flags_json"))
        payload = {
            "weak_or_stale_candidates": weak,
            "model_proposed_candidates": model,
            "evidence_trails_with_stale_flags": stale_trails,
        }
        has_warnings = weak > 0 or model > 0 or stale_trails > 0
        return self._section(
            "confidence_and_stale_unknown_warnings",
            payload,
            "deterministic",
            review_required=False,
            stale_unknown=payload if has_warnings else None,
        )

    def _section_deferred(self, kind: str, source_table: str, pending: str) -> dict[str, Any]:
        return self._section(
            kind,
            {"available": False, "deferred_source": source_table, "pending_prompt": pending},
            "stale_or_unresolved",
            stale_unknown={"deferred_source": source_table, "pending_prompt": pending},
        )


def meeting_prep_brief_status(
    store: Optional[ConstructionStore] = None, *, project_filter: Optional[str] = None
) -> dict[str, Any]:
    """Read-only coverage report over the V25 meeting-prep brief tables."""
    store = store or ConstructionStore()
    runs = store.list_meeting_prep_brief_runs(project_key=project_filter, limit=100000)
    run_ids = {r["brief_run_id"] for r in runs}
    sections = [
        s
        for s in store.list_meeting_prep_brief_sections(limit=100000)
        if project_filter is None or s["brief_run_id"] in run_ids
    ]
    by_section_kind: dict[str, int] = {}
    review_required = 0
    for s in sections:
        by_section_kind[s["section_kind"]] = by_section_kind.get(s["section_kind"], 0) + 1
        if s["review_required"]:
            review_required += 1
    return {
        "command": "construction-agent meeting-prep status",
        "ok": True,
        "schema_version": LATEST_SCHEMA_VERSION,
        "project_filter": project_filter,
        "summary": {
            "runs": len(runs),
            "sections": len(sections),
            "blocked_runs": sum(1 for r in runs if r["status"] == "blocked"),
            "materialized_runs": sum(1 for r in runs if r["status"] == "materialized"),
            "review_required_sections": review_required,
            "by_section_kind": dict(sorted(by_section_kind.items())),
        },
        "guardrails": _BRIEF_GUARDRAILS,
    }
