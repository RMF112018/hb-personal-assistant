# Addendum Correction Register

## ADD-P0-001 — Ruff lint failure in security scanner

### Problem

`ruff check .` fails due:

- unsorted imports in `src/hb_assistant/security/__init__.py`;
- unused `os` import in `src/hb_assistant/security/sensitive_scan.py`.

### Required Correction

Run Ruff auto-fix or manually fix the two violations.

### Acceptance Criteria

- `ruff check .` exits `0`.
- No Ruff suppressions are added for these trivial issues.

---

## ADD-P0-002 — Application Support permission handling blocks auth/Graph/proof

### Problem

Auth and Graph commands fail with:

```text
Operation not permitted: '/Users/bobbyfetting/Library/Application Support/HB Personal Assistant'
```

The code attempts to chmod the full Application Support root during token cache manager initialization.

### Required Correction

1. Harden `PathPolicy.ensure_dirs()`:
   - only strict-fail on the auth directory when strict mode is explicitly requested;
   - treat parent Application Support chmod failures as warnings;
   - avoid failing `auth status` before it can return diagnostics.
2. Harden `TokenCacheManager`:
   - initialize safely even when repair is required;
   - return structured status errors instead of raising raw `PermissionError`.
3. Add path diagnostics/repair command:
   - report owner, mode, writable status, ACL indicator where possible;
   - support dry-run repair output;
   - optionally support explicit repair if safe.

### Acceptance Criteria

- `hb-assistant auth status --json` returns valid JSON and does not traceback.
- `hb-assistant diagnostics graph --safe --json` returns valid JSON; it may report no token, but not a chmod error.
- `hb-assistant diagnostics proof delegated-graph --json` can reach token availability checks without path-permission crash.

---

## ADD-P0-003 — SQLite DB open blocker

### Problem

`files ingest --dry-run` and `run morning --dry-run` fail with:

```text
OperationalError: unable to open database file
```

### Required Correction

1. Add DB readiness checks before `sqlite3.connect()`.
2. Ensure DB parent exists and is writable.
3. Emit actionable structured JSON errors.
4. Add a path repair helper for DB/log/cache dirs.
5. Ensure dry-run commands do not traceback.

### Acceptance Criteria

- `hb-assistant files ingest --dry-run --json` returns valid JSON.
- No candidates should return `no_provenance_candidates`, not a DB exception.
- `hb-assistant run morning --dry-run --json` returns valid JSON and either completes or reports structured skipped stages.
- SQLite migrations initialize successfully when paths are writable.

---

## ADD-P0-004 — Delegated Graph proof still unverified

### Problem

Delegated proof runner exists but is blocked by path permissions.

### Required Correction

After ADD-P0-002, rerun proof.

### Acceptance Criteria

- Proof reaches delegated-token state.
- If no token exists, output is structured and instructs `hb-assistant auth login --json`.
- If token exists, `/me`, mail metadata, calendar, file metadata, app-only rejection, and sensitive scan steps run.
- Any Microsoft permission gap is documented as a manual external blocker.

---

## ADD-P1-001 — Bounded body mention detection beyond preview

### Problem

The current classifier still operates on `body_preview_redacted`. Original MVP requires emails to be included when Bobby is mentioned in body even when not in To/Cc and not visible in preview.

### Required Correction

Add bounded in-memory body inspection.

### Acceptance Criteria

- Full body may be fetched only for bounded candidates.
- Full body is never persisted.
- HTML is normalized safely in memory.
- Detection result persists only flags, method, confidence, and optional redacted match window.
- Test proves a mention outside `bodyPreview` is detected.
