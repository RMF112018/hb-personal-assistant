# Rendered State Summary

Phase 7 extends the existing Project Schedule page with a PM-facing Schedule Controls dashboard.

Rendered sections:
- Controls Overview: forecast completion, critical remaining, source/export negative float, remaining work, later/earlier movement, finish changed, float movement, and moved milestones from the resolved hub summary.
- Trend Analytics: monthly start/finish distribution, planned vs actual percent complete, schedule performance ratio, schedule delay over time, and schedule changes over time from Phase 6 payloads.
- Schedule Health / Feasibility: health index, feasibility, recovery days, critical path length index, and total float consumption index when backend payloads are available.
- Blocked / Not Yet Available Metrics: UDF-normalization and selected-baseline-dependent metrics remain visible as unavailable cards.

State handling covered by tests:
- Loading state uses .
- Trend API errors use  and do not expose raw backend stack/error text.
- Available metrics with empty  render an empty-state message or backend data-quality note.
- Blocked metrics remain unavailable and are not promoted to active charts.
