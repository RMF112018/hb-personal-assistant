# Daily Brief V2 — Output Path & Receipt Policy Proof (Prompt 04)

**Package:** HB_Construction_Intelligence_Phase_09_Addendum_Daily_Brief_V2_Executive_Utility_Hardening
**Prompt:** 04 — Obsidian Output Path and Receipt Policy
**Date:** 2026-06-06

## Corrected output path (defect D7)

- Canonical directory: `/Users/bobbyfetting/Documents/Obsidian Vault/Work/Daily Brief/`
- Filename convention (date-stable): `YYYY-MM-DD-daily-brief.md`
- Resolved default path: `/Users/bobbyfetting/Documents/Obsidian Vault/Work/Daily Brief/2026-06-06-daily-brief.md`
- Path with the space in "Daily Brief" works natively (`Path`); the directory is created if missing on a
  local write (`write_rendered_brief(..., apply=True)` → `mkdir(parents=True, exist_ok=True)`).

## Receipt — metadata-only, excluded from trusted stores

The rendered-brief receipt references the packet id/hash and the rendered file path and carries only
metadata attestations (no body). Exclusion/no-persist flags:

| attestation | value |
| --- | --- |
| `advisory_only` | true |
| `not_source_truth` | true |
| `imported_to_memory` | false |
| `imported_to_vector_index` | false |
| `imported_to_source_manifest` | false |
| `imported_to_source_linked_proof` | false |
| `persisted_to_sqlite` | false |
| `external_writeback` | false |
| `import_enabled` | false |

The rendered body is written only to the advisory vault file and is **never** persisted to SQLite.
Import into trusted stores remains deferred (`import_rendered_brief` fails closed).

## Scope note

Only the Claude-rendered advisory narrative path is corrected. The deterministic Phase 08A brief writer
(`daily_brief/output.py` `resolve_brief_path`/`write_brief_output`) and its governed seeds
(`phase_08a_obsidian_index_policy.seed.yaml`, the approved source manifest) are **intentionally
unchanged** — that brief is an approved, indexed, manifest-referenced generated output, which is the
opposite of the advisory rendered narrative. See architecture record 181.

## Verification

- `hb-assistant second-brain daily-brief output-receipt-proof --json` → `proof_passed: true` (12 checks,
  including `rendered_path_is_correct` and `not_persisted_to_sqlite`).
- `tests/test_phase_09_daily_brief_output_receipt.py` green (path correct, filename date-stable,
  dir-creation-with-spaces, dry-run, metadata-only, exclusion, no-SQLite).
- `tests/test_daily_brief_output.py` + `tests/test_phase_09_source_manifest.py` green (deterministic
  Phase 08A writer/governance undisturbed).
- Machine-readable companion: `daily-brief-v2-output-path-receipt-proof.json`.
