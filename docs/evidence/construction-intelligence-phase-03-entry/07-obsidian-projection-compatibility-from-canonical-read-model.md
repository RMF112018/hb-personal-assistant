# Phase 03 Prompt 07 — Obsidian Projection Compatibility From Canonical Read Model

Wires the V5 canonical read model (`construction_source_locations` +
`drive_item_bridge.read_drive_items_unified`) into the manifest /
document-card projection layer via an additive adapter. The legacy
V2-keyed `build_document_card(source=…)` path stays; a new
`build_document_card_from_source_id(source_id=…)` method renders a
document card keyed by the V5 canonical `source_id`.

## Files Touched

- `src/hb_assistant/construction/manifests/canonical_adapter.py` (new)
- `src/hb_assistant/construction/manifests/service.py`
- `src/hb_assistant/construction/manifests/models.py`
- `src/hb_assistant/construction/manifests/renderer.py`
- `src/hb_assistant/construction/manifests/__init__.py`
- `resources/templates/document_card.template.md`
- `tests/test_construction_manifests.py`
- `tests/test_construction_vault_writer.py`

## Test Pass Counts (verbatim pytest tails)

```
$ python -m pytest tests/test_construction_manifests.py tests/test_construction_vault_writer.py
92 passed in 2.49s
```

```
$ python -m pytest tests/test_construction_*.py tests/test_mutation_lockout.py
399 passed in 4.89s
```

## Ruff

```
$ ruff check src/hb_assistant/construction/
All checks passed!
```

## Forbidden-Substring Grep Against Canonical Render

The canonical document_card render was generated with the V2 delta-link
token deliberately seeded with sentinel substrings (`CANONsecretXYZ`,
`@odata.deltaLink`-shaped URL, `skiptoken=`, `Bearer `, `eyJ`,
`access_token=`). The grep over the rendered Markdown returned exit 1
(no matches):

```
$ grep -E "@odata\.deltaLink|@odata\.nextLink|skiptoken|Bearer |eyJ|access_token=" doc.md sync.md
$ echo $?
1
```

## `raw_delta_link_redacted: true` Attestation

The DocumentCard model intentionally does not carry receipt-level
attestations (its `guardrails` block is unchanged by this prompt). The
sync_receipt projection produced from the same canonical source via
`build_sync_receipt_from_store(source_key=…)` carries the explicit
proof line that no raw Graph delta token reached the Markdown output:

```
$ grep -n "raw_delta_link_redacted" sync.md
19:- raw_delta_link_redacted: true
```

The DocumentCard projection's structural redaction proof — that
`delta_token_storage: sqlite` is enumerated in the rendered guardrails
block — is preserved from the legacy path:

```
## Guardrails

- delta_token_storage: `sqlite`
- external_systems: `read_only`
- markdown_role: `projection_only`
- metadata_only: `true`
- sqlite_authoritative: `true`
- writeback: `none`
```

## Sample Rendered Frontmatter (canonical path)

```
---
type: construction-document-card
domain: construction
status: active
tags: [construction, document-card, "sp_2023projects_23_435_01_tropical_sl"]
owner: Bobby Fetting
generated: 2026-05-28T06:18:06.060084+00:00
source_key: sp_2023projects_23_435_01_tropical_sl
source_id: sp_2023projects_23_435_01_tropical_sl
item_id: canon-item-1
policy_reason: manual review
---
```

`source_key` (V2 alias) and `source_id` (V5 canonical) both appear as
distinct frontmatter fields. Under the current V5 projection mapping
(registry `source_key` → V5 `source_id`) the two strings match for
every registered source; the template now reads from distinct model
fields so the canonical path can diverge in the future without a model
migration.

## Reuse Surfaces (untouched)

- `drive_item_bridge.read_drive_items_unified` / `V5DriveItem`
- `source_projection.project_registry_to_v5_source_locations`
- `ConstructionStore.list_drive_items` / `list_inventory`
- `ConstructionVaultWriter` (the canonical document-card render passes
  through unchanged markers / atomic write paths)
- All redaction helpers in `service.py` (`delta_link_fingerprint`,
  `GUARDRAILS_DEFAULT`)
