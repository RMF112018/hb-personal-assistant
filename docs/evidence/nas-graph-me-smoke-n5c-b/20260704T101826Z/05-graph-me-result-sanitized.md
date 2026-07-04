# 05 — Graph /me Result (sanitized)

## Outcome
```
me_exit = 0
status  = ok
graph_endpoint = /v1.0/me
http_status    = 200
content_type   = application/json
```

## Account proof (names + hashes + booleans only)
```
response_keys   = <profile field NAMES only — no values>
upn_sha256_12   = <12-char sha256 prefix of userPrincipalName>
id_present         = true
mail_present       = true
displayName_present = true
raw_body_printed = false
tokens_printed   = false
```

## Interpretation
- **HTTP 200 + `application/json`** from `https://graph.microsoft.com/v1.0/me` proves the NAS-persisted delegated token
  cache is **usable** and that Graph accepted the bearer token from the NAS container. Core objective achieved.
- The presence booleans confirm a real profile document (`id`, `mail`, `displayName` present) without exposing any
  value. The UPN is represented only by a truncated sha256 (matching the account-proof style used in N5C-A).
- **No** raw profile field values, **no** tokens, **no** authorization header, **no** full response body were printed
  or committed.

## Boundary honored
Exactly **one** Graph call was made (`/v1.0/me`). No mail, calendar, drive/OneDrive, SharePoint, Procore, or vault
endpoint was touched. No pagination, no `$expand`, no follow-on requests.
