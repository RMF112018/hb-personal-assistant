# 12 — Phase 9 Readiness Assessment

## Readiness: Ready with Conditions

## Rationale

The Schedule CPM engine (Phases 1–8) is merged to `main` (schema v89) and is demonstrably
functional on a real imported schedule (`tropical|1071|2026-06-23 08:00`, TWNU19, 1507
activities). The full six-stage chain (graph diagnostics → forward → backward → float → longest
path → criticality) persists; the DCMA critical-path metric is **measurable** on
application-computed CPM only (`available_app_cpm_recalculated`, basis
`application_computed_cpm`, `source_critical_flags_used: false`); the four read-only API
endpoints return `available: true`; and the Computed CPM page surfaces the chain. Backend and
frontend CPM validations pass (doc 09). The remaining items are **conditions and caveats**, not
blocking defects — hence *Ready with Conditions*.

## Conditions (before or during Phase 9)

1. **Backend DB binding** — evidence/runtime API launches must use explicit
   `create_app(db_path=...)`, **or** a future patch must make `create_app()` honor
   `HB_ASSISTANT_DB_PATH`. Without this, a factory launch shows `available: false` over a
   populated DB (docs 07, 08, 11).
2. **`graph_diagnostics` status label** — the `not_implemented` label (diagnostics-only scope)
   should be reviewed/relabeled before any executive-facing presentation so it is not misread as
   a failed computation (docs 04, 11).
3. **`computed_critical_outside_longest_path` caveat** — must be carried into Phase 9 narrative
   language; do not present a single flat "critical path = N activities" claim (doc 06).
4. **No legal / root-cause delay causation** — Phase 9 must not claim delay causation or
   "certified DCMA compliant" / "true / P6 critical path."

## What Phase 9 should consume

- The persisted CPM chain runs and the DCMA evaluation (`available_app_cpm_recalculated`) as the
  **basis** for PM-facing storytelling.
- The longest-path output (`..._p01`, 45 activities) and the criticality classification, **with**
  the `computed_critical_outside_longest_path` caveat attached.
- The read-only API/read-service layer (no recomputation in read paths).

## What Phase 9 must NOT do

- Reinterpret or reintroduce **source** critical/driving/float fields into application-computed
  CPM (keep the doc-05 separation).
- Trigger CPM recomputation from read/UI paths.
- Make causal/root-cause or certification claims.
- Mix source-export evidence into application-computed CPM evidence.
- Change CPM logic, API/frontend behavior, or schema as part of "narrative" work.

## Conclusion

```
Readiness: Ready with Conditions
```

The engine and its surfacing are evaluated and sound; Phase 9 (PM-facing schedule storytelling)
may proceed provided the four conditions above are honored.
