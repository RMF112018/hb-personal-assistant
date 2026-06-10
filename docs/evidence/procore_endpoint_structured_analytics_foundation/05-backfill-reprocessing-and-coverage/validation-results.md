# Validation Results

Copied-DB backfill reprocessed all existing `procore_live_records` rows into raw landing plus
structured endpoint-family rows. Reprocessing did not make live Procore calls. The coverage gate is
based on structured rows, not raw payload rows.
