# Known Limitations & Risks — Phase 9A.2

## Deferred by design
- **CPM Intelligence is a shell.** It surfaces availability + run-chain + a link, not the rich
  render (longest-path table, criticality/float cards, DCMA basis+caveat). Those land in **9A.3**,
  consuming the same `computed_cpm_health` envelope.
- **No visualizations.** No recharts/bars yet (recharts ^2.12.0 is available but reserved for the
  9A.6 risk-visualizations phase). Cockpit uses the existing card/table primitives only.
- **Logic Health grouping folded into Quality.** The SOW's separate "Logic Health" section is not
  introduced — the current backend surfaces logic checks within DCMA/source metrics. No fabricated
  logic data; a dedicated Logic panel waits for data that warrants it.
- **Action Queue is the existing Findings table.** Not yet a re-prioritized/clustered queue across
  quality + CPM + baseline + version-readiness — that richer triage is a later phase.

## Refactor risk + mitigation
- The reorg moved JSX and the 18 helpers **verbatim** and centralized derivation in
  `buildHealthModel()`; the 14 pre-existing test assertions all still pass, plus 2 new tests.
- `HealthCard`/`CapabilityList` had to be split into `healthCards.tsx` (separate from
  `healthShared.tsx`) to satisfy `react-refresh/only-export-components`.

## Provenance / copy guardrails honored
- No forbidden terms introduced ("true/P6/forensic critical path", "certified DCMA", "root cause").
- Source-export vs Application-computed CPM kept distinct via per-section badges + legend; the
  Critical-Path/Float section keeps its existing "does not say calculated critical path unless …"
  disclaimer.

## Pre-existing / unrelated
- 3 frontend test reds (`TodayPage` ×1, `MyItemsPage` ×2) exist on the base and are unrelated to
  Schedule Health; not fixed here.
- The stale `cpm_recalculation: "deferred"` capability still shows under Unavailable/Deferred
  (source-export view); the Computed CPM shell reports actual run availability separately. Reconciling
  the capability writer is out of scope (would be a backend change).

## Stacking
Branch is stacked on 9A.1 (unmerged). Rebase onto `origin/main` once 9A.1 merges. The PR diff
includes 9A.1's commit until then.
