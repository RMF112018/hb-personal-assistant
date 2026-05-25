# Token Cache Location and Encryption Decision

## 1. Decision Summary
Decision:
- Primary cache location: `~/Library/Application Support/HB Daily Brief/auth/msal-token-cache.bin`
- MVP protection method: MSAL serializable token cache with strict filesystem permissions.
- Hardening path: add Keychain-backed encryption/wrapping only after validating launchd/headless reliability on Bobby’s machine.

Rationale:
- Best balance of macOS convention, user scoping, accidental-commit prevention, CLI ergonomics, and launchd compatibility.

## 2. Requirements
Token cache must:
- stay outside git repo;
- be user-scoped to Bobby local account;
- use restrictive permissions;
- be easy to clear via CLI;
- avoid leaking into Obsidian content;
- support delegated Bobby-user auth and optional isolated app-only cache;
- remain operational for CLI and launchd background runs.

## 3. Candidate Locations Evaluated
| Candidate | macOS Convention Fit | Security Posture | Discoverability/Cleanup | Commit Risk | launchd/CLI Suitability | MSAL Persistence Fit | Notes |
|---|---|---|---|---|---|---|---|
| `~/.hb-daily-brief/auth/` | Medium | High with `700/600` | High | Low | High | High | Hidden-dot dir is practical but less standard than Application Support. |
| `~/Library/Application Support/HB Daily Brief/auth/` | **High** | **High** with `700/600` | High | **Very Low** | **High** | **High** | Recommended macOS-native app state location. |
| `~/Library/Containers/<app-id>/...` | Low (for non-sandbox CLI) | Medium-High | Low | Very Low | Medium | Medium | Better for sandboxed app bundles, not current CLI/tooling posture. |
| `./.local/auth/` | Low (prod) / High (dev) | Medium | High | **High** | Medium | High | Dev-only; easy accidental commit if ignore rules drift. |

## 4. Candidate Encryption / Protection Methods Evaluated
| Method | Security | Complexity | launchd/Headless Reliability | Debug Burden | Portability | Decision |
|---|---|---|---|---|---|---|
| MSAL cache + file permissions only | Medium-High | Low | **High** | Low | High | **MVP selected** |
| MSAL extensions/platform persistence (Python) | Medium-High | Medium | Medium (platform nuances) | Medium | Medium | Secondary option after controlled validation |
| Python `keyring` + macOS Keychain | High | Medium-High | Medium (can be session/keychain-state sensitive) | Medium-High | Medium | Future hardening candidate |
| Custom encryption key in Keychain + encrypted cache file | High | High | Medium | High | Medium | Future hardening candidate |
| No persistent cache | Highest token-at-rest minimization | Low | High | Medium (frequent login) | High | Not selected for MVP usability |

## 5. Recommended Token Cache Location
Primary:
- `~/Library/Application Support/HB Daily Brief/auth/msal-token-cache.bin`

Recommended state layout:
- `~/Library/Application Support/HB Daily Brief/auth/`
- `~/Library/Application Support/HB Daily Brief/config/`
- `~/Library/Application Support/HB Daily Brief/db/`
- `~/Library/Application Support/HB Daily Brief/cache/`
- `~/Library/Application Support/HB Daily Brief/logs/`
- `~/Library/Application Support/HB Daily Brief/evidence/`

Optional isolation:
- Delegated cache: `.../auth/msal-token-cache.bin`
- App-only cache (if needed): `.../auth/msal-token-cache-app.bin`

## 6. Recommended Encryption / Protection Method
MVP:
- Use MSAL serializable token cache file.
- Protect with strict local permissions (`700` directories, `600` files).

Hardening track:
- Evaluate Keychain-backed wrapping in a controlled follow-up prompt.
- Accept Keychain integration only if it remains stable under launchd/headless jobs.
- If Keychain causes headless instability, retain permission-hardened cache and document residual risk.

## 7. File Permission Standard
Expected ownership and permissions:
- Owner: `bobbyfetting`
- Group: `staff` (or local default primary group)
- Directories: `700`
- Token cache files: `600`

Validation commands:
```bash
BASE="$HOME/Library/Application Support/HB Daily Brief"
stat -f "%Sp %Su %Sg %N" "$BASE" "$BASE/auth" "$BASE/auth/msal-token-cache.bin"
```

Remediation commands:
```bash
BASE="$HOME/Library/Application Support/HB Daily Brief"
chmod 700 "$BASE" "$BASE/auth"
chmod 600 "$BASE/auth/msal-token-cache.bin"
```

## 8. Cache Clear / Logout Behavior
Required future CLI behaviors:
- `hb-brief auth status`
- `hb-brief auth login`
- `hb-brief auth logout`
- `hb-brief auth clear-cache`
- `hb-brief diagnostics auth`

Expected behavior definitions:
- `auth logout`: revoke session where possible and remove active account token entries.
- `auth clear-cache`: remove local cache files from `auth/` and confirm deletion.
- `diagnostics auth`: report cache-path, perms, token-classification capability, and safe connectivity checks (no token output).

## 9. launchd Compatibility Notes
- File-permission cache strategy is launchd-friendly and does not require interactive Keychain unlock flows.
- Keychain-backed methods may require additional entitlement/session handling depending on execution context.
- For unattended runs, prefer non-interactive cache read/write paths with strict filesystem controls first.

## 10. Backup / Retention Notes
- Application Support content may be included in system backups by default.
- Recommendation: minimize retention of auth artifacts and allow explicit cache purge via CLI.
- Consider excluding `.../auth/` from backups if operational policy permits.

## 11. Risks and Mitigations
1. Token cache theft from local disk.
- Mitigation: strict permissions, user account hardening, optional future encryption.

2. Accidental repository inclusion.
- Mitigation: keep cache outside repo + `.gitignore` safety patterns.

3. Headless instability with Keychain integration.
- Mitigation: keep MVP on permission-hardened MSAL file cache; validate Keychain in a separate test phase.

4. Mixed delegated/app-only token confusion.
- Mitigation: use separate cache files/namespaces and explicit token classification in diagnostics.

## 12. Implementation Guidance for Later Prompts
- Implement a cache manager module that centralizes cache paths and permission enforcement.
- Enforce path defaults to `~/Library/Application Support/HB Daily Brief/auth/`.
- Add startup diagnostics that fail fast on weak permissions.
- Add delegated vs app-only cache isolation switch.
- Keep all logs token-redacted by default.

## 13. Decision Record
- Date: 2026-05-25
- Decider: Local agent execution for Bobby’s local-first MVP
- Status: Accepted for MVP
- Revisit trigger:
  - when launchd jobs are introduced, or
  - when enterprise hardening requires Keychain-backed encryption at rest.
