"""Forecast comprehensive — integrated forecast model layer.

Deterministic top-level integrator that DISCOVERS and CONSUMES the accepted forecast evidence packages
(context, intelligence, monthly, probability, history-informed, cost-frequency, plus crosswalk-v2 and
schedule-integrated for completeness), normalizes them into a per-budget-code evidence registry, scores
advisory evidence within configured bounds (with explicit accept/downgrade/reject reason codes and
independence-group de-duplication), and emits integrated final-cost / monthly-phasing / probability
recommendations with full lineage, an evidence-conflict register, and a human-acceptance review queue.

It never re-runs the heavy generators and never mutates any package. CostEntries/Sage incurred cost is
accounting truth; actual cost to date is the only hard floor; no evidence is ever a hard cap. Probability
is a deterministic transform of the accepted probability package (not a fresh Monte Carlo). Every
posture-changing recommendation carries evidence lineage and human-acceptance status (default pending).
"""
