# 13 — Known limitations

1. **New Today is deterministic in the scheduled run (v1).** The scheduled `daily-run run` builds New
   Today without the optional Ollama overlay → `new_today.model_enrichment_status = "not_requested"`.
   The bounded overlay (why/action phrasing polish) remains available via `daily-brief new-today`.
   Deterministic facts are authoritative regardless; wiring the overlay into the scheduled path is a
   future increment, with its status field already reserved (`used|withheld|unavailable`).

2. **`daily_brief.status = failed` is the digest-exception path only.** A New Today build exception
   degrades to the legacy brief and reports `failed` with `new_today_unavailable:<Type>`. The run does
   not hard-fail; legacy diagnostics still render. Not exercised in the live validation (the digest
   built cleanly with 42 events).

3. **Guard-columns proof is vacuous on the scheduled run.** `daily-run` builds New Today read-only, so
   `daily_brief_change_events` is empty on the copy (`row_count = 0`, all guard sums 0). Persistence-
   path guard enforcement (CHECK constraints + caps) is proven by the `daily-brief new-today` CLI
   tests in `tests/test_phase_10_new_today.py`, not by this run.

4. **Legacy subsystems retained as diagnostics.** Candidate/ranking/assembly, LLM synthesis, and MEI
   were not deleted (no dead-code proof attempted); they remain wired but demoted below the fold and
   stripped of any user-facing status ownership.

5. **Committed HTML/Markdown samples are synthetic.** To honor the no-private-content constraint, the
   committed `07-browser-html-sample.html` / `08-markdown-sample.md` are rendered from the synthetic
   seed fixture. The real prod-derived run was scanned (egress + forbidden-token clean) but its
   rendered HTML is **not** committed; only its raw-safe counts/status excerpt is
   (`06-daily-run-json-sample.json`).

6. **`projection_coverage_degraded` in the live run** reflects the plain Application Support root's
   email/calendar projection coverage at validation time, not a regression introduced by this change.
