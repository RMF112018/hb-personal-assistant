# Known limitations (by design, Phase 2)

- **Forward pass only.** No backward pass, no late start/finish.
- **No float of any kind** (total/free/interfering/independent) and **no longest/critical/near-critical path**.
- **No source-field overwrite or read for logic.** Source early/late dates, total/derived float, source_critical_flag, source_driving_path_flag, is_critical are untouched and never consulted. DCMA critical-path metric still returns NOT_MEASURABLE_RECALC.
- **`cpm_recalculation_status='forward_pass_only'`** — never reported as a complete CPM engine.
- **Date model is a simplification.** Timing is computed as continuous working-day-equivalent **day-offsets from the anchor** (authoritative). The derived `computed_early_start/finish` ISO datetimes use **calendar-day** addition — there is NO weekend/holiday/calendar engine (none exists in-repo). Offsets are the source of truth.
- **MSP ISO8601 durations** (e.g. `PT40H0M0S`) are not parsed in this phase → flagged `missing_duration`. XER (hours) and P6 XML (hours) are handled.
- **No frontend/API change.** Service + repository + tests only.

## Next recommended phase
Phase 3: CPM backward pass (late start/finish) over the same graph + anchor, then total float — source-field-preserving, written to computed columns only.
