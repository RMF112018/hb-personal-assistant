# N2 · 07 — NAS Copied-DB Smoke Plan (PLAN ONLY — not executed)

For a later phase (**N3+**), gated on ALL of: schema drift fixed (N2 ✓), auth/security hardened OR
secrets explicitly excluded, public exposure confirmed safe, safe DB copy completed via backup API
(`05`), secrets strategy approved (`08`), copied DB on a NAS-local path. **Copied-DB smoke is
prohibited until explicitly authorized.**

## Preconditions (all required before smoke)

- N2 schema fix committed and on the deploy branch (head = 98).
- Backup-API copy completed + verified (`05`): integrity ok, schema head 98, row counts reconciled.
- Copied DB at `/volume1/personal-assistant/app-support/db/hb-personal-assistant.sqlite` (NAS-local).
- auth/security ACLs hardened, or secrets/Text-Vault explicitly out of scope for the smoke.
- Public exposure confirmed (firewall/router/Tailscale) — see `09`.

## Smoke procedure

1. Start the HB container against the **copied DB only** (never the live Mac DB) with:
   - NAS-local app-support (`/volume1/personal-assistant/app-support`).
   - `HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS=1`.
   - Loopback-only or tailnet-restricted bind (`127.0.0.1:8000` or `<nas-tailnet-ip>`), never `0.0.0.0` publish.
2. `GET /health` → assert `schema_version == schema_expected` (both 98) and `schema_ready true`.
3. Assert **no** workers/watchers/scheduler started (`background_worker_mode: disabled` in `/health`).
4. Assert **no** vault/source-root writes (no mounts of live vault/source; count-stable app-support).
5. Stop/down the container; confirm port 8000 freed.
6. Confirm the copied DB was **not mutated except** the expected/allowed schema migration (compare
   `schema_migrations` + key table row counts before/after; the on-open migrate to 98 is expected and,
   post-N2, a no-op since the copy is already at 98).
7. Produce N3 evidence (health payload, before/after fingerprints) — redacted, no raw content.

## Hazards addressed

Auto-migrate-on-open (`02` Q10) **will** run on first repository/app touch — post-N2 this is a no-op on
an already-98 copy, but the plan still fingerprints before/after to prove it. No secrets are read unless
`08` clears them.
