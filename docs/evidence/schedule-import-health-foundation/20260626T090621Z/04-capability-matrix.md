# Capability Matrix

Capability statuses are constrained to:

- `available`
- `partially_available`
- `unavailable`
- `not_applicable`
- `requires_companion_file`
- `requires_user_mapping`
- `conflict_detected`
- `deferred`

Capability rows are written to `schedule_source_capabilities`. Older imports without package rows return empty capability structures through health-data reads rather than failing.

Key domains covered:

- current schedule rows
- WBS/calendars/codes/UDFs
- explicit float/source driving path
- baseline assignment and rows
- baseline drift/BEI/missed tasks
- version comparison
- deferred cost/schedule correlation
