# Phase 02 — Prompt 07: Procore Project Mapping Correction and Audit Readiness

## Summary

Corrected the Procore project mapping seed and installed a model-level guard that prevents the recurrence of the underlying defect.

- `resources/config/procore_projects.seed.yaml` was carrying `procore_project_id: "23-435-01"` for Tropical. `23-435-01` is an HB internal project-number (pattern `YY-NNN-VV`), **not** a Procore API project ID. Any live audit using this mapping would have queried the wrong system. Tropical's canonical Procore ID `2525840` was already known from the construction-side registry; the Procore-side seed had simply never been synchronised.
- Expanded the seed from 2 rows to 6 to mirror the canonical project-key set in `resources/config/sharepoint_onedrive_sources.seed.yaml` (tropical, pga-modern-garage, alton-hilltop-pbg, the-wellington, hilltop, hilltop-gardens). Four are now `pilot` with verified numeric IDs; two remain `pending` (hilltop legacy, hilltop-gardens canonical) — no Procore IDs were invented.
- Added a `@model_validator(mode="after")` to `ProcoreProjectMapping` that enforces three rules at construction time:
  1. `status == "pending"` → `procore_project_id` must be empty.
  2. `status` in `{pilot, deprecated}` → `procore_project_id` must be non-empty.
  3. Non-pending `procore_project_id` must **not** match `^\d{2}-\d{3}-\d{2}$` (the HB-number shape) and **must** match `^\d+$` (numeric Procore ID).
- Error messages include the offending value and the offended pattern verbatim so operators see the failure mode at a glance.
- Updated synthetic harness fixtures (`fixtures/procore.py`) whose pilot-only entries used non-numeric IDs (`A-100`, `B-200`) — these would otherwise fail the new validator and break unrelated harness suites.
- Per user direction, enforcement lives **only** at the model layer. The loader constructs the model, so loader rejection is automatic; the auditor reads from the validated registry, so auditor inputs are guaranteed clean. No auditor-layer or loader-layer guard was added.

## Repo HEAD

- Before: `9045def4875c0c333c408b26454770b5d33304e8`
- After: `18d76f87b25f4e40ba932ba093ae81cdda900ae5`

## Files changed

```
 resources/config/procore_projects.seed.yaml       |  43 ++++++--
 src/hb_assistant/construction/fixtures/procore.py |   4 +-
 src/hb_assistant/procore/models.py                |  40 +++++++
 tests/test_procore_endpoint_audit.py              | 122 +++++++++++++++++++---
 4 files changed, 185 insertions(+), 24 deletions(-)
```

Plus this evidence file.

## Validation commands and outputs

### `python -m pytest tests/test_construction_*.py tests/test_procore_*.py`

```
348 passed in 3.78s
```

(342 → 348; +6 net: five new validator tests + one new cross-registry parity test. The existing `test_seed_projects_includes_tropical_pilot` was updated in place rather than duplicated.)

### `ruff check src/hb_assistant/construction/ src/hb_assistant/procore/ src/hb_assistant/cli/construction.py src/hb_assistant/cli/procore.py`

```
All checks passed!
```

### `hb-assistant construction-agent validate --json`

```json
{
  "command": "construction-agent validate",
  "checks": [
    {"name": "schema", "ok": true, "detail": "schema_version=5"},
    {"name": "source_registry", "ok": true, "detail": "6 projects, 14 sources"},
    {"name": "review_rules", "ok": true, "detail": "version=1; 16 rules; threshold=0.7"}
  ]
}
```

Result: `ok=true`, all 4 checks passing (truncated).

### `hb-assistant construction-agent sources validate --json`

```
project_count: 6, source_count: 14, resolved_count: 0, pending_count: 9, ok: true
```

### `hb-assistant construction-agent index status --json`

```
schema_version: 5, project_count: 6, source_count: 14, sources_in_view: 14, rule_count: 16
```

### `hb-assistant procore mapping validate --json`

Exit code: `1` (by design — `hilltop` and `hilltop-gardens` remain `pending`).

```
total: 6
by_status: { pilot: 4, pending: 2 }
ok: false
rows:
  - tropical          -> 2525840  (pilot,  mapped=true)
  - pga-modern-garage -> 2091445  (pilot,  mapped=true)
  - alton-hilltop-pbg -> 2982068  (pilot,  mapped=true)
  - the-wellington    -> 3215931  (pilot,  mapped=true)
  - hilltop           -> ""       (pending, mapped=false)
  - hilltop-gardens   -> ""       (pending, mapped=false)
guardrails: external_systems=read_only, writeback=none, live_calls_disabled=true,
            correspondence_excluded=true, schedule_tasks_deferred=true
```

### `hb-assistant procore tools list --json`

```
endpoint_count: 13
by_status: { validated: 6, sensitive_validated: 4, excluded: 1, deferred: 2 }
guardrails: external_systems=read_only, writeback=none, live_calls_disabled=true
```

(Endpoint contract untouched by this prompt.)

### Validator smoke test (Python REPL)

Five direct constructions against `ProcoreProjectsRegistry.model_validate`:

```
OK1: HB-number ("23-435-01") rejected; error includes "23-435-01" and `^\d{2}-\d{3}-\d{2}$`
OK2: numeric ID ("2525840") accepted
OK3: pending + blank accepted
OK4: pilot + blank rejected
OK5: pending + non-empty ("1234") rejected
```

## Guardrail attestation

- Model-level validator now enforces HB-number rejection at construction time; the loader inherits the guard via `ProcoreProjectsRegistry.model_validate`, and the auditor reads only from a validated registry.
- No Procore HTTP client introduced. `test_procore_module_imports_no_http_client` continues to ban `requests`, `httpx`, `urllib3`, `aiohttp` across the entire `hb_assistant.procore` package surface.
- No writeback path added. `test_every_cli_payload_advertises_no_writeback` still locks `writeback=none` and `external_systems=read_only` on every CLI payload.
- Mailbox surfaces, SharePoint surfaces, OneDrive surfaces, source-document-copy paths: all untouched.
- Read-only invariants intact: SQLite V5 CHECK constraints on `read_only=1`, `mailbox_writeback_allowed=0`, `persist_full_body=0`, singleton policy `id=1` remain in place (no migrator change).

## Blocked live / external validation

- Procore OAuth remains intentionally stubbed. `hb-assistant procore auth status --json` continues to report `env_absent` in this non-interactive shell. No live `/vapid/projects` call attempted.
- Microsoft Graph token cache still empty in this shell; no live Graph call attempted.

## Cross-registry parity (new test)

`test_seed_projects_covers_canonical_construction_registry_keys` loads both seeds and asserts every `project_key` in `sharepoint_onedrive_sources.seed.yaml` has a corresponding row in `procore_projects.seed.yaml`. This locks the two registries together so future seed edits cannot silently drift apart again.

Canonical project set covered: `tropical`, `hilltop` (Phase 01 compat), `pga-modern-garage`, `alton-hilltop-pbg`, `the-wellington`, `hilltop-gardens`.

## Status enum note (no conflict surfaced)

The Phase 02 package draft mentioned a `pilot_candidate` status. Repo truth (`procore/models.py`) carries `ProjectMappingStatus = Literal["pilot", "pending", "deprecated"]`. Per CLAUDE.md §5 source-of-truth rule, repo wins; `pilot` was used for the three newly-mapped projects as the closest accurate value. No model enum change made — `pilot_candidate` introduction is deferred to a future prompt that can update the auditor's status-bucket logic in lockstep.

## Out of scope (deferred, unchanged from plan)

- Live Procore OAuth / HTTP client.
- Unifying `ProjectIdentity.procore_project_id` (construction side) and `ProcoreProjectMapping.procore_project_id` (Procore side) into a single source of truth.
- Auditor-layer audit-report findings for invalid mapping shapes (unreachable given model-layer validator).
- Endpoint contract changes (`procore_endpoint_contract.seed.yaml` untouched).
- Loader env-override paths (unchanged).

## Next prompt readiness

Repo HEAD advanced; working tree clean after commit; full pytest + ruff + CLI suite green; canonical project-key parity now enforced by test. Ready for Phase 02 Prompt 08.
