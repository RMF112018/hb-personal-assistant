# Phase 08B — Prompt 14: No-Writeback / No-Raw-HTML Proof

**Status:** Implemented (additive). Schema **V34 unchanged** (no new table); package stays `1.3.0`.
**Baseline:** atop `d7498f6` (08B Prompt 13; 08A closeout `954a518` is ancestor).
**Date:** 2026-06-03.
**Scope:** Extends the existing `build_second_brain_no_writeback_proof` with an explicit **no-raw-HTML**
facet — a tag-shaped markup scan over persisted receipt rows + generated runtime output, plus a
`no_raw_html_persisted` field on the `no-writeback-proof` surface. No schema/table/CLI change.

---

## 1. Files Changed

- `src/hb_assistant/construction/second_brain/safety.py` —
  - `_HTML_MARKUP_PATTERNS` + `_scan_text_for_html_markup(text)` (value-shaped tag scan; matches
    `<!doctype` and real tags, not a stray `<` nor the `.html` path substring).
  - `_scan_second_brain_tables_for_html(conn)` (live-row markup scan over `_PHASE_08A_TABLES`).
  - `_scan_generated_outputs()` now returns `{"secrets", "html"}` (the dry-run brief/handoff blob is
    HTML-scanned too).
  - `build_second_brain_no_writeback_proof`: `html_ok` folded into `proof_passed`; two new
    `checks_detail` entries (`sqlite_html_markup_scan_08b_tables`, `generated_brief_handoff_html_scan`);
    new `no_raw_html_persisted` (+ `_scope`) field; `raw_html_persisted: False` guardrail.
- `tests/test_second_brain_no_writeback_proof.py` — clean-pass asserts `no_raw_html_persisted`; the new
  checks added to `test_all_checks_present`; a scanner unit test (clean `.html` paths / hashes / reason
  codes / titles → none; real HTML → hits); a planted-HTML end-to-end test (proof fails closed); CLI
  asserts `no_raw_html_persisted=true`.
- `docs/architecture/86-phase-08b-no-raw-html-proof.md` (new).

**No schema / table / contract / seed / CLI-command change.** Schema **V34 / 151 tables** unchanged.

---

## 2. Tests Run

| Command | Result |
|---|---|
| `ruff check src tests` | All checks passed |
| `mypy src` | Success — no issues in **254** source files |
| `pytest tests/test_second_brain_no_writeback_proof.py -q` | 10 passed (incl. 2 new HTML tests) |
| `pytest -m "not integration and not live and not manual"` | **2780 passed, 0 failed, 0 errors** (junit `tests=2780 failures=0 errors=0`) |
| `construction-agent validate --json` | 4/4 passed (schema_version=34, unchanged) |
| `second-brain data-quality no-writeback-proof --json` | `proof_passed=true`, **`no_raw_html_persisted=true`**, schema 34 |
| `second-brain data-quality phase-08a-gates --json` | 8 pass / 1 warning / 0 fail / 3 deferred (unchanged) |
| `second-brain data-quality phase-08b-gates --json` | 15 pass / 0 / 0 / 1 deferred (unchanged) |

---

## 3. Specific Checks → repo-truth evidence

- **Schema version + table lifecycle registrations:** schema **V34 / 151 tables unchanged**; this
  prompt adds no table.
- **CLI dry-run-by-default for apply-capable ops:** the proof is **read-only** (no apply-capable
  operation to dry-run); it scans, never mutates.
- **No external writeback / delivery / raw-content / raw-HTML:** the extended proof passes at schema 34
  with `no_external_writeback=true`, `no_raw_values_persisted=true`, and now
  `no_raw_html_persisted=true`. The HTML scan covers persisted receipt rows + generated output; the
  renderer's module source (legit HTML templates) and the rendered HTML file (outside the repo) are
  intentionally excluded.
- **Actionable status / check names:** two new named checks — `sqlite_html_markup_scan_08b_tables`,
  `generated_brief_handoff_html_scan` — each with `passed` + `findings`.
- **success / failure / blocked / stale / dry-run coverage:** success = clean-repo proof passes
  (`no_raw_html_persisted=true`); failure = the planted-HTML temp-DB test proves it fails closed
  (`proof_passed=false`, the finding names the planted cell); the scanner unit test covers the
  clean-vs-dirty boundary (no false positive on `.html` paths). The proof is read-only (the dry-run
  posture); blocked/stale are not applicable to a read-only scan.

---

## 4. Guardrails Verified

- Read-only, fail-closed (any HTML finding → `proof_passed=false`). No schema change; additive; no
  existing check weakened (all 10 pre-existing checks still pass).
- HTML scan scoped to persisted data + generated runtime output — never the renderer's module source
  (legit HTML templates) nor the rendered HTML file (legit HTML, written outside the repo).
- No external writeback/delivery; no raw-content / raw-HTML persisted. Phase 08A guardrails preserved:
  phase-08a-gates unchanged (8/1/0/3); phase-08b-gates unchanged (15/0/0/1).

---

## 5. Known Limitations

1. The markup scan is pattern-based over a fixed structural/script/style/embed tag allow-list; novel
   tags outside the list are not matched (the list covers the tags that matter for a "raw HTML
   persisted" leak).
2. `automation_execution` stays `deferred_not_blocking` — the lone unbuilt 08B surface.

---

## 6. Next-Prompt Readiness

The next 08B prompt can safely assume:
- The Phase 08B no-writeback proof now also proves **no raw HTML is persisted** — an explicit
  tag-shaped scan over live receipt rows + generated output, fail-closed, exposed as
  `no_raw_html_persisted` on `second-brain data-quality no-writeback-proof`.
- Full matrix green at schema **V34 / 151 tables**: ruff clean, mypy 254, validate 4/4, pytest 2780
  passed / 0 fail, no-writeback proof (proof_passed + no_raw_html_persisted) at schema 34,
  phase-08a-gates 8/1/0/3, phase-08b-gates 15/0/0/1.
- The remaining build target is the **full automation executor** — flipping the lone deferred
  `automation_execution` gate.
