# Reliability damping refined to target overshooters — live re-diff (2026-06-22)

The original damping lever (fixed owner/trend set) RAISED one overrun code by +$113k when flipped on
(see ADR 293 context). This refines it to damp the **overshooters** (any estimate above the blend
median) at low completion — monotonic-down by construction. Opt-in, ships default-OFF.

## Live off-vs-on production diff (`_RELIABILITY_DAMPING` off vs on; `_P75_STAGE_GATE` on in both)
- **1 of 127 codes** change — now a **reduction** (was an increase under the old lever).
- `1000.15-09-600.SUB`: **3,618,999.19 → 3,454,537.75 (−$164,461)** — the refined lever down-weights the
  ~$17.9M `procore_progress` overshooter (the actual driver), instead of the old lever removing the low
  owner/trend anchors and pushing it up.
- `all_changes_are_reductions: true`; `worst_credible_unchanged_for_changed: true` (exposure ceiling intact).

## Why it's safe now
Position-based damping (above the blend median) is **monotonic-down**: it can only lower the central,
never raise it. The +$113k surprise class is impossible by construction. Doctrine intact: reliability
weighting only (no ERP anchor), worst-case ceiling preserves the overrun exposure.

## Status / next
Lever stays default-OFF (this PR is the refinement + evidence). With the production diff now confirmed
as a reduction, flipping `_RELIABILITY_DAMPING` on is a clean follow-up. Noted fidelity gap (separate):
the gate's backtest still reconstructs only 4 methods (omits procore_progress) — the lever is
safe-by-construction regardless.

## Files
- `production_impact.json` — off-vs-on per-code diff + the previously-offending code.
