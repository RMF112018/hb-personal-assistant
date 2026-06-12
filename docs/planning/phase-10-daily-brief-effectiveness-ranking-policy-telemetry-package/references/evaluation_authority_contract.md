# Evaluation Authority Contract

Telemetry is observational only.

Allowed:

- count outcomes;
- compute metrics;
- persist raw-free evaluation facts;
- render raw-free reports;
- recommend next tuning actions.

Forbidden:

- changing lifecycle state;
- changing review status;
- adding/removing source refs;
- suppressing/merging/rejecting/accepting/snoozing candidates;
- changing rank policy thresholds automatically;
- calling external services;
- storing raw prompts/responses or raw content.

Every public result must state that metrics are advisory and observational.
