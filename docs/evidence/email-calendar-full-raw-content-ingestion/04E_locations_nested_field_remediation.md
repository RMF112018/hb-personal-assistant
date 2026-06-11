# 04E — Calendar `locations[]` Nested-Field Projection Remediation

Remediates seven Microsoft Graph calendar `locations[]` nested business fields that were
observed in production raw rows but not mapped, which made the calendar projection
completeness gate **fail closed**. Counts / paths / hashes / statuses only — no raw bodies,
join URLs, address values, coordinate values, tokens, or credentials appear in this evidence.

## The seven nested leaf fields

The locations child array (`calendar_raw_event_locations_structured`) declared the
containers `address` and `coordinates` but not their leaf paths. The completeness matrix
(`_flatten_paths`) yields each dotted leaf path, so these were classified `unmapped`:

```text
raw_sidecar_json.locations[].address.street            -> address_street
raw_sidecar_json.locations[].address.city              -> address_city
raw_sidecar_json.locations[].address.state             -> address_state
raw_sidecar_json.locations[].address.countryOrRegion   -> address_country_or_region
raw_sidecar_json.locations[].address.postalCode        -> address_postal_code
raw_sidecar_json.locations[].coordinates.latitude      -> coordinates_latitude
raw_sidecar_json.locations[].coordinates.longitude     -> coordinates_longitude
```

## Change (registry + engine only)

- `projection_registry.py` — added the seven dotted `item_fields` and the seven dotted
  `declared_item_keys` to the locations `ChildArray` (mirrors the existing `recurrence`
  child array's `pattern.type` / `range.startDate` dotted convention).
- `projection_engine.py` — `_calendar_event_values` location row builder now reads the
  nested `address` / `coordinates` sub-objects into the seven dedicated child columns.
- Schema / migrator unchanged in source: the V49 DDL is generated from the registry and the
  V49 column reconciliation runs unconditionally, so the seven additive columns are created
  on fresh DBs and `ALTER TABLE ADD COLUMN`-reconciled onto existing V49 DBs automatically.
- `raw_sidecar_json` lossless preservation unchanged; join-URL policy unchanged
  (`join_url` remains `excluded_policy_blocked`; the parent carries only `has_join_url`).

## Lane 1 — Pristine production-copy proof

Production DB resolved from `PathPolicy().get_db_path()` (plain app-support root). A fresh
`/tmp` copy was made; migration/reconciliation and projection ran against the **copy only**.

```text
production DB path:   ~/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite
production sha256 (before & after):  74452bd8143e85fe714fa7f3e0be59f1f319f8de6162c5d0700c9ebb89a4323e
production size  (before & after):   489226240 bytes
production mtime (before & after):   1781170501708092358 ns
production DB unchanged during validation:  TRUE  (sha256 + size + mtime identical)
/tmp copy schema head: 49 -> 49  (unconditional V49 reconcile applied to the COPY only)
seven additive columns present on calendar_raw_event_locations_structured after reconcile: TRUE
```

### Before vs after on the live production copy

The current production DB already contains calendar location objects carrying populated
`address` / `coordinates` — so this is an active gate failure, not a forward-looking one:

```text
                          coverage.ok   total_unmapped   calendar unmapped_nested   calendar status
PRE-change registry        FALSE             7                   7                   failed_unmapped_fields
POST-change registry       TRUE              0                   0                   complete_with_policy_exclusions

PRE-change unmapped_nested_samples (exactly the seven leaves):
  raw_sidecar_json.locations[].address.street
  raw_sidecar_json.locations[].address.city
  raw_sidecar_json.locations[].address.state
  raw_sidecar_json.locations[].address.countryOrRegion
  raw_sidecar_json.locations[].address.postalCode
  raw_sidecar_json.locations[].coordinates.latitude
  raw_sidecar_json.locations[].coordinates.longitude
```

Under the committed registry, enforce-mode reprocess raises `UnknownProjectionPath` for
`calendar_event`; after the remediation it succeeds.

### Coverage + projection on the copy (post-change)

```text
calendar_event raw parent rows:        138
calendar_event projected parent rows:  138
calendar location child rows:           93
reprocess (enforce, apply on copy):    ok=True, no UnknownProjectionPath
```

### Populated nested leaves in current production (counts only)

```text
locations with populated address_street / city / state / country_or_region / postal_code:  6 each
locations with populated coordinates_latitude / longitude:                                  4 each
distinct calendar events with >=1 populated address/coordinate location:                    6
```

All seven leaves now route to dedicated `child_table_column` destinations (see
`email_calendar_projection_matrix.csv`); the remaining locations carry NULL for these
columns, with zero unmapped fields.

## Lane 2 — Synthetic deterministic fixture proof

`tests/test_email_calendar_structured_projection_remediation.py` seeds a calendar event whose
`raw_sidecar_json.locations[]` carries `address` (street/city/state/countryOrRegion/postalCode)
and `coordinates` (latitude/longitude). It asserts all seven fields project into
`calendar_raw_event_locations_structured`, that `unmapped_nested_business_fields == 0`, and that
enforce-mode reprocess does not raise `UnknownProjectionPath`.

## Validation scope separation

```text
fixture validation:      tests/test_email_calendar_structured_projection_remediation.py (synthetic)
/tmp DB-copy validation: prod copy at /tmp; reconcile + coverage + reprocess; prod sha256/size/mtime unchanged
production rollout:      operator-controlled; structured projection NOT applied to production here
```
