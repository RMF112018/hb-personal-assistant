"""Phase 07D Prompt 03 — unified cross-source relationship substrate.

Normalizes the existing edge-shaped per-source relationship candidates — document→record
(V24), calendar↔email (V23), and email→project/procore/calendar (V11) — into the unified
``cross_source_relationship_candidates`` table (V25) plus a redacted ``source_evidence_trails``
row per edge. This is the substrate's first population pass.

Scope (Prompt 03): seed the substrate from the three existing relationship-candidate tables,
with deterministic-hash idempotent IDs and policy-driven review routing. Out of scope (Prompt
04): Procore-native edges, source-record-map / resolution-queue arms, cross-family project_key
alignment, dedup across families, and policy-gated promotion into ``cross_source_relationships``
(the build path here never promotes — every row is ``promotion_status='candidate'``).

Guardrails: local-first, read-only against external systems; record refs are local stable
identifiers or existing hashes (never re-derived from raw); no raw body/text/calendar payload,
signed/download URL, token, or secret is read or persisted; weak/model/sensitive/high-impact
relationships always route to review and are never auto-promoted. Outputs are advisory.
"""

from __future__ import annotations

import json
from collections.abc import Iterator
from typing import Any, Optional

from pydantic import BaseModel

from hb_assistant.construction.relationships.contracts import (
    load_phase_07d_contract,
    load_phase_07d_seed,
)
from hb_assistant.construction.store.repositories import ConstructionStore
from hb_assistant.normalize.redaction import hash_value
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION

_SUBSTRATE_GUARDRAILS: dict[str, Any] = {
    "external_systems": "read_only",
    "auto_promotion": False,
    "no_raw_content": True,
    "refs_are_local_ids_or_hashes": True,
    "weak_model_sensitive_always_review": True,
    "writes": "local_sqlite_candidates_and_evidence_only",
    "promotions_written": False,
}


class NormalizedEdge(BaseModel):
    """A source-agnostic relationship edge produced by a per-source adapter.

    All refs are local stable identifiers or existing hashes — never raw content.
    """

    source_family: str
    source_record_type: str
    source_record_ref: str
    target_family: str
    target_record_type: str
    target_record_ref: str
    relationship_type: str
    confidence_score: float
    project_key: Optional[str] = None
    deterministic: bool = False
    model_proposed: bool = False
    sensitive_high_impact: bool = False
    origin_table: str = ""
    origin_review_required: bool = False

    model_config = {"extra": "forbid"}


# --- per-source adapters -------------------------------------------------------


def _document_edges(store: ConstructionStore) -> Iterator[NormalizedEdge]:
    """document→record relationship candidates (V24)."""
    for r in store.list_document_relationship_candidates_full():
        src_ref = r.get("source_reference_json")
        project_key = src_ref.get("project_key") if isinstance(src_ref, dict) else None
        ctype = r.get("candidate_type") or ""
        yield NormalizedEdge(
            source_family="document",
            source_record_type="document",
            source_record_ref=str(r["document_card_id"]),
            target_family=str(r.get("target_system") or "procore"),
            target_record_type=str(r["target_record_type"]),
            target_record_ref=str(r["target_record_key_hash"]),
            relationship_type=str(r.get("relationship_type") or "document_record_reference"),
            confidence_score=float(r.get("confidence") or 0.0),
            project_key=project_key,
            deterministic=ctype == "deterministic",
            model_proposed=ctype == "model_proposed",
            origin_table="construction_document_relationship_candidates",
            origin_review_required=bool(r.get("review_required")),
        )


def _meeting_email_edges(store: ConstructionStore) -> Iterator[NormalizedEdge]:
    """calendar event → email thread candidates (V23)."""
    for r in store.list_meeting_email_relationship_candidates(limit=100000):
        yield NormalizedEdge(
            source_family="calendar",
            source_record_type="calendar_event",
            source_record_ref=str(r["event_index_id"]),
            target_family="email",
            target_record_type="email_thread",
            target_record_ref=str(r["thread_key_hash"]),
            relationship_type="meeting_email_correlation",
            confidence_score=float(r.get("confidence") or 0.0),
            project_key=r.get("project_key"),
            deterministic=bool(r.get("deterministic")),
            model_proposed=bool(r.get("model_proposed")),
            origin_table="meeting_email_relationship_candidates",
            origin_review_required=bool(r.get("review_required")),
        )


# Map an email candidate's target_source_system to a unified relationship family.
_EMAIL_TARGET_FAMILY = {
    "hb_construction": "project",
    "procore": "procore",
    "microsoft-graph": "calendar",
}


def _email_edges(store: ConstructionStore) -> Iterator[NormalizedEdge]:
    """email → project / procore / calendar candidates (V11)."""
    for r in store.list_email_relationship_candidates(limit=100000):
        ctype = str(r.get("candidate_type") or "unknown")
        target_family = _EMAIL_TARGET_FAMILY.get(
            str(r.get("target_source_system") or ""), "project"
        )
        # target_key may be null for some email candidate types; fall back to a stable
        # local hash so the edge still has a non-empty, non-raw target ref.
        target_ref = r.get("target_key") or hash_value(
            f"{r['candidate_id']}|{r.get('match_signal') or ctype}"
        )
        yield NormalizedEdge(
            source_family="email",
            source_record_type="email_message",
            source_record_ref=str(r["message_id"]),
            target_family=target_family,
            target_record_type=ctype,
            target_record_ref=str(target_ref),
            relationship_type=str(r.get("match_signal") or ctype),
            confidence_score=float(r.get("confidence") or 0.0),
            project_key=r.get("project_key"),
            origin_table="email_relationship_candidates",
            origin_review_required=bool(r.get("review_required")),
        )


_ADAPTERS = (_document_edges, _meeting_email_edges, _email_edges)


# --- classification + routing --------------------------------------------------


def _confidence_class(edge: NormalizedEdge) -> str:
    """Map a normalized edge to the unified V25 confidence_class enum."""
    if edge.model_proposed:
        return "model_proposed"
    if edge.deterministic:
        return "deterministic"
    if edge.confidence_score >= 0.8:
        return "strong_heuristic"
    return "weak_heuristic"


def _is_sensitive(edge: NormalizedEdge, categories: set[str]) -> bool:
    """True when the source flagged it sensitive or a sensitive category token appears in
    the edge's relationship/record types."""
    if edge.sensitive_high_impact:
        return True
    blob = (
        f"{edge.relationship_type} {edge.target_record_type} {edge.source_record_type}"
    ).lower()
    for cat in categories:
        if cat == "sensitive_high_impact":
            continue
        if cat in blob or cat.replace("_", " ") in blob:
            return True
    return False


def _review_required(
    confidence_class: str, sensitive: bool, origin_review_required: bool, always_classes: set[str]
) -> bool:
    if confidence_class in always_classes:
        return True
    if sensitive:
        return True
    return bool(origin_review_required)


class CrossSourceRelationshipSubstrateBuilder:
    """Normalize existing per-source relationship candidates into the unified V25 substrate.

    Counts are computed regardless of ``dry_run``; rows are written only when ``dry_run`` is
    False. Idempotent: ``candidate_id`` is a deterministic hash of the edge identity, matching
    the table's UNIQUE edge key, so re-runs upsert rather than duplicate.
    """

    def __init__(self, store: Optional[ConstructionStore] = None) -> None:
        self._store = store or ConstructionStore()
        # Validate the relationship contract (asserts the no-auto-promotion classes exist).
        contract = load_phase_07d_contract("cross_source_relationship_contract")
        blocked = set(contract.get("no_auto_promotion_for", []))
        assert {"weak_heuristic", "model_proposed", "sensitive_high_impact"} <= blocked, (
            "cross_source_relationship_contract must block weak/model/sensitive auto-promotion"
        )
        self._contract_version = contract.get("version")
        rules = load_phase_07d_seed("review_required_relationship_rules")
        always = rules.get("always_review_required", {})
        self._always_review_classes = set(always.get("confidence_classes", []))
        self._sensitive_categories = set(always.get("categories", []))

    def build(
        self,
        *,
        dry_run: bool = True,
        project_filter: Optional[str] = None,
        max_edges: int = 100000,
    ) -> dict[str, Any]:
        edges_considered = 0
        candidates_written = 0
        evidence_trails_written = 0
        review_required_count = 0
        dedup_collapsed = 0
        skipped_project_filter = 0
        by_source_family: dict[str, int] = {}
        by_confidence_class: dict[str, int] = {}
        by_target_family: dict[str, int] = {}
        seen: set[str] = set()

        for adapter in _ADAPTERS:
            for edge in adapter(self._store):
                if len(seen) >= max_edges:
                    break
                if project_filter is not None and edge.project_key != project_filter:
                    skipped_project_filter += 1
                    continue
                edges_considered += 1

                candidate_id = hash_value(
                    f"{edge.source_family}|{edge.source_record_ref}|{edge.target_family}"
                    f"|{edge.target_record_ref}|{edge.relationship_type}"
                )
                if candidate_id is None:  # pragma: no cover - refs are always non-empty
                    continue
                if candidate_id in seen:
                    dedup_collapsed += 1
                    continue
                seen.add(candidate_id)

                conf_class = _confidence_class(edge)
                sensitive = _is_sensitive(edge, self._sensitive_categories)
                review_required = _review_required(
                    conf_class, sensitive, edge.origin_review_required, self._always_review_classes
                )
                evidence_trail_id = hash_value(f"evt|{candidate_id}")

                by_source_family[edge.source_family] = by_source_family.get(edge.source_family, 0) + 1
                by_confidence_class[conf_class] = by_confidence_class.get(conf_class, 0) + 1
                by_target_family[edge.target_family] = by_target_family.get(edge.target_family, 0) + 1
                if review_required:
                    review_required_count += 1

                source_reference_json = json.dumps(
                    {
                        "source_family": edge.source_family,
                        "source_record_type": edge.source_record_type,
                        "source_record_ref": edge.source_record_ref,
                        "target_family": edge.target_family,
                        "target_record_type": edge.target_record_type,
                        "target_record_ref": edge.target_record_ref,
                        "relationship_type": edge.relationship_type,
                        "origin_table": edge.origin_table,
                        "confidence_class": conf_class,
                    },
                    sort_keys=True,
                )
                signals_json = json.dumps(
                    {
                        "confidence_score": round(edge.confidence_score, 4),
                        "deterministic": edge.deterministic,
                        "model_proposed": edge.model_proposed,
                        "sensitive_high_impact": sensitive,
                        "origin_review_required": edge.origin_review_required,
                    },
                    sort_keys=True,
                )
                stale_unknown_flags_json = json.dumps(
                    {"unknown_project_key": edge.project_key is None}, sort_keys=True
                )

                if not dry_run:
                    self._store.upsert_source_evidence_trail(
                        evidence_trail_id=evidence_trail_id,
                        evidence_kind="relationship_candidate",
                        source_refs_json=source_reference_json,
                        confidence_class=conf_class,
                        project_key=edge.project_key,
                        relationship_candidate_id=candidate_id,
                        review_required=review_required,
                        stale_unknown_flags_json=stale_unknown_flags_json,
                    )
                    self._store.upsert_cross_source_relationship_candidate(
                        candidate_id=candidate_id,
                        source_family=edge.source_family,
                        source_record_type=edge.source_record_type,
                        source_record_ref=edge.source_record_ref,
                        target_family=edge.target_family,
                        target_record_type=edge.target_record_type,
                        target_record_ref=edge.target_record_ref,
                        relationship_type=edge.relationship_type,
                        confidence_score=edge.confidence_score,
                        confidence_class=conf_class,
                        source_reference_json=source_reference_json,
                        project_key=edge.project_key,
                        deterministic=edge.deterministic,
                        model_proposed=edge.model_proposed,
                        sensitive_high_impact=sensitive,
                        review_required=review_required,
                        promotion_status="candidate",
                        signals_json=signals_json,
                        evidence_trail_id=evidence_trail_id,
                    )
                    evidence_trails_written += 1
                candidates_written += 1

        return {
            "command": "construction-agent relationships build",
            "mode": "apply" if not dry_run else "dry_run",
            "ok": True,
            "schema_version": LATEST_SCHEMA_VERSION,
            "contract_version": self._contract_version,
            "project_filter": project_filter,
            "summary": {
                "edges_considered": edges_considered,
                "candidates_written": candidates_written if not dry_run else 0,
                "candidates_planned": candidates_written,
                "evidence_trails_written": evidence_trails_written if not dry_run else 0,
                "review_required": review_required_count,
                "dedup_collapsed": dedup_collapsed,
                "skipped_project_filter": skipped_project_filter,
                "by_source_family": dict(sorted(by_source_family.items())),
                "by_confidence_class": dict(sorted(by_confidence_class.items())),
                "by_target_family": dict(sorted(by_target_family.items())),
            },
            "guardrails": _SUBSTRATE_GUARDRAILS,
        }


def relationship_substrate_status(
    store: Optional[ConstructionStore] = None, *, project_filter: Optional[str] = None
) -> dict[str, Any]:
    """Read-only coverage report over the V25 substrate tables."""
    store = store or ConstructionStore()
    candidates = store.list_cross_source_relationship_candidates(
        project_key=project_filter, limit=100000
    )
    by_source_family: dict[str, int] = {}
    by_confidence_class: dict[str, int] = {}
    review_required_count = 0
    for c in candidates:
        sf = str(c.get("source_family"))
        cc = str(c.get("confidence_class"))
        by_source_family[sf] = by_source_family.get(sf, 0) + 1
        by_confidence_class[cc] = by_confidence_class.get(cc, 0) + 1
        if c.get("review_required"):
            review_required_count += 1
    return {
        "command": "construction-agent relationships status",
        "ok": True,
        "schema_version": LATEST_SCHEMA_VERSION,
        "project_filter": project_filter,
        "summary": {
            "candidates": len(candidates),
            "evidence_trails": store.count_source_evidence_trails(),
            "promoted_relationships": store.count_cross_source_relationships(),
            "review_required": review_required_count,
            "by_source_family": dict(sorted(by_source_family.items())),
            "by_confidence_class": dict(sorted(by_confidence_class.items())),
        },
        "guardrails": _SUBSTRATE_GUARDRAILS,
    }
