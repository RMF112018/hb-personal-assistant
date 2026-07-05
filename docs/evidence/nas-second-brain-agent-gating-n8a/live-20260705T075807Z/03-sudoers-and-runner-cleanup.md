# 03 — Sudoers + Runner Cleanup

## A. Temporary proof runners — already revoked
Read-only check (`01` §1): no `hb-pa-proof05/06/07-runner`, driver, or `/volume2` config remains in `/usr/local/sbin`. The three temporary root-owned proof runners installed for N8 proofs 05/06/07 are **gone**. **No action required** (the committed `05a` "revocation due at closeout" is satisfied).

## B. Dead `/volume1` sudoers rule — CONFIRMED ABSENT
The N8 `05a` note flagged a dead `/volume1/personal-assistant/bin/hb-mcp-runner` sudoers rule. `bfetting` cannot list `/etc/sudoers.d/` without root, so this was confirmed via **one operator-run root command** (sudo stayed password-required — the operator entered their password interactively; no NOPASSWD grant was installed):

```
sudo grep -rns "/volume1/personal-assistant/bin/hb-mcp-runner" /etc/sudoers /etc/sudoers.d/ ; echo "rc=$?"
→ rc=1   (no match — rule absent)
```
`rc=1` (grep no-match) ⇒ **already clean; nothing to remove.** This resolves the item: the dead rule was removed at the N8 operational closeout and is confirmed gone at rest. No `visudo` edit was necessary.

## C. No N8A privileged grant installed
N8A installed **no** sudoers drop-in and **no** NOPASSWD grant. Because both remediations turned out to be no-ops (A resolved; drift resolved per `02`), the exact-command runner that was prepared for this phase was **not needed and not installed**. "Sudo remains password-required" is preserved end-to-end.

## Verdict
**A: closed** (runners already revoked). **B: closed** (dead `/volume1` sudoers rule confirmed absent, `rc=1`). **C: no new privilege added.** No residual N8A grant to revoke.
