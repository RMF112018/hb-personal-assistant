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

Phase 02 Prompt 10 additions (below): email-intelligence deferred-foundation
policy regression tests + mailbox-mutation-endpoint static scans.
"""

from __future__ import annotations

import re
import subprocess
from pathlib import Path

import pytest
from pydantic import ValidationError


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


# ---------------------------------------------------------------------------
# Phase 02 Prompt 10: email-intelligence deferred-foundation policy
# ---------------------------------------------------------------------------


def _valid_policy_dict() -> dict:
    return {
        "mail_read_all_granted": True,
        "mail_readwrite_all_granted": True,
        "mailbox_writeback_allowed": False,
        "persist_full_body": False,
        "review_required_for_sensitive": True,
        "future_phase": "phase_03",
    }


def test_email_intelligence_deferred_policy_yaml_loads_and_locks_writeback() -> None:
    from hb_assistant.construction.policy import load_email_intelligence_deferred_policy

    policy = load_email_intelligence_deferred_policy()
    assert policy.mailbox_writeback_allowed is False
    assert policy.persist_full_body is False
    assert policy.review_required_for_sensitive is True
    # Tenant grants are operator truth; they do not loosen the lockout.
    assert policy.mail_read_all_granted is True
    assert policy.mail_readwrite_all_granted is True


def test_email_intelligence_deferred_policy_rejects_mailbox_writeback_allowed_true() -> None:
    from hb_assistant.construction.policy import EmailIntelligenceDeferredPolicy

    data = _valid_policy_dict()
    data["mailbox_writeback_allowed"] = True
    with pytest.raises(ValidationError):
        EmailIntelligenceDeferredPolicy.model_validate(data)


def test_email_intelligence_deferred_policy_rejects_persist_full_body_true() -> None:
    from hb_assistant.construction.policy import EmailIntelligenceDeferredPolicy

    data = _valid_policy_dict()
    data["persist_full_body"] = True
    with pytest.raises(ValidationError):
        EmailIntelligenceDeferredPolicy.model_validate(data)


def test_email_intelligence_deferred_policy_rejects_review_required_for_sensitive_false() -> None:
    from hb_assistant.construction.policy import EmailIntelligenceDeferredPolicy

    data = _valid_policy_dict()
    data["review_required_for_sensitive"] = False
    with pytest.raises(ValidationError):
        EmailIntelligenceDeferredPolicy.model_validate(data)


def test_email_intelligence_deferred_policy_rejects_unknown_fields() -> None:
    from hb_assistant.construction.policy import EmailIntelligenceDeferredPolicy

    data = _valid_policy_dict()
    data["secret_writeback_override"] = True
    with pytest.raises(ValidationError):
        EmailIntelligenceDeferredPolicy.model_validate(data)


def test_email_intelligence_deferred_policy_allows_mail_readwrite_all_granted_true_without_loosening_lockout() -> None:
    """The central grant-but-suppress assertion: tenant may grant
    Mail.ReadWrite.All, but the three locked guardrails stay locked."""
    from hb_assistant.construction.policy import EmailIntelligenceDeferredPolicy

    policy = EmailIntelligenceDeferredPolicy.model_validate(_valid_policy_dict())
    assert policy.mail_readwrite_all_granted is True
    # All three locked guardrails remain at their required values:
    assert policy.mailbox_writeback_allowed is False
    assert policy.persist_full_body is False
    assert policy.review_required_for_sensitive is True


# ---------------------------------------------------------------------------
# Phase 02 Prompt 10: runtime delegated-scope defense
# ---------------------------------------------------------------------------


_FORBIDDEN_MAIL_SCOPES = (
    "Mail.ReadWrite.All",
    "Mail.ReadWrite",
    "Mail.ReadWrite.Shared",
    "Mail.Send",
    "Mail.Send.Shared",
)


def test_identity_default_scopes_do_not_request_mailbox_write_scopes() -> None:
    """Despite tenant-level Mail.ReadWrite.All consent, the application's
    MSAL scope request must continue to ask only for Mail.Read at runtime.

    The default IdentityConfig is the single source of truth for delegated
    scopes; this test pins it against accidental broadening."""
    from hb_assistant.config.models import IdentityConfig

    identity = IdentityConfig()
    for scope in _FORBIDDEN_MAIL_SCOPES:
        assert scope not in identity.delegated_scopes, (
            f"IdentityConfig.delegated_scopes default unexpectedly contains "
            f"{scope!r}; Phase 02 must request only 'Mail.Read'"
        )
    # Sanity: Mail.Read should remain present so the read paths still work.
    assert "Mail.Read" in identity.delegated_scopes


def test_identity_default_scopes_match_granted_app_registration_scopes() -> None:
    """Pin the runtime delegated scope set to exactly what the HB SharePoint
    Creator app registration has admin-consented in Azure AD.

    Calendars.ReadWrite.Shared and Files.ReadWrite.All replace the original
    Calendars.Read / Files.Read.All requests, which blocked device-code login
    because neither read-only scope was admin-consented in the target tenant
    (0e834bd7-628b-42c8-b9ec-ecebc9719be4). The broader scopes are requested
    but controller guardrails still prohibit any source-system mutation."""
    from hb_assistant.config.models import IdentityConfig

    identity = IdentityConfig()
    expected = [
        "User.Read",
        "Mail.Read",
        "Calendars.ReadWrite.Shared",
        "Files.ReadWrite.All",
        "offline_access",
    ]
    for scope in expected:
        assert scope in identity.delegated_scopes, (
            f"IdentityConfig.delegated_scopes default missing required "
            f"{scope!r}; expected runtime set: {expected!r}"
        )

    # Old read-only scope strings must NOT reappear: they trigger the
    # admin-approval blocker because the tenant only admin-consented the
    # ReadWrite variants.
    forbidden_old_read_scopes = ("Calendars.Read", "Files.Read.All")
    for scope in forbidden_old_read_scopes:
        assert scope not in identity.delegated_scopes, (
            f"IdentityConfig.delegated_scopes default unexpectedly contains "
            f"the previously-blocking read-only scope {scope!r}"
        )

    # `.default` must never appear in the delegated runtime scope list. The
    # AppOnlyAuthProvider (cert flow) uses '.default' separately; the
    # delegated path must request named scopes only.
    for scope in identity.delegated_scopes:
        assert ".default" not in scope, (
            f"IdentityConfig.delegated_scopes default unexpectedly contains "
            f"'.default' literal in {scope!r}"
        )


# ---------------------------------------------------------------------------
# Phase 02 Prompt 10: mailbox-mutation-endpoint static scan
# ---------------------------------------------------------------------------


_MAILBOX_PATH_RE = re.compile(r"/me/(messages|mailFolders)")
_WRITE_VERB_CALL_RE = re.compile(r"\.(post|patch|delete)\s*\(")
_MAILBOX_ACTION_ENDPOINT_RE = re.compile(
    r"/(sendMail|reply|replyAll|forward"
    r"|microsoft\.graph\.move|microsoft\.graph\.copy"
    r"|microsoft\.graph\.sendMail|microsoft\.graph\.reply"
    r"|microsoft\.graph\.replyAll|microsoft\.graph\.forward)"
)


def test_graph_clients_do_not_contain_mailbox_mutation_endpoints() -> None:
    """Static scan over src/hb_assistant/graph/**.py for:

    1. write-verb HTTP calls (.post/.patch/.delete) on lines that also
       reference /me/messages or /me/mailFolders;
    2. literal mailbox-action endpoints (/sendMail, /reply, /replyAll,
       /forward, microsoft.graph.move|copy on messages).

    Defense-in-depth alongside the broader
    test_no_m365_write_apis_in_graph_clients which forbids any write verb
    anywhere in the graph module tree."""
    root = Path(__file__).resolve().parents[1]
    graph_dir = root / "src" / "hb_assistant" / "graph"
    violations: list[str] = []

    for py_file in sorted(graph_dir.rglob("*.py")):
        for line_no, line in enumerate(
            py_file.read_text(encoding="utf-8").splitlines(), start=1,
        ):
            if _WRITE_VERB_CALL_RE.search(line) and _MAILBOX_PATH_RE.search(line):
                violations.append(
                    f"{py_file.relative_to(root)}:{line_no}: write verb against "
                    f"mailbox endpoint: {line.strip()!r}"
                )
            if _MAILBOX_ACTION_ENDPOINT_RE.search(line):
                violations.append(
                    f"{py_file.relative_to(root)}:{line_no}: mailbox action "
                    f"endpoint: {line.strip()!r}"
                )

    assert not violations, (
        "Mailbox mutation endpoints / write verbs detected in Graph client "
        "source — Phase 02 requires mailbox read-only behavior:\n"
        + "\n".join(violations)
    )
