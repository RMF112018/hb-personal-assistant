# DB-copy migration / backfill / idempotency proof

All work was performed against a **timestamped `/tmp` copy** of the production DB. Production
was opened read-only for the SHA only; the working DB was a `shutil.copy2` copy.

## Production DB unchanged (no mutation)

```
prod_sha256_before : f93b78081dfbbd7d40ebbfc9254227eab7d306bb08d73e8b92d76e7b33ae4759
prod_sha256_after  : f93b78081dfbbd7d40ebbfc9254227eab7d306bb08d73e8b92d76e7b33ae4759
prod_unchanged     : True
```
(SHA over file content; not a credential.)

## Schema

```
schema_head : 46          # V46 preserved — no schema change introduced by this remediation
```

## Backfill (idempotent)

```
run 1 (apply): mode=apply  raw_landing_written=30059  structured_written=30059  skipped=0
               live_procore_calls=0  external_writeback_performed=0
run 2 (apply): structured_written=30059  skipped=0     # re-run upserts in place; no duplication
invoice_items_rows_after : 13136
```

Idempotency is also covered by unit test
`test_backfill_financial_amount_is_idempotent` (re-applied backfill yields a single
`procore_raw_invoice_items` row with the same `amount`, no duplicate).

## Reproduce

```bash
cd <worktree>
TS=$(date +%Y%m%d-%H%M%S)
PYTHONPATH="$PWD/src" .venv/bin/python3.12 /tmp/hb_fin_remediation_matrix.py "$TS"
```
The script copies prod → `/tmp/hb_fin_copy_<ts>.sqlite`, migrates to V46, backfills twice,
and emits the matrix + SHA before/after. `/tmp` copies are disposable.
