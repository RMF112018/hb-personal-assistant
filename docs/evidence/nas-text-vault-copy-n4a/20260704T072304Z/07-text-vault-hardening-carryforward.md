# 07 — Text Vault Hardening Carry-Forward

## Fail-open hazard (from N4, still present in code)
`src/hb_assistant/security/text_vault.py`:
- `_key()` **silently generates a new Fernet key** when the key file is absent and `HB_TEXT_VAULT_KEY` is unset.
- `decrypt_text` returns `None` on missing key/blob/`InvalidToken` — no error surfaced.
- No code validates key↔blob↔DB coherence; the "move key+blobs+DB together" invariant is documentation-only.

Because N4A has now installed the real key + blobs on the NAS, the immediate risk is mitigated for this host — but
the code-level hazard remains for any future bring-up.

## Recommended hardening (future work; NOT done this phase)
1. **Fail closed when refs exist but material is absent:** if the DB contains encrypted refs and no key file /
   `HB_TEXT_VAULT_KEY` is present, refuse to auto-generate a key; raise/report incoherence instead.
2. **Explicit coherence check command/tool:** promote the count-based ref↔blob existence check used in N4/N4A into a
   supported CLI/readiness probe (e.g. surfaced by `/health` or a `hb-assistant vault check`), so incoherence is
   observable rather than silent.
3. **Guard accidental key generation against migrated DB roots:** before backend production cutover, assert that the
   app-support root's key decrypts a sample of existing blobs (no-print), and abort startup on mismatch.
4. **Startup guard before cutover:** wire the above into the FastAPI startup (or a pre-start check) so a
   misconfigured/keyless NAS bring-up fails fast instead of minting a new key and orphaning bodies.

These are carried into N5 planning; N4A does not modify code.
