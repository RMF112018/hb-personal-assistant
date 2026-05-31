# Phase 06B — Prompt 11: Responsible Party & Relationship Quality Diagnostics

**Status:** COMPLETE.
**Run date:** 2026-05-31
**Parent HEAD at start:** `8ec77b5` (`phase-06b prompt-10: schedule exposure model`)
**Objective:** Expose relationship-quality and responsibility gaps so Bobby can see which records are
orphaned, missing owners/assignees/BIC/responsible-contractor/vendor/location, weakly linked, or
duplicated — surfaced as `procore live responsible-party-gaps` + `procore live relationship-quality`.
Advisory/review aid; read-only over local SQLite; no live access; no raw values; no determinations.

---

## 1. What was built

- `src/hb_assistant/store/procore_relationship_quality.py` — two deterministic, read-only read
  models. Reuses `_record_key` (`procore_action_queue`), `_commitment_exists`
  (`procore_commitment_projection`), and the relationship edges emitted by `emit_record_edge` /
  `link_record_entities`.
- CLI top-level `live` verbs (mirror `live project-health` / `live overdue`):
  - `procore live responsible-party-gaps --project KEY [--endpoint E] --json`
  - `procore live relationship-quality --project KEY [--max-items N] --json`

### Relationship edge map (operator label → concrete `procore_record_edges.edge_type`)
| Label | Edge type |
| --- | --- |
| `owner` | `created_by` *(owner-proxy — no dedicated Procore owner edge; surfaced explicitly)* |
| `assignee` | `assignee` |
| `ball_in_court` | `ball_in_court` |
| `responsible_contractor` | `responsible_contractor` |
| `vendor` | `vendor` |
| `location` | `at_location` |

### Responsible-party-gaps — per (endpoint, relationship)
`records`, `records_with_edge`, `missing`, `coverage_pct`, `status`. **Non-guessing rule:**
- `not_observed` — no record of the endpoint carries the edge (relationship not asserted to apply).
- `partial_gap` — some records carry it, others do not (a genuine, actionable gap).
- `covered` — all records carry it.

Only `partial_gap` rows feed `summary.partial_gap_relationships` / `missing_total`.

### Relationship-quality — three structural lenses
- **orphans** — child records (`parent_procore_id != ''`) whose `parent_procore_id` is not the
  `procore_record_id` of any project record; `orphan_count`, per-endpoint counts, capped refs-only
  sample (`endpoint_id`, `procore_record_id`, `parent_procore_id`).
- **linkage** — `child_records`, `children_with_resolved_parent`, `linkage_pct`,
  `linkage_status` (`complete` / `partial` / `unknown` when there are no child records).
- **duplicate_warnings** — `purchase_order`-family contracts whose `contract_id` already exists as a
  `commitment` (via `_commitment_exists`) — the only repo-supported dedupe surface.

---

## 2. Repo-truth / stop-condition reconciliation

- **All six relationship types are real entity edges** emitted across the projection layer
  (`created_by`, `assignee`, `ball_in_court`, `responsible_contractor`, `vendor`, `at_location`);
  Prompt 11 measures their coverage rather than inventing relationships.
- **Stop condition honored — "stop if record linkage cannot be inferred safely; output
  unknown/unsupported instead of guessing."** A relationship never seen on an endpoint is
  `not_observed` (never a fabricated 100% gap); linkage with no child records is `unknown`; dedupe is
  limited to the commitment/PO logic the repo already supports.
- **No persistence / no migration (decision).** Required-work item 5's
  `procore_relationship_quality_metrics` is explicitly conditional ("if … is implemented"). With no
  downstream consumer and consistent with Prompts 06–10 (schema stays V19, dry-run-default,
  simplicity-first), both reports are derived on demand. No V20 migration was added.
- **Owner mapping documented** — `owner → created_by` (creator is the concrete owner-proxy); the
  `owner` label is surfaced so the report never overclaims a dedicated owner relationship.

---

## 3. Proof (11-responsible-party-and-relationship-quality-proof.json)

Seeded an isolated temp DB: two RFIs (one with `assignee` + `created_by`, one with neither), a
commitment with `vendor` + `responsible_contractor`, a meeting with a resolving topic and an
orphaned topic (`parent 999`), and PO/commitment contracts sharing `contract_id 55`. Dumped both
reports:

```
responsible_party_gaps: 4 endpoints, partial_gap_relationships 2
  (RFIs partial_gap on owner + assignee; vendor/BIC/responsible/location not_observed)
relationship_quality: total_records 6, child_records 2, orphan_records 1 (meeting-topics),
  linkage_pct 50.0 (partial), duplicate_warnings 1 (PO 55 duplicates commitment 55)
```

See [`11-responsible-party-and-relationship-quality-proof.json`](./11-responsible-party-and-relationship-quality-proof.json).

---

## 4. Validation (no live calls)

| Command | Exit | Result |
| --- | --- | --- |
| `pytest tests/test_procore_relationship_quality.py` | 0 | 13 passed (partial_gap / covered / not_observed / endpoint filter / six-relationships / orphan / linkage unknown+complete / PO-commitment dedupe / no-determination / empty / 2× CLI) |
| `pytest -m "not live" tests/test_procore*.py` | 0 | no regression (+13) |
| `ruff check src/hb_assistant/cli/procore.py tests/test_procore_relationship_quality.py` | 0 | All checks passed |
| `mypy src` | 0 | Success: no issues found in 143 source files |
| `hb-assistant procore validate --json` | 0 | ok, 28/28 |
| `hb-assistant procore live responsible-party-gaps --project tropical --json` | 0 | ok (39 endpoints, 15 partial gaps) |
| `hb-assistant procore live relationship-quality --project tropical --json` | 0 | ok (1780 records, 0 orphans, 10 dupes) |

---

## 5. Guardrail attestations

- **No live Procore call** (`no_live_call_performed: true`); **no writeback**; **read-only**
  (no migration, no persistence).
- **No raw bodies, tokens, signed URLs, or PEMs** — only record/edge metadata, relationship labels,
  counts, and refs (`record_key` / endpoint / record id). Proof JSON secret/raw-value scanned
  (0 findings).
- **No legal/claims/safety/entitlement/responsibility determination** (`determinations_made:
  false`) — banned-determination-word scan over the content of both reports (0 findings). Coverage
  that cannot be inferred is `not_observed` / `unknown`, never guessed.
