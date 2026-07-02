# Artifact scanner design

`scripts/dev_schedule_evidence_artifact_scan.py` scans PM-facing evidence for leaks and unsafe language.

## Default posture

Fail-closed: unknown files are PM-facing unless listed in `artifact_scan_allowlist.json`.

## Detects

- Raw schedule keys and DB paths
- Tracebacks and absolute source paths
- Causation language and stale readiness claims
