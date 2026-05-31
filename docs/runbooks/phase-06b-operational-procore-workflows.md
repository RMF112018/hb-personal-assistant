# Phase 06B — Procore Operational Intelligence: Operator Runbook

Bobby-facing reference for the Phase 06B operational surface. **Every command below is local SQLite
only, read-only, never calls Procore, and makes no determinations** (intelligence / review aids). The
Obsidian commands are **dry-run by default**; writes require explicit `--apply --confirm` and a
configured vault (`HB_CONSTRUCTION_VAULT_ROOT`).

Schema is **V19** (unchanged) — every read model is derived on demand; nothing is persisted.

## Daily driver

```bash
# one-screen operator digest (health status + headline counts)
hb-assistant procore live digest --project tropical --json
hb-assistant procore live digest --project tropical --since "24 hours ago" --json   # + changes_in_window

# top operational risks (high-importance or cost/schedule/safety/overdue dimension)
hb-assistant procore live risks --project tropical --json
```

## Project health & freshness

```bash
hb-assistant procore live project-health --project tropical --json    # status + score components + top risks
hb-assistant procore live stale --project tropical --json             # stale / never-synced endpoints
```

## Work queues & exposure (review aids — not determinations)

```bash
hb-assistant procore live overdue --project tropical --json                       # overdue/action queue
hb-assistant procore live financial exposure --project tropical --json            # cost exposure (decimal-safe; never summed)
hb-assistant procore live schedule exposure --project tropical --json             # schedule exposure signals
```

## Relationship / responsibility quality

```bash
hb-assistant procore live responsible-party-gaps --project tropical --json        # owner/assignee/BIC/vendor/location coverage
hb-assistant procore live relationship-quality --project tropical --json          # orphans, linkage, PO/commitment dupes
```

## Retrieval & assurance

```bash
hb-assistant procore live retrieval-ready --project tropical --json    # retrieval fact manifest (redacted, source-linked)
hb-assistant procore live no-writeback-proof --json                    # formal no-writeback/no-secret/no-raw-body proof (exit 3 if it fails)
```

## Obsidian operational notes (dry-run default → explicit apply)

```bash
hb-assistant procore obsidian project-health --project tropical --dry-run --json
hb-assistant procore obsidian meeting-prep   --project tropical --since "7 days ago"  --dry-run --json
hb-assistant procore obsidian daily-digest   --project tropical --since "24 hours ago" --dry-run --json

# write the marker-bounded note into the local vault (01_Projects/) — explicit, gated:
hb-assistant procore obsidian project-health --project tropical --apply --confirm
```

Each note opens with a freshness + review-required warning banner; `review_required` records are
diverted to the banner and never inlined. Output carries only redacted scalar fields + source-link
refs — never raw payload bodies, signed URLs, or tokens.

## Endpoint posture

```bash
hb-assistant procore live endpoints list --json     # 59-endpoint registry
hb-assistant procore live endpoints ledger --json    # promotion ledger (status / evidence / next step)
hb-assistant procore validate --json                 # 28-check contract validation
```

Held-endpoint dispositions (3 Phase 05 fail-closed endpoints, preserved): see
`docs/evidence/construction-intelligence-phase-06b-procore-operational-intelligence/held-endpoint-disposition.json`.
