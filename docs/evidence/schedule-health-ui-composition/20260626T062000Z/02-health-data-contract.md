# Health Data Contract

Frontend client added:

```text
GET /api/schedules/versions/{schedule_version_key}/health-data?project_key={project_key}
```

Primary response fields consumed:

```text
schedule_version_key
project_key
current_schedule
import_package
capabilities
quality_summary
default_prior_version
default_version_diff
available_version_diffs
baseline_projects
baseline_health_facts
top_health_findings
deferred_domains
```

Capability statuses rendered:

```text
available
partially_available
unavailable
not_applicable
requires_companion_file
requires_user_mapping
conflict_detected
deferred
```

Legacy quality endpoint use is limited to supporting DCMA/source/GAO detail tables. The page does not synthesize Schedule Health from old quality-only or diff-only endpoints.
