# N8C-8 — V104 schema & record contract

## Migration
- New head: **`LATEST_SCHEMA_VERSION = 104`**, migration `v104_assistant_decision_memory` (wiring
  mirrors V103: `_v104_statements()` + a `WHERE version = 104` guarded insert; head bump 103→104).
- Additive + idempotent: applying twice leaves exactly one v104 row
  (`test_decision_memory_v104_migration.py`). Prior V100–V103 rows and tables survive
  (`test_prior_v100_v101_v102_v103_rows_remain`, `test_schema_version_head_consistency.py::
  test_prior_assistant_tables_survive_v104`).

## Four N8C-8-owned tables (`store/assistant_decision_memory_tables.py`, `V104_STATEMENTS`)
All TEXT PKs, `created_at`/`updated_at DEFAULT CURRENT_TIMESTAMP`, `*_json` bounded, **no FKs**; enum
tuples in the module are the single source of truth for the DB `CHECK` constraints and the Python layer.
Each of the three record tables carries a shared provenance block and a **table CHECK requiring ≥1
provenance anchor** (`source_id / note_rel_path / claim_id / memory_node_id / memory_mention_id /
compilation_id / pack_id / pack_item_id / receipt_id`) — no floating record can exist
(`test_decision_memory_v104_migration.py::test_provenance_check_enforced`).

1. **`assistant_decision_records`** — `decision_id` PK, `identity_key`, `decision_type` CHECK
   (decision / decision_candidate / policy / architecture_decision / operator_preference_decision /
   unknown), `decision_text`, `normalized_subject`, `normalized_decision`, `domain`, `status` CHECK
   (candidate / accepted / rejected / superseded / stale; **default candidate**), `review_state` CHECK
   (unreviewed / needs_review / operator_accepted / operator_rejected / not_required; **default
   unreviewed**), `confidence` 0..1, provenance block, `observed_at/decided_at/valid_from/valid_until`.
2. **`assistant_preference_records`** — `preference_id` PK, `identity_key`, `preference_type` CHECK
   (user_ / system_ / domain_ / workflow_ / tool_ / communication_preference / unknown),
   `preference_text`, `normalized_subject`, `normalized_preference`, `domain`, `strength` CHECK
   (weak / medium / strong / explicit), `status`+`review_state` (same enums/defaults), provenance block.
3. **`assistant_open_loop_records`** — `open_loop_id` PK, `identity_key`, `open_loop_type` CHECK
   (commitment / task_candidate / question / risk_followup / decision_needed / waiting_for / unknown),
   `open_loop_text`, `normalized_subject`, `normalized_action`, `domain`, `status` CHECK (candidate /
   open / closed / rejected / stale / superseded; **default candidate**), `review_state`, `priority`
   CHECK (low / medium / high / unknown), provenance block, `observed_at/due_at/stale_after/owner_hint`.
4. **`assistant_decision_memory_events`** — append-only lifecycle for ALL three kinds: `event_id` PK,
   `record_kind` CHECK (decision / preference / open_loop), `record_id`, `event_type` CHECK (created /
   updated / marked_stale / closed / reopened / superseded / rejected / failed), `from_status`,
   `to_status`, `detail`. NOT an N8D job/execution event table.

## Reserved (deferred — enum values only, no workflow in N8C-8)
`accepted`/`rejected` (decision/preference), `open`/`closed`/`rejected` (open-loop), `operator_*`
(review_state), and the `closed`/`reopened` events are reserved for a future operator-disposition slice.
N8C-8 implements only **creation**, **explicit stale**, and **lineage-scoped supersede**.

## Deterministic identity (idempotency + lineage-scoped supersede)
- `anchor_key` = first available STABLE provenance anchor, precedence
  `source_id → claim_id → pack_item_id → compilation_id → receipt_id → note_rel_path` (robust when
  `source_id` is absent — `test_anchor_key_falls_back_when_source_absent`).
- `identity_key = sha256(kind | normalized_subject | normalized_action | extra | anchor_key)[:24]`,
  where `extra` folds a secondary discriminator (preference `domain` / open-loop `type`) INTO the
  identity — so a genuinely different record is never a supersede target.
- `record_id = sha256(identity_key | evidence_digest | EXTRACTOR_VERSION)[:24]`
  (`evidence_digest = sha256(evidence_excerpt | source_digest | card_digest)`). Same identity + same
  evidence → same id (idempotent); a changed evidence digest → a new id.
- **Supersede is lineage-scoped:** a genuinely new id supersedes ONLY prior `candidate` rows with the
  SAME `identity_key` (same subject+action+lineage). Independent corroborating sources get a different
  `anchor_key` → different `identity_key` → they **coexist** and never auto-obsolete each other
  (`test_decision_memory_repository.py::{test_changed_evidence_supersedes_same_lineage,
  test_independent_sources_coexist}`). `EXTRACTOR_VERSION = "decision-memory-v1"`.
