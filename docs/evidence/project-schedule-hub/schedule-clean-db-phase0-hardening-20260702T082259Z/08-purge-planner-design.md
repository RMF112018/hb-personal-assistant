# Purge planner design

`scripts/dev_clean_tropical_schedule_db.py` purges Tropical schedule rows from copied DBs only.

## Delete ordering

- FK metadata from `PRAGMA foreign_key_list`
- Supplemental map in `purge_dependency_map.py` for SQLite FK gaps
- Emits `manual_review_required` for unclassified schedule-like tables

## Safety

- Live DB always rejected
- `--apply` requires `--confirm-clean-copy`
- Preserves `procore_ep_projects` catalog rows
