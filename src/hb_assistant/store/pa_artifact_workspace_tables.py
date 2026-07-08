"""V112 (part 1) — Structured Intelligence Artifact Workspace (N8C-23).

Durable, operator-reviewed staging → promotion of second-brain artifacts proposed by a connected client.
The connected client is a DRAFTING/REVIEW interface; the server is the RECORDS AUTHORITY. Nothing here is
canonical until an operator-approved, server-validated promotion runs. All tables ship EMPTY; rows are only
written by the explicit N8C-23 staging/promotion surfaces.

Trust model (N8C-23 amendments):
  * ``operator_approval_id`` is SERVER-MINTED from a recorded ``pa_artifact_review_decisions`` approval and
    bound to the bundle + approved proposals — never client-supplied.
  * ``pa_artifact_validation_receipts`` binds a ``validation_hash`` over the exact promotion plan; promotion
    apply recomputes and must match, else fails closed (revalidation required).
  * Idempotency is server-derived (sha256(bundle_id + validation_hash + operator_approval_id)).

Narrow and workspace-owned. NOT a raw/arbitrary write surface, NOT an executor, NOT an external-task creator.
Additive only; no existing table is touched.
"""

from __future__ import annotations


def _csv(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# The artifact types a proposal / canonical record can carry (Part 8). Neutral, organization-agnostic.
ARTIFACT_TYPE_VALUES: tuple[str, ...] = (
    "session_note",
    "decision",
    "preference",
    "open_loop",
    "workflow",
    "research_packet",
    "answer_draft",
    "architecture_note",
    "source_card_annotation",
    "review_item",
    "feedback",
    "action_stage",
    "quality_finding",
    "person_note",
    "company_note",
    "project_context",
    "knowledge_note",
)

# Proposal-bundle lifecycle.
BUNDLE_STATUS_VALUES: tuple[str, ...] = (
    "proposed",
    "in_review",
    "revision_requested",
    "approved_for_promotion",
    "partially_promoted",
    "promoted",
    "rejected",
    "archived",
)

# Per-proposal review lifecycle.
PROPOSAL_REVIEW_STATUS_VALUES: tuple[str, ...] = (
    "proposed",
    "approved",
    "rejected",
    "revision_requested",
    "revised",
    "merged",
    "split",
    "session_note_only",
    "promotion_blocked",
    "promoted",
    "archived",
)

# Operator review decisions (Part 7.5).
REVIEW_DECISION_VALUES: tuple[str, ...] = (
    "approve",
    "reject",
    "request_revision",
    "merge",
    "split",
    "session_note_only",
    "defer",
)

# Promotion-bundle lifecycle.
PROMOTION_STATUS_VALUES: tuple[str, ...] = (
    "ready",
    "validating",
    "blocked",
    "promoting",
    "promoted",
    "partial_failure",
    "failed",
    "rolled_back",
)

# Canonical record status.
CANONICAL_STATUS_VALUES: tuple[str, ...] = (
    "canonical",
    "superseded",
    "archived",
    "needs_materialization_repair",
    "needs_index_repair",
    "promotion_partial_failure",
)

# Durable cross-reference graph link kinds (Part 7.8).
LINK_TYPE_VALUES: tuple[str, ...] = (
    "supports",
    "supersedes",
    "related_to",
    "derived_from",
    "conflicts_with",
    "implements",
    "references",
    "belongs_to_session",
    "belongs_to_project",
    "belongs_to_person",
    "belongs_to_company",
)

# Promotion-receipt outcome.
RECEIPT_STATUS_VALUES: tuple[str, ...] = (
    "promoted",
    "partial_failure",
    "failed",
)

# Redaction posture recorded on a capture / proposal.
REDACTION_STATE_VALUES: tuple[str, ...] = (
    "redacted",
    "operator_confirmed_clean",
    "unredacted_pending",
)

# Repair queue kinds for partial failures.
REPAIR_TYPE_VALUES: tuple[str, ...] = (
    "materialization",
    "index",
)

REPAIR_STATUS_VALUES: tuple[str, ...] = (
    "open",
    "resolved",
)


V112_ARTIFACT_WORKSPACE_STATEMENTS: list[str] = [
    # --- session captures: provenance for the capture event (bounded; no raw transcript) ---
    f"""
    CREATE TABLE IF NOT EXISTS pa_session_captures (
      session_id TEXT PRIMARY KEY,
      source_client TEXT NOT NULL,
      source_client_session_ref TEXT,
      operator_id TEXT,
      capture_trigger TEXT NOT NULL,
      captured_at TEXT NOT NULL,
      session_title TEXT NOT NULL,
      session_summary TEXT NOT NULL,
      selected_excerpts_json TEXT,
      content_hash TEXT NOT NULL,
      redaction_state TEXT NOT NULL DEFAULT 'redacted' CHECK(redaction_state IN ({_csv(REDACTION_STATE_VALUES)})),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pa_session_captures_client "
    "ON pa_session_captures(source_client, captured_at)",
    # --- proposal bundles ---
    f"""
    CREATE TABLE IF NOT EXISTS pa_artifact_proposal_bundles (
      proposal_bundle_id TEXT PRIMARY KEY,
      session_id TEXT NOT NULL,
      source_client TEXT NOT NULL,
      status TEXT NOT NULL DEFAULT 'proposed' CHECK(status IN ({_csv(BUNDLE_STATUS_VALUES)})),
      candidate_count INTEGER NOT NULL DEFAULT 0,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      review_started_at TEXT,
      review_completed_at TEXT,
      promotion_receipt_id TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pa_proposal_bundles_session "
    "ON pa_artifact_proposal_bundles(session_id, status)",
    # --- artifact proposals ---
    f"""
    CREATE TABLE IF NOT EXISTS pa_artifact_proposals (
      proposal_id TEXT PRIMARY KEY,
      proposal_bundle_id TEXT NOT NULL,
      session_id TEXT NOT NULL,
      artifact_type TEXT NOT NULL CHECK(artifact_type IN ({_csv(ARTIFACT_TYPE_VALUES)})),
      proposed_title TEXT NOT NULL,
      proposed_summary TEXT,
      proposed_body_markdown TEXT,
      structured_payload_json TEXT,
      confidence REAL,
      rationale TEXT,
      supporting_excerpt TEXT,
      source_refs_json TEXT,
      candidate_links_json TEXT,
      affected_existing_artifacts_json TEXT,
      proposed_domain TEXT,
      proposed_vault_path TEXT,
      proposed_tags_json TEXT,
      proposed_backlinks_json TEXT,
      review_status TEXT NOT NULL DEFAULT 'proposed' CHECK(review_status IN ({_csv(PROPOSAL_REVIEW_STATUS_VALUES)})),
      review_notes TEXT,
      version INTEGER NOT NULL DEFAULT 1,
      supersedes_proposal_id TEXT,
      operator_approval_id TEXT,
      content_hash TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pa_proposals_bundle "
    "ON pa_artifact_proposals(proposal_bundle_id, review_status)",
    "CREATE INDEX IF NOT EXISTS idx_pa_proposals_type "
    "ON pa_artifact_proposals(artifact_type)",
    # --- proposal versions (preserve revision history; never overwrite v1) ---
    """
    CREATE TABLE IF NOT EXISTS pa_artifact_proposal_versions (
      proposal_version_id TEXT PRIMARY KEY,
      proposal_id TEXT NOT NULL,
      version INTEGER NOT NULL,
      body_markdown TEXT,
      structured_payload_json TEXT,
      operator_instruction TEXT,
      revision_summary TEXT,
      created_by_client TEXT,
      content_hash TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pa_proposal_versions_proposal "
    "ON pa_artifact_proposal_versions(proposal_id, version)",
    # --- operator review decisions (approval ids are minted here) ---
    f"""
    CREATE TABLE IF NOT EXISTS pa_artifact_review_decisions (
      review_decision_id TEXT PRIMARY KEY,
      proposal_id TEXT NOT NULL,
      proposal_bundle_id TEXT NOT NULL,
      operator_id TEXT,
      decision TEXT NOT NULL CHECK(decision IN ({_csv(REVIEW_DECISION_VALUES)})),
      review_notes TEXT,
      operator_approval_id TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pa_review_decisions_bundle "
    "ON pa_artifact_review_decisions(proposal_bundle_id, proposal_id)",
    "CREATE INDEX IF NOT EXISTS idx_pa_review_decisions_approval "
    "ON pa_artifact_review_decisions(operator_approval_id)",
    # --- promotion bundles ---
    f"""
    CREATE TABLE IF NOT EXISTS pa_artifact_promotion_bundles (
      promotion_bundle_id TEXT PRIMARY KEY,
      proposal_bundle_id TEXT NOT NULL,
      session_id TEXT NOT NULL,
      operator_approval_id TEXT,
      status TEXT NOT NULL DEFAULT 'ready' CHECK(status IN ({_csv(PROMOTION_STATUS_VALUES)})),
      validation_summary_json TEXT,
      validation_hash TEXT,
      idempotency_key TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      promoted_at TEXT,
      failed_at TEXT,
      failure_reason TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pa_promotion_bundles_proposal "
    "ON pa_artifact_promotion_bundles(proposal_bundle_id, status)",
    "CREATE INDEX IF NOT EXISTS idx_pa_promotion_bundles_idem "
    "ON pa_artifact_promotion_bundles(idempotency_key)",
    # --- validation receipts (bind the exact promotion plan) ---
    """
    CREATE TABLE IF NOT EXISTS pa_artifact_validation_receipts (
      validation_receipt_id TEXT PRIMARY KEY,
      promotion_bundle_id TEXT NOT NULL,
      proposal_bundle_id TEXT NOT NULL,
      operator_approval_id TEXT,
      validation_hash TEXT NOT NULL,
      validation_summary_json TEXT,
      approved_proposal_ids_json TEXT,
      proposed_canonical_ids_json TEXT,
      proposed_paths_json TEXT,
      passed INTEGER NOT NULL DEFAULT 0 CHECK(passed IN (0, 1)),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pa_validation_receipts_bundle "
    "ON pa_artifact_validation_receipts(promotion_bundle_id, validation_hash)",
    # --- canonical artifacts (the durable records authority) ---
    f"""
    CREATE TABLE IF NOT EXISTS pa_canonical_artifacts (
      canonical_id TEXT PRIMARY KEY,
      artifact_type TEXT NOT NULL CHECK(artifact_type IN ({_csv(ARTIFACT_TYPE_VALUES)})),
      title TEXT NOT NULL,
      summary TEXT,
      body_markdown TEXT,
      structured_payload_json TEXT,
      status TEXT NOT NULL DEFAULT 'canonical' CHECK(status IN ({_csv(CANONICAL_STATUS_VALUES)})),
      domain TEXT,
      source_client TEXT,
      source_session_id TEXT,
      source_proposal_id TEXT,
      promotion_receipt_id TEXT,
      version INTEGER NOT NULL DEFAULT 1,
      supersedes_canonical_id TEXT,
      superseded_by_canonical_id TEXT,
      vault_path TEXT,
      tags_json TEXT,
      backlinks_json TEXT,
      content_hash TEXT NOT NULL,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      promoted_at TEXT,
      archived_at TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pa_canonical_type "
    "ON pa_canonical_artifacts(artifact_type, status)",
    "CREATE INDEX IF NOT EXISTS idx_pa_canonical_session "
    "ON pa_canonical_artifacts(source_session_id)",
    "CREATE INDEX IF NOT EXISTS idx_pa_canonical_hash "
    "ON pa_canonical_artifacts(content_hash)",
    # --- artifact links (durable graph) ---
    f"""
    CREATE TABLE IF NOT EXISTS pa_artifact_links (
      link_id TEXT PRIMARY KEY,
      from_canonical_id TEXT NOT NULL,
      to_canonical_id TEXT NOT NULL,
      link_type TEXT NOT NULL CHECK(link_type IN ({_csv(LINK_TYPE_VALUES)})),
      confidence REAL,
      created_by TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pa_artifact_links_from "
    "ON pa_artifact_links(from_canonical_id, link_type)",
    "CREATE INDEX IF NOT EXISTS idx_pa_artifact_links_to "
    "ON pa_artifact_links(to_canonical_id)",
    # --- promotion receipts (durable audit) ---
    f"""
    CREATE TABLE IF NOT EXISTS pa_promotion_receipts (
      promotion_receipt_id TEXT PRIMARY KEY,
      promotion_bundle_id TEXT NOT NULL,
      session_id TEXT NOT NULL,
      operator_id TEXT,
      created_count INTEGER NOT NULL DEFAULT 0,
      updated_count INTEGER NOT NULL DEFAULT 0,
      superseded_count INTEGER NOT NULL DEFAULT 0,
      archived_count INTEGER NOT NULL DEFAULT 0,
      failed_count INTEGER NOT NULL DEFAULT 0,
      created_paths_json TEXT,
      validation_summary_json TEXT,
      validation_hash TEXT,
      receipt_vault_path TEXT,
      status TEXT NOT NULL DEFAULT 'promoted' CHECK(status IN ({_csv(RECEIPT_STATUS_VALUES)})),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pa_promotion_receipts_bundle "
    "ON pa_promotion_receipts(promotion_bundle_id)",
    # --- repair queue for partial failures ---
    f"""
    CREATE TABLE IF NOT EXISTS pa_artifact_repair_tasks (
      repair_task_id TEXT PRIMARY KEY,
      canonical_id TEXT NOT NULL,
      promotion_receipt_id TEXT,
      repair_type TEXT NOT NULL CHECK(repair_type IN ({_csv(REPAIR_TYPE_VALUES)})),
      status TEXT NOT NULL DEFAULT 'open' CHECK(status IN ({_csv(REPAIR_STATUS_VALUES)})),
      detail TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      resolved_at TEXT
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_pa_repair_tasks_status "
    "ON pa_artifact_repair_tasks(status, repair_type)",
]
