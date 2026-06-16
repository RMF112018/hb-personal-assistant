"""Operator forecast-controls slice.

An operator-controlled, human-accepted, auditable constraint layer over the forecast model. Lets the
operator set per-code forecast stop dates / closeout windows and accepted remaining-cost / final-cost
allowances BEFORE monthly and comprehensive generation, so substantially-complete codes stop carrying
model forecast through the final month.

Controls are explicit operator decisions (source, reason, acceptance metadata) — never model truth.
CostEntries/Sage incurred cost remains accounting truth and actual cost to date is the only hard floor.
No source Excel / accepted package / SQLite mutation; no live external calls. Posture-changing controls
(post-stop zeroing, dollar changes) apply only when human-accepted; pending controls surface in the
review queue without changing the forecast.
"""
