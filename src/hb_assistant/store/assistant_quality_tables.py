"""V111 — Maintenance, Freshness, Quality Loops, and Workflow Evaluation (N8C-20).

Deterministic, read-only EVALUATION over existing N8C records. A quality run inspects one target (a workflow
route, feedback record, action stage, answer draft, research packet, review item, context pack, or
intelligence projection) and emits **advisory** quality findings — freshness / citation coverage /
review-state consistency / source-ref validity / policy compliance / duplication / boundedness. It NEVER
rebuilds an artifact, repairs anything, executes anything, stages an action, mutates any upstream record,
contacts an external system, reads a source file, or calls an LLM.

  * ``assistant_quality_runs`` — run headers (target_kind, target_id, target_digest, run-record lifecycle
    status draft/evaluated/superseded, evaluator version, digests, severity counts, the fixed no-execution /
    evaluate-only / advisory-review-loop policy). ``evaluated`` is a RUN-RECORD lifecycle status ONLY — it
    never means an action ran, a record was repaired, or a review was accepted/rejected/applied. There is
    deliberately NO accept / reject / defer / dispose / close / reopen / repair / execute field anywhere.
  * ``assistant_quality_findings`` — one advisory finding each (finding_type + severity info/warn/risk +
    bounded detail/advice + preserved provenance). Every finding is pinned to no_execution / evaluate_only /
    advisory_review_loop / requires_operator_review=1 by CHECK. A finding may RECOMMEND operator review; it
    never sets, implies, or mutates a review disposition.
  * ``assistant_quality_targets`` — the evaluated target(s) with preserved provenance anchors + copied
    review/effective state (bounded metadata, never written back).
  * ``assistant_quality_receipts`` — derivation receipts (evaluator version + digests + counts).
  * ``assistant_quality_events`` — append-only run lifecycle (created / evaluated / finding_added /
    superseded). NOT a repair/execution/disposition ledger.

Narrow and quality-owned. NOT a repairer, NOT an executor, NOT a review-disposition writer, NOT a stager, NOT
N8D. Additive only; no existing table is touched. All five tables ship EMPTY; only an explicit bounded
``quality build --apply`` command / evaluator call writes rows.
"""

from __future__ import annotations

from hb_assistant.store.assistant_review_tables import (
    EFFECTIVE_STATE_VALUES,
    REVIEW_STATE_VALUES,
)


def _csv(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# What a quality run may evaluate. Each names an EXISTING N8C artifact family read via its own read-only
# repository; the run never writes back to it.
QUALITY_TARGET_KIND_VALUES: tuple[str, ...] = (
    "action_stage",
    "action_stage_item",
    "feedback",
    "feedback_recommendation",
    "answer_draft",
    "research_packet",
    "workflow",
    "review_item",
    "context_pack",
    "intelligence_projection",
    "unknown",
)

# Run-RECORD lifecycle ONLY (never execution/repair/disposition). ``evaluated`` = the run finished computing
# its advisory findings; ``superseded`` = a newer run of the same lineage replaced it.
QUALITY_RUN_STATUS_VALUES: tuple[str, ...] = (
    "draft",
    "evaluated",
    "superseded",
)

# The advisory quality signals a run may emit. Every value is an OBSERVATION for operator review — never an
# applied change, a repair, or a review disposition.
QUALITY_FINDING_TYPE_VALUES: tuple[str, ...] = (
    "missing_citation",
    "missing_source_ref",
    "stale_source_ref",
    "stale_review_state",
    "candidate_without_label",
    "trusted_without_accepted_review",
    "excluded_used_as_support",
    "duplicate_stage_candidate",
    "duplicate_feedback",
    "orphan_feedback_target",
    "orphan_stage_citation",
    "unbounded_payload_risk",
    "raw_payload_leak_risk",
    "policy_mismatch",
    "external_action_risk",
    "finality_language_risk",
    "execution_language_risk",
    "workflow_section_empty",
    "insufficient_context",
    "unknown_target",
    "unknown",
)

# Advisory severity. Ordering info < warn < risk is by convention; no severity implies an action.
QUALITY_SEVERITY_VALUES: tuple[str, ...] = (
    "info",
    "warn",
    "risk",
)

# Append-only run lifecycle events. NOT repair/execution/disposition events.
QUALITY_EVENT_TYPE_VALUES: tuple[str, ...] = (
    "created",
    "evaluated",
    "finding_added",
    "superseded",
)

_REVIEW_STATES = REVIEW_STATE_VALUES
_EFFECTIVE_STATES = EFFECTIVE_STATE_VALUES

# Fixed, non-overridable quality policy (mirrored in the models + asserted by tests). Pinned by CHECK so a
# quality row can never claim execution, a repair, a review-disposition write, or source mutation.
_QUALITY_POLICY = """
      action_policy TEXT NOT NULL DEFAULT 'no_execution' CHECK(action_policy = 'no_execution'),
      execution_policy TEXT NOT NULL DEFAULT 'evaluate_only' CHECK(execution_policy = 'evaluate_only'),
      review_policy TEXT NOT NULL DEFAULT 'advisory_review_loop' CHECK(review_policy = 'advisory_review_loop'),
      source_policy TEXT NOT NULL DEFAULT 'preserve_source_truth' CHECK(source_policy = 'preserve_source_truth'),
      citation_policy TEXT NOT NULL DEFAULT 'preserve_citations' CHECK(citation_policy = 'preserve_citations'),
      requires_operator_review INTEGER NOT NULL DEFAULT 1 CHECK(requires_operator_review = 1),
"""

# Optional typed upstream anchors carried on a finding / target for preserved provenance (bounded ids only —
# never a body/payload).
_PROVENANCE_COLUMNS = """
      workflow_id TEXT,
      stage_id TEXT,
      stage_item_id TEXT,
      feedback_id TEXT,
      recommendation_id TEXT,
      draft_id TEXT,
      draft_section_id TEXT,
      packet_id TEXT,
      projection_id TEXT,
      projection_item_id TEXT,
      context_pack_id TEXT,
      review_item_id TEXT,
      claim_id TEXT,
      citation_id TEXT,
      decision_id TEXT,
      preference_id TEXT,
      open_loop_id TEXT,
      source_id TEXT,
      source_ref TEXT,
      source_root_key TEXT,
      rel_path TEXT,
      note_rel_path TEXT,
"""


V111_STATEMENTS: list[str] = [
    f"""
    CREATE TABLE IF NOT EXISTS assistant_quality_runs (
      quality_run_id TEXT PRIMARY KEY,
      target_kind TEXT NOT NULL CHECK(target_kind IN ({_csv(QUALITY_TARGET_KIND_VALUES)})),
      target_id TEXT NOT NULL,
      target_digest TEXT,
      title TEXT,
      status TEXT NOT NULL DEFAULT 'evaluated' CHECK(status IN ({_csv(QUALITY_RUN_STATUS_VALUES)})),
{_QUALITY_POLICY}      evaluator_version TEXT,
      created_by TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      request_digest TEXT,
      input_digest TEXT,
      output_digest TEXT,
      policy_json TEXT,
      finding_count INTEGER NOT NULL DEFAULT 0,
      risk_count INTEGER NOT NULL DEFAULT 0,
      warn_count INTEGER NOT NULL DEFAULT 0,
      info_count INTEGER NOT NULL DEFAULT 0,
      truncated INTEGER NOT NULL DEFAULT 0 CHECK(truncated IN (0, 1)),
      metadata_json TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_quality_runs_target "
    "ON assistant_quality_runs(target_kind, target_id, status);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_quality_runs_lineage "
    "ON assistant_quality_runs(target_kind, target_id, policy_json, status);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_quality_runs_request "
    "ON assistant_quality_runs(request_digest);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_quality_findings (
      finding_id TEXT PRIMARY KEY,
      quality_run_id TEXT NOT NULL,
      finding_order INTEGER NOT NULL DEFAULT 0,
      finding_type TEXT NOT NULL CHECK(finding_type IN ({_csv(QUALITY_FINDING_TYPE_VALUES)})),
      severity TEXT NOT NULL DEFAULT 'warn' CHECK(severity IN ({_csv(QUALITY_SEVERITY_VALUES)})),
      target_kind TEXT,
      target_id TEXT,
      detail TEXT,
      advice TEXT,
      action_policy TEXT NOT NULL DEFAULT 'no_execution' CHECK(action_policy = 'no_execution'),
      execution_policy TEXT NOT NULL DEFAULT 'evaluate_only' CHECK(execution_policy = 'evaluate_only'),
      review_policy TEXT NOT NULL DEFAULT 'advisory_review_loop'
        CHECK(review_policy = 'advisory_review_loop'),
      requires_operator_review INTEGER NOT NULL DEFAULT 1 CHECK(requires_operator_review = 1),
{_PROVENANCE_COLUMNS}      review_state TEXT CHECK(review_state IS NULL OR review_state IN ({_csv(_REVIEW_STATES)})),
      effective_state TEXT
        CHECK(effective_state IS NULL OR effective_state IN ({_csv(_EFFECTIVE_STATES)})),
      finding_digest TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_quality_findings_run "
    "ON assistant_quality_findings(quality_run_id, finding_order);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_quality_findings_type "
    "ON assistant_quality_findings(finding_type, severity);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_quality_targets (
      quality_target_id TEXT PRIMARY KEY,
      quality_run_id TEXT NOT NULL,
      target_order INTEGER NOT NULL DEFAULT 0,
      target_kind TEXT NOT NULL CHECK(target_kind IN ({_csv(QUALITY_TARGET_KIND_VALUES)})),
      target_id TEXT NOT NULL,
      target_label TEXT,
{_PROVENANCE_COLUMNS}      target_digest TEXT,
      review_state TEXT CHECK(review_state IS NULL OR review_state IN ({_csv(_REVIEW_STATES)})),
      effective_state TEXT
        CHECK(effective_state IS NULL OR effective_state IN ({_csv(_EFFECTIVE_STATES)})),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_quality_targets_run "
    "ON assistant_quality_targets(quality_run_id, target_order);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_quality_targets_target "
    "ON assistant_quality_targets(target_kind, target_id);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_quality_receipts (
      quality_receipt_id TEXT PRIMARY KEY,
      quality_run_id TEXT NOT NULL,
      evaluator_version TEXT,
      request_digest TEXT,
      input_digest TEXT,
      output_digest TEXT,
      finding_count INTEGER NOT NULL DEFAULT 0,
      risk_count INTEGER NOT NULL DEFAULT 0,
      warn_count INTEGER NOT NULL DEFAULT 0,
      info_count INTEGER NOT NULL DEFAULT 0,
      dropped_count INTEGER NOT NULL DEFAULT 0,
      truncated INTEGER NOT NULL DEFAULT 0 CHECK(truncated IN (0, 1)),
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      metadata_json TEXT
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_quality_receipts_run "
    "ON assistant_quality_receipts(quality_run_id, created_at);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_quality_events (
      event_id TEXT PRIMARY KEY,
      quality_run_id TEXT NOT NULL,
      event_type TEXT NOT NULL CHECK(event_type IN ({_csv(QUALITY_EVENT_TYPE_VALUES)})),
      from_status TEXT,
      to_status TEXT,
      detail TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_quality_events_run "
    "ON assistant_quality_events(quality_run_id, created_at);",
]
