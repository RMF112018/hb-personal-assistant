# Test Failure Triage — Apple MCC

When an Apple MCC test fails:

1. Capture reproduction command and log under the detached EV root.
2. Record triage via `tools/apple_mcc/plan_scripts/tf_issue_create.py`.
3. Validate with `tf_validate.py` (open_unresolved_count must be 0 for green).
4. Do not weaken tests to obtain a pass.
