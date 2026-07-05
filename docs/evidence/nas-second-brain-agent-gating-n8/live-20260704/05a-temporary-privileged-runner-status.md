# 05a — Temporary Privileged Proof-05 / 06 / 07 Runners — STATUS / SECURITY NOTE

Records the temporary privileged paths installed to run Proofs 05, 06, and 07, their current status, and the
outstanding cleanup obligations. **No sudoers cleanup has been performed** — the runners remain installed by
design as the explicit rollback paths. With all live proofs (04–07) complete, revocation is now due at N8
live-proof closeout unless explicitly retained.

## Installed components
Proof 05 (DB ingest + rollback path):
- **Runner:** `/usr/local/sbin/hb-pa-proof05-runner` (root-owned) · **Driver:** `/usr/local/sbin/hb-pa-proof05-driver.py`
- **Sudoers drop-in:** `/etc/sudoers.d/hb-pa-proof05` (root-owned, mode `0440`)

Proof 06 (one Obsidian card + rollback; separate runner so the proof-05 path stayed untouched):
- **Runner:** `/usr/local/sbin/hb-pa-proof06-runner` (root-owned) · **Driver:** `/usr/local/sbin/hb-pa-proof06-driver.py`
- **Minimal `/volume2` config:** `/usr/local/sbin/hb-pa-proof06-config.yml` (container-only `HB_PA_CONFIG`; no secrets)
- **Sudoers drop-in:** `/etc/sudoers.d/hb-pa-proof06` (root-owned, mode `0440`)

Proof 07 (duplicate-prevention; separate runner; proof-05/06 paths untouched):
- **Runner:** `/usr/local/sbin/hb-pa-proof07-runner` (root-owned) · **Driver:** `/usr/local/sbin/hb-pa-proof07-driver.py`
- **Minimal `/volume2` config:** `/usr/local/sbin/hb-pa-proof07-config.yml` (container-only `HB_PA_CONFIG`; no secrets)
- **Sudoers drop-in:** `/etc/sudoers.d/hb-pa-proof07` (root-owned, mode `0440`)

## Allowed subcommands (exact, no wildcards)
- proof05: `status` · `backup` · `ingest` · `restore`
- proof06: `card-preflight` · `backup` · `card` · `restore`
- proof07: `preflight` · `backup` · `assert-refusals` · `assert-xroot` · `restore`

Each sudoers line is an exact command with a fixed argument — no other argv is accepted. None of the drop-ins
grant `docker`, `su`, `bash`/`sh`, `cp`/`rsync`, `sqlite3`, or `python`, and none grant arbitrary `sudo -u`.
The DB stays `0600` service-owned; `bfetting` never gains direct DB read/write.

## Current status
- All three runners remain **installed but idle** after Proofs 05, 06, and 07 completed. Each is retained
  **only** as its rollback/status path (proof05 `status`/`restore`; proof06 `card-preflight`/`restore`;
  proof07 `preflight`/`restore`).
- The proof-06 `restore` WAS run once (operator-authorized) to reverse a partial-write stop condition, then
  the proof completed cleanly on retry. No `restore` is queued now; none runs without explicit authorization
  after a stop condition.

## Revocation obligation
- **All three** privileged paths **must be revoked at N8 live-proof closeout** (remove each sudoers drop-in,
  runner, driver, and the proof-06/07 configs) **unless explicitly retained** by Bobby. They are standing,
  time-bounded exceptions, not permanent grants.

## Separate, still-open item — stale `/volume1` sudoers drift
- A pre-existing sudoers entry referencing `/volume1/personal-assistant/bin/hb-mcp-runner` remains present.
  The path is absent / not writable by a non-root user, so it is a **dead rule**, not an active grant — but
  it is **drift that remains open and is tracked separately** from the Proof 05 runner. It was **not**
  modified as part of this proof.

## Cleanup performed
- **None.** No sudoers cleanup, no runner/driver removal, no `/volume1` drift remediation was performed in
  this evidence-capture pass. All are deferred to N8 live-proof closeout (or earlier, on explicit request).
