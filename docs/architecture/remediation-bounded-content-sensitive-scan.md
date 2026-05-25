# Remediation: Bounded Content Sensitive Scanner (Prompt 10)

## Summary

Prompt 10 upgrades sensitive scanning from filename/path heuristics to bounded line-level content scanning with strict redaction in outputs.

## Scanner Behavior

- Dedicated scanner module under `src/hb_assistant/security/`.
- Scans repo root, Application Support path, and evidence path.
- Applies bounded traversal and per-file limits.
- Skips excluded noise paths (`.git`, `.venv`, caches, `__pycache__`) for false-positive control.
- Skips binary files and oversize non-high-risk files.
- High-risk extensions (`.env`, `.pem`, `.key`, `.pfx`, `.json`) are scanned even when large.

## Detection Categories

- PEM/private key headers
- JWT-like token structures
- OAuth/access token field assignments
- `client_secret` assignments
- bearer token strings
- MSAL/token cache indicators
- `.env` secret assignments

## Output Contract

- Findings include only:
  - `category`
  - `path`
  - `line`
  - `severity`
  - `rule_id`
  - optional `hint`
- Matched secret values are never emitted.
- Category aggregates are retained for backward compatibility.
