# Phase 06B — Prompt 13: Obsidian Project Health / Meeting Prep / Daily Digest

**Status:** COMPLETE.
**Run date:** 2026-05-31
**Parent HEAD at start:** `877e28c` (`phase-06b prompt-12: operational CLI surface`)
**Objective:** Create decision-useful, marker-bounded Obsidian outputs from the Phase 06B read models
— project health, meeting prep, daily digest. Derived from local SQLite (never live Procore),
dry-run by default, `--apply` writes one marker-bounded note into the configured local vault only.
Freshness + review-required warnings; redacted/source-linked content; no determinations.

---

## 1. What was built

`src/hb_assistant/procore/obsidian_operational.py` — three deterministic build/apply pairs mirroring
`procore/obsidian_register.py` (`_render_note` + `_table`/`_section` + `_write_procore_artifact` +
`ConstructionVaultWriter` + `PROCORE_GUARDRAILS`). Three new `procore obsidian` CLI verbs.

| Command | Read models | Marker / file (01_Projects/) |
| --- | --- | --- |
| `procore obsidian project-health --project KEY --dry-run --json` | `build_project_health` | `HB-PROCORE-OPERATIONAL-PROJECT-HEALTH` → `{project}.procore-project-health.md` |
| `procore obsidian meeting-prep --project KEY --since … --dry-run --json` | open meeting action signals + `procore_live_records` meetings + `build_risks` | `HB-PROCORE-OPERATIONAL-MEETING-PREP` → `{project}.procore-meeting-prep.md` |
| `procore obsidian daily-digest --project KEY --since … --dry-run --json` | `build_operational_digest` + `build_overdue_queue` + `build_risks` + windowed `get_procore_changes` | `HB-PROCORE-OPERATIONAL-DAILY-DIGEST` → `{project}.procore-daily-digest.md` |

**Sections:**
- **project-health** — Health Status, Score Components, Top Risks, Stale Endpoints, Review-Required Items.
- **meeting-prep** — Open Meeting Actions, Recent/Upcoming Meetings, Carryover Risks.
- **daily-digest** — Headline (digest), Overdue, Top Risks, Changes In Window.

Each note opens with a freshness + review-required **warning banner**.

---

## 2. Guardrail / stop-condition reconciliation

- **Local read models only** — every section is derived from the Phase 06B SQLite read models;
  no live Procore call (`source: procore_phase06b_read_models_sqlite`, "no Procore call" in body).
- **Redacted / source-linked content only** — rendered cells use `title_redacted`, counts, status,
  `due_at_utc`, `source_url_redacted`, `record_key`, plus a local query-command reference. No raw
  payload bodies, signed URLs, or tokens.
- **Stop condition honored** — `review_required` records are diverted to the warning banner and
  **never inlined** with sensitive content. A seeded review-only meeting title is asserted absent
  from every rendered note (test + proof scan).
- **Dry-run default, explicit apply** — `--apply` requires `--confirm` in non-TTY contexts and only
  writes when the vault is configured (`HB_CONSTRUCTION_VAULT_ROOT`); marker-bounded + atomic write.
  Unconfigured vault and unparseable `--since` both fail closed (`exit_code=3`).
- **No determinations / no writeback / no migration** (schema stays V19, consistent with Prompts 06–12).

---

## 3. Proof (obsidian-operational-dry-run.json)

Seeded an isolated temp DB (RFI/submittal/inspection overdue + safety signals, a coordination
meeting with an open high-priority topic, and a review-flagged meeting) and captured the three
dry-run envelopes:

```
project_health: top_risks 4, review_required_items 1, open_signals 4; warnings review_required 1
meeting_prep:   meeting_actions 1, meetings 1, carryover_risks 4, review_flagged_meetings 1
daily_digest:   overdue 2, top_risks 4, changes_in_window 0; warnings review_required 1
```

All envelopes `dry_run: true`, `written_paths: []`; the review-flagged meeting title does not appear.
See [`obsidian-operational-dry-run.json`](./obsidian-operational-dry-run.json).

---

## 4. Validation

| Command | Exit | Result |
| --- | --- | --- |
| `pytest tests/test_procore_obsidian_operational.py` | 0 | 11 passed (renderer ×3, no-secret/no-banned ×3, marker-bounded idempotent apply, dry-run writes-nothing, apply-without-confirm fails, apply-no-vault fail-closed, unparseable-since fail-closed) |
| `pytest -m "not live" tests/test_procore*.py` | 0 | no regression (+11) |
| `ruff check src/hb_assistant/cli/procore.py tests/test_procore_obsidian_operational.py` | 0 | All checks passed |
| `mypy src` | 0 | Success: no issues found in 144 source files |
| `hb-assistant procore validate --json` | 0 | ok, 28/28 |
| `hb-assistant procore obsidian {project-health,meeting-prep,daily-digest} --dry-run --json` | 0 | ok envelopes, `written_paths: []` |

---

## 5. Guardrail attestations

- **No live Procore call** — all sections from local SQLite read models; **no writeback**;
  **dry-run default** (apply explicit + vault-gated + `--confirm`).
- **No raw bodies, tokens, signed URLs, or PEMs** — only redacted columns, counts, and source-link
  refs. Dry-run JSON secret/raw-value scanned (0 findings); review-flagged content diverted (verified
  absent).
- **No legal/claims/financial/safety/entitlement/schedule determination** — banned-determination-word
  scan over the rendered notes (0 findings).
