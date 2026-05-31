# 29 — Phase 07B: No-Writeback / No-Secret / No-Raw-Body Proof

Phase 07B Prompt 12. Status: implemented at this record's commit.

## Problem

The `data-quality no-writeback-proof` prover (`construction/data_quality/safety.py`) covered
only Phase 07A — its 6 modules, 8 V20/V21 tables, and the 07A evidence dir. Every Phase 07B
prompt (06–11) recorded the same residual gap: the prover did not yet cover the V11/V14/V23
calendar/email tables, the 07B source modules, or the 07B evidence dir.

## Change

`build_data_quality_no_writeback_proof()` now additionally proves the Phase 07B surfaces, so
the single authoritative command proves both phases (07A keys + formula unchanged; six
namespaced `*_07b` keys added; all folded into `proof_passed`, fail-closed):

- **Module scan** (`_scan_module_set`) over the 10 07B modules
  (`construction/calendar/{event_indexer,project_matcher,policy,contracts}.py`,
  `construction/email/thread_summary.py`,
  `construction/relationships/meeting_email_candidates.py`,
  `construction/correspondence/correspondence_review.py`,
  `construction/calendar_email_obsidian.py`,
  `graph/{calendar_endpoint_guard,calendar_readonly_client}.py`) — mutation verbs (regex +
  AST), banned HTTP/Graph imports, and secrets.
- **Guard-column probe** (`_probe_table_guards`, driven by `_PHASE_07B_TABLE_GUARDS`): per
  table, each declared guard CHECK column must be present and store only its constant —
  `email_model_classifications` (`advisory_only=1`, `plaintext_body/raw_prompt/raw_response=0`),
  the V23 run/index/candidate tables (`raw_body/full_text/raw_prompt/raw_response/
  external_writeback=0` as declared). Metadata-only tables (`email_thread_summaries`,
  `calendar_event_attendees`) have no guard columns and are covered by the content + module
  scans.
- **Content leak scan** (`_scan_table_contents` + `_scan_text_for_raw_leakage`): every string
  cell of every 07B table is scanned for shared secret patterns **plus** URLs, raw email
  addresses, and iCal blocks — the substantive proof that no raw value actually reached the
  data (beyond the CHECK flags). Findings are `table.column: label` only — never the value.
- **Evidence scan** (`_scan_evidence_outputs`) over the 07B evidence dir.

### Supporting refactor
`construction/calendar/event_indexer.py` built its metadata dict via `fields.update({...})`.
The prover's AST scan flags bare `.update()` calls, so this was rewritten as explicit
`fields[...] = ...` assignments (identical behavior) to keep the 07B module scan clean.

No CLI change — `construction-agent data-quality no-writeback-proof` exits 0 on
`proof_passed`, 3 otherwise.

## Guardrail invariants
- Read-only and Graph-free; no Microsoft 365 mutation/writeback; no SQLite writes (schema +
  rows + files are only read).
- Fail-closed: any mutation verb, banned import, secret, raw body/prompt/response, URL, raw
  email, or iCal block flips `proof_passed=false`.
- The proof itself cannot leak — findings are pattern labels and `table.column` locations
  only, never the offending value (verified by the fail-closed tests).

## Evidence

`docs/evidence/construction-intelligence-phase-07b-calendar-email/12-no-writeback-no-secret-proof.md`.
Live, against the real store, all six `*_07b` checks pass with 0 findings over the populated
07B tables (108 events / 117 candidates / 1250 attendees / 40 classifications / 19 threads),
`proof_passed=true`, `no_raw_values_persisted=true`. **This closes the residual prover-coverage
gap carried since Prompt 06.**
