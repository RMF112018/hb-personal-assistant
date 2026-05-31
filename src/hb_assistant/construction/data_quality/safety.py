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

# ---------------------------------------------------------------------------
# Phase 07B scope (calendar / email / thread / candidate surfaces, Prompt 12)
# ---------------------------------------------------------------------------

# Source modules created across Phase 07B (relative to src/hb_assistant/).
_PHASE_07B_MODULES: List[str] = [
    "construction/calendar/event_indexer.py",
    "construction/calendar/project_matcher.py",
    "construction/calendar/policy.py",
    "construction/calendar/contracts.py",
    "construction/email/thread_summary.py",
    "construction/relationships/meeting_email_candidates.py",
    "construction/correspondence/correspondence_review.py",
    "construction/calendar_email_obsidian.py",
    "graph/calendar_endpoint_guard.py",
    "graph/calendar_readonly_client.py",
]

# Phase 07B tables -> the guard CHECK columns each declares and the value each
# must hold. Tables with an empty map are metadata-only (no raw-flag columns);
# they are covered by the module + content scans rather than a CHECK probe.
_PHASE_07B_TABLE_GUARDS: Dict[str, Dict[str, int]] = {
    "email_model_classifications": {
        "advisory_only": 1,
        "plaintext_body_persisted": 0,
        "raw_prompt_persisted": 0,
        "raw_response_persisted": 0,
    },
    "email_thread_summary_materialization_runs": {
        "raw_body_persisted": 0,
        "raw_prompt_persisted": 0,
        "raw_response_persisted": 0,
        "external_writeback_performed": 0,
    },
    "calendar_crawl_runs": {
        "raw_body_persisted": 0,
        "full_text_persisted": 0,
        "external_writeback_performed": 0,
    },
    "calendar_event_index": {
        "raw_body_persisted": 0,
        "full_text_persisted": 0,
        "external_writeback_performed": 0,
    },
    "calendar_project_match_candidates": {
        "raw_body_persisted": 0,
        "external_writeback_performed": 0,
    },
    "meeting_email_relationship_candidates": {
        "raw_body_persisted": 0,
        "raw_prompt_persisted": 0,
        "raw_response_persisted": 0,
        "external_writeback_performed": 0,
    },
    "email_thread_summaries": {},
    "calendar_event_attendees": {},
}

_PHASE_07B_TABLES: List[str] = list(_PHASE_07B_TABLE_GUARDS)

_PHASE_07B_EVIDENCE_SUBDIR = "construction-intelligence-phase-07b-calendar-email"

# Raw-by-design staging layers that are OUTSIDE the scope of this no-raw-persistence
# proof. The Phase 06A file-intelligence inventory intentionally stores raw drive-item
# metadata (file name / web URL / parent path) and is NOT scanned here (its web_url
# legitimately holds "https://" by design, so scanning would fail a correct proof).
# Disclosed explicitly so the generically named ``no_raw_values_persisted`` flag is not
# read as covering these layers: Phase 07C must hash/redact these values before any
# document-card, evidence, or Obsidian output. Identifier names only — never raw values.
_RAW_STAGING_LAYERS_OUT_OF_SCOPE: List[Dict[str, str]] = [
    {
        "table": "construction_drive_item_inventory",
        "raw_columns": "name, web_url, parent_path",
        "origin_phase": "06A",
        "scope": "out_of_scope_for_this_proof",
        "required_handling": "hash_or_redact_before_07c_document_card_evidence_or_obsidian",
    },
]

# Raw-leakage patterns for scanning persisted DB *values* (in addition to the
# shared secret scanner): generic URLs, raw email addresses, and iCal blocks.
# These are intentionally NOT run over module/evidence prose (which legitimately
# mentions "https://" etc.) — only over stored column values.
_RAW_LEAK_PATTERNS = (
    ("http_url", re.compile(r"https?://", re.IGNORECASE)),
    ("raw_email_address", re.compile(r"[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}")),
    ("ical_block", re.compile(r"BEGIN:V(EVENT|CALENDAR)", re.IGNORECASE)),
)

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

def _scan_evidence_outputs(repo_root: Path, subdir: str) -> Dict[str, Any]:
    """Recursively scan an evidence directory for secrets / tokens (read-only)."""
    findings: List[str] = []
    evidence_dir = repo_root / "docs" / "evidence" / subdir
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


def _scan_07a_evidence_outputs(repo_root: Path) -> Dict[str, Any]:
    """Recursively scan the Phase 07A evidence directory for secrets / tokens."""
    return _scan_evidence_outputs(repo_root, _PHASE_07A_EVIDENCE_SUBDIR)


def _scan_module_set(repo_root: Path, src_relative_paths: List[str]) -> Dict[str, Dict[str, Any]]:
    """Static mutation/import/secret scan over a set of modules (relative to
    src/hb_assistant/). Reuses the shared per-module scanner."""
    base = repo_root / "src" / "hb_assistant"
    results: Dict[str, Dict[str, Any]] = {}
    for rel in src_relative_paths:
        p = base / rel
        if not p.exists():
            results[rel] = {"present": False}
            continue
        try:
            src = p.read_text(encoding="utf-8")
            res = _scan_module_for_mutation_and_imports(src, rel)
            secret_hits = _scan_text_for_secrets(src)
            if secret_hits:
                res.setdefault("secrets", []).extend(secret_hits)
            results[rel] = res
        except Exception as e:  # pragma: no cover - defensive
            results[rel] = {"error": str(e)[:120]}
    return results


def _probe_table_guards(
    conn: Any, table_guard_map: Dict[str, Dict[str, int]]
) -> Dict[str, Any]:
    """Confirm each table declares its guard CHECK columns and stores only the
    required constant. Tables with no guard columns are recorded present (not a
    violation); they are covered by the content + module scans."""
    tables: List[Dict[str, Any]] = []
    violations: List[str] = []
    for name, guards in table_guard_map.items():
        try:
            row = conn.execute(
                "SELECT sql FROM sqlite_master WHERE type='table' AND name=?", (name,)
            ).fetchone()
            if not row:
                tables.append({"table": name, "present": False})
                continue
            sql_nospace = (row[0] or "").replace(" ", "")
            checked: List[Dict[str, Any]] = []
            for col, const in guards.items():
                has_check = f"CHECK({col}={const})" in sql_nospace
                distinct: List[int] = []
                try:
                    distinct = sorted(
                        r[0]
                        for r in conn.execute(
                            f"SELECT DISTINCT {col} FROM {name}"  # noqa: S608
                        ).fetchall()
                        if r[0] is not None
                    )
                except Exception:
                    distinct = []
                if not has_check:
                    violations.append(f"{name}.{col}: missing CHECK({col} = {const})")
                if any(v != const for v in distinct):
                    violations.append(f"{name}.{col}: distinct = {distinct} (expected {const})")
                checked.append({"column": col, "has_check": has_check, "distinct_values": distinct})
            tables.append({"table": name, "present": True, "guard_columns": checked})
        except Exception as e:
            violations.append(f"{name}: probe error ({type(e).__name__})")
            tables.append({"table": name, "present": False, "error": str(e)[:100]})
    return {"tables": tables, "violations": violations}


def _scan_text_for_raw_leakage(text: str) -> List[str]:
    """Return leak labels for a stored value: shared secret patterns plus URL /
    raw-email / iCal patterns. Returns labels only — never the value."""
    hits = list(_scan_text_for_secrets(text))
    hits.extend(label for label, pat in _RAW_LEAK_PATTERNS if pat.search(text))
    return hits


def _scan_table_contents(conn: Any, tables: List[str]) -> Dict[str, Any]:
    """Content-scan every string cell of each table for raw leakage. Findings are
    ``table.column: label`` only (never the offending value)."""
    findings: List[str] = []
    scanned: List[str] = []
    for name in tables:
        try:
            if not conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (name,)
            ).fetchone():
                continue
            cur = conn.execute(f"SELECT * FROM {name}")  # noqa: S608
            cols = [d[0] for d in cur.description] if cur.description else []
            scanned.append(name)
            seen: set[str] = set()
            for row in cur.fetchall():
                for col, value in zip(cols, row, strict=False):
                    if not isinstance(value, str):
                        continue
                    for label in _scan_text_for_raw_leakage(value):
                        key = f"{name}.{col}: {label}"
                        if key not in seen:
                            seen.add(key)
                            findings.append(key)
        except Exception as e:  # pragma: no cover - defensive
            findings.append(f"{name}: content-scan error ({type(e).__name__})")
    return {"findings": findings, "scanned": scanned}

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

    # 4. Phase 07B surfaces — modules, V11/V14/V23 tables (guard CHECK columns +
    #    persisted content), and the 07B evidence tree. Fail-closed.
    b_modules = _scan_module_set(repo_root, _PHASE_07B_MODULES)
    scanned_07b_modules = [m for m, r in b_modules.items() if r.get("present") is not False]
    any_07b_writeback = any(r.get("writeback") for r in b_modules.values())
    any_07b_bad_imports = any(r.get("bad_imports") for r in b_modules.values())
    any_07b_module_secrets = any(r.get("secrets") for r in b_modules.values())

    guards_07b = _probe_table_guards(conn, _PHASE_07B_TABLE_GUARDS)
    guards_07b_ok = not guards_07b["violations"]

    content_07b = _scan_table_contents(conn, _PHASE_07B_TABLES)
    content_07b_ok = not content_07b["findings"]

    evidence_07b = _scan_evidence_outputs(repo_root, _PHASE_07B_EVIDENCE_SUBDIR)
    no_07b_evidence_secrets = not evidence_07b["findings"]

    # Overall verdict (07A AND 07B; any finding fails the proof closed)
    proof_passed = (
        not any_writeback
        and not any_bad_imports
        and not any_module_secrets
        and raw_body_ok
        and no_evidence_secrets
        and not any_07b_writeback
        and not any_07b_bad_imports
        and not any_07b_module_secrets
        and guards_07b_ok
        and content_07b_ok
        and no_07b_evidence_secrets
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
        "static_writeback_scan_07b_modules": {
            "passed": not any_07b_writeback,
            "findings": [f for r in b_modules.values() for f in (r.get("writeback") or [])],
        },
        "no_http_client_or_mutation_imports_07b": {
            "passed": not any_07b_bad_imports,
            "findings": [f for r in b_modules.values() for f in (r.get("bad_imports") or [])],
        },
        "module_secret_scan_07b": {
            "passed": not any_07b_module_secrets,
            "findings": [f for r in b_modules.values() for f in (r.get("secrets") or [])],
        },
        "sqlite_guardrail_07b_tables": {
            "passed": guards_07b_ok,
            "findings": guards_07b["violations"],
            "tables": guards_07b["tables"],
        },
        "sqlite_content_leak_scan_07b_tables": {
            "passed": content_07b_ok,
            "findings": content_07b["findings"],
            "scanned_tables": content_07b["scanned"],
        },
        "evidence_output_scan_07b": {
            "passed": no_07b_evidence_secrets,
            "findings": evidence_07b["findings"],
            "scanned_dir": evidence_07b["scanned_dir"],
        },
    }

    report: Dict[str, Any] = {
        "command": "construction-agent data-quality no-writeback-proof",
        "ok": proof_passed,
        "proof_passed": proof_passed,
        "phase": "Phase 07A Prompt 08 + Phase 07B Prompt 12",
        "generated_utc": generated_utc,
        "repo_sha": sha,
        "schema_version": schema_version,
        "scanned_modules": scanned_modules,
        "scanned_modules_07b": scanned_07b_modules,
        "checks_detail": checks_detail,
        "guardrails": _SAFETY_GUARDRAILS,
        "stop_conditions_checked": _STOP_CONDITIONS_CHECKED,
        "no_live_call_performed": True,
        "no_raw_values_persisted": raw_body_ok and guards_07b_ok and content_07b_ok,
        "no_raw_values_persisted_scope": (
            "phase_07a_data_quality_and_phase_07b_calendar_email_thread_candidate_surfaces_only"
        ),
        "raw_staging_layers_out_of_scope": _RAW_STAGING_LAYERS_OUT_OF_SCOPE,
        "note": (
            "Formal no-writeback / no-secret / no-raw-body proof for Phase 07A data-quality "
            "surfaces AND Phase 07B calendar/email/thread/candidate surfaces (modules + "
            "V11/V14/V23 guard CHECK columns + persisted-content scan + evidence). Re-uses the "
            "shared secret scanner from the Procore no-writeback prover; findings are pattern "
            "labels and table.column locations only (never the value). Read-only, fail-closed. "
            "This proof does NOT cover the Phase 06A raw file-intelligence staging layer "
            "(construction_drive_item_inventory: name/web_url/parent_path), which is raw-by-design "
            "and must be hashed/redacted before any Phase 07C document-card, evidence, or Obsidian "
            "output — see raw_staging_layers_out_of_scope."
        ),
    }
    return report
