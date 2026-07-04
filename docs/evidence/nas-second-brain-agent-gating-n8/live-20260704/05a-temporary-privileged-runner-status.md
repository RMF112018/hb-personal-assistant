# 05a — Temporary Privileged Proof-05 Runner — STATUS / SECURITY NOTE

Records the temporary privileged path installed to run Proof 05, its current status, and the outstanding
cleanup obligations. **No sudoers cleanup has been performed** — the runner remains installed by design as
the explicit rollback path pending Proof 06/07.

## Installed components
- **Runner:** `/usr/local/sbin/hb-pa-proof05-runner` (root-owned)
- **Driver:** `/usr/local/sbin/hb-pa-proof05-driver.py` (root-owned; runs inside the pinned container as the service uid)
- **Sudoers drop-in:** `/etc/sudoers.d/hb-pa-proof05` (root-owned, mode `0440`)

## Allowed subcommands (exact, no wildcards)
`status` · `backup` · `ingest` · `restore`

Each sudoers line is an exact command with a fixed argument — no other argv is accepted. The drop-in does
**not** grant `docker`, `su`, `bash`/`sh`, `cp`/`rsync`, `sqlite3`, or `python`, and grants **no** arbitrary
`sudo -u`. The DB stays `0600` service-owned; `bfetting` never gains direct DB read/write.

## Current status
- The runner remains **installed but unused** after Proof 05 completed. It is retained **only** as the
  rollback/status path (`status` for read-only inspection, `restore` for rollback from the Proof 05 backup)
  pending Proof 06 and Proof 07.
- `restore` has **not** been run and must not be run unless explicitly authorized after a stop condition.

## Revocation obligation
- This privileged path **must be revoked at N8 live-proof closeout** (remove the sudoers drop-in, runner,
  and driver) **unless explicitly retained** by Bobby. Its continued existence is a standing, time-bounded
  exception, not a permanent grant.

## Separate, still-open item — stale `/volume1` sudoers drift
- A pre-existing sudoers entry referencing `/volume1/personal-assistant/bin/hb-mcp-runner` remains present.
  The path is absent / not writable by a non-root user, so it is a **dead rule**, not an active grant — but
  it is **drift that remains open and is tracked separately** from the Proof 05 runner. It was **not**
  modified as part of this proof.

## Cleanup performed
- **None.** No sudoers cleanup, no runner/driver removal, no `/volume1` drift remediation was performed in
  this evidence-capture pass. All are deferred to N8 live-proof closeout (or earlier, on explicit request).
