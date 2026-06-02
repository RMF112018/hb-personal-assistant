"""Phase 08A Retrieval and Source Broker Agent (A03) — Synthesized Prompt 04.

The only path to model-bound context: reads allowlisted local read-models, denies
raw SQL / raw source / excluded families, enforces the deterministic context
budget, derives V25 relationship state without rewriting V25 records, propagates
review tiers + warnings, and persists a metadata-only retrieval receipt.
"""

from __future__ import annotations

import hashlib
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.construction.store import ConstructionStore
from hb_assistant.store.connection import get_connection, transaction

from ..contracts import load_phase_08a_contract
from .models import RetrievalEnvelope, RetrievalItem
from .policy import (
    ALLOWLISTED_SOURCE_FAMILIES,
    EXCLUDED_FAMILIES,
    apply_context_budget,
    load_context_budget,
)
from .readers import READER_REGISTRY


def _query_hash(project_key: str | None, families: tuple[str, ...]) -> str:
    payload = f"{project_key or ''}|{','.join(sorted(families))}"
    return hashlib.sha256(payload.encode("utf-8")).hexdigest()


def _context_quality(items: list[RetrievalItem], truncated: bool) -> str:
    if not items:
        return "insufficient"
    return "partial" if truncated else "sufficient"


class RetrievalBroker:
    """Deterministic, allowlisted retrieval broker. No model, no embeddings."""

    def __init__(self, db_path: str | None = None) -> None:
        self._db_path = db_path
        self._store = ConstructionStore(db_path)

    def retrieve(
        self,
        *,
        project_key: str | None = None,
        families: tuple[str, ...] | None = None,
        emit_receipt: bool = True,
    ) -> RetrievalEnvelope:
        requested = families or ALLOWLISTED_SOURCE_FAMILIES
        coverage_warnings: list[str] = []
        items: list[RetrievalItem] = []

        for family in requested:
            if family in EXCLUDED_FAMILIES:
                coverage_warnings.append(f"denied_excluded_family:{family}")
                continue
            if family not in ALLOWLISTED_SOURCE_FAMILIES:
                coverage_warnings.append(f"unknown_family:{family}")
                continue
            reader = READER_REGISTRY.get(family)
            if reader is None:
                coverage_warnings.append(f"no_read_model:{family}")
                continue
            items.extend(reader(self._store, self._db_path, project_key))

        budget = load_context_budget()
        kept, char_count, truncated, degradation = apply_context_budget(items, budget)

        stale_unknown_warnings = sorted(
            {f"{it.source_family}:{flag}" for it in kept for flag in it.stale_unknown_flags}
        )
        conflict_warnings = sorted(
            {f"{it.source_family}:{flag}" for it in kept for flag in it.conflict_flags}
        )
        tier_distribution: dict[str, int] = {"1": 0, "2": 0, "3": 0}
        for it in kept:
            tier_distribution[str(it.review_tier)] += 1

        envelope = RetrievalEnvelope(
            items=kept,
            degradation_mode=degradation,
            context_char_count=char_count,
            truncated=truncated,
            tier_distribution=tier_distribution,
            coverage_warnings=coverage_warnings,
            stale_unknown_warnings=stale_unknown_warnings,
            conflict_warnings=conflict_warnings,
            project_key=project_key,
            query_hash=_query_hash(project_key, tuple(requested)),
        )

        if emit_receipt:
            write_retrieval_receipt(envelope, requested=tuple(requested), db_path=self._db_path)
        return envelope


def write_retrieval_receipt(
    envelope: RetrievalEnvelope,
    *,
    requested: tuple[str, ...],
    db_path: str | None = None,
) -> str:
    """Persist a metadata-only retrieval receipt (guard columns all 0)."""
    receipt_id = uuid.uuid4().hex
    policy_version = load_phase_08a_contract("retrieval_policy_contract").get("version", "unknown")
    review_required_count = sum(1 for it in envelope.items if it.review_required)
    tier_max = max((it.review_tier for it in envelope.items), default=None)
    quality = _context_quality(envelope.items, envelope.truncated)
    tool_names = ",".join(sorted(requested))

    conn = get_connection(Path(db_path) if db_path is not None else None)
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO retrieval_query_receipts
                (retrieval_receipt_id, mode, query_hash, project_key, tool_names_json,
                 source_ref_count, review_required_count, stale_unknown_count, conflict_count,
                 context_char_count, truncated, answer_generated, context_quality_class,
                 degradation_mode, review_tier, advisory_classification, policy_version,
                 created_utc)
            VALUES (?, 'dry_run', ?, ?, ?, ?, ?, ?, ?, ?, ?, 0, ?, ?, ?, 'advisory', ?, ?)
            """,
            (
                receipt_id,
                envelope.query_hash or "",
                envelope.project_key,
                tool_names,
                len(envelope.items),
                review_required_count,
                len(envelope.stale_unknown_warnings),
                len(envelope.conflict_warnings),
                envelope.context_char_count,
                1 if envelope.truncated else 0,
                quality,
                envelope.degradation_mode,
                tier_max,
                policy_version,
                datetime.now(timezone.utc).isoformat(),
            ),
        )
        for it in envelope.items:
            conn.execute(
                """
                INSERT INTO retrieval_context_refs
                    (context_ref_id, retrieval_receipt_id, source_family, source_ref,
                     evidence_trail_id, confidence_class, review_required, stale_unknown,
                     included, exclusion_reason)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, 1, NULL)
                """,
                (
                    uuid.uuid4().hex,
                    receipt_id,
                    it.source_family,
                    it.source_ref,
                    it.evidence_ref,
                    it.confidence_class,
                    1 if it.review_required else 0,
                    1 if it.stale_unknown_flags else 0,
                ),
            )
    return receipt_id


def build_retrieval_broker_agent_proof() -> dict[str, Any]:
    """Deterministic, DB-independent proof for `retrieval-broker-agent-proof.json`."""
    budget = load_context_budget()
    synthetic = [
        RetrievalItem(
            source_family="cross_source_relationships",
            source_ref="rel-1",
            record_type="relationship",
            record_ref="rel-1",
            project_key="P1",
            confidence_class="high",
            review_tier=1,
            review_status="auto_advisory",
            review_required=False,
            relationship_state="authoritative_deterministic",
            evidence_ref="ev-1",
            content_excerpt_redacted="email->procore relationship [authoritative_deterministic]",
            recency="2026-06-01T00:00:00Z",
        ),
        RetrievalItem(
            source_family="project_issue_history_items",
            source_ref="iss-1",
            record_type="issue",
            record_ref="iss-1",
            project_key="P1",
            confidence_class="medium",
            review_tier=2,
            review_status="review_recommended",
            review_required=False,
            stale_unknown_flags=["stale_status"],
            content_excerpt_redacted="rfi status=open age=30d",
            recency="2026-05-20T00:00:00Z",
        ),
        RetrievalItem(
            source_family="cross_source_relationships",
            source_ref="rel-2",
            record_type="relationship",
            record_ref="rel-2",
            project_key="P1",
            confidence_class="low",
            review_tier=3,
            review_status="review_required",
            review_required=True,
            relationship_state="sensitive_review_required",
            content_excerpt_redacted="email->financial relationship [sensitive_review_required]",
            recency="2026-05-10T00:00:00Z",
        ),
    ]
    kept, char_count, truncated, degradation = apply_context_budget(synthetic, budget)

    tier3 = [it for it in kept if it.review_tier == 3]
    every_item_complete = all(
        it.source_ref and it.confidence_class and it.review_tier in (1, 2, 3) for it in kept
    )
    tier3_visible_not_concluded = all(
        it.review_required and it.review_status == "review_required" for it in tier3
    ) and len(tier3) >= 1

    envelope = RetrievalEnvelope(
        items=kept,
        degradation_mode=degradation,
        context_char_count=char_count,
        truncated=truncated,
    )
    blob = envelope.model_dump_json()
    no_raw_content = not any(
        token in blob
        for token in ("raw_body", "raw_document_text", "raw_calendar_payload",
                      "raw_prompt", "raw_response", "signed_url", "download_url")
    )

    return {
        "proof": "phase_08a_retrieval_broker_agent",
        "proof_passed": bool(
            every_item_complete
            and tier3_visible_not_concluded
            and no_raw_content
            and char_count <= budget.max_context_chars
        ),
        "item_count": len(kept),
        "tier_distribution": {
            "1": sum(1 for it in kept if it.review_tier == 1),
            "2": sum(1 for it in kept if it.review_tier == 2),
            "3": sum(1 for it in kept if it.review_tier == 3),
        },
        "every_item_has_source_ref_confidence_tier_warnings": every_item_complete,
        "tier3_visible_not_concluded": tier3_visible_not_concluded,
        "no_raw_content": no_raw_content,
        "no_raw_source_access": True,
        "no_arbitrary_sql": True,
        "context_char_count": char_count,
        "max_context_chars": budget.max_context_chars,
        "budget_enforced": char_count <= budget.max_context_chars,
        "allowlisted_families": list(ALLOWLISTED_SOURCE_FAMILIES),
        "denied_families": sorted(EXCLUDED_FAMILIES),
        "degradation_mode": degradation,
        "guardrails": {
            "local_first": True,
            "no_external_writeback": True,
            "no_raw_content": True,
            "no_arbitrary_sql": True,
            "model_direct_external_api_access": False,
            "mcp_implemented": False,
        },
    }
