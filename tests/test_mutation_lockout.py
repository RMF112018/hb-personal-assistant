"""Phase 13 mutation lockout static test.

Proves there are no Microsoft 365 write APIs (POST/PUT/PATCH/DELETE to Graph)
called from any of the client modules or orchestrator paths.

This satisfies:
- 14_Testing_Validation_And_Evidence_Plan.md "Static tests prove no M365 write APIs"
- 15_Acceptance_Criteria_And_Closure_Checklist.md "No Microsoft 365 mutation path exists"

The general-purpose GraphHttpClient supports the method for future-proofing,
but all current high-level clients (MailClient, CalendarClient, DriveItemClient)
and the MorningRunOrchestrator / LaunchdManager only ever perform read operations
or local filesystem writes (cache, evidence, logs, plist files).

Config default: microsoft_365_writeback_enabled = False (defense in depth).
"""

from __future__ import annotations

import subprocess
from pathlib import Path


def test_no_m365_write_apis_in_graph_clients():
    """Static analysis: no Graph write verbs invoked from client code."""
    root = Path(__file__).resolve().parents[1]  # repo root
    graph_dir = root / "src" / "hb_assistant" / "graph"

    # Search for any call that looks like a write to Graph
    # We look for .post( .put( .patch( .delete( on the client or http
    pattern = r'\.(post|put|patch|delete)\s*\('

    result = subprocess.run(
        ["grep", "-rnE", pattern, str(graph_dir)],
        capture_output=True,
        text=True,
    )

    # Only acceptable hits would be inside comments or test mocks, but we assert zero
    # (our code never calls them for M365)
    output = result.stdout.strip()
    assert output == "", f"Found Graph write calls (mutation lockout violation):\n{output}"


def test_config_writeback_disabled_by_default():
    """Config default prevents any write-back even if code paths existed."""
    from hb_assistant.config.models import AppConfig

    cfg = AppConfig()
    assert cfg.security.microsoft_365_writeback_enabled is False, (
        "M365 writeback must remain disabled for MVP (mutation lockout)"
    )


def test_no_write_methods_in_automation_orchestrator():
    """Orchestrator and LaunchdManager only do local FS or read Graph."""
    # We already proved graph clients; double-check automation source for any stray write
    root = Path(__file__).resolve().parents[1]
    auto_dir = root / "src" / "hb_assistant" / "automation"

    pattern = r'\.(post|put|patch|delete)\s*\('
    result = subprocess.run(
        ["grep", "-rnE", pattern, str(auto_dir)],
        capture_output=True,
        text=True,
    )
    output = result.stdout.strip()
    assert output == "", f"Found write calls in automation (mutation lockout violation):\n{output}"


def test_mutation_lockout_redaction_in_test_artifacts():
    """The test file itself must not contain any real secrets or tokens (redaction proof)."""
    test_file = Path(__file__).read_text(encoding="utf-8")
    # The list below is the definition of what we check for; it is allowed only in this list.
    # Any other occurrence in the file body would be a violation.
    forbidden = ["SECRET", "PRIVATE KEY", "access_token", "Bearer "]
    for bad in forbidden:
        # Count occurrences; the definition line itself contributes 1 per item.
        # If >1, there is a real secret elsewhere in the file.
        count = test_file.count(bad)
        assert count <= 1, f"Redaction violation: {bad} appears {count} times (should be only in the forbidden list)"
