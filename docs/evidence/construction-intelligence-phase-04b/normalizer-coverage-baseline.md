# Phase 04B Prompt 00 — Normalizer Coverage Baseline

> Source of truth: repo normalizers (declared verbatim key tuples) diffed against the observed
> raw top-level field names in [`payload-field-inventory.json`](./payload-field-inventory.json).
> **Names only — no raw values.** `HEAD` = `48dbcc4c3de09c02cd797289c8fd048f9b8a3347`.

## Method

- **verbatim** — raw top-level key present in the normalizer's `*_CANONICAL_FIELD_KEYS` / `*_STRUCTURED_KEYS` tuple → persisted as a structured field inside `canonical_json_redacted`.
- **summary/derived** — key reduced to a `*_summary` (SHA-256 hash-only for free text/people) or a count, or derived (e.g. `source_url`). Present but not structured-verbatim.
- **not-yet-normalized** — raw top-level key observed in the payload but neither in the verbatim tuple nor a known summary input → **enrichment candidate for Phase 04B**.

Coverage ratio counts only **top-level** raw keys (nested object/array sub-paths are summarized or dropped wholesale today). Endpoints sourced from `normalizer_source` had **0 live records** in the operator capture, so their raw surface is the normalizer contract itself (ratio = 1.0 by construction; real raw surface to be re-confirmed when records exist).

## Coverage summary (top-level keys)

| Endpoint | Source | Raw top-level | Verbatim | Summary/derived | Not-yet-normalized | Verbatim ratio |
|---|---|---|---|---|---|---|
| `activities` | local | 31 | 28 | 1 | 2 | 0.90 |
| `daily-log-dcrs` | normalizer | 25 | 24 | 1 | 0 | 0.96 |
| `daily-log-delays-review-routed` | normalizer | 9 | 6 | 3 | 0 | 0.67 |
| `daily-log-deliveries` | normalizer | 9 | 9 | 0 | 0 | 1.00 |
| `daily-log-inspections` | normalizer | 9 | 7 | 2 | 0 | 0.78 |
| `daily-log-manpower` | normalizer | 8 | 8 | 0 | 0 | 1.00 |
| `daily-log-notes` | normalizer | 8 | 5 | 3 | 0 | 0.62 |
| `daily-log-weather` | normalizer | 10 | 10 | 0 | 0 | 1.00 |
| `inspection-items` | local | 22 | 12 | 1 | 9 | 0.55 |
| `inspection-sections` | local | 5 | 5 | 0 | 0 | 1.00 |
| `inspections` | local | 48 | 24 | 10 | 14 | 0.50 |
| `meeting-detail` | local | 21 | 15 | 4 | 2 | 0.71 |
| `meeting-topics` | local | 13 | 4 | 4 | 5 | 0.31 |
| `meetings` | local | 19 | 1 | 1 | 17 | 0.05 |
| `observations` | local | 25 | 8 | 4 | 13 | 0.32 |
| `projects` | local | 46 | 7 | 2 | 37 | 0.15 |
| `punch-items` | local | 40 | 20 | 9 | 11 | 0.50 |
| `rfi-responses` | local | 8 | 1 | 2 | 5 | 0.12 |
| `rfis` | local | 40 | 7 | 5 | 28 | 0.17 |
| `schedules` | local | 16 | 16 | 0 | 0 | 1.00 |
| `submittal-packages` | normalizer | 6 | 6 | 0 | 0 | 1.00 |
| `submittal-responses` | normalizer | 5 | 5 | 0 | 0 | 1.00 |
| `submittals` | local | 39 | 8 | 4 | 27 | 0.21 |

## Per-endpoint detail

### `activities`  ·  source=local_raw_inspect  ·  observed_records=1  ·  raw_field_paths=31

- **verbatim (28)**: `activity_id`, `activity_name`, `assigned_company`, `calendar_id`, `company_id`, `constraint_date`, `constraint_type`, `created_at`, `created_by`, `crew_size`, `deadline_date`, `deadline_variance`, `duration`, `duration_display_unit`, `duration_unit`, `finish_date`, `is_actual_finish`, `is_actual_start`, `is_critical`, `ordered_parent_index`, `parent_id`, `percent_complete`, `project_id`, `schedule_id`, `start_date`, `total_float`, `updated_at`, `updated_by`
- **summary/derived (1)**: `notes`
- **not-yet-normalized (2)**: `category_data`, `resource_data`

### `daily-log-dcrs`  ·  source=normalizer_source  ·  observed_records=0  ·  raw_field_paths=25

- **verbatim (24)**: `apprentice_hours`, `created_at`, `date`, `datetime`, `first_year_hours`, `foreman_hours`, `id`, `journeyman_hours`, `local_city_hours`, `local_county_hours`, `location`, `minority_hours`, `number_of_apprentice_workers`, `number_of_foreman_workers`, `number_of_journeyman_workers`, `number_of_other_workers`, `other_hours`, `position`, `status`, `trade`, `updated_at`, `vendor`, `veteran_hours`, `women_hours`
- **summary/derived (1)**: `notes`
- **not-yet-normalized (0)**: —

### `daily-log-delays-review-routed`  ·  source=normalizer_source  ·  observed_records=0  ·  raw_field_paths=9

- **verbatim (6)**: `date`, `delay_type`, `id`, `impact_days`, `status`, `updated_at`
- **summary/derived (3)**: `cause`, `description`, `safety_violation`
- **not-yet-normalized (0)**: —

### `daily-log-deliveries`  ·  source=normalizer_source  ·  observed_records=0  ·  raw_field_paths=9

- **verbatim (9)**: `contractor_id`, `date`, `id`, `location`, `quantity`, `status`, `unit`, `updated_at`, `vendor_id`
- **summary/derived (0)**: —
- **not-yet-normalized (0)**: —

### `daily-log-inspections`  ·  source=normalizer_source  ·  observed_records=0  ·  raw_field_paths=9

- **verbatim (7)**: `date`, `id`, `inspection_type`, `inspector_id`, `location`, `status`, `updated_at`
- **summary/derived (2)**: `comments`, `description`
- **not-yet-normalized (0)**: —

### `daily-log-manpower`  ·  source=normalizer_source  ·  observed_records=0  ·  raw_field_paths=8

- **verbatim (8)**: `contractor_id`, `date`, `hours`, `id`, `location`, `updated_at`, `vendor_id`, `workers`
- **summary/derived (0)**: —
- **not-yet-normalized (0)**: —

### `daily-log-notes`  ·  source=normalizer_source  ·  observed_records=0  ·  raw_field_paths=8

- **verbatim (5)**: `author_id`, `date`, `id`, `location`, `updated_at`
- **summary/derived (3)**: `body`, `comments`, `note`
- **not-yet-normalized (0)**: —

### `daily-log-weather`  ·  source=normalizer_source  ·  observed_records=0  ·  raw_field_paths=10

- **verbatim (10)**: `average_temperature`, `conditions`, `date`, `high_temperature`, `humidity`, `id`, `low_temperature`, `precipitation`, `updated_at`, `wind_speed`
- **summary/derived (0)**: —
- **not-yet-normalized (0)**: —

### `inspection-items`  ·  source=local_raw_inspect  ·  observed_records=1  ·  raw_field_paths=46

- **verbatim (12)**: `id`, `list_id`, `name`, `number`, `parent_item_id`, `position`, `relative_position`, `responded_with`, `section_id`, `status`, `template_item_id`, `updated_at`
- **summary/derived (1)**: `item_response`
- **not-yet-normalized (9)**: `company_template_item_details`, `details`, `display_conditions`, `evidence_configuration`, `item_reference_ids`, `response`, `response_set`, `signature_request_ids`, `type`

### `inspection-sections`  ·  source=local_raw_inspect  ·  observed_records=1  ·  raw_field_paths=5

- **verbatim (5)**: `id`, `name`, `position`, `template_section_id`, `updated_at`
- **summary/derived (0)**: —
- **not-yet-normalized (0)**: —

### `inspections`  ·  source=local_raw_inspect  ·  observed_records=1  ·  raw_field_paths=64

- **verbatim (24)**: `closed_at`, `closed_observations_count`, `conforming_item_count`, `created_at`, `deficient_item_count`, `deleted`, `due_at`, `id`, `inspected_item_count`, `inspection_date`, `item_count`, `list_template_id`, `list_template_name`, `managed_equipment_id`, `name`, `neutral_item_count`, `not_applicable_item_count`, `number`, `observations_count`, `overdue`, `private`, `status`, `template_id`, `updated_at`
- **summary/derived (10)**: `attachments`, `closed_by`, `created_by`, `custom_fields`, `description`, `distribution_members`, `inspectors`, `point_of_contact`, `responsible_contractor`, `signature_requests`
- **not-yet-normalized (14)**: `asset_ids`, `current_drawing_revision_ids`, `default_response_phrasing`, `drawing_ids`, `equipment_id`, `identifier`, `inspection_type`, `location`, `reinspected_by_id`, `reinspected_from_id`, `respondable_item_count`, `schedule`, `specification_section`, `trade`

### `meeting-detail`  ·  source=local_raw_inspect  ·  observed_records=1  ·  raw_field_paths=44

- **verbatim (15)**: `created_at`, `created_by_id`, `ends_at`, `id`, `is_draft`, `is_private`, `location`, `meeting_template_id`, `mode`, `occurred`, `position`, `starts_at`, `time_zone`, `title`, `updated_at`
- **summary/derived (4)**: `attachments`, `conclusion`, `description`, `meeting_categories`
- **not-yet-normalized (2)**: `attendees`, `remote_meeting_url`

### `meeting-topics`  ·  source=local_raw_inspect  ·  observed_records=20  ·  raw_field_paths=19

- **verbatim (4)**: `due_date`, `id`, `status`, `title`
- **summary/derived (4)**: `assignments`, `attachments`, `description`, `minutes`
- **not-yet-normalized (5)**: `created_on`, `meeting_category`, `number`, `position`, `priority`

### `meetings`  ·  source=local_raw_inspect  ·  observed_records=31  ·  raw_field_paths=22

- **verbatim (1)**: `title`
- **summary/derived (1)**: `description`
- **not-yet-normalized (17)**: `created_at`, `created_by_id`, `distributed_at`, `distributed_by`, `ends_at`, `id`, `is_private`, `last_distributed_event`, `location`, `meeting_template_id`, `meeting_topics_count`, `mode`, `occurred`, `parent_id`, `position`, `starts_at`, `updated_at`

### `observations`  ·  source=local_raw_inspect  ·  observed_records=1  ·  raw_field_paths=62

- **verbatim (8)**: `closed_at`, `created_at`, `due_date`, `number`, `priority`, `status`, `type`, `updated_at`
- **summary/derived (4)**: `assignees`, `created_by`, `custom_fields`, `description`
- **not-yet-normalized (13)**: `assignee`, `category`, `date_notified`, `deleted_at`, `description_rich_text`, `id`, `location`, `name`, `origin`, `permissions`, `personal`, `specification_section`, `trade`

### `projects`  ·  source=local_raw_inspect  ·  observed_records=1  ·  raw_field_paths=59

- **verbatim (7)**: `active`, `display_name`, `id`, `name`, `project_number`, `stage`, `updated_at`
- **summary/derived (2)**: `created_by`, `custom_fields`
- **not-yet-normalized (37)**: `accounting_project_number`, `address`, `city`, `company`, `completion_date`, `country_code`, `county`, `created_at`, `delivery_method`, `designated_market_area`, `estimated_value`, `is_demo`, `latitude`, `longitude`, `origin_code`, `origin_data`, `origin_id`, `owners_project_id`, `parent_job`, `parent_job_id`, `phone`, `photo_id`, `project_bid_type_id`, `project_owner_type_id`, `project_region_id`, `project_sector_id`, `project_stage`, `project_template`, `projected_finish_date`, `sector`, `start_date`, `state_code`, `store_number`, `time_zone`, `total_value`, `work_scope`, `zip`

### `punch-items`  ·  source=local_raw_inspect  ·  observed_records=1  ·  raw_field_paths=97

- **verbatim (20)**: `closed_at`, `cost_impact`, `cost_impact_amount`, `created_at`, `deleted_at`, `due_date`, `has_resolved_responses`, `has_unresolved_responses`, `id`, `name`, `position`, `priority`, `private`, `reference`, `schedule_impact`, `schedule_impact_days`, `schedule_risk`, `status`, `updated_at`, `workflow_status`
- **summary/derived (9)**: `assignees`, `assignments`, `ball_in_court`, `closed_by`, `created_by`, `custom_fields`, `description`, `final_approver`, `punch_item_manager`
- **not-yet-normalized (11)**: `cost_code`, `due_tomorrow`, `flagged_by`, `has_attachments`, `location`, `manager_notified_at`, `overdue`, `punch_item_type`, `schedule_risk_reason`, `should_display_risk_flag`, `trade`

### `rfi-responses`  ·  source=local_raw_inspect  ·  observed_records=1  ·  raw_field_paths=8

- **verbatim (1)**: `id`
- **summary/derived (2)**: `attachments`, `created_by`
- **not-yet-normalized (5)**: `answer_date`, `created_by_id`, `official`, `plain_text_body`, `rich_text_body`

### `rfis`  ·  source=local_raw_inspect  ·  observed_records=1  ·  raw_field_paths=69

- **verbatim (7)**: `created_at`, `due_date`, `initiated_at`, `number`, `status`, `subject`, `updated_at`
- **summary/derived (5)**: `assignees`, `ball_in_court`, `created_by`, `custom_fields`, `responsible_contractor`
- **not-yet-normalized (28)**: `assignee`, `ball_in_courts`, `connect_export_origin`, `cost_code`, `cost_impact`, `current_revision`, `full_number`, `has_revisions`, `id`, `link`, `location`, `location_id`, `prefix`, `priority`, `private`, `project_stage`, `proposed_solution`, `questions`, `received_from`, `reference`, `revision`, `rfi_manager`, `schedule_impact`, `source_rfi_header_id`, `specification_section_id`, `sub_job`, `time_resolved`, `translated_status`

### `schedules`  ·  source=local_raw_inspect  ·  observed_records=1  ·  raw_field_paths=16

- **verbatim (16)**: `calendar_id`, `company_id`, `created_at`, `created_by`, `data_date`, `deleted_at`, `deleted_by`, `is_active`, `parent_schedule_id`, `project_id`, `schedule_id`, `schedule_name`, `schedule_type`, `start_date`, `updated_at`, `updated_by`
- **summary/derived (0)**: —
- **not-yet-normalized (0)**: —

### `submittal-packages`  ·  source=normalizer_source  ·  observed_records=0  ·  raw_field_paths=6

- **verbatim (6)**: `created_at`, `id`, `number`, `status`, `title`, `updated_at`
- **summary/derived (0)**: —
- **not-yet-normalized (0)**: —

### `submittal-responses`  ·  source=normalizer_source  ·  observed_records=0  ·  raw_field_paths=5

- **verbatim (5)**: `author_id`, `created_at`, `id`, `response_status`, `updated_at`
- **summary/derived (0)**: —
- **not-yet-normalized (0)**: —

### `submittals`  ·  source=local_raw_inspect  ·  observed_records=1  ·  raw_field_paths=107

- **verbatim (8)**: `created_at`, `due_date`, `number`, `specification_section`, `status`, `title`, `type`, `updated_at`
- **summary/derived (4)**: `ball_in_court`, `created_by`, `custom_fields`, `responsible_contractor`
- **not-yet-normalized (27)**: `approvers`, `attachments_count`, `buffer_time`, `closed_at`, `current_revision`, `distributed_at`, `for_record_only`, `formatted_number`, `id`, `is_rejected`, `issue_date`, `location`, `open_date`, `operation_item_errors`, `private`, `received_date`, `received_from`, `rejected_submittal_log_approver_id`, `required_on_site_date`, `revision`, `scheduled_task`, `sub_job`, `submit_by`, `submittal_manager`, `submittal_package`, `submittal_workflow_template`, `submittal_workflow_template_applied_at`

## Phase 04B enrichment inputs (from gaps above)

The Phase 04B objective (people/company/location/attachment/custom-field entities, relationship
edges, action signals, endpoint projections) maps onto the **not-yet-normalized** and
**summary/derived** columns. Highest-yield raw surfaces currently reduced or dropped:

- **People/company entities** — `assignees`, `ball_in_court`, `created_by`, `closed_by`,
  `point_of_contact`, `responsible_contractor`, `inspectors`, `distribution_members` (hashed today; Phase 04B wants entity rows + edges).
- **Attachments** — `attachments`, `signature_requests` (count-only today; Phase 04B wants attachment entities).
- **Custom fields** — `custom_field_*` (hashed/preserved per type today; Phase 04B wants typed custom-field entities).
- **Locations / trades / spec sections** — nested objects preserved verbatim but not projected as entities.
- **Nested child collections** — `responses`, `replies`, `histories`, `attachment_histories`,
  `item_response`, `meeting_categories[].meeting_topic[]` (summarized today; Phase 04B wants timeline/change events).

## History / memory gap (schema)

`migrator.py` V6 persists **latest-state only** (`procore_live_records` upsert; single
`canonical_json_redacted` column). There is **no** history, snapshot, change-event, or timeline
table, and `procore_repositories.py` exposes no history-tracking function. Phase 04B's
historical-memory workstream requires a new additive migration (V7+) plus repository functions —
none of which exist at this baseline.
