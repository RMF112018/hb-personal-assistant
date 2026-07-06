"""V101 — Typed Qwen Enrichment Queue tables (N8C-5).

A bounded, typed job queue above the N8C-4 claim layer: the NAS queues enrichment jobs, a
MacBook/Qwen worker claims them under an atomic lease, executes a local model, and returns a
**receipt** (prompt/model/input/output digests). Claim-extraction results flow back through the
N8C-4 ``future_qwen`` seam as ``candidate``/``unreviewed`` claims — Qwen never owns source/card
identity, never writes a raw source/import table, and never rewrites the vault.

Narrow and neutral — NOT a graph schema, NOT a context-pack/compiler schema. Additive only; no
existing table is touched.

Invariants baked into the schema (DB is the backstop; the repository validates first with clean
errors):
  * a job is subject-backed — `CHECK(source_id IS NOT NULL OR note_rel_path IS NOT NULL)`;
  * `job_type` / `status` / `subject_type` and receipt `applied_status` are constrained to enums;
  * `priority` / `attempt_count` / `max_attempts` are non-negative;
  * bounded JSON/text columns are hard-capped by the repository before write (see enrichment_models).

Both tables ship EMPTY; nothing populates them on startup — only an explicit bounded command /
service / worker call writes rows. No backend lifespan / scheduler / watcher path enqueues or runs.
"""

from __future__ import annotations


def _csv(values: tuple[str, ...]) -> str:
    return ", ".join(f"'{v}'" for v in values)


# What kind of enrichment a job requests. Start minimal (three implemented types). "claim_validation"
# is RESERVED here — like N8C-4's "future_qwen" — so a later slice can implement it without a CHECK
# rebuild; the worker refuses it until implemented.
ENRICHMENT_JOB_TYPE_VALUES: tuple[str, ...] = (
    "source_summary",
    "claim_extraction",
    "backlink_suggestions",
    "claim_validation",
)

# What the job is anchored to.
ENRICHMENT_SUBJECT_TYPE_VALUES: tuple[str, ...] = (
    "source",
    "card",
    "note",
    "claim",
)

# Job lifecycle. queued -> claimed -> running -> {completed | failed | stale}; also skipped /
# cancelled as terminal operator states. A failed job with attempts left returns to queued.
ENRICHMENT_STATUS_VALUES: tuple[str, ...] = (
    "queued",
    "claimed",
    "running",
    "completed",
    "failed",
    "stale",
    "skipped",
    "cancelled",
)

# How a completed job's model result was applied. Nothing here auto-accepts a claim — ingested
# claims are candidate/unreviewed only (N8C-4).
ENRICHMENT_APPLIED_STATUS_VALUES: tuple[str, ...] = (
    "stored_only",
    "candidate_claims_ingested",
    "rejected",
    "stale_rejected",
    "failed",
)


V101_STATEMENTS: list[str] = [
    f"""
    CREATE TABLE IF NOT EXISTS assistant_enrichment_jobs (
      job_id TEXT PRIMARY KEY,
      job_type TEXT NOT NULL CHECK(job_type IN ({_csv(ENRICHMENT_JOB_TYPE_VALUES)})),
      subject_type TEXT NOT NULL DEFAULT 'source'
        CHECK(subject_type IN ({_csv(ENRICHMENT_SUBJECT_TYPE_VALUES)})),
      -- provenance (at least one of source_id / note_rel_path is required)
      source_id TEXT,
      note_rel_path TEXT,
      card_id TEXT,
      claim_id TEXT,
      status TEXT NOT NULL DEFAULT 'queued' CHECK(status IN ({_csv(ENRICHMENT_STATUS_VALUES)})),
      priority INTEGER NOT NULL DEFAULT 100 CHECK(priority >= 0),
      payload_json TEXT,
      -- digests snapshotted at enqueue; re-checked at completion to reject stale model output
      source_digest TEXT,
      card_digest TEXT,
      input_digest TEXT,
      -- atomic single-owner lease
      lease_owner TEXT,
      lease_expires_at TEXT,
      attempt_count INTEGER NOT NULL DEFAULT 0 CHECK(attempt_count >= 0),
      max_attempts INTEGER NOT NULL DEFAULT 3 CHECK(max_attempts >= 1),
      last_error TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      updated_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP,
      claimed_at TEXT,
      completed_at TEXT,
      CHECK(source_id IS NOT NULL OR note_rel_path IS NOT NULL)
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_enrichment_jobs_status "
    "ON assistant_enrichment_jobs(status, priority, created_at);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_enrichment_jobs_type "
    "ON assistant_enrichment_jobs(job_type);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_enrichment_jobs_source "
    "ON assistant_enrichment_jobs(source_id);",
    "CREATE INDEX IF NOT EXISTS idx_assistant_enrichment_jobs_lease "
    "ON assistant_enrichment_jobs(lease_owner, lease_expires_at);",
    f"""
    CREATE TABLE IF NOT EXISTS assistant_enrichment_receipts (
      receipt_id TEXT PRIMARY KEY,
      job_id TEXT NOT NULL,
      job_type TEXT NOT NULL CHECK(job_type IN ({_csv(ENRICHMENT_JOB_TYPE_VALUES)})),
      worker_id TEXT,
      runtime TEXT,
      model_name TEXT,
      prompt_version TEXT,
      input_digest TEXT,
      output_digest TEXT,
      source_digest_at_completion TEXT,
      card_digest_at_completion TEXT,
      result_json TEXT,
      applied_status TEXT NOT NULL DEFAULT 'stored_only'
        CHECK(applied_status IN ({_csv(ENRICHMENT_APPLIED_STATUS_VALUES)})),
      safety_flags_json TEXT,
      error_message TEXT,
      created_at TEXT NOT NULL DEFAULT CURRENT_TIMESTAMP
    );
    """,
    "CREATE INDEX IF NOT EXISTS idx_assistant_enrichment_receipts_job "
    "ON assistant_enrichment_receipts(job_id, created_at);",
]
