# N8C-21 — schema & migration proof

Fresh empty DB migrated by `SQLiteMigrator.apply()`:

```
head == LATEST_SCHEMA_VERSION == 111
fresh-migrate object counts (excl sqlite_%): tables=548  views=2  objects=550
schema_migrations records every version V100..V111 (and all priors); head == code constant
migration is idempotent (re-apply → still 111, no table dropped/rewritten)
a row written post-migrate survives a second migrate (prior rows survive)
```

`tests/test_n8c_final_validation.py` asserts all of the above plus the consolidated N8C-table presence:
every anchor table across N8C-4 claims → N8C-5 enrichment → N8C-6 context-packs → N8C-7 memory →
N8C-8 decision/preference/open-loop → N8C-9 review → N8C-10 intelligence → N8C-11 research-packets →
N8C-14 answer-drafts → N8C-18 feedback → N8C-19 action-stage → N8C-20 quality exists in the fresh DB
(`test_all_n8c_tables_present`). Assistant-table floor ≥ 48 (`test_assistant_table_count_floor`).

`tests/test_schema_version_head_consistency.py` (pre-existing, head-agnostic) independently confirms
`test_fresh_db_migrates_to_latest_constant` and `test_recorded_head_equals_latest_constant`.
