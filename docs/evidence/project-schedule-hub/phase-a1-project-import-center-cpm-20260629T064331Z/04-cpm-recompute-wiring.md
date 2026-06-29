# CPM recompute wiring

```
ScheduleImportService.commit()
  → persist import + identity + quality queue
  → ScheduleCpmRecomputeService.recompute(schedule_version_key)
       → run_graph_diagnostics
       → run_forward_pass
       → run_backward_pass
       → run_float_calculation
       → run_longest_path
       → run_criticality_classification
  → return cpm_recompute_* fields on commit response
```

Project pipeline retry: `POST /api/projects/{key}/schedule/imports/{import_id}/recompute-cpm`

Failure handling: CPM exceptions do not roll back committed import; status surfaces `failed` / `partial`.