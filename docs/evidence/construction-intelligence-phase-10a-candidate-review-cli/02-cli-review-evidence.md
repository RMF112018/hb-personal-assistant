# Phase 10A Candidate Review CLI — Captured CLI / JSON / Proof Evidence

**Date:** 2026-06-08
**Scope:** Real captured output of the `second-brain review` verbs, the guardrail
SQL attestation, and the validation suite result.
**Method:** Seeded a throwaway local `--db` (two task + one commitment candidate,
all `pending`), ran the commands below, captured output verbatim, then deleted the
DB. Timestamps/UUIDs are real captured snapshot values; all output is redacted
(safe fields only).

---

## 1. CLI help (`second-brain review --help`)

```
 Usage: hb-assistant second-brain review [OPTIONS] COMMAND [ARGS]...

 Review surfaces: Phase 09 burden reduction/advisory promotion policy
 (policy-status/burden/queue/clusters) and Phase 10A candidate triage
 (list/show/summary; read-only).

 Commands:
   policy-status  Phase 09 review burden policy seed + contract (read-only).
   burden         Phase 09 review burden clusters + two-step gate (read-only).
   queue          Top operator-visible review clusters (read-only).
   clusters       Full clustered view (read-only).
   list           List Phase 10A task + commitment review candidates (read-only).
   show           Show a single Phase 10A candidate + its source refs (read-only).
   summary        Counts of Phase 10A candidates by review_status (read-only).
   accept         Accept Phase 10A candidate(s) (review_status -> accepted).
   ignore         Ignore Phase 10A candidate(s) (review_status -> suppressed).
   reject         Reject Phase 10A candidate(s) (review_status -> rejected).
   snooze         Snooze a candidate until an ISO-8601 timestamp (-> snoozed).
   edit           Edit title/assignee/waiting_state (records changes_json_redacted).
   export         Export the review queue (redacted/safe) to stdout or --out file.
```

(The Phase 09 `policy-status/burden/queue/clusters` verbs pre-date this package and
are unchanged; the Phase 10A verbs `list/show/summary/accept/ignore/reject/snooze/
edit/export` are this package's surface.)

## 2. `review summary --json`

```json
{
  "command": "second-brain review summary",
  "phase": "10A",
  "ok": true,
  "project_key": null,
  "task": { "total": 2, "pending": 2 },
  "commitment": { "total": 1, "pending": 1 },
  "combined": { "pending": 3, "total": 3 },
  "guardrails": {
    "read_only": true, "advisory_only": true, "local_only": true,
    "no_determination": true, "no_raw_no_writeback": true,
    "source_refs_immutable": true
  }
}
```

## 3. `review list --status pending --limit 25 --json` (one candidate shown; 2 more elided)

```json
{
  "command": "second-brain review list",
  "phase": "10A",
  "ok": true,
  "status": "pending",
  "count": 3,
  "candidates": [
    {
      "candidate_id": "t-1001",
      "stable_key": "HBR:task:t-1001",
      "title_redacted": "Submit foundation inspection report",
      "project_key": "HBR-2026",
      "assignee_class": "user",
      "due_at_utc": "2026-06-10T17:00:00-04:00",
      "urgency": "high",
      "waiting_state": "waiting_on_me",
      "safety_category": "normal",
      "confidence": 0.91,
      "reason_redacted": "Explicit ask in thread; inspector on site tomorrow.",
      "recommended_next_action": "review",
      "review_status": "pending",
      "snoozed_until_utc": null, "reviewed_utc": null, "reviewed_by": null,
      "review_note_redacted": null,
      "candidate_type": "task"
    }
  ],
  "guardrails": { "read_only": true, "advisory_only": true, "...": "..." }
}
```

## 4. `review show --candidate-id t-1001 --json` (source refs preserved, redacted)

```json
{
  "command": "second-brain review show",
  "phase": "10A",
  "ok": true,
  "candidate_type": "task",
  "candidate": { "candidate_id": "t-1001", "review_status": "pending", "...": "..." },
  "source_refs": [
    {
      "source_ref_id": "sr-t-1001",
      "candidate_type": "task",
      "candidate_id": "t-1001",
      "source_family": "email_message_raw_content",
      "source_ref_hash": "b1946ac9",
      "source_table": "email_message_raw_content",
      "source_primary_key_hash": "b1946ac9",
      "evidence_redacted": "Submit foundation inspection report",
      "created_utc": "2026-06-08T19:03:52.244240+00:00"
    }
  ],
  "guardrails": { "read_only": true, "source_refs_immutable": true, "...": "..." }
}
```

## 5. Actions — accept / ignore / reject (`--json`)

`review accept --candidate-id t-1001 --reason "verified; report ready"`:
```json
{
  "command": "second-brain review accept", "phase": "10A", "ok": true,
  "candidate_id": "t-1001", "candidate_type": "task", "action": "accept",
  "prior_review_status": "pending", "new_review_status": "accepted",
  "reviewed_by": "operator", "reviewed_utc": "2026-06-08T19:04:22.037857+00:00",
  "review_note_redacted": "verified; report ready", "snoozed_until_utc": null,
  "review_event_id": "351ba373-ee02-4af4-9668-97c61b5d6023",
  "guardrails": {
    "local_db_update_only": true, "advisory_only": true, "review_event_written": true,
    "source_refs_immutable": true, "no_external_writeback": true, "no_email_send": true,
    "no_calendar_mutation": true, "no_graph_or_procore_writeback": true
  }
}
```

`review ignore --candidate-id c-2002 --reason "not actionable"` (note `ignore` → stored `suppressed`):
```json
{
  "command": "second-brain review ignore", "phase": "10A", "ok": true,
  "candidate_id": "c-2002", "candidate_type": "commitment", "action": "ignore",
  "prior_review_status": "pending", "new_review_status": "suppressed",
  "reviewed_by": "operator", "review_note_redacted": "not actionable",
  "review_event_id": "b8097443-c15e-489e-9df8-2804cfb862e9",
  "guardrails": { "local_db_update_only": true, "no_external_writeback": true, "...": "..." }
}
```

`review reject --candidate-id t-1003 --reason "incorrect extraction"`:
```json
{
  "command": "second-brain review reject", "phase": "10A", "ok": true,
  "candidate_id": "t-1003", "candidate_type": "task", "action": "reject",
  "prior_review_status": "pending", "new_review_status": "rejected",
  "reviewed_by": "operator", "review_note_redacted": "incorrect extraction",
  "review_event_id": "d81fa410-6491-4e2c-a42c-64221a7e6f07",
  "guardrails": { "local_db_update_only": true, "no_external_writeback": true, "...": "..." }
}
```

Final review_status distribution after the three actions:
`t-1001 = accepted`, `t-1003 = rejected`, `c-2002 = suppressed`.

## 6. Guardrail SQL / proof output

`SELECT COALESCE(SUM(<13 _P10_GUARDS columns>),0)` over each candidate-review table
**after** the accept/ignore/reject actions:

```
task_candidates              rows=2  guard_sum=0
commitment_candidates        rows=1  guard_sum=0
candidate_review_events      rows=3  guard_sum=0
candidate_source_refs        rows=1  guard_sum=0
guard_column_count=13
```

All 13 raw/writeback guard columns remain 0 — review actions persisted status +
lifecycle columns + audit rows only, never a raw/writeback flag. The named no-raw /
no-writeback proofs are `test_candidate_review_and_cli_import_no_external_write_surface`
and `test_no_raw_persisted_in_candidate_review_tables` (see `01-no-raw-no-writeback-proof.md`).

## 7. Test output (package validation command)

```
pytest tests/test_phase_08d_no_raw_access.py tests/test_phase_08d_no_writeback.py \
       tests/test_second_brain_no_writeback_proof.py \
       tests/test_phase_10a_candidate_review.py tests/test_phase_10a_candidate_review_cli.py
=> 66 passed
```

## 8. Guardrails reaffirmed

Review actions are local SQLite updates only. No email send, calendar mutation,
Graph writeback, Procore writeback, or external/cloud LLM dependency. No raw email
body / document text / calendar / Procore payload / prompt / response / signed URL /
download URL / token / secret persisted or emitted. Source refs immutable.
