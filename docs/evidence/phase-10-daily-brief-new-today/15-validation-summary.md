# 15 — Validation summary (Phase 10 · 252 · New Today)

| Requirement | Result | Evidence |
|---|---|---|
| New Today exists and is the first visible business section | ✅ | 05, 06, 07, 10 |
| Header `Today's Daily Brief` + subhead contract match | ✅ | 05, 10 (`header_ok`, `subhead_ok`) |
| No schedule/status metadata above New Today | ✅ | 06/07 (status in collapsed `<details>`) |
| Business-event sentences, not signal/category/count summaries | ✅ | 10 (`forbidden_signal_language_present` all false; anchors present) |
| Fixture per source family (email, calendar, RFI, invoice, change order/commitment, SharePoint) | ✅ | 03 (24 tests), `tests/_phase_10_new_today_seed.py` |
| Project aliases render, not keys | ✅ | 10 (`no_raw_project_keys`), 03 |
| Markdown render and browser HTML match semantically | ✅ | 03 (parity test), 05 vs 06 |
| Local Ollama path tested with mock provider | ✅ | 08, 03 |
| Deterministic fallback tested with no model client | ✅ | 09, 03 |
| Production DB SHA-256 unchanged during validation | ✅ | 12 (UNCHANGED) |
| Guard columns zero | ✅ | 13 (event_guard_sum=0, ref_guard_sum=0) |
| Raw-safety scan passes | ✅ | 11 (all categories empty), 03 |
| DB-copy validation (apply on /tmp copy of real prod) | ✅ | 04 (V52→V54 migrate, 16 events persisted, raw-safe) |
| Source tables not mutated | ✅ | 14 (`all_source_tables_unmutated=true`) |

## Refresh-window contract (revision 5)

`04-db-copy-validation.json` records the exact resolved window (`refresh_window.source` +
`rationale`). On the synthetic fixture the deterministic fallback window is used and explained; the
test suite also proves a `run_markers` window from real sync-run boundaries.

## Reviewer revisions — disposition

1. **Ollama input policy** — bounded local context (facts + short raw excerpt) reaches the model;
   never persisted/committed/cloud; output scanned + rejected if unsupported. ✅
2. **Email usefulness gate** — substrate + zero actionable ⇒ `email_degraded` + user-facing warning;
   "email follow-up unavailable" never counts as a successful New Today item. ✅ (03, 09 gates)
3. **Procore detail-or-drop** — record renders only with real number/vendor/amount/status/impact;
   else demoted to a diagnostic; never "…signal" text. ✅ (03, 10)
4. **Collapsed diagnostics** — labeled diagnostic; legacy `project_label` now resolves display names
   so no raw project keys; passes the same fences. ✅ (07, 11)
5. **Refresh-window contract** — most-recent-successful-refresh window with explicit source/rationale
   in evidence. ✅ (04)
6. **Render-model-first** — in-memory render model proven before V54 persistence. ✅ (01)
7. **Exact fixture-level business assertions** — present; fail on regression to signal/count. ✅ (03)

## Known limitations

- Email "company" is a best-effort label derived from the sender domain (domain only; the address is
  never rendered); it can be `None` when the domain is a public provider or a concatenated word.
- The scheduled `daily-run` surfaces New Today but does not (yet) escalate the run's top-level
  `status` to `degraded` on the email gate — it appends a warning + the `new_today` summary; the
  `new-today` CLI command reports `degraded` directly. The render-model degraded warning is shown in
  both surfaces.
- Procore per-record-type output is capped at 8 items (no silent truncation in the gates/diagnostics).
