"""Repo-wide sensitive scan with an explicit allowlist (Phase 03, Prompt 12).

Runs ``SensitiveScanner`` over the repo root and asserts that only known-safe
findings appear. New files that introduce credential-shaped strings will fail
this test and must either remove the string or update the allowlist with a
deliberate justification.
"""

from __future__ import annotations

from pathlib import Path

from hb_assistant.security import ScanConfig, SensitiveScanner

REPO_ROOT = Path(__file__).resolve().parents[1]

_ALLOWED_PREFIXES_BY_RULE: dict[str, tuple[str, ...]] = {
    "bearer_token": (
        "src/hb_assistant/procore/fixtures.py",
        "src/hb_assistant/procore/redaction.py",
        "src/hb_assistant/security/sensitive_scan.py",
        "tests/test_procore_redaction.py",
        "tests/test_repo_sensitive_scan.py",
        "tests/test_procore_http_client.py",
        "tests/test_procore_live_sync_verified_chain.py",
        "tests/test_procore_sensitive_routing_proof_corpus.py",
        "tests/test_construction_manifests.py",
        "tests/test_procore_no_writeback_proof.py",
        # Phase 08D: synthetic "Bearer abc…xyz" fixture asserting the evidence-collector
        # safety scanner *flags* a token (no real secret).
        "tests/test_phase_08d_agent_data_evaluation_evidence_collector.py",
        "docs/",
    ),
    "jwt_like": (
        "src/hb_assistant/procore/fixtures.py",
        "src/hb_assistant/procore/redaction.py",
        "src/hb_assistant/security/sensitive_scan.py",
        "tests/test_procore_redaction.py",
        "tests/test_repo_sensitive_scan.py",
    ),
    "client_secret_assignment": (
        "src/hb_assistant/security/sensitive_scan.py",
        "src/hb_assistant/procore/config.py",
        "tests/test_sensitive_scan.py",
        "tests/test_sensitive_scan_cli.py",
        "tests/test_repo_sensitive_scan.py",
        "docs/",
    ),
    "oauth_access_token_field": (
        "src/hb_assistant/",
        "tests/",
        "scripts/",
        "docs/",
    ),
    "pem_block": (
        "src/hb_assistant/security/sensitive_scan.py",
        "tests/test_procore_no_writeback_proof.py",
    ),
    "pem_private_key": ("tests/test_procore_no_writeback_proof.py",),
}

_BROADLY_ALLOWED_RULES: frozenset[str] = frozenset(
    {
        # Keyword-style rule: triggers on any line with a SECRET/TOKEN/PASSWORD/
        # API_KEY/CLIENT_SECRET variable assignment, including legitimate env-var
        # name constants in Python source. Its real value is for scanning .env-
        # style files, which the existing test_sensitive_scan.py probes directly.
        "env_secret_assignment",
        # Keyword scanner for the words msal/token_cache/refresh_token/
        # access_token. Noisy on docs and comments.
        "msal_cache_content",
    }
)


def _is_allowed(finding: dict) -> bool:
    if finding["category"] in _BROADLY_ALLOWED_RULES:
        return True
    prefixes = _ALLOWED_PREFIXES_BY_RULE.get(finding["category"], ())
    return any(finding["path"].startswith(p) for p in prefixes)


def test_repo_has_no_unallowed_sensitive_findings() -> None:
    scanner = SensitiveScanner(ScanConfig(max_file_size_bytes=512_000, max_files=10_000))
    payload = scanner.scan(repo=str(REPO_ROOT))

    assert payload["implemented"] is True

    unexpected = [f for f in payload["findings"] if not _is_allowed(f)]
    if unexpected:
        rendered = "\n".join(
            f"  - {f['category']:32s} {f['severity']:8s} {f['path']}:{f['line']}"
            for f in unexpected[:50]
        )
        raise AssertionError(
            f"Unallowed sensitive findings ({len(unexpected)}):\n{rendered}\n"
            "If the finding is benign, add its path prefix to "
            "_ALLOWED_PREFIXES_BY_RULE in tests/test_repo_sensitive_scan.py."
        )


def test_sensitive_scan_stats_are_present() -> None:
    scanner = SensitiveScanner(ScanConfig(max_file_size_bytes=512_000, max_files=10_000))
    payload = scanner.scan(repo=str(REPO_ROOT))

    stats = payload["stats"]
    assert stats["files_scanned"] > 0
    assert stats["files_considered"] >= stats["files_scanned"]
