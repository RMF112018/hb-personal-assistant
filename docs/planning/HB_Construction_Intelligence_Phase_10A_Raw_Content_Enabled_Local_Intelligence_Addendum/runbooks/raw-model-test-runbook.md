# Raw Model Test Runbook

1. Build raw email context packet.
2. Build raw calendar context packet.
3. Run local model extraction with strict schema.
4. Validate candidate quality.

Expected improvement over metadata-only baseline:

- no `{}`;
- no generic `data_cleaning`;
- source-linked task/commitment/follow-up candidates;
- actual meeting-prep output from calendar body.
