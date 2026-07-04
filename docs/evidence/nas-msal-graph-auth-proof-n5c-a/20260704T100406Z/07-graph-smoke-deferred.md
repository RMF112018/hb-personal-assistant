# 07 — Graph Smoke

**Graph smoke: deferred by design. Auth cache metadata proof only.**

No Graph API call (`/me` or otherwise) was made. Per N5C-A §14, a Graph smoke is not run by default and was not
separately authorized. The proof is limited to MSAL cache creation + least-privilege metadata.

## What was proven without a Graph call
The login result already confirms a working delegated token acquisition at the MSAL layer (`status=login_success`,
effective scopes returned). A live Graph read (e.g. `/me` profile metadata) remains available as a **separate,
explicitly-authorized** sub-proof if desired later — bounded to `/me` metadata only, no email/file/calendar content,
no raw JSON committed.

This deferral is one of the reasons N5C-A closes **WARN** rather than PASS (§17), though the auth-cache objective is
fully achieved.
