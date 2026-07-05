# 03 — Memory Class Boundaries Proof

Deliverable: `docs/architecture/n8c-memory-classes-and-boundaries.md`.

Required-content coverage:

| Required | Section |
|---|---|
| Four memory classes (immutable raw / readable archive / compiled / system records) | §1 |
| DB mutation boundary (read raw broadly; mutate only owned assistant/index/enrichment/graph tables) | §2 |
| Vault write boundary (user-authored notes processed not rewritten; only sanctioned writes) | §3 |
| `.eml` raw / DB record / archive note / source-summary-card model (all three preserved) | §4 |
| NAS-owns-identity / MacBook-Qwen-owns-execution split; manual DB triage allowance | §5 |

N8C-1 satisfies the boundaries trivially: **no schema change** (`LATEST_SCHEMA_VERSION = 99`), **no DB
row written**, **no raw source mutated**, and the only vault write remains the folder-locked
`ai_outputs_card_upsert`. No new write surface is introduced (the `domain` param is metadata-only).
