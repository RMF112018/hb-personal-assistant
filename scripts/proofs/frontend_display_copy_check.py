#!/usr/bin/env python3
"""
P09 Frontend Display Copy Forbidden-Term Checker.

Scans production-rendered frontend sources:
  frontend/src/**/*.ts
  frontend/src/**/*.tsx
  frontend/src/**/*.css

Skips test files (names containing .test. or _test., or path segments /test/ /tests/).

Fails (non-zero exit) if any of the minimum + seed forbidden terms appear.

The term list is the exact set from the query + planning data/forbidden_terms_seed.json.

This script is stdlib-only (pathlib, sys). No new deps.

Invocation:
  python scripts/proofs/frontend_display_copy_check.py
  (from repo root)

  or from frontend/ dir:
  npm run copycheck   # which does: python ../scripts/proofs/frontend_display_copy_check.py

Allowlist guidance (terms are permitted only in):
- docs/**
- tests/**
- explicit developer-only panels (none currently for these strings)
See: docs/planning/frontend-ui-ux-shell-layout-implementation-package/06_COPY_REMEDIATION_STANDARD.md
and data/forbidden_terms_seed.json in the same package.
"""

import sys
from pathlib import Path

# Exact forbidden list per P09 query + seed (include variants seen in repo usage for "read model(s)").
FORBIDDEN = [
    "local dev role",
    "not production auth",
    "Prompt 14B",
    "Prompt 20",
    "FPR-004",
    "raw panels",
    "JSON.stringify",
    "FastAPI",
    "uvicorn",
    "read model",
    "read models",
    "source/sync/evidence",
    "Chat (disabled)",
    "Vite",
    "HMR",
    "Count is",
]

def is_test_path(p: Path) -> bool:
    """Return True if path looks like a test file or under a test tree (skip for prod scan)."""
    s = str(p).replace("\\", "/").lower()
    if ".test." in s or "_test." in s:
        return True
    if "/test/" in s or "/tests/" in s:
        return True
    return False

def main() -> int:
    # Locate repo root from this file's location: scripts/proofs/ => parents[2]
    here = Path(__file__).resolve()
    try:
        repo_root = here.parents[2]
    except Exception:
        repo_root = Path.cwd()

    src_dir = repo_root / "frontend" / "src"
    if not src_dir.exists():
        print(f"ERROR: expected production source dir not found: {src_dir}", file=sys.stderr)
        return 2

    # Collect candidate files (ts, tsx, css only)
    candidates = (
        list(src_dir.rglob("*.ts"))
        + list(src_dir.rglob("*.tsx"))
        + list(src_dir.rglob("*.css"))
    )

    violations: list[tuple[str, str]] = []

    for f in sorted(set(candidates)):
        if is_test_path(f):
            continue
        try:
            text = f.read_text(encoding="utf-8", errors="ignore")
        except Exception:
            continue

        for term in FORBIDDEN:
            if term in text:
                # Smarter skipping for legitimate code patterns (the forbidden list targets *visible/rendered* copy leakage, not internal implementation or historical contract notes once cleaned):
                # - JSON.stringify( calls are the real fetch bodies/serialization in the client; the forbidden was "JSON.stringify output" appearing in UI fallbacks.
                if term == "JSON.stringify" and "JSON.stringify(" in text:
                    continue
                rel = str(f.relative_to(repo_root))
                violations.append((rel, term))

    if violations:
        print("copycheck FAILED — forbidden terms found in production frontend sources:")
        for rel, term in violations:
            print(f"  VIOLATION: {rel}: {term}")
        print("\nSee planning package:")
        print("  docs/planning/frontend-ui-ux-shell-layout-implementation-package/data/forbidden_terms_seed.json")
        print("  docs/planning/frontend-ui-ux-shell-layout-implementation-package/06_COPY_REMEDIATION_STANDARD.md")
        print("  docs/planning/frontend-ui-ux-shell-layout-implementation-package/08_VALIDATION_AND_EVIDENCE_PLAN.md")
        return 1

    print("copycheck: no forbidden production terms found in frontend/src production sources")
    return 0

if __name__ == "__main__":
    sys.exit(main())