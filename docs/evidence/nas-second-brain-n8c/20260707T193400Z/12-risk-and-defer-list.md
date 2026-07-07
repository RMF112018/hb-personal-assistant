# 12 — Risk & Deferral List

## Deferred (unchanged, honest)
- **N8C-13** operator UI for the workflow surfaces — no branch, not started.
- **N8C-18** action staging / delivery — the four workflows' `stage_*` capabilities (task/reminder/agenda/
  invite/brief delivery) and `external_source_sync` (Procore/Sage/Graph). Reported as
  `deferred_capabilities`, never executed.
- **N8D** `agent_bridge` — untouched, not imported.

## Design decisions worth flagging for review
- **Extractor `status=accepted` alone is NOT trusted.** Because the decision/preference/open-loop/claim
  review overlay (`review_state`) is effectively always present (NOT NULL, default `unreviewed`), a record
  is placed in a *trusted* section only when its overlay is `operator_accepted` (or an equivalent trusted
  token). A `status=accepted` record still `unreviewed` lands in *candidate*. This is the deliberately
  conservative reading of clarification #8 ("missing/unknown defaults to candidate, not trusted") and the
  review layer's "nothing is auto-accepted" posture. If Bobby wants extractor-accepted records treated as
  trusted pre-review, that is a one-line change to `_classify` — flagged, not assumed.
- **Claims are surfaced as references, not content.** `_CLAIM_WL` omits `claim_text`/`evidence_excerpt`, so
  a "trusted fact" is a bounded pointer the consumer follows via the existing claim read surface. This keeps
  us strictly within the bounded-metadata rule (#4) at the cost of the fact text not appearing inline.
- **Citations are read only for explicitly-supplied artifacts** (meeting_prep draft/packet), not for every
  listed item, to keep daily_brief bounded and fast. Listed items contribute cheap source-refs. The
  `missing_citation_coverage` warning uses citation+source-ref coverage of trusted content.

## Not a risk
- Schema untouched (V108); migrator not edited.
- `nas_mcp` change is a single additive read-only pass-through line, explicitly authorized.
- No persistence, no execution, no live source read, no external sync, no new tool/route/command.
