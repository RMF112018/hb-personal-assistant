# 252 — Phase 10: Daily-brief "New Today" overnight change digest

## Context

The daily brief (phases 249–251) opened with candidate-derived abstractions — `Top Priorities`,
`Calendar Prep`, `Procore Financial / Project Signals`, `Email / Follow-up: None` — i.e. signal
families, counts, and generic CTAs rather than business events. This record documents the New Today
digest that rebuilds the top of the brief around source-linked business changes from the most recent
overnight refresh cycle.

**Overriding principle:** New Today is built from business records and source content, never from
candidate labels or signal categories.

## Data flow

```
source projections (reused)                     refresh window (deterministic)
  email_raw_message_structured + task/commitment_candidates   compute_refresh_window:
  calendar_raw_event_structured                                 run markers → actual nightly window
  procore_ep_rfis / _raw_rfi_responses /                        else fallback ending at 05:00 ET anchor
    _ep_subcontractor_invoices / _ep_commitment_change_orders /
    _ep_commitment_contracts
  construction_drive_items
          │
          ▼
  new_today_digest.build_new_today_digest()           ← deterministic facts authoritative
   ├─ per-family extractors → DailyBriefChangeEvent     (detail-or-drop for Procore;
   ├─ deterministic sentence builders + attention class  email usefulness gate)
   └─ gates + diagnostics + refresh window
          │
          ▼  (optional, advisory, bounded)
  ollama_new_today.apply_model_overlay()              ← polishes why/action + attention ±1 step;
   bounded local-context packet; deterministic           summary_text never overwritten; leak ⇒ withheld;
   summary_text immutable; hash-only receipt             fail-closed to deterministic
          │
          ▼
  new_today_presentation.build_render_model()         ← single render model (3 attention groups)
   ├─ render_markdown()  → daily_run.py vault brief    (New Today first; legacy brief wrapped in a
   └─ render_daily_run_html(new_today=…) → browser       collapsed "Run details / diagnostics" block)
          │
          ▼  (optional)
  persist_new_today_digest() → V54 daily_brief_change_events (+ _refs)   ← fail-closed on --max-persist
```

## Schema (V54, additive)

`daily_brief_change_events` + `daily_brief_change_event_refs`, both carrying the 13-column
`_P10_GUARDS` (`CHECK(col = 0)`). Redacted / title-only / hash-linked columns only; the model layer
is referenced by hash-only `model_run_receipt_id`. `LATEST_SCHEMA_VERSION = 54`. `CREATE IF NOT
EXISTS` — re-apply is a no-op; V1–V53 untouched.

## Guardrails

- Deterministic facts authoritative; model advisory only and cannot overwrite the factual sentence.
- Bounded local raw context may reach the local model for grounding, but is never persisted,
  committed to evidence, or sent to any cloud service; output is scanned and rejected if unsupported.
- Dual output fence (`assert_clean_display` + `scan_text_for_forbidden`) over Markdown; egress scan
  over HTML. No raw project keys, candidate IDs, table names, `None.`, URLs, emails, or JSON dumps —
  including inside the collapsed diagnostics block.
- No writeback; dry-run default; `--apply` requires `--max-persist` + a `/tmp` `--db` copy. Validation
  proved the production DB SHA-256 unchanged and all guard columns zero.

## CLI

`second-brain daily-brief new-today` — `--brief-date`, `--apply/--dry-run`, `--max-persist`,
`--profile`, `--model`, `--provider ollama`, `--timeout-seconds`, `--no-client`, `--mock-output`,
`--db`, `--allow-non-tmp-db`, `--json`. The scheduled `daily-run` also leads with New Today.

## Evidence

`docs/evidence/phase-10-daily-brief-new-today/` — markdown + browser samples, ollama / deterministic
proofs, copy-quality + raw-safety scans, DB-copy validation, prod-DB-SHA-unchanged, guard-columns-zero,
source-table-no-mutation, and the validation summary.
