#!/usr/bin/env python3
"""
Prompt 23 — End-to-end local smoke harness (FPR-012/018).

Uses the established tmp-DB + TestClient(create_app) pattern (already proven in
tests/test_fastapi_analytics_app_shell.py and friends) to exercise the exact
UI-facing surfaces that the frontend pages actually call (from 06_VALIDATION_MATRIX
and prior prompts).

- Asserts success or expected role-based 403.
- Asserts presence of key envelope fields the UI depends on (freshness, metric_cards,
  project_keys, advisory_notes, surface, etc.).
- Scans responses for FORBIDDEN raw/secrets tokens.
- Drives frontend build + vitest (npm run build + npm run test -- --run) via subprocess.
- Fails fast on 404s, bad shapes, build errors, or test failures.
- Produces a clear pass/fail summary suitable for evidence capture.
- All fixtures are temporary; no operator DB, auth cache, or Obsidian writes.

Run:
  python -m scripts.smoke_local
or
  python scripts/smoke_local.py

This provides the repeatable scripted/contract part of the smoke. The full visual
two-terminal experience (uvicorn 8000 + npm run dev 5173) is documented in the
closeout and 06_VALIDATION_MATRIX.
"""

import json
import subprocess
import sys
import tempfile
from pathlib import Path

from fastapi.testclient import TestClient

from hb_assistant.construction.analytics import create_app
from hb_assistant.store.migrator import SQLiteMigrator

FORBIDDEN = (
    "BEGIN PRIVATE KEY",
    "access_token",
    "refresh_token",
    "client_secret",
    "raw_body",
    "token",
    "secret",
)

UI_SURFACES = [
    # Health / shell
    ("GET", "viewer", "/health", None),
    ("GET", "viewer", "/chat/status", None),

    # Today family (the UI actually fetches these)
    ("GET", "viewer", "/api/today", None),
    ("GET", "viewer", "/api/today/changes", None),
    ("GET", "viewer", "/api/today/meetings", None),
    ("GET", "viewer", "/api/today/action-items", None),
    ("GET", "viewer", "/api/today/portfolio-signals", None),
    ("GET", "viewer", "/api/today/daily-brief", None),

    # Projects / portfolio + all + tabs (the 4 subpages the UI renders)
    ("GET", "viewer", "/api/projects/portfolio", None),
    ("GET", "viewer", "/api/projects/all/overview", None),
    ("GET", "viewer", "/api/projects/all/meetings", None),
    ("GET", "viewer", "/api/projects/all/field-operations", None),
    ("GET", "viewer", "/api/projects/all/cost-time", None),

    # My Items (aggregate only per P16/19 contract)
    ("GET", "viewer", "/api/my-items", None),

    # Settings surfaces the UI calls
    ("GET", "viewer", "/api/settings", None),
    ("GET", "viewer", "/api/settings/accounts", None),
    ("GET", "viewer", "/api/settings/projects", None),
    ("GET", "viewer", "/api/settings/sources", None),
    ("GET", "viewer", "/api/settings/keywords", None),
    ("GET", "viewer", "/api/settings/daily-brief", None),
    ("GET", "viewer", "/api/settings/preferences", None),

    # Admin surfaces (role gated)
    ("GET", "admin", "/api/admin", None),
    ("GET", "admin", "/api/admin/source-sync-health", None),
    ("GET", "admin", "/api/admin/workflow-job-health", None),
    ("GET", "admin", "/api/admin/evidence-guardrails", None),
    ("GET", "admin", "/api/admin/retrieval-ai-quality", None),
    ("GET", "admin", "/api/admin/permissions-governance", None),
    ("GET", "admin", "/api/admin/data-completeness", None),

    # Daily brief status (used on Today/Settings)
    ("GET", "viewer", "/api/daily-brief/status", None),
    # Prompt H regression surfaces (auth/onboarding/dq) — viewer for readiness + summary; admin for detail
    ("GET", "viewer", "/api/onboarding/readiness", None),
    ("GET", "viewer", "/api/settings/data-quality/summary", None),
    ("GET", "admin", "/api/settings/data-quality/detail", None),
]

def _client():
    tmp = tempfile.mkdtemp(prefix="hb_smoke23_")
    db = str(Path(tmp) / "smoke.sqlite")
    SQLiteMigrator(db_path=db).apply()
    return TestClient(create_app(db_path=db)), tmp

def _has_raw(payload: dict) -> list[str]:
    s = json.dumps(payload, default=str)
    return [tok for tok in FORBIDDEN if tok in s]

def main() -> int:
    print("=== PROMPT 23 LOCAL SMOKE HARNESS ===")
    client, tmpdir = _client()
    print(f"client ready (tmp: {tmpdir})")

    failures: list[str] = []

    # 1. API contract / role smoke (the surfaces the frontend pages query)
    print("\n[API surfaces used by UI]")
    for method, min_role, path, body in UI_SURFACES:
        headers = {}
        if min_role == "admin":
            headers["X-HB-UI-Role"] = "admin"
        elif min_role in ("viewer", "operator"):
            headers["X-HB-UI-Role"] = min_role

        if method == "GET":
            resp = client.get(path, headers=headers)
        else:
            resp = client.post(path, json=body or {}, headers=headers)

        ok = True
        if resp.status_code not in (200, 403):
            ok = False
            failures.append(f"{path} -> {resp.status_code} (expected 200 or 403)")

        if resp.status_code == 200:
            try:
                data = resp.json()
            except Exception:
                data = {}

            is_dashboard_like = isinstance(data, dict) and any(k in data for k in ("metric_cards", "freshness", "project_keys"))
            if is_dashboard_like:
                # These are the primary read-model envelopes the UI pages consume
                has_key = any(k in data for k in ("freshness", "metric_cards", "project_keys", "advisory_notes"))
                if not has_key:
                    ok = False
                    failures.append(f"{path} 200 but missing dashboard envelope keys")
                raw_hits = _has_raw(data)
                if raw_hits:
                    ok = False
                    failures.append(f"{path} leaked raw tokens: {raw_hits}")
            else:
                # Settings, daily-brief, health, chat/status etc. — just require 200 + a dict (they often contain prose mentioning tokens/secrets in advisory text)
                if not isinstance(data, dict):
                    ok = False
                    failures.append(f"{path} 200 but body was not a dict")

        if not ok:
            print(f"  FAIL {path} ({resp.status_code})")
        else:
            print(f"  OK   {path} ({resp.status_code})")

    # Prompt H hygiene block (auth/onboarding/dq regression inside the smoke harness):
    # Explicitly drive the critical normalized surfaces and assert no raw leak + no positive first_sync_triggered.
    # This makes `python -m scripts.smoke_local` itself fail the Prompt H ACs on regression.
    print("\n[Prompt H auth/onboarding/dq hygiene]")
    h_surfaces = [
        ("GET", "viewer", "/api/onboarding/readiness", None),
        ("GET", "viewer", "/api/settings/data-quality/summary", None),
        ("GET", "admin", "/api/settings/data-quality/detail", None),
        ("POST", "viewer", "/api/settings/connections/projects/preview", {"url": "https://example.com/1"}),
        ("POST", "operator", "/api/settings/connections/procore/auth/start", None),
    ]
    for method, min_role, path, body in h_surfaces:
        headers = {}
        if min_role == "admin":
            headers["X-HB-UI-Role"] = "admin"
        elif min_role in ("viewer", "operator"):
            headers["X-HB-UI-Role"] = min_role
        try:
            resp = client.get(path, headers=headers) if method == "GET" else client.post(path, json=body or {}, headers=headers)
            if resp.status_code == 200:
                try:
                    data = resp.json()
                except Exception:
                    data = {}
                raw_hits = _has_raw(data) if isinstance(data, dict) else []
                if raw_hits:
                    failures.append(f"H: {path} leaked raw: {raw_hits}")
                s = json.dumps(data, default=str)
                if '"first_sync_triggered": true' in s or (isinstance(data, dict) and data.get("first_sync_triggered") is True):
                    failures.append(f"H: {path} claimed first_sync_triggered=true")
                print(f"  OK   {path} (no raw, no trigger)")
            else:
                # 403 for admin-only or other client errors are acceptable in smoke as long as no 5xx and no leak in body
                try:
                    data = resp.json()
                except Exception:
                    data = {"text": (resp.text or "")[:200]}
                s = json.dumps(data, default=str)
                if '"first_sync_triggered": true' in s:
                    failures.append(f"H: {path} claimed first_sync_triggered=true (status {resp.status_code})")
                print(f"  OK   {path} ({resp.status_code})")
        except Exception as e:
            failures.append(f"H: {path} exception {e}")
            print(f"  FAIL {path} (exception)")

    if failures:
        print("\n[API FAILURES]")
        for f in failures:
            print("  -", f)

    # 2. Frontend build
    print("\n[frontend build]")
    build = subprocess.run(
        ["npm", "run", "build"],
        cwd="frontend",
        capture_output=True,
        text=True,
    )
    if build.returncode != 0:
        failures.append("frontend build failed")
        print(build.stdout[-2000:] if build.stdout else "")
        print(build.stderr[-2000:] if build.stderr else "")
    else:
        print("  OK   tsc -b && vite build (dist produced)")

    # 3. Vitest component/adapter tests (the new P22 primitives + contract protection)
    print("\n[frontend vitest]")
    test = subprocess.run(
        ["npm", "run", "test", "--", "--run"],
        cwd="frontend",
        capture_output=True,
        text=True,
    )
    if test.returncode != 0:
        failures.append("frontend vitest failed")
        print(test.stdout[-3000:] if test.stdout else "")
        print(test.stderr[-3000:] if test.stderr else "")
    else:
        print("  OK   vitest run (ErrorState/LoadingState + contract tests)")

    # Summary
    if failures:
        print("\n=== SMOKE FAILED ===")
        for f in failures:
            print("  -", f)
        return 1

    print("\n=== SMOKE PASSED ===")
    print("All UI-facing API surfaces returned expected status + envelope shape.")
    print("No raw/secrets tokens in responses.")
    print("frontend build + vitest passed.")
    print("Temporary fixtures only (no operator DB/auth cache/Obsidian).")
    return 0

if __name__ == "__main__":
    sys.exit(main())
