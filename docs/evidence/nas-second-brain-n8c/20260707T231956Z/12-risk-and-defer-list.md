# N8C-21 — risk & defer list

## Deferred (explicitly out of scope; require separate authorization)
- **NAS deployment** — service restart, container redeploy, production migration, prod-DB mutation, Cloudflare
  tunnel/exposure change, credential/token rotation. DOCUMENTED as operator commands (`08-...md`); not run here.
- **Live LLM-client pass** — the over-the-tunnel validation is an operator step (`09-...md`); the local
  read-only analogue is proven now.
- **N8C-13 operator UI / command center** — still deferred, no branch.
- **N8D** — bridge/job tables, code-agent execution, model-adapter selection, run orchestration, escalation,
  workspace-cache, implementation-agent runners. Not touched.
- **MEMORY.md compaction** — a separate deferred pass (still under the hard limit); not mixed into this
  deliverable.

## Residual risks (low)
- `validate-db.sh` expected object counts (548/2/550) are the deterministic FRESH-migrate counts; a production
  DB that has diverged (manual objects) would WARN/FAIL there — intended, and all counts are env-overridable.
- Smoke tolerates per-group list-tool NAME drift (the 78-tool inventory count is the authoritative check), so a
  renamed list tool would silently skip its read line but still be caught by the inventory test.

## Commit posture
N8C-21 is implemented, validated, and evidenced but **UNCOMMITTED** (working tree), per instruction. No push,
no PR, no merge.
