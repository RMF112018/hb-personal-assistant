# Import preview mutation finding

## Classification

Schedule import preview is **db_neutral** for schedule data rows on the tested fixture (`minimal_schedule.xml`).

Preview does not insert into `schedule_file_imports` or activity tables before commit.

## Side effects

`ensure_schedule_schema()` may still migrate schema on preview when the DB is behind — this is separate from schedule row mutation and should be tracked in full validation evidence.

## Commit

No commit was executed in this probe (`commit_executed: false`).
