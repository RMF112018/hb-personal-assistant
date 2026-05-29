# Phase 04A — `mapping_consistent` validate failure resolution (2026-05-29)

## Objective

Resolve the long-standing 28th `mapping_consistent` failure in
`hb-assistant procore validate --json` by triaging the two `pending`
project entries (`hilltop`, `hilltop-gardens`) in
`resources/config/procore_projects.seed.yaml`. No live Procore call, no
schema change, no new CLI surface — pure data triage + the smallest test
rewrites necessary to keep the pending-handling invariant tested.

## Triage decision

Operator confirmation via AskUserQuestion during planning:

> `hilltop` and `hilltop-gardens` are the same project (project number
> `24-606-01`, procore id `2982068`). Each title represents a different
> sharepoint drive/site. `hilltop` represents the sharepoint drive
> `b!MIrSJI…`, drive item id `01GH6UUK…`. `hilltop-gardens` represents a
> team-controlled site `https://hedrickbrotherscom.sharepoint.com/sites/HilltopGardens`.
> Both should be normalized as `hilltop` but with the source clearly
> identified.

Disposition chosen (follow-up question): **keep `alton-hilltop-pbg`,
retire `hilltop` + `hilltop-gardens`**. `alton-hilltop-pbg` already
carried the Procore project id `2982068` and is therefore the canonical
HB-side mapping for project 24-606-01 going forward. The two SharePoint
surfaces remain valid source records.

## Source files participating in the change

### Modified

- `resources/config/procore_projects.seed.yaml` — removed the two pending
  rows; updated the preamble comment to acknowledge that Procore-side
  coverage may legitimately be a strict subset of SharePoint-side
  project_keys when multiple SharePoint surfaces index one Procore
  project.
- `resources/config/procore_project_mapping.seed.yaml` — removed the same
  two rows from `mappings:`; removed the corresponding guardrail-comment
  line.
- `tests/test_procore_endpoint_audit.py`:
  - `test_seed_projects_covers_canonical_construction_registry_keys`
    extended with a `KNOWN_ORPHAN_SHAREPOINT_KEYS` allowlist
    (`{"hilltop", "hilltop-gardens"}`); any future SharePoint-only key
    not on that list still fails the drift guard.
  - `test_auditor_marks_unmapped_project_endpoints_not_mapped` rewritten
    to build a synthetic `ProcoreProjectsRegistry` (mirroring the sibling
    `test_mapping_validation_passes_when_only_pilots_and_deprecated`
    idiom) so the "unmapped project → project_not_mapped verdict"
    semantics stays tested without depending on a pending entry in the
    live seed.
  - `test_mapping_validation_reports_pending_as_not_ok` rewritten the
    same way.
  - CLI test renamed from `test_cli_mapping_validate_pending_yields_exit_1`
    to `test_cli_mapping_validate_clean_seed_yields_exit_0`; asserts
    exit code 0 and `ok=True` against the now-clean seed.
- `tests/test_procore_endpoint_reference.py` — renamed
  `test_procore_projects_5280_pilots_vs_pending_hilltop_explicit` to
  `…_pilots_only_post_consolidation`; assertions updated to "4 pilots, 0
  pending".
- `tests/test_procore_sync_guards.py` — every test that previously
  exercised pending-handling against the live `hilltop` /
  `hilltop-gardens` entries now patches
  `hb_assistant.procore.sync.load_procore_projects` to return a synthetic
  registry created by `_registry_with_pending()`. The sync-coordinator
  semantics — default sync target excludes pending, plan/apply fail
  closed on a pending key, `allow_pending=True` soft path — remain fully
  exercised.

### Untouched (intentional)

- `resources/config/sharepoint_onedrive_sources.seed.yaml` — the two
  SharePoint surfaces remain valid source records; `hilltop` and
  `hilltop-gardens` continue as SharePoint-side `project_key` values.
  The `KNOWN_ORPHAN_SHAREPOINT_KEYS` allowlist in the drift-guard test is
  the documented bridge between the seeds.

## Before / after

### `hb-assistant procore validate --json`

```
Before: 27 / 28
After:  28 / 28
```

### `MappingValidationReport.by_status`

```
Before: {"pilot": 4, "pending": 2}, total=6, ok=False
After:  {"pilot": 4},                total=4, ok=True
```

### `procore_projects.seed.yaml` rows

```
Before: 4 pilot (tropical, pga-modern-garage, alton-hilltop-pbg,
        the-wellington) + 2 pending (hilltop, hilltop-gardens)
After:  4 pilot (tropical, pga-modern-garage, alton-hilltop-pbg,
        the-wellington)
```

## Why the `mapping_consistent` check was *not* loosened

The check's strictness is the load-bearing property: a `pending` row is
intentionally a hard stop on validate so that any HB project added to
the SharePoint sources side without a Procore mapping decision will nag
the validate gate until disposed of. Loosening the check would silently
accept future drift. The user-chosen disposition route (retire the
pending entries) preserves the check's strictness while clearing the
current backlog.

The pending-handling invariant ("any pending row → `ok=False`") remains
pinned by the rewritten
`tests/test_procore_endpoint_audit.py::test_mapping_validation_reports_pending_as_not_ok`
against a synthetic registry, and by the synthetic-registry
sync-coordinator tests in `tests/test_procore_sync_guards.py`.

## Verification

```
$ hb-assistant procore validate --json | python -c "
import sys, json
d = json.load(sys.stdin)
ok = sum(1 for c in d['checks'] if c.get('ok'))
n = len(d['checks'])
print(f'validate: {ok}/{n}')
"
validate: 28/28

$ python -m pytest -q tests/test_procore_endpoint_audit.py \
                     tests/test_procore_endpoint_reference.py \
                     tests/test_procore_sync_guards.py
59 passed

$ python -m pytest -q --no-header
959 passed, 2 skipped in 18.92s

$ ruff check .
All checks passed!

$ mypy .
Success: no issues found in 182 source files

$ python -m compileall -q src tests
(clean — no output)

$ hb-assistant procore tools list --json    # canonical envelope
$ hb-assistant procore mapping validate --json   # canonical envelope
```

## Stop conditions honored

- No live Procore call (pure local-seed edit + test rewrites).
- No raw body or secret introduced (synthetic registries only).
- `mapping_consistent` check kept strict — future pending entries still
  fail validate.
- Cross-seed drift guard preserved (with one documented allowlist entry
  for the two retired SharePoint aliases).
- No change to the `EndpointAuditor`, `ProcoreProjectMapping`,
  `ProcoreSyncCoordinator`, or CLI surfaces.

## Related references

- Architecture addendum:
  `docs/architecture/14-procore-live-sync-phase-04a.md`
  (section "Mapping consistency closeout (2026-05-29)").
- Predecessor in the evidence series:
  `docs/evidence/construction-intelligence-phase-04a/18-idempotency-reconciliation-rollback.md`.
- Seed files: `resources/config/procore_projects.seed.yaml`,
  `resources/config/procore_project_mapping.seed.yaml`,
  `resources/config/sharepoint_onedrive_sources.seed.yaml` (untouched).
- Test surfaces: `tests/test_procore_endpoint_audit.py`,
  `tests/test_procore_endpoint_reference.py`,
  `tests/test_procore_sync_guards.py`.
