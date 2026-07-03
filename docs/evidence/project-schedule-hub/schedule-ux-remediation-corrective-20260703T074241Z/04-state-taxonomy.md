# State taxonomy

Helper: `frontend/src/lib/scheduleDataState.ts`

## States

| State | When | User-facing message (examples) |
|-------|------|--------------------------------|
| `loading` | `isLoading \|\| isPending`, no prior data | "Loading schedule trend data…" / "Loading computed CPM status…" |
| `refreshing` | `isFetching` with prior data, or identity stale | "Refreshing schedule trend data for the selected as-of date…" |
| `no_schedule` | No imported schedule | Import prompt copy |
| `no_metric_payload` | API returned no metric body | "No trend metric payload returned…" |
| `metric_unsupported` | Metric not supported for basis | "This metric is not supported for the selected comparison basis." |
| `baseline_not_selected` | Reason mentions baseline | "Select a baseline anchor before this trend metric can be shown." |
| `cpm_not_computed` | CPM runs absent for version | "CPM has not been computed for this schedule update on the local database." |
| `api_error` | Query error | "Schedule trend data could not be loaded right now." |
| `data_stale` | Retained data identity mismatch | "Trend data is refreshing; prior values are not shown as current." |
| `ready` | Identity matches, payload available | Render chart / positive CPM status |

## Rule

**Never** show trend/CPM "unavailable" while `loading`, `refreshing`, or `data_stale`.

## Applied surfaces

- `ProjectScheduleDashboardVisualizations` — `MetricPanel` via `metricPanelUiState` + `metricPanelMessage`
- `ProjectSchedulePage` — CPM card via `cpmUnavailableLabel`
- `ScheduleControlsPanel` — fetching prop gates premature empty rendering
- `ScheduleBaselineSelector` — fetching prop

## CPM reason mapping (`cpmUnavailableLabel`)

| API reason | Message |
|------------|---------|
| `no_computed_cpm` | CPM has not been computed for this schedule update on the local database |
| `no_schedule` | Import a schedule update before CPM can be computed |
| (other) | Humanized underscore → space |

## Copied DB note

`as_of=2026-06-22` → `tropical|1069|2026-05-26 08:00` — API CPM summary `available: false` (reason-aware label, not loading flicker).  
`as_of=2026-06-29` → `tropical|1071|2026-06-23 08:00` — API CPM summary `available: true`.
