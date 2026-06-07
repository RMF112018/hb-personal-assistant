# Synthetic Daily Brief Fixtures (FPR-014)

These committed read-only .md files provide negative / boundary / path-display cases for the FastAPI analytics Daily Brief surfaces (detect-latest, status, today daily-brief) without ever containing real secrets, tokens, raw bodies, or user content.

## Usage in tests
- Tests MUST copy the fixture to a per-test temporary output_folder (e.g. `shutil.copy(fixture, target)` or equivalent).
- After copy, tests may adjust mtime via `os.utime` for stale cases.
- Configure the Daily Brief (via API or service) to point at the *temp* folder with appropriate pattern.
- Exercise the UI-facing surfaces: GET /api/daily-brief/status, POST /api/daily-brief/detect-latest (or the settings alias), and/or /api/today/daily-brief.
- Assert:
  - HTTP 200 and safe envelope (via existing _assert_safe or equivalent on safe subsets: parse_warnings, last_file, config, guardrails, state, label, etc.).
  - Expected state/label (brief_stale, markdown_parse_warning, etc.).
  - Path display: the distinctive token (e.g. PATHDISPLAY or the full synthetic filename) appears in `last_file.path` or top-level `path`.
  - Bounded content: for the overly-long case, the returned `content` length respects the service bound (raw[:100000]); sections bodies respect their per-section caps.
  - Parse warnings (if any) are themselves run through safe asserts.
- **Original file preservation (mutation proof)**: before and after the test actions that use the fixture, compute sha256 of the *committed fixture file on disk* (the path under tests/fixtures/daily_brief_analytics/) and assert pre == post. This proves the test did not mutate the committed original.

Example helper (to be used in the test file):

```python
import hashlib
from pathlib import Path

def _sha256(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()

# in test:
fixture = Path("tests/fixtures/daily_brief_analytics/HB-Daily-Brief-SYNTHETIC-....md")
pre = _sha256(fixture)
# ... copy to tmp, configure, call APIs, assertions ...
post = _sha256(fixture)
assert pre == post, "original fixture file must remain unchanged on disk (no source file mutation)"
```

All content uses only FAKE/SYNTHETIC markers. No real tokens/secrets/PEM/raw content from any system is present. These fixtures are for local deterministic testing only.

See: tests/test_fastapi_analytics_daily_brief.py (expanded for FPR-014), Prompt 24 closeout, and the Daily Brief service (bounded reads, _parse_sections, _compute_state, last_file.path exposure, no .md writes).

Do not edit these files except to add new synthetic cases following the same rules.
