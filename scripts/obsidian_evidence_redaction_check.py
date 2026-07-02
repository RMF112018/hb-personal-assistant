#!/usr/bin/env python3
"""Safe-evidence redaction checker (Phase 10L-I).

Scans a committable evidence tree — EXCLUDING any ``local-sensitive/`` subtree — and fails (exit 1) if it
finds material that must never appear in safe evidence: absolute ``/Users/…`` paths, 64-hex content
SHAs, 32-hex source IDs, generated card/note filenames (``…__<12hex>.md``), email addresses, and
angle-bracket ``Message-ID`` values. Reports only category + file + line (NEVER the matched value), per
the repo's sensitive-scan convention.

``00-repo-state`` files are NOT blanket-exempt: they are scanned like everything else, except that a bare
git commit SHA (short or 40-hex, which is distinct from the 32/64-hex identifiers above) is permitted
there — the redaction rules below already ignore 40-hex tokens, so no special-casing is required beyond
still enforcing the path/email/id rules.
"""

from __future__ import annotations

import argparse
import re
import sys
from pathlib import Path

_TEXT_SUFFIXES = frozenset({".md", ".txt", ".json", ".yaml", ".yml", ".csv"})
_LOCAL_SENSITIVE_SEGMENTS = frozenset({"local-sensitive"})

# (category, compiled pattern). Ordered most-specific first. 40-hex git SHAs are intentionally NOT matched
# (64-hex content sha and 32-hex source_id are; a git SHA is 7-40 hex → allowed).
_RULES: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("absolute_user_path", re.compile(r"/Users/[A-Za-z0-9._-]+")),
    ("content_sha256", re.compile(r"(?<![0-9a-fA-F])[0-9a-f]{64}(?![0-9a-fA-F])")),
    ("source_id_32hex", re.compile(r"(?<![0-9a-fA-F])[0-9a-f]{32}(?![0-9a-fA-F])")),
    ("generated_note_path", re.compile(r"__[0-9a-f]{12}\.(?:md|pdf|docx|xlsx|csv|txt)")),
    ("email_address", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("message_id", re.compile(r"<[^@\s<>]+@[^@\s<>]+>")),
)


def scan_file(path: Path) -> list[tuple[str, int, str]]:
    """Return [(category, line_number, rel_hint)] findings — never the matched value."""
    findings: list[tuple[str, int, str]] = []
    try:
        text = path.read_text(encoding="utf-8", errors="replace")
    except OSError:
        return findings
    for lineno, line in enumerate(text.splitlines(), start=1):
        for category, pat in _RULES:
            if pat.search(line):
                findings.append((category, lineno, path.name))
    return findings


def scan_tree(root: Path) -> list[tuple[str, str, int]]:
    """Return [(category, rel_path, line_number)] over the safe tree (local-sensitive/ excluded)."""
    out: list[tuple[str, str, int]] = []
    for path in sorted(root.rglob("*")):
        if not path.is_file() or path.suffix.lower() not in _TEXT_SUFFIXES:
            continue
        rel_parts = {p.lower() for p in path.relative_to(root).parts}
        if rel_parts & _LOCAL_SENSITIVE_SEGMENTS:
            continue
        rel = str(path.relative_to(root))
        for category, lineno, _name in scan_file(path):
            out.append((category, rel, lineno))
    return out


def main(argv: list[str] | None = None) -> int:
    p = argparse.ArgumentParser(description="Fail if safe evidence leaks sensitive material.")
    p.add_argument("evidence_dir")
    args = p.parse_args(argv)
    root = Path(args.evidence_dir)
    if not root.is_dir():
        print(f"redaction-check: not a directory: {args.evidence_dir}", file=sys.stderr)
        return 2
    findings = scan_tree(root)
    if findings:
        print(f"redaction-check: FAIL — {len(findings)} finding(s) in safe evidence:", file=sys.stderr)
        for category, rel, lineno in findings:
            print(f"  {category}: {rel}:{lineno}", file=sys.stderr)
        return 1
    print("redaction-check: PASS — no sensitive material in safe evidence (local-sensitive/ excluded).")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
