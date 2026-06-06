# Daily Brief Output Receipt & Optional Import Policy

**Phase:** 09 Addendum — Daily Brief / MCP Handoff & Rendering · **Prompt:** 05
**Status:** Governance policy. Read-only / metadata-only. Schema unchanged (V39).

This policy defines where daily-brief outputs live and prevents Claude-rendered narrative from
contaminating trusted retrieval or memory stores.

## Output classes

### 1. Trusted Packet (`trusted_daily_brief_packet`)

Application-generated `DailyBriefHandoffPacketV1` (Prompt 01).

- metadata-only · source-linked · approved · safe for MCP
- may be referenced by manifest/evidence · may be regenerated
- `external_writeback = false`

**Location:** `docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality/daily-brief-packets/`
(or the existing daily-brief evidence/output path). Packets are regenerable on demand via
`hb-assistant second-brain daily-brief packet`.

### 2. Rendered Narrative (`rendered_daily_brief_narrative`)

Claude scheduled-task output (Prompt 03 templates → Prompt 02 MCP tool → Prompt 04 quality check).

- human-readable · advisory narrative · **not source truth**
- **not** approved memory · **not** vector-index input
- **not** source-linked-proof input unless validated separately

**Location (Prompt 04 — corrected):** `/Users/bobbyfetting/Documents/Obsidian Vault/Work/Daily Brief/`
(`<vault>/Work/Daily Brief/`), a clearly marked local advisory output directory, with the date-stable
filename `YYYY-MM-DD-daily-brief.md` (e.g. `2026-06-06-daily-brief.md`). The directory is created if
missing on a local write; the rendered body is never persisted to SQLite. `resolve_rendered_brief_path`
/ `write_rendered_brief` (`daily_brief/output_receipt.py`) resolve and apply-only write this path. This
is **not** the deterministic Phase 08A brief root (`daily_brief/output.py`), which remains an approved,
indexed, manifest-referenced generated output and is intentionally unchanged.

## Rendered-brief output receipt (metadata-only)

Each rendered brief carries a metadata receipt with:

| field | value |
| --- | --- |
| `packet_id` | the source packet id |
| `packet_hash` | sha256[:48] of the source packet |
| `rendered_file_path` | path to the rendered markdown (advisory output dir) |
| `rendered_utc` | render timestamp |
| `renderer` | e.g. `claude_scheduled_task` |
| `validation_proof_status` | `passed` / `failed` / `not_run` (Prompt 04 validator) |
| `advisory_only` | `true` |
| `not_source_truth` | `true` |
| `imported_to_memory` | `false` |
| `imported_to_vector_index` | `false` |
| `imported_to_source_manifest` | `false` |
| `imported_to_source_linked_proof` | `false` |
| `persisted_to_sqlite` | `false` |
| `external_writeback` | `false` |
| `import_enabled` | `false` |

The trusted-packet receipt mirrors the trusted-packet properties above.

## Exclusion by construction

Rendered narrative cannot enter trusted stores because `rendered_daily_brief_narrative`:

- is **not** in `ALLOWLISTED_SOURCE_FAMILIES` (the 10 retrieval families — the superset of embeddable +
  manifest read-model + source-linked families), so it is not a vector-index, source-manifest, or
  source-linked-proof input;
- is **not** one of the approved-manifest categories (`generated_outputs`, `approved_obsidian_outputs`,
  `reviewed_memory`, `approved_read_models`);
- has no accepted-memory path: accepted memory loads only `review_status='accepted'` items
  (`retrieval/memory_loader.py`), and there is no rendered-brief memory type.

## Optional import policy — DEFERRED

Import of rendered narrative into trusted stores is **not implemented** in this package.
`import_rendered_brief(...)` fails closed. A later import would require:

- rendered briefs are **not ingested** today;
- later import would require an **explicit review** (human-gated);
- later import would require **source-link preservation**;
- later import would need **no-raw / no-writeback / no-determination** proofs.

## Verification

`hb-assistant second-brain daily-brief output-receipt-proof --json` →
`daily-brief-rendered-output-receipt-proof.{json,md}`.
