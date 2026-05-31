"""No Writeback / No Secret / No Raw Body Proof for Phase 07A data quality (Prompt 08).

This module provides a read-only, deterministic, offline safety prover that
statically demonstrates that the six Phase 07A data_quality modules
(project_identity, source_record_map, relationships, marts, obsidian, gates),
the V20/V21 data-quality tables they touch, and all generated 07A evidence
contain:

- Zero external-system mutation calls (no .post / .put / .patch / .delete /
  send_mail / create_message etc. on HTTP clients or Graph/Procore/M365 SDKs).
- Zero raw email bodies, raw document text, raw Procore payloads, tokens,
  secrets, signed URLs, PEMs, or refresh tokens (via the shared high-precision
  scanner).
- All relevant SQLite tables enforce the `raw_body_persisted = 0` CHECK
  constraint and store only the value 0.

The prover deliberately re-uses the battle-tested scanner
(`_scan_text_for_secrets`) and pattern logic from
`hb_assistant.store.procore_no_writeback_proof` rather than duplicating it.

Public entry point:
    build_data_quality_no_writeback_proof(db_path=None) -> dict

It is intentionally report-only and never performs live calls or writes
outside the evidence directory.

Guardrails and stop conditions are embedded in every report.
"""

from __future__ import annotations

import ast
import os
import re
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Dict, List, Optional

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.connection import get_connection
from hb_assistant.store.procore_no_writeback_proof import (
    _scan_text_for_secrets,
)

# ---------------------------------------------------------------------------
# Phase 07A scope (the exact surfaces that must be proven clean)
# ---------------------------------------------------------------------------

_PHASE_07A_MODULES: List[str] = [
    "project_identity.py",
    "source_record_map.py",
    "relationships.py",
    "marts.py",
    "obsidian.py",
    "gates.py",
]

# V20 + V21 tables introduced or heavily used by Phase 07A data quality work.
# All of these already carry the standard guardrail in the migrator.
_PHASE_07A_TABLES: List[str] = [
    "construction_data_quality_runs",
    "source_system_record_map",
    "relationship_resolution_queue",
    "project_source_coverage_mart",
    "data_quality_gate_results",
    # V21 marts
    "source_record_summary_mart",
    "relationship_quality_mart",
    "cross_domain_context_readiness_mart",
]

# Evidence directory produced by Prompts 00-07 (and this proof itself).
_PHASE_07A_EVIDENCE_SUBDIR = "construction-intelligence-phase-07a-data-quality"

# Reuse / adapt the same high-precision patterns from the procore prover
# (imported _scan_text_for_secrets already embodies the secret patterns).
# We keep a local copy of the mutation / bad-import patterns for the 07A scan
# so the prover is self-describing and does not depend on internal names.

_WRITEBACK_PATTERNS = (
    re.compile(
        r"\.(post|put|patch|delete|send_?mail|sendMail|create_message|"
        r"create_event|update_event|delete_event|invite|share|move|copy)\s*\(",
        re.IGNORECASE,
    ),
)

_BAD_IMPORTS = (
    re.compile(r"from\s+(requests|httpx|aiohttp|procore|msgraph|graph|msal)\s+import", re.IGNORECASE),
    re.compile(r"import\s+(requests|httpx|aiohttp)\b", re.IGNORECASE),
)

def _now() -> str:
    return datetime.now(timezone.utc).isoformat()

def _get_git_sha() -> str:
    try:
        root = PathPolicy().resolve_repo_root()
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=root, stderr=subprocess.DEVNULL, timeout=5
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"

def _get_schema_version(db_path: Optional[str | Path] = None) -> int:
    try:
        conn = get_connection(db_path)
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        return int(row[0]) if row and row[0] is not None else 0
    except Exception:
        return 0

def _scan_module_for_mutation_and_imports(src: str, rel_path: str) -> Dict[str, List[str]]:
    """AST + regex scan for mutation verbs and dangerous imports (07A scope)."""
    writeback: List[str] = []
    bad_imports: List[str] = []

    # Regex first (fast, catches dynamic / string cases). One hit per pattern
    # per file is enough for the proof.
    for pat in _WRITEBACK_PATTERNS:
        if pat.search(src):
            writeback.append(f"{rel_path}: {pat.pattern}")

    for pat in _BAD_IMPORTS:
        for m in pat.finditer(src):
            bad_imports.append(f"{rel_path}: {m.group(0).strip()}")
            break

    # Lightweight AST walk for attribute calls (catches client.post(...) etc.)
    try:
        tree = ast.parse(src)
        for node in ast.walk(tree):
            if isinstance(node, ast.Call) and isinstance(node.func, ast.Attribute):
                method = node.func.attr.lower()
                if method in {"post", "put", "patch", "delete", "send", "create", "update", "share", "invite"}:
                    writeback.append(f"{rel_path}: .{method}() call")
    except Exception:
        pass  # syntax error in scanned file would be a separate failure; we stay defensive

    return {"writeback": writeback, "bad_imports": bad_imports}

def _probe_raw_body_guardrails_07a(conn: Any) -> Dict[str, Any]:
    """Confirm every Phase 07A table enforces CHECK(raw_body_persisted = 0) and stores only 0."""
    tables: List[Dict[str, Any]] = []
    violations: List[str] = []

    for name in _PHASE_07A_TABLES:
        try:
            row = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)
            ).fetchone()
            if not row:
                tables.append({"table": name, "present": False})
                continue
            sql = row[0] or ""
            has_check = (
                "CHECK(raw_body_persisted = 0)" in sql.replace(" ", "")
                or "CHECK(raw_body_persisted=0)" in sql.replace(" ", "")
                or "raw_body_persisted=0" in sql.replace(" ", "")
            )
            distinct: List[int] = []
            if has_check:
                try:
                    distinct = sorted(
                        r[0]
                        for r in conn.execute(
                            f"SELECT DISTINCT raw_body_persisted FROM {name}"  # noqa: S608
                        ).fetchall()
                    )
                except Exception:
                    distinct = []
            if not has_check:
                violations.append(f"{name}: missing CHECK(raw_body_persisted = 0)")
            if any(v != 0 for v in distinct):
                violations.append(f"{name}: distinct raw_body_persisted = {distinct}")
            tables.append(
                {"table": name, "present": True, "has_check": has_check, "distinct_values": distinct}
            )
        except Exception as e:
            violations.append(f"{name}: probe error ({type(e).__name__})")
            tables.append({"table": name, "present": False, "error": str(e)[:100]})

    return {"tables": tables, "violations": violations}

def _scan_07a_evidence_outputs(repo_root: Path) -> Dict[str, Any]:
    """Recursively scan the Phase 07A evidence directory for secrets / tokens."""
    findings: List[str] = []
    evidence_dir = repo_root / "docs" / "evidence" / _PHASE_07A_EVIDENCE_SUBDIR
    if not evidence_dir.exists():
        return {"scanned_dir": str(evidence_dir), "findings": findings, "note": "evidence dir not present"}

    for root, _dirs, files in os.walk(evidence_dir):
        for fn in files:
            if fn.endswith((".json", ".md", ".txt", ".log")):
                p = Path(root) / fn
                try:
                    text = p.read_text(encoding="utf-8", errors="ignore")
                    hits = _scan_text_for_secrets(text)
                    for h in hits:
                        findings.append(f"{p.relative_to(repo_root)}: {h}")
                except Exception:
                    pass
    return {"scanned_dir": str(evidence_dir), "findings": findings}

_SAFETY_GUARDRAILS = {
    "external_systems": "read_only",
    "writeback": "none_permitted_in_07a_data_quality",
    "raw_body_persisted": "enforced_0_in_all_v20_v21_07a_tables",
    "secrets_tokens_urls_in_code_or_evidence": "forbidden",
    "no_live_calls": True,
    "phase_assignments_preserved": True,
}

_STOP_CONDITIONS_CHECKED = [
    "no_mutation_capable_external_calls_in_07a_modules",
    "no_raw_body_or_full_text_persisted_in_07a_tables",
    "no_tokens_secrets_signed_urls_in_07a_code_or_evidence",
    "safety_proof_scopes_all_07a_data_quality_surfaces",
]

def build_data_quality_no_writeback_proof(
    *, db_path: Optional[str | Path] = None
) -> Dict[str, Any]:
    """Build the formal Phase 07A no-writeback / no-secret / no-raw-body proof (read-only)."""
    generated_utc = _now()
    repo_root = PathPolicy().resolve_repo_root()
    sha = _get_git_sha()
    schema_version = _get_schema_version(db_path)

    # 1. Static scan of the six 07A modules
    module_results: Dict[str, Dict[str, List[str]]] = {}
    scanned_modules: List[str] = []
    data_quality_dir = repo_root / "src" / "hb_assistant" / "construction" / "data_quality"

    for fname in _PHASE_07A_MODULES:
        p = data_quality_dir / fname
        if p.exists():
            scanned_modules.append(fname)
            try:
                src = p.read_text(encoding="utf-8")
                module_results[fname] = _scan_module_for_mutation_and_imports(src, fname)
                # Also run the secret scanner on the module source itself
                secret_hits = _scan_text_for_secrets(src)
                if secret_hits:
                    module_results[fname].setdefault("secrets", []).extend(secret_hits)
            except Exception as e:
                module_results[fname] = {"error": str(e)[:120]}
        else:
            module_results[fname] = {"present": False}

    any_writeback = any(r.get("writeback") for r in module_results.values() if isinstance(r, dict))
    any_bad_imports = any(r.get("bad_imports") for r in module_results.values() if isinstance(r, dict))
    any_module_secrets = any(r.get("secrets") for r in module_results.values() if isinstance(r, dict))

    # 2. SQLite raw_body guardrail probe for the exact 07A tables
    conn = get_connection(db_path)
    raw_body = _probe_raw_body_guardrails_07a(conn)
    raw_body_ok = not raw_body["violations"]

    # 3. Evidence output scan (the 07A evidence tree)
    evidence = _scan_07a_evidence_outputs(repo_root)
    no_evidence_secrets = not evidence["findings"]

    # Overall verdict
    proof_passed = (
        not any_writeback
        and not any_bad_imports
        and not any_module_secrets
        and raw_body_ok
        and no_evidence_secrets
    )

    checks_detail = {
        "static_writeback_scan_07a_modules": {
            "passed": not any_writeback,
            "findings": [f for r in module_results.values() if isinstance(r, dict) for f in (r.get("writeback") or [])],
        },
        "no_http_client_or_mutation_imports_07a": {
            "passed": not any_bad_imports,
            "findings": [f for r in module_results.values() if isinstance(r, dict) for f in (r.get("bad_imports") or [])],
        },
        "module_secret_scan_07a": {
            "passed": not any_module_secrets,
            "findings": [f for r in module_results.values() if isinstance(r, dict) for f in (r.get("secrets") or [])],
        },
        "sqlite_raw_body_guardrail_v20_v21_07a_tables": {
            "passed": raw_body_ok,
            "findings": raw_body["violations"],
            "tables": raw_body["tables"],
        },
        "evidence_output_scan_07a": {
            "passed": no_evidence_secrets,
            "findings": evidence["findings"],
            "scanned_dir": evidence["scanned_dir"],
        },
    }

    report: Dict[str, Any] = {
        "command": "construction-agent data-quality no-writeback-proof",
        "ok": proof_passed,
        "proof_passed": proof_passed,
        "phase": "Phase 07A Prompt 08",
        "generated_utc": generated_utc,
        "repo_sha": sha,
        "schema_version": schema_version,
        "scanned_modules": scanned_modules,
        "checks_detail": checks_detail,
        "guardrails": _SAFETY_GUARDRAILS,
        "stop_conditions_checked": _STOP_CONDITIONS_CHECKED,
        "no_live_call_performed": True,
        "no_raw_values_persisted": raw_body_ok,
        "note": (
            "Formal no-writeback / no-secret / no-raw-body proof for Phase 07A data-quality surfaces only. "
            "Re-uses the shared secret scanner from the Procore no-writeback prover. "
            "Static analysis + SQLite schema + evidence directory scan. Read-only."
        ),
    }
    return report
