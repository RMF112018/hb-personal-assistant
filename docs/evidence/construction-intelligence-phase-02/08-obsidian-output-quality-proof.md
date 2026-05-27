# Phase 02 — Prompt 08: Obsidian Output Projection Quality

## Summary

Hardened the Obsidian vault projection layer with three surgical additions:

1. **Explicit redaction-proof field** — `raw_delta_link_redacted: bool = True` added to `SyncReceipt` and `ProcessingReceipt` models, plumbed through the renderer, and surfaced in `sync_receipt.template.md` and `processing_receipt.template.md`. The field is an attestation, not a switch: the existing service layer never writes raw delta tokens to vault output (only a SHA256 fingerprint via `delta_link_fingerprint()` at `service.py:47-57`); this field makes that promise visible to anyone reading a generated receipt.
2. **Canonical `source_id` frontmatter alias** — `document_card.template.md` now emits both `source_key: {source_key}` and `source_id: {source_key}` in its YAML frontmatter (identical values during the alias-bridge window). The other three frontmatter-bearing templates (`registry_overview`, `project_card`, `review_required`) aggregate across sources and were intentionally not given a single source_id. No manifest-layer Python field rename was performed; the Phase 02 schema source-id ↔ source-key alias bridge already runs at the registry-load layer.
3. **Defense-in-depth rendered-output guardrails** — extended the existing parametrized test fence to cover all 7 output types (manifests, sync receipts, processing receipts, registry overview, project cards, review notes, document cards) for no-body-text + no-raw-delta-link, added a no-token-shaped-secret regex scan, added byte-identical idempotency proof, and added redaction-proof-field assertions.

Per user direction, enforcement of guardrails lives where it's cheapest:
- Body-text absence is enforced at model construction time via `extra: forbid` on every Pydantic model (no body/content/text/excerpt fields exist).
- Delta-token absence is enforced at the service layer via `delta_link_fingerprint()` (raw tokens stay in SQLite).
- These new tests are regression fences at the Markdown-output boundary so future model or template edits cannot silently regress the invariants.

## Repo HEAD

- Before: `bd72570` (Phase 02 Prompt 07 closeout)
- After: `6e386f204c5d17159ec1543e0260c7055cdb33b6`

## Files changed

```
 resources/templates/document_card.template.md      |   1 +
 resources/templates/processing_receipt.template.md |   1 +
 resources/templates/sync_receipt.template.md       |   1 +
 src/hb_assistant/construction/manifests/models.py  |   5 +
 .../construction/manifests/renderer.py             |   2 +
 tests/test_construction_manifests.py               | 207 +++++++++++++++++++++
 tests/test_construction_vault_writer.py            |  19 ++
 7 files changed, 236 insertions(+)
```

Plus this evidence file.

## Validation commands and outputs

### `python -m pytest tests/test_construction_*.py tests/test_procore_*.py`

```
379 passed in 5.45s
```

(348 → 379; +31 from this prompt: 7 parametrized × 4 tests = 28, plus 3 named tests — receipt redaction proof × 2 and document_card source_id frontmatter × 1.)

### `ruff check src/hb_assistant/construction/ src/hb_assistant/procore/ src/hb_assistant/cli/construction.py src/hb_assistant/cli/procore.py`

```
All checks passed!
```

### `hb-assistant construction-agent validate --json`

```
ok: True
schema           True schema_version=5
source_registry  True 6 projects, 14 sources
review_rules     True version=1; 16 rules; threshold=0.7
model_routing    True version=1; default_model=llama3.2:1b
```

### `hb-assistant procore mapping validate --json`

```
total: 6, by_status: {'pilot': 4, 'pending': 2}, ok: False
```

(Exit 1 by design — `hilltop` + `hilltop-gardens` remain `pending`. Unchanged from Prompt 07.)

### Rendered-output spot-checks

**Sync receipt (truncated)** — note the new `raw_delta_link_redacted: true` line:

```
# Sync Receipt — a

> **Projection only.** SQLite is authoritative; this file is a recomputable view.

- run_id: `r`
- mode: `apply`
- status: `ok`
- started_at: `t`
- finished_at: `n/a`

## Counts

- pages_seen: 0
- items_seen: 0
- items_new: 0
- items_updated: 0
- items_deleted: 0
- delta_link_recorded: false
- raw_delta_link_redacted: true
```

**Document card frontmatter** — both `source_key` and `source_id` present with identical values:

```
---
type: construction-document-card
domain: construction
status: active
tags: [construction, document-card, "tropical-sharepoint"]
owner: Bobby Fetting
generated: 2026-05-27T19:19:59.328677+00:00
source_key: tropical-sharepoint
source_id: tropical-sharepoint
item_id: i1
policy_reason: manual review
---
```

## Guardrail attestation

| Guardrail                                                                  | Status   | Where enforced |
|----------------------------------------------------------------------------|----------|----------------|
| No body text in rendered Markdown                                          | Enforced | Pydantic `extra: forbid` on every manifest model + parametrized test across all 7 outputs |
| No raw Graph delta tokens in rendered Markdown                             | Enforced | `delta_link_fingerprint()` at service layer + parametrized test across all 7 outputs |
| No token-shaped secrets (`Bearer`, `eyJ`, `*_token=`, `client_secret=`, `api_key=`, `Authorization: Bearer`) in rendered Markdown | Enforced | New parametrized regex test across all 7 outputs |
| `raw_delta_link_redacted: true` advertised on every sync + processing receipt | Enforced | New Pydantic field default + template line + dedicated tests |
| Frontmatter exposes both `source_key` and `source_id` where source identity is carried | Enforced | `document_card.template.md` + new frontmatter parity test |
| Render-twice byte equality across all 7 output types                       | Enforced | New parametrized idempotency test pinned to the renderer (not the service, which intentionally captures build-time clock) |
| Marker-bounded vault writes preserve user text                             | Enforced (unchanged) | `vault_writer.py:44-150` + existing tests |
| No source-document copies into Obsidian                                    | Enforced (unchanged) | `DocumentCardPolicyError` requires explicit `policy_reason`; no body content in `DocumentCard` model |
| No mailbox writeback / no SharePoint writeback / no Procore writeback      | Enforced (unchanged) | Module import scan tests + service-layer guardrails dict |

## Blocked live / external validation

- Procore OAuth remains intentionally stubbed; `procore mapping validate` continues to exit 1 by design.
- Microsoft Graph token cache empty in this non-interactive shell; no live Graph call attempted.
- Ollama runtime not exercised in this prompt.

## Cross-references

- `delta_link_fingerprint()` — `src/hb_assistant/construction/manifests/service.py:47-57`
- `ManifestRenderer.render_*` — `src/hb_assistant/construction/manifests/renderer.py:151-266`
- Marker-bounded write logic — `src/hb_assistant/construction/manifests/vault_writer.py:44-150`
- New all-output parametrized fence — `tests/test_construction_manifests.py` (`ALL_OUTPUT_KINDS`, `_build_all_renders`, four parametrized tests)
- Document-card frontmatter parity — `tests/test_construction_vault_writer.py` (`test_document_card_frontmatter_exposes_source_id_alongside_source_key`)

## Out of scope (deferred)

- Full manifest-layer rename of `source_key` → `source_id` across models, renderer, vault_writer file slugs, CLI, and tests. Deferred to a dedicated migration prompt.
- Manifest integration of `BaselineComparison` (deferred from Prompt 04).
- Email-deferred-note generation pipeline (deferred to Prompt 10).
- Acceptance-matrix template usage.
- Adding `source_id` to aggregate-template frontmatter (registry_overview, project_card, review_required) — these templates do not carry a single source identity, and inventing one would be misleading.

## Next prompt readiness

Repo HEAD advanced; working tree clean after commit; full pytest (379 passing) + ruff + CLI suite green; canonical project-key parity from Prompt 07 still enforced; new rendered-output guardrails in place across all 7 output types. Ready for Phase 02 Prompt 09.
