# Background worker warning disposition

## Symptom

Prior test output included:

`RuntimeWarning: coroutine '_forecast_lifespan.<locals>._quality_poll_loop' was never awaited`

## Root cause

Enabled-worker tests mocked `asyncio.create_task` with `return_value=None`, but `_quality_poll_loop()` was still instantiated and passed to `create_task` without being awaited or closed.

## Resolution

Updated `tests/test_schedule_clean_db_phase0_background_workers.py` to use a `side_effect` that calls `coro.close()` before returning `None`.

No product change to `api.py` was required; the disabled-worker path already avoids creating the poll task.

## Verification

`pytest tests/test_schedule_clean_db_phase0_background_workers.py -q` reran without the coroutine warning (see `04-background-worker-proof.txt`).
