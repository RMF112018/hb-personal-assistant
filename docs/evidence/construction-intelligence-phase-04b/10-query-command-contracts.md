# Phase 04B — Prompt 10 — Query Command Contracts

**Date:** 2026-05-29
**Branch:** main
**Scope:** Expose local SQLite query commands that make the second-brain memory
usable from the terminal (and later from assistant workflows).

## Scope decisions

- **Read-only / local only.** No Procore call, no live gate (`HB_PROCORE_LIVE`),
  no token, no `--confirm-live-get`. Each command opens the same SQLite DB the
  sync writes (`PathPolicy().get_db_path()`), runs `SQLiteMigrator().apply()`, and
  emits stable JSON via the existing `_emit` helper.
- **No migration / V7 change** (migration stays 7); **endpoint registry stays 27**.
- **Evidence-safe output:** only already-redacted columns + field names/types —
  never raw payload values (coverage reports keys/types only, matching the
  Prompt 00 `no_raw_values_persisted` posture).

## Files

### Created
- `src/hb_assistant/procore/time_window.py` — `parse_since()` relative-time parser.
- `src/hb_assistant/procore/coverage.py` — `compute_payload_coverage()` field-coverage report.
- `tests/test_procore_time_window.py` — 14 parser cases.
- `tests/test_procore_query_commands.py` — 15 command-contract tests.

### Modified
- `src/hb_assistant/store/procore_history.py` — `get_procore_timeline()` reader (+ `__all__`).
- `src/hb_assistant/store/procore_enrichment.py` — `get_procore_action_signals()` reader (+ `__all__`).
- `src/hb_assistant/procore/live_sync.py` — public `resolve_normalizer()` (lookup only).
- `src/hb_assistant/cli/procore.py` — five `live` query commands.
- `docs/operations/procore-operator-runbook.md` — Prompt 10 command section.

## Commands

All under `hb-assistant procore live`; all read-only / local.

| Command | Args | Reads | Output (key fields) |
| --- | --- | --- | --- |
| `history` | `--project --endpoint --record-id [--parent-id]` | snapshots + change events for one `record_key` | `record_key`, `snapshot_count`, `change_count`, `snapshots[]`, `changes[]` |
| `changes` | `--project --since [--until] [--endpoint] [--record-id]` | `procore_live_record_change_events` | `since_utc`, `change_count`, `changes[]` |
| `timeline` | `--project --since [--until] [--endpoint]` | `procore_record_timeline_events` | `since_utc`, `event_count`, `timeline[]` |
| `actions` | `--project [--status] [--endpoint] [--importance] [--signal-type]` | `procore_action_signals` | `filters`, `action_count`, `actions[]` |
| `coverage` | `--project --endpoint --raw-payload <path>` | local JSON file (no DB, no network) | `raw_field_count`, `captured[]`, `uncaptured[]`, `coverage_ratio`, entity/edge/signal counts |

The `record_key` is built as `project|endpoint_id|parent|record_id` (matching the
history repository key format). Every payload includes the `_GUARDRAILS` block
(`live_calls_disabled: true`).

### Relative-time grammar (`parse_since`)

`"N minutes|hours|days|weeks ago"` (relative to now) or an ISO-8601 timestamp
(trailing `Z` accepted; naive treated as UTC). Returns normalized `...Z` UTC.
Unparseable input → `ValueError` → command fail-closes with `since_unparseable`.

### Coverage method

Resolves the endpoint normalizer (`live_sync.resolve_normalizer`), runs it over
the first record of the local payload (dict / list / v2 `{"data":[…]}` envelope),
and classifies each raw top-level key as **captured** (present in
`canonical_fields` directly, as `<key>_summary` / `<key>_id`, as a known alias
e.g. `html_url`→`source_url`, or as a prefixed canonical key) or **uncaptured**.
Emits names + types only — a test asserts the raw title value never appears in the
report.

## Failure modes (fail-closed, exit 3)

`endpoint_alias_unknown` (unknown `--endpoint`), `since_unparseable` (bad time
phrase), `raw_payload_unreadable` (missing/invalid JSON file),
`coverage_compute_failed` (no normalizer / malformed payload).

## Sample JSON shapes (synthetic)

`live actions --project tropical --json`:
```json
{
  "command": "hb-assistant procore live actions", "ok": true,
  "project_key": "tropical",
  "filters": {"status": "open", "endpoint_id": null, "importance": null, "signal_type": null},
  "action_count": 1,
  "actions": [{"action_signal_id": "…", "record_key": "tropical|rfis||1",
               "endpoint_id": "rfis", "signal_type": "rfi_overdue", "signal_status": "open",
               "importance": "high", "title_redacted": "rfi_overdue", "first_detected_at_utc": "…"}],
  "guardrails": {"live_calls_disabled": true, "...": "..."}
}
```

`live coverage … --endpoint submittals`:
```json
{
  "ok": true, "endpoint_id": "submittals",
  "raw_field_count": 13, "canonical_field_count": 6,
  "captured": ["number", "specification_section", "status", "title", "type", "..."],
  "uncaptured": ["packages", "responses", "..."],
  "coverage_ratio": 0.62, "entity_count": 0, "edge_count": 0, "action_signal_count": 0,
  "no_raw_values_persisted": true
}
```

## Validation

- `python -m pytest -q tests/test_procore_time_window.py tests/test_procore_query_commands.py` → **29 passed**
  (help output, JSON shape, record-history reconstruction, project lookback,
  action filters, timeline shape, coverage from fixture, fail-closed paths).
- `python -m pytest -q --no-header` → full suite **green** (endpoint count 27, migration version 7 unchanged).
- `ruff check .` → **All checks passed**; `mypy .` → **Success (205 source files)**; `compileall` → **OK**.
- Manual local smoke (no network): `hb-assistant procore live actions --project tropical --json` → `ok=true`, `live_calls_disabled=true`.
- `hb-assistant diagnostics scan-sensitive --repo . --json` → **0 findings** in the new/edited files.
