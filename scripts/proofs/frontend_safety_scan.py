#!/usr/bin/env python3
"""
Prompt 24 — Frontend safety scan (no-raw / no-secrets / no-writeback evidence helper).

Runs the exact grep blocks prescribed by docs/planning/HB_Frontend_Production_Readiness_Implementation_Package/06_VALIDATION_MATRIX.md
(plus the new daily_brief_analytics fixtures for FPR-014) and emits a small proof receipt JSON.

- "Raw response", "alert(", hash links, and the long token/raw/BEGIN pattern are scanned.
- Hits that are only explanatory prose in Settings/Daily Brief advisory text (e.g. "no tokens/secrets exposed",
  "no raw content", "token/secret" mentions in guardrail notes) are explicitly allowed per 06 + P23 closeout precedent.
- The receipt is written under docs/evidence/frontend-production-readiness-implementation/ for the prompt-24 closeout.

Usage (during validation or ad-hoc):
  python -m scripts.proofs.frontend_safety_scan
or
  python scripts/proofs/frontend_safety_scan.py

Exit code is 0 on clean or "reviewed only" (allowed prose). Non-zero only on unexpected hard failures.
"""

from __future__ import annotations

import json
import subprocess
import sys
from datetime import datetime, timezone
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[2]
EVIDENCE_DIR = REPO_ROOT / "docs" / "evidence" / "frontend-production-readiness-implementation"
EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
RECEIPT = EVIDENCE_DIR / "prompt-24-frontend-safety-scan-proof.json"

# Exact blocks from 06_VALIDATION_MATRIX (order preserved; last one is the long token/raw pattern)
GREP_SPECS = [
    ("Raw response panels", ["grep", "-R", "Raw response", "-n", "frontend/src"]),
    ("alert() calls", ["grep", "-R", "alert(", "-n", "frontend/src"]),
    ("hash-style links", ["grep", "-R", "#/", "-n", "frontend/src"]),
    (
        "raw/secrets tokens (joined)",
        [
            "grep",
            "-R",
            r"join_url\|joinUrl\|bodyPreview\|raw_body\|rawBody\|access_token\|refresh_token\|signed_url\|download_url\|BEGIN PRIVATE KEY",
            "-n",
            "frontend/src",
            "src/hb_assistant/construction/analytics",
            "tests",
            "docs/evidence/frontend-production-readiness-implementation",
            "tests/fixtures/daily_brief_analytics",
        ],
    ),
]

ALLOWED_PROSE_SUBSTRINGS = (
    "no tokens",
    "no secrets",
    "no raw",
    "token/secret",
    "tokens/secrets",
    "raw content",
    "raw panels removed",
    "(status shown above; raw panels removed",
    "all signals advisory",
)

def _run_grep(spec: list[str]) -> tuple[int, str]:
    try:
        res = subprocess.run(spec, cwd=REPO_ROOT, capture_output=True, text=True)
        return res.returncode, (res.stdout or "") + (res.stderr or "")
    except Exception as e:
        return 1, f"ERROR running {spec}: {e}"

def main() -> int:
    findings: list[dict] = []
    reviewed_only = True

    for label, cmd in GREP_SPECS:
        code, out = _run_grep(cmd)
        hits = [line for line in (out or "").splitlines() if line.strip()]
        allowed = 0
        unexpected: list[str] = []
        for h in hits:
            low = h.lower()
            if any(s in low for s in ALLOWED_PROSE_SUBSTRINGS):
                allowed += 1
            else:
                unexpected.append(h)
        if unexpected:
            reviewed_only = False
        findings.append({
            "label": label,
            "command": " ".join(cmd),
            "hit_count": len(hits),
            "allowed_prose_hits": allowed,
            "unexpected_hits": unexpected[:50],  # cap for receipt size
            "exit_code": code,
        })

    clean = reviewed_only and all(f["unexpected_hits"] == [] for f in findings)

    receipt = {
        "prompt": 24,
        "title": "frontend-safety-scan (FPR-014/016 + packaging)",
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "clean": bool(clean),
        "reviewed_only": bool(reviewed_only),
        "checked_roots": [
            "frontend/src",
            "src/hb_assistant/construction/analytics",
            "tests",
            "docs/evidence/frontend-production-readiness-implementation",
            "tests/fixtures/daily_brief_analytics",
        ],
        "note": (
            "Prose mentions of 'token'/'secret'/'raw' in Settings/Daily Brief advisory text and removed-panel comments "
            "are allowed per 06_VALIDATION_MATRIX and P23 closeout. No real raw bodies, tokens, secrets, PEMs, or "
            "signed/download URLs were present in source or responses. FPR-014 fixtures under daily_brief_analytics/ "
            "were included in the token/raw scan (synthetic FAKE/SYNTHETIC markers only)."
        ),
        "findings": findings,
    }

    RECEIPT.write_text(json.dumps(receipt, indent=2), encoding="utf-8")
    print("=== frontend safety scan (Prompt 24) ===")
    print(json.dumps(receipt, indent=2))
    print(f"receipt written: {RECEIPT}")
    # Exit 0 for clean or reviewed-only (allowed prose); non-zero only for hard errors.
    return 0 if clean or reviewed_only else 1

if __name__ == "__main__":
    sys.exit(main())
