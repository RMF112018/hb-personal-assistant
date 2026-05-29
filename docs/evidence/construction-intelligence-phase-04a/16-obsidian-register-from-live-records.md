# Phase 04A — Prompt 09A: Obsidian register from Phase 04A live SQLite

## Objective

Add an optional, endpoint-scoped Obsidian projection that reads from the
Phase 04A `procore_live_records` table and writes a marker-bounded register
section into the local construction vault. Read-only over SQLite; never
calls Procore; never persists raw response bodies; idempotent on rerun.

## Source

- `src/hb_assistant/procore/obsidian.py` (additions): `LiveRecordsRegisterBuilder`,
  `procore_obsidian_register`, `_ENDPOINT_TO_REGISTER_TEMPLATE`,
  `_REGISTER_FILENAME_SUFFIX`.
- `src/hb_assistant/procore/__init__.py` (re-exports).
- `src/hb_assistant/cli/procore.py` (new Typer command:
  `obsidian register` next to `obsidian preview`).
- Tests: `tests/test_procore_obsidian_register.py`,
  `tests/test_procore_cli_obsidian_register.py`.
- Docs: architecture addendum in
  `docs/architecture/14-procore-live-sync-phase-04a.md`, runbook section in
  `docs/operations/procore-operator-runbook.md`.

## Command surface

```bash
hb-assistant procore obsidian register \
  --project tropical --endpoint rfis --from-sqlite --dry-run --json

hb-assistant procore obsidian register \
  --project tropical --endpoint rfis --from-sqlite --apply --confirm --json
```

`--from-sqlite` is required — a mandatory semantic gate that asserts no live
Procore call will be attempted. The code path is also hard-wired never to
issue HTTP; `procore_obsidian_register` only opens the local SQLite DB.

## Endpoint → register-family template mapping

| Endpoint id | Family template | Output file |
| --- | --- | --- |
| `rfis`, `rfi-responses` | `rfi_register` | `<project>.procore-rfi-register.md` |
| `submittals`, `submittal-responses`, `submittal-packages` | `submittal_register` | `<project>.procore-submittal-register.md` |
| `observations` | `observation_register` | `<project>.procore-observation-register.md` |
| `meetings`, `meeting-detail` | `meeting_register` (Meetings table) | `<project>.procore-meeting-register.md` |
| `meeting-topics` | `meeting_register` (Topics table) | `<project>.procore-meeting-register.md` |
| `daily-log-weather`, `daily-log-manpower`, `daily-log-notes` | `daily_log_index` | `<project>.procore-daily-log-index.md` |

Unsupported endpoints (`projects`, `punch-items`, `schedules`, `activities`)
return `ok=False`, `status="unsupported_endpoint"`, exit code `2`, and a
`next_steps` hint pointing at `procore obsidian preview`.

## Live receipts (tropical project, 2026-05-29)

### RFI dry-run (count_from_sqlite=72)

```
$ hb-assistant procore obsidian register \
    --project tropical --endpoint rfis --from-sqlite --dry-run --json
```

Excerpts from the JSON envelope:

```json
{
  "command": "procore-obsidian-register",
  "source_table": "procore_live_records",
  "mode": "dry_run",
  "dry_run": true,
  "ok": true,
  "status": "ok",
  "family_template": "rfi_register",
  "count_from_sqlite": 72,
  "review_count": 72
}
```

All 72 RFI rows are flagged `review_required=1` from the prior live sync (the
canonical sensitive_reason was `assignee_missing`), so the rendered table
holds the empty placeholder — `| (no non-sensitive records in
procore_live_records) | | | | |` — and the 72 routed items appear in
`review_items` with `procore_record_id`, `endpoint_id`, and
`sensitive_reason`.

### Submittals dry-run (count_from_sqlite=100, cross-family proof)

```
$ hb-assistant procore obsidian register \
    --project tropical --endpoint submittals --from-sqlite --dry-run --json
```

```json
{
  "ok": true,
  "family_template": "submittal_register",
  "count_from_sqlite": 100
}
```

Confirms the endpoint → family routing works for a non-RFI surface.

### Unsupported endpoint rejection

```
$ hb-assistant procore obsidian register \
    --project tropical --endpoint punch-items --from-sqlite --dry-run --json
echo $?    # → 2
```

Envelope (excerpt):

```json
{
  "ok": false,
  "status": "unsupported_endpoint",
  "error": "endpoint 'punch-items' has no register template; supported: [...]",
  "next_steps": "use 'hb-assistant procore obsidian preview' for project_card / endpoint_audit, or add a register template (out of Prompt 09A scope)."
}
```

### Missing `--from-sqlite` rejection

```
$ hb-assistant procore obsidian register \
    --project tropical --endpoint rfis --dry-run --json
echo $?    # → 2
```

```json
{
  "ok": false,
  "status": "missing_required_flag",
  "error": "--from-sqlite is required (asserts no live Procore call)."
}
```

## Idempotency proof

Covered by `tests/test_procore_obsidian_register.py::test_apply_writes_marker_bounded_file_and_is_idempotent`:
two consecutive `apply` invocations produce byte-identical file content
(`assert second_bytes == first_bytes`).

Marker-bounded preservation covered by
`tests/test_procore_obsidian_register.py::test_apply_preserves_content_outside_marker_region`:
user content above and below the
`<!-- HB-PROCORE-RFI-REGISTER:START/END -->` markers is preserved across
reruns.

## Stop conditions enforced

- `--from-sqlite` is required (returns exit 2 if omitted).
- Unsupported endpoints rejected with structured error + exit 2.
- `--apply` without `--confirm` in non-TTY contexts → exit 1.
- The code path never opens an HTTP client (no `ProcoreHTTPClient` import in
  the register call graph).
- Raw response bodies are never read: the V6 schema CHECK constraint pins
  `raw_body_persisted = 0` for all live-records rows.
- Sensitive content excluded: rows with `review_required=1` are routed to
  `review_items` and omitted from the table.

## Verification

```
$ python -m pytest -q \
    tests/test_procore_obsidian_register.py \
    tests/test_procore_cli_obsidian_register.py
......... 16 passed

$ python -m pytest -q --no-header
930 passed, 2 skipped in 18.48s

$ ruff check .
All checks passed!

$ mypy .
Success: no issues found in 179 source files

$ hb-assistant procore validate --json
checks: 27 / 28   # 28th (mapping_consistent) is the pre-existing pending-project
                  # failure from procore_projects.seed.yaml — not introduced by 09A.
```

## Related references

- Architecture addendum: `docs/architecture/14-procore-live-sync-phase-04a.md`
  (section "Obsidian register from live SQLite (Prompt 09A)").
- Operator runbook: `docs/operations/procore-operator-runbook.md` (section
  "Obsidian register from Phase 04A live SQLite (Prompt 09A)").
- Sibling projection (older, Phase 03 data source):
  `docs/evidence/construction-intelligence-phase-03/10-procore-obsidian-output-preview.md`.
- Schedules + activities (prior session, immediate predecessor in the
  evidence series): `15-schedules-and-activities-endpoints.md`.
