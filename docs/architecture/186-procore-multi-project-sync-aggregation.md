# 186 — Procore Multi-Project Sync Aggregation

**Objective:** make `hb-assistant procore sync run` work for all mapped pilots when
`--project` is omitted, instead of crashing with
`KeyError: "unknown hb_project_key: 'multi'"`.

## Problem

The all-project path resolved multiple pilot keys but then passed the synthetic
sentinel `"multi"` into project-level audit logic —
`EndpointAuditor.build_audit_run_receipt("multi")` →
`dry_run_audit_project("multi")` → `registry.get("multi") is None` →
`raise KeyError(...)` (`procore/auditor.py`). The same `"multi"` sentinel was also
used for watermark get/set and normalizer tagging in `apply()`.

## Design

`ProcoreSyncCoordinator.plan()` / `apply()` are now thin orchestrators over extracted
single-project bodies plus one aggregator (`procore/sync.py`):

- **`_resolve_validated_pilots(project_key, *, allow_pending)`** — `_resolve_pilot_projects`
  + `_assert_no_pending`, then validates every resolved key exists in the registry. An
  unknown explicit key raises `ProcoreMappingUnavailable` (a typed `ProcoreAPIError`,
  clear message) **before** any audit, so the auditor never receives an unmapped key.
- **`_plan_one(project_key, ...)` / `_apply_one(project_key, ...)`** — the original
  per-endpoint logic, but always over a single **real** key: the audit gate calls
  `build_audit_run_receipt(project_key)` (or the mock `audit_endpoints_for_pilots([key])`),
  and every watermark/normalizer call uses the real key. `_apply_one` substitutes the
  pilot's real `procore_project_id` into the request path
  (`path_template.format(company_id=..., project_id=procore_project_id)`), replacing the
  former hardcoded `"pilot"` placeholder, so each pilot's live GET targets its own
  Procore project. Each returns the un-redacted `SyncReceipt` object.
- **`_aggregate_receipts(receipts, *, mode, project_key, policy)`** — merges per-project
  receipts into one redacted aggregate: dict counts (`audit_verdict_summary`,
  `category_counts`, `sensitivity_counts`) summed; ints
  (`total_planned_requests`, `total_items_normalized`) summed; lists (`per_endpoint`,
  `redacted_errors`) concatenated; `audit_prerequisite_passed = all(...)`;
  `persisted_to_sqlite = any(...)`. Each per-project receipt is carried in the new
  `per_project` list field.

`"multi"` survives only as a top-level display label and is never passed into
project-level audit/watermark logic.

### `project_scope` field

The evidence redactor (`redact_for_evidence`) strips any dict key containing `"key"`,
so `pilot_project_key` is removed from emitted JSON. A new redaction-surviving
`project_scope` field on `SyncReceipt` carries the project identifier: `"multi"` (or the
lone key) on the aggregate, and the real key on each `per_project` entry.

### CLI

`cli/procore.py::sync_run` wraps the `run_sync(...)` call in
`try/except ProcoreAPIError`, emitting a clean JSON `{status: "failed", error: ...}`
envelope (exit 2) so an unknown `--project` (or pending/mapping error) fails closed
with a clear message instead of a traceback. The existing apply gate (`--confirm`,
`require_live_env`, `assert_live_mapping_strict`) is unchanged.

## Guardrails

Unchanged and preserved: read-only external; no Procore writeback; GET-only; dry-run
writes nothing (`persisted_to_sqlite=False`, zero items); apply writes local SQLite
only after the per-project audit gate; no secrets/bodies in artifacts (redaction
applied at aggregate level). Single-project behavior is unchanged (same fields plus a
one-element `per_project`).

## Tests

`tests/test_procore_sync_multi_project.py` — all-project dry-run succeeds with the real
seed (2+ pilots); the auditor is never called with `"multi"`; apply aggregates
per-project results; single-project unchanged; unknown key fails closed (raise + clean
CLI error); dry-run writes nothing; `--apply` requires `--confirm` and the live gate;
no source-system writeback. `tests/test_procore_sync.py` (single-project) passes
unchanged.
