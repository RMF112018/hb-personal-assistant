# Production DB Unchanged Proof

Production DB path resolved from runtime config (PathPolicy.get_db_path), not from memory.

- Path: `~/Library/Application Support/HB Personal Assistant/db/hb-personal-assistant.sqlite`
- sha256 BEFORE: `25e5bce9b9d4c8a21a5175fc1cf09aead2362ec513c03404d2df7d2327deb2d8`
- sha256 AFTER:  `25e5bce9b9d4c8a21a5175fc1cf09aead2362ec513c03404d2df7d2327deb2d8`
- size after: 253255680 bytes; mtime after: 1781026209
- **UNCHANGED: True**

All validation ran on copies (`/tmp/hb_email_followup_raw_enrichment_proof.sqlite`, `/tmp/hb_efe_seeded_proof.sqlite`). Production was read once (baseline) and copied; never written.
