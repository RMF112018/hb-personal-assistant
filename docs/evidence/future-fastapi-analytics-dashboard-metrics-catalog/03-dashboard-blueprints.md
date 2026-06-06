# Dashboard Blueprints

The primary UI should feel like a GC operations command center. Admin / Data Confidence is a supporting trust layer, not the default landing experience.

## Primary Layer: Construction Operations

- Executive Portfolio: company-wide attention items, cost exposure signals, aging decisions, cash/closeout attention, and project risk mix.
- Project Health: open action signals, relationship gaps affecting follow-up, recent changes, and confidence badges as supporting context.
- Cost & Financial Exposure: pending change exposure, budget movements, RFQ quote exposure, commitment/owner cost signals, and financial readiness context.
- Change Management: aging change events, change-order approval aging, RFQ follow-through, documentation completeness, and schedule-impact signals.
- Schedule & Procurement Risk: overdue RFI/submittal signals, low-float activity signals, buyout/procurement aging, vendor compliance attention.
- RFIs / Submittals / Design Decisions: RFI aging, response latency, official-answer coverage, submittal review aging, design decision backlog.
- Field Operations / Quality / Safety: open field issues, punch/observation/inspection follow-through, field hotspots, review-required quality/safety signals.
- Document Control: classification review, extraction-blocked files, document relationship candidates, document type coverage.
- Correspondence & Decision Velocity: correspondence trend, decision aging, thread summary coverage, owner/design-team response aging.
- Meetings / Action Items: open and aging meeting actions, meeting prep readiness, meeting-email candidates, owner follow-through.
- Subcontractor / Vendor Performance: vendor open action load, aging response signals, compliance attention, invoice attention, quality signals.
- Billing / Cash / Retention: payment application status, retainage signals, current-payment-due signals, invoice aging, billing period coverage.
- Closeout Readiness: closeout action blockers, punch aging, closeout document coverage, final compliance and billing/retainage attention.

## Supporting Layer: Admin / Data Confidence

- Source / Sync Health: source coverage, freshness, Graph delta, mailbox, calendar, blocked/review-routed items.
- Workflow / Job Health: daily brief, automation, retry, no-overlap, and generated-output receipts.
- Evidence / Guardrail Health: data-quality gates, no-writeback/no-raw proofs, guardrail column coverage, schema confidence, evidence freshness.
- Retrieval / AI Quality: approved source manifests, vector/LlamaIndex/embedding readiness, evals, unsupported-claim checks, memory review.
- Permissions / Governance: MCP calls/denials, permission posture, prohibited metric attempts, policy compliance.
- Data Completeness / Coverage: table inventory, Procore endpoint data, financial completeness, document/correspondence coverage.

## UX Rule

Operations pages may show compact confidence badges, but the headline labels should remain construction-facing. Detailed confidence, evidence, and guardrail diagnostics belong in Admin / Data Confidence drilldowns.
