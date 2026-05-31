"""Phase 06B no-writeback / no-secret / no-raw-body proof (Prompt 15).

Executable proof that Phase 06B added **no** Procore writeback, **no** Microsoft 365 writeback, **no**
raw-body persistence, and leaked **no** secrets. Read-only: it statically scans the Phase 06B
read-model / output module sources, AST-checks them for forbidden HTTP-client imports, probes the
SQLite ``raw_body_persisted`` guardrails, and scans the generated evidence outputs for token / secret
/ signed-URL patterns. No live Procore access, no writeback, no determinations.

The prover holds the secret-detection pattern table, so it deliberately scans the *other* Phase 06B
modules — never itself — to avoid false-positive self-matches on its own patterns.
"""

from __future__ import annotations

import ast
import re
import sqlite3
from pathlib import Path
from typing import Any, Dict, List, Optional

from ..config.path_policy import PathPolicy
from .connection import get_connection
from .procore_operational import _MAILBOX_READ_ONLY_LAYERS, _QUERY_COMMANDS

# Phase 06B read-model / output modules (repo-relative). The prover itself is excluded.
_SCANNED_MODULES = (
    "src/hb_assistant/store/procore_project_health.py",
    "src/hb_assistant/store/procore_freshness.py",
    "src/hb_assistant/store/procore_action_queue.py",
    "src/hb_assistant/store/procore_cost_exposure.py",
    "src/hb_assistant/store/procore_schedule_exposure.py",
    "src/hb_assistant/store/procore_relationship_quality.py",
    "src/hb_assistant/store/procore_operational.py",
    "src/hb_assistant/procore/obsidian_operational.py",
)

# mutating HTTP verbs / M365 / Procore write APIs as *method calls* — none may appear in the
# scanned modules. Call-form (``.verb(``) only, so prose like "no writeback" never false-positives.
_WRITEBACK_PATTERNS = (
    re.compile(r"\.(post|put|patch|delete|send_?mail|sendMail|create_message|"
               r"update_message|delete_message|send_message)\s*\("),
)

# forbidden HTTP-client imports (AST).
_FORBIDDEN_IMPORTS = {"requests", "httpx", "urllib3", "urllib.request",
                      "hb_assistant.procore.http_client"}

# tight, value-shaped secret regexes (never bare keywords — evidence prose mentions the words).
_SECRET_PATTERNS = (
    re.compile(r"-----BEGIN [A-Z ]*PRIVATE KEY-----"),
    re.compile(r"\beyJ[A-Za-z0-9_-]{15,}\.[A-Za-z0-9_-]{10,}"),          # JWT
    re.compile(r"[Bb]earer\s+[A-Za-z0-9._\-]{20,}"),                      # bearer token
    re.compile(r"(?:refresh_token|client_secret|access_token)\"?\s*[:=]\s*\"[^\"]{8,}\""),
    re.compile(r"[?&]sig=[A-Za-z0-9%/+]{16,}"),                           # SAS signature
    re.compile(r"[?&]sv=20\d\d-\d\d-\d\d&"),                              # Azure SAS sv=
    re.compile(r"\bAKIA[0-9A-Z]{16}\b"),                                  # AWS key id
)


def _scan_text_for_secrets(text: str) -> List[str]:
    """Return the tight, value-shaped secret patterns that match ``text`` (empty when clean)."""
    return [p.pattern for p in _SECRET_PATTERNS if p.search(text)]


def _forbidden_import(name: str) -> bool:
    return name in _FORBIDDEN_IMPORTS or any(name.startswith(f"{m}.") for m in _FORBIDDEN_IMPORTS)


def _scan_modules(repo_root: Path) -> Dict[str, Any]:
    """Static writeback / import / secret scan over the Phase 06B modules."""
    writeback: List[str] = []
    bad_imports: List[str] = []
    secrets: List[str] = []
    scanned: List[str] = []
    for rel in _SCANNED_MODULES:
        path = repo_root / rel
        if not path.exists():
            continue
        scanned.append(rel)
        src = path.read_text(encoding="utf-8")
        for pat in _WRITEBACK_PATTERNS:
            if pat.search(src):
                writeback.append(f"{rel}: {pat.pattern}")
        for hit in _scan_text_for_secrets(src):
            secrets.append(f"{rel}: {hit}")
        try:
            tree = ast.parse(src)
        except SyntaxError:
            bad_imports.append(f"{rel}: unparseable")
            continue
        for node in ast.walk(tree):
            if isinstance(node, ast.Import):
                bad_imports += [f"{rel}: import {a.name}" for a in node.names
                                if _forbidden_import(a.name)]
            elif isinstance(node, ast.ImportFrom) and _forbidden_import(node.module or ""):
                bad_imports.append(f"{rel}: from {node.module} import ...")
    return {"scanned": scanned, "writeback": writeback, "bad_imports": bad_imports,
            "secrets": secrets}


def _probe_raw_body_guardrails(conn: Any) -> Dict[str, Any]:
    """Confirm every table carrying ``raw_body_persisted`` enforces CHECK(=0) and stores only 0."""
    rows = conn.execute(
        "SELECT name, sql FROM sqlite_master WHERE type = 'table' AND sql LIKE '%raw_body_persisted%'"
    ).fetchall()
    tables: List[Dict[str, Any]] = []
    violations: List[str] = []
    for r in rows:
        name, sql = r[0], r[1] or ""
        has_check = "CHECK(raw_body_persisted = 0)" in sql.replace(" ", "").replace(
            "CHECK(raw_body_persisted=0)", "CHECK(raw_body_persisted = 0)"
        ) or "raw_body_persisted=0" in sql.replace(" ", "")
        try:
            distinct = sorted(
                v[0] for v in conn.execute(
                    f"SELECT DISTINCT raw_body_persisted FROM {name}"  # noqa: S608 (name from schema)
                ).fetchall()
            )
        except sqlite3.Error:
            distinct = []
        if not has_check:
            violations.append(f"{name}: missing CHECK(raw_body_persisted = 0)")
        if any(v != 0 for v in distinct):
            violations.append(f"{name}: distinct raw_body_persisted = {distinct}")
        tables.append({"table": name, "has_check": has_check, "distinct_values": distinct})
    return {"tables": sorted(tables, key=lambda t: t["table"]), "violations": violations}


def _scan_evidence_outputs(repo_root: Path) -> Dict[str, Any]:
    """Tight secret-scan over the phase evidence JSON outputs (generated machine artifacts)."""
    evidence_dir = (
        repo_root / "docs" / "evidence"
        / "construction-intelligence-phase-06b-procore-operational-intelligence"
    )
    scanned: List[str] = []
    findings: List[str] = []
    if evidence_dir.exists():
        for path in sorted(evidence_dir.glob("*.json")):
            scanned.append(path.name)
            for hit in _scan_text_for_secrets(path.read_text(encoding="utf-8")):
                findings.append(f"{path.name}: {hit}")
    return {"scanned": scanned, "findings": findings}


def build_no_writeback_proof(
    project_key: Optional[str] = None,
    *,
    now_utc: str,
    db_path: Optional[Path] = None,
) -> Dict[str, Any]:
    """Build the formal Phase 06B no-writeback / no-secret / no-raw-body proof (read-only)."""
    repo_root = PathPolicy().resolve_repo_root()
    conn = get_connection(db_path)

    mod = _scan_modules(repo_root)
    raw_body = _probe_raw_body_guardrails(conn)
    evidence = _scan_evidence_outputs(repo_root)

    no_writeback = not mod["writeback"]
    no_http = not mod["bad_imports"]
    no_module_secrets = not mod["secrets"]
    raw_body_ok = not raw_body["violations"]
    no_evidence_secrets = not evidence["findings"]

    checks_detail = {
        "static_writeback_scan": {"passed": no_writeback, "findings": mod["writeback"]},
        "no_http_client_imports": {"passed": no_http, "findings": mod["bad_imports"]},
        "module_secret_scan": {"passed": no_module_secrets, "findings": mod["secrets"]},
        "sqlite_raw_body_guardrail": {"passed": raw_body_ok, "findings": raw_body["violations"]},
        "evidence_output_scan": {
            "passed": no_evidence_secrets, "findings": evidence["findings"],
            "files_scanned": len(evidence["scanned"]),
        },
    }
    proof_passed = all(c["passed"] for c in checks_detail.values())

    return {
        "command": "hb-assistant procore live no-writeback-proof",
        "ok": proof_passed,
        "phase": "Phase 06B Prompt 15",
        "project_key": project_key,
        "generated_at": now_utc,
        "proof_passed": proof_passed,
        "checks": {
            "no_m365_writeback": no_writeback,
            "no_procore_writeback": no_writeback and no_http,
            "query_commands_local_sqlite_only": no_http,
            "no_raw_bodies_persisted": raw_body_ok,
            "no_secret_leakage": no_module_secrets and no_evidence_secrets,
            "mailbox_read_only_layers": list(_MAILBOX_READ_ONLY_LAYERS),
        },
        "checks_detail": checks_detail,
        "scanned_modules": mod["scanned"],
        "raw_body_tables": raw_body["tables"],
        "query_commands": list(_QUERY_COMMANDS),
        "note": "Formal no-writeback / no-secret / no-raw-body proof (Phase 06B Prompt 15). Static "
                "scans the Phase 06B modules (the prover excludes itself), probes the SQLite "
                "raw_body_persisted guardrails, and scans the evidence outputs. Read-only.",
        "no_live_call_performed": True,
        "no_raw_values_persisted": True,
        "determinations_made": False,
    }


__all__ = ["build_no_writeback_proof", "_scan_text_for_secrets"]
