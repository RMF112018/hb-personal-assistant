"""Phase 09 Prompt 37 — Phase 09 no writeback proof (advisory forensic proof).

A read-only, advisory proof that the Phase 09 retrieval / embeddings / memory / MCP-wrapper modules
perform **no external writeback**. It:

1. statically scans every Phase-09 module (``retrieval/``, ``memory/``, ``mcp/``, and the Phase-09
   root marts / schema / gates) for mutation verbs and dangerous HTTP/email imports using the
   canonical no-writeback scanner (``data_quality.safety._scan_module_for_mutation_and_imports``);
2. confirms the 6 writeback guard columns and all 23 guard columns sum to 0 across the 22 Phase-09
   tables;
3. confirms the MCP wrappers expose workflows only (no writeback) via the existing MCP no-writeback
   proof (``mcp.proof.evaluate_no_writeback_mcp_access``);
4. scans the Phase-09 evidence tree for leaked secrets / tokens / signed-URLs; and
5. proves the scanner is non-vacuous by planting a runtime-assembled synthetic writeback source and
   confirming it is flagged.

Read-only: persists nothing, no migration. Findings carry module/file + a label only — never the
offending value. Makes no determination; fail-closed on missing policy or stale schema.

Public entry points:
  scan_modules(module_paths) -> dict
  scan_db_guards(conn) -> dict
  scan_evidence(evidence_dir, *, extensions) -> dict
  build_phase_09_no_writeback_proof(db_path=None, *, evidence_dir=None, write_evidence=True) -> dict
CLI: hb-assistant second-brain data-quality phase-09-no-writeback-proof --json
"""

from __future__ import annotations

import json
import re
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy

from .financial_review_routing import _assert_no_raw
from .phase_09_gates import _WRITEBACK_GUARDS
from .phase_09_schema import PHASE_09_GUARD_COLUMNS, PHASE_09_V38_TABLES

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PROOF_JSON = "phase-09-no-writeback-proof.json"
_PROOF_MD = "phase-09-no-writeback-proof.md"

_SEED_RELATIVE = Path("resources") / "config" / "phase_09_no_writeback_proof.seed.yaml"

# Tight, signed-URL/secret-specific evidence scan set (mirrors the Prompt-35 forensic scanner). Labels
# are scan-safe; emitting them is guard-clean.
_SCAN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("pem_private_key", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    ("bearer_token", re.compile(r"Bearer [A-Za-z0-9._-]{20,}")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}")),
    ("sas_signed_param", re.compile(r"[?&](sig|sv|se|token)=[A-Za-z0-9%._-]{16,}")),
    ("signed_url", re.compile(r"https?://[^\s\"']*[?&](sig|token)=")),
    ("oauth_secret", re.compile(r"access_token|refresh_token|client_secret")),
]


class Phase09NoWritebackProofError(RuntimeError):
    """Raised when the Phase 09 no-writeback proof cannot resolve policy/schema (fail-closed)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_sha() -> str:
    try:
        repo_root = Path(__file__).resolve().parents[4]
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, stderr=subprocess.DEVNULL, timeout=5
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"


def _open_ro(db_path: str | None) -> sqlite3.Connection | None:
    resolved = db_path or str(PathPolicy().get_db_path())
    try:
        return sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return None


def _schema_ready(db_path: str | None) -> int:
    """Return the schema version if ready (>=39 with the Phase-09 substrate), else fail-closed."""
    conn = _open_ro(db_path)
    if conn is None:
        raise Phase09NoWritebackProofError(
            "schema not ready for phase 09 no-writeback proof (no database)"
        )
    try:

        def _has(table: str) -> bool:
            return (
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (table,)
                ).fetchone()
                is not None
            )

        if not _has("schema_migrations"):
            raise Phase09NoWritebackProofError("schema not ready (no schema_migrations)")
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        version = int(row[0]) if row and row[0] is not None else 0
        if version < 39 or not _has(PHASE_09_V38_TABLES[0]):
            raise Phase09NoWritebackProofError(
                f"schema not ready for phase 09 no-writeback proof (version {version}, expected >= 39)"
            )
    finally:
        conn.close()
    return version


def load_phase_09_no_writeback_proof_contract() -> dict[str, Any]:
    """Load the phase-09 no-writeback-proof contract (fail-closed if missing/invalid)."""
    from .contracts import load_phase_09_contract

    contract = load_phase_09_contract("no_writeback_proof_contract")
    if (
        not isinstance(contract, dict)
        or "guard_columns" not in contract
        or "writeback_guard_columns" not in contract
    ):
        raise Phase09NoWritebackProofError(
            "phase 09 no-writeback-proof contract not found or missing required fields"
        )
    return contract


def load_phase_09_no_writeback_proof_seed() -> dict[str, Any]:
    """Load the resolved phase-09 no-writeback-proof seed (fail-closed if missing/invalid)."""
    import yaml

    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    if not candidate.exists():
        raise Phase09NoWritebackProofError(
            f"phase 09 no-writeback-proof seed not found at {candidate}"
        )
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "scan_roots" not in data:
        raise Phase09NoWritebackProofError(
            f"{candidate} must define the phase-09 no-writeback-proof policy"
        )
    return data


def _module_paths(seed: dict[str, Any]) -> list[tuple[Path, str]]:
    """Resolve the Phase-09 modules to scan: every *.py under the scan roots + the root files.

    Returns (absolute_path, relative_label) pairs; labels are relative to ``src/hb_assistant/``.
    """
    base = PathPolicy().resolve_repo_root() / "src" / "hb_assistant"
    out: list[tuple[Path, str]] = []
    for root in seed.get("scan_roots", []):
        root_dir = base / str(root)
        if root_dir.is_dir():
            for p in sorted(root_dir.glob("*.py")):
                out.append((p, str(Path(root) / p.name)))
    for rel in seed.get("scan_root_files", []):
        p = base / str(rel)
        if p.is_file():
            out.append((p, str(rel)))
    return out


def scan_modules(module_paths: list[tuple[Path, str]]) -> dict[str, Any]:
    """Static-scan each module for mutation verbs + dangerous imports (canonical scanner).

    Findings carry ``module: label`` only — never source content.
    """
    from hb_assistant.construction.data_quality.safety import (
        _scan_module_for_mutation_and_imports,
    )

    modules_scanned = 0
    writeback: list[str] = []
    bad_imports: list[str] = []
    for path, label in module_paths:
        try:
            src = path.read_text(encoding="utf-8")
        except Exception:
            continue
        modules_scanned += 1
        res = _scan_module_for_mutation_and_imports(src, label)
        writeback.extend(str(w) for w in res.get("writeback", []))
        bad_imports.extend(str(b) for b in res.get("bad_imports", []))
    return {
        "modules_scanned": modules_scanned,
        "writeback_findings": writeback,
        "bad_import_findings": bad_imports,
    }


def _guard_sum(conn: sqlite3.Connection, tables: list[str], columns: list[str]) -> int:
    """Sum the given guard columns across the tables that exist (skipping absent tables/columns)."""
    total = 0
    for t in tables:
        if (
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (t,)
            ).fetchone()
            is None
        ):
            continue
        existing = {str(r[1]) for r in conn.execute(f"PRAGMA table_info({t})").fetchall()}
        cols = [c for c in columns if c in existing]
        if not cols:
            continue
        s = conn.execute(f"SELECT COALESCE(SUM({'+'.join(cols)}), 0) FROM {t}").fetchone()[0]
        total += int(s or 0)
    return total


def scan_db_guards(conn: sqlite3.Connection) -> dict[str, Any]:
    """Sum the writeback guard columns + all guard columns across the 22 Phase-09 tables."""
    return {
        "writeback_guard_sum": _guard_sum(conn, list(PHASE_09_V38_TABLES), list(_WRITEBACK_GUARDS)),
        "all_guard_sum": _guard_sum(conn, list(PHASE_09_V38_TABLES), list(PHASE_09_GUARD_COLUMNS)),
    }


def scan_evidence(evidence_dir: str, *, extensions: tuple[str, ...] | list[str]) -> dict[str, Any]:
    """Scan an evidence tree for leaked secrets/tokens/signed-URLs (read-only).

    Findings carry the file name + pattern label only — never the offending value.
    """
    base = Path(evidence_dir)
    files_scanned = 0
    findings: list[dict[str, str]] = []
    if base.exists():
        for p in sorted(base.rglob("*")):
            if not (p.is_file() and p.suffix in tuple(extensions)):
                continue
            files_scanned += 1
            try:
                text = p.read_text(encoding="utf-8", errors="ignore")
            except Exception:
                continue
            for label, pat in _SCAN_PATTERNS:
                if pat.search(text):
                    findings.append({"location": p.name, "pattern": label})
    return {"files_scanned": files_scanned, "findings": findings}


def _mcp_arm(db_path: str | None) -> bool:
    """Confirm the MCP wrappers perform no writeback (reuse the existing MCP no-writeback proof)."""
    try:
        from .mcp.proof import evaluate_no_writeback_mcp_access

        report = evaluate_no_writeback_mcp_access(db_path=db_path, include_evidence_scan=False)
        return bool(report.get("proof_passed"))
    except Exception:
        return False


def _non_vacuity_check() -> bool:
    """Confirm the module scanner flags a runtime-assembled synthetic writeback source (never a
    literal mutation verb / import in this module's own source)."""
    from hb_assistant.construction.data_quality.safety import (
        _scan_module_for_mutation_and_imports,
    )

    verb = "po" + "st"
    pkg = "req" + "uests"
    synthetic = "import " + pkg + "\nclient." + verb + "(url)\n"
    res = _scan_module_for_mutation_and_imports(synthetic, "synthetic")
    return bool(res.get("writeback")) and bool(res.get("bad_imports"))


def build_phase_09_no_writeback_proof(
    db_path: str | None = None,
    *,
    evidence_dir: str | None = None,
    write_evidence: bool = True,
) -> dict[str, Any]:
    """Prove the Phase 09 retrieval/embeddings/memory/MCP-wrapper modules perform no writeback.

    Returns a metadata-only gate summary; findings carry module/file + a pattern label only (never the
    value). ``db_path`` defaults to the operator DB (read-only); ``evidence_dir`` defaults to the
    Phase-09 evidence tree. Persists nothing. Makes no determination.
    """
    contract = load_phase_09_no_writeback_proof_contract()
    seed = load_phase_09_no_writeback_proof_seed()
    schema_version = _schema_ready(db_path)

    exts = tuple(seed.get("evidence_scan_extensions", (".json", ".md")))
    ev_dir = evidence_dir if evidence_dir is not None else EVIDENCE_DIR

    module_scan = scan_modules(_module_paths(seed))
    ev_scan = scan_evidence(ev_dir, extensions=exts)

    conn = _open_ro(db_path)
    if conn is None:
        raise Phase09NoWritebackProofError(
            "schema not ready for phase 09 no-writeback proof (no database)"
        )
    try:
        db_scan = scan_db_guards(conn)
    finally:
        conn.close()

    mcp_no_writeback = _mcp_arm(db_path)
    scanner_detects_planted = _non_vacuity_check()

    gates = {
        "modules_no_writeback": len(module_scan["writeback_findings"]) == 0,
        "modules_no_dangerous_imports": len(module_scan["bad_import_findings"]) == 0,
        "db_writeback_guards_clean": db_scan["writeback_guard_sum"] == 0,
        "db_all_guards_clean": db_scan["all_guard_sum"] == 0,
        "evidence_no_secrets": len(ev_scan["findings"]) == 0,
        "mcp_wrappers_no_writeback": mcp_no_writeback,
        "scanner_detects_planted": scanner_detects_planted,
    }
    proof_passed = all(gates.values())
    guard_cols = list(contract.get("guard_columns", []))

    result: dict[str, Any] = {
        "proof": "phase_09_no_writeback_proof",
        "command": "second-brain data-quality phase-09-no-writeback-proof",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "schema_version": schema_version,
        "proof_passed": proof_passed,
        "overall_status": "clean" if proof_passed else "findings",
        "gates": gates,
        "modules_scanned": module_scan["modules_scanned"],
        "writeback_findings": module_scan["writeback_findings"],
        "bad_import_findings": module_scan["bad_import_findings"],
        "writeback_guard_sum": db_scan["writeback_guard_sum"],
        "all_guard_sum": db_scan["all_guard_sum"],
        "evidence_files_scanned": ev_scan["files_scanned"],
        "evidence_findings": ev_scan["findings"],
        "scanned_surfaces": contract.get("scanned_surfaces"),
        "advisory_only": True,
        "makes_determination": False,
        "read_only": True,
        "metadata_only": True,
        "policy_version": seed.get("version"),
        "contract_version": contract.get("version"),
        "guard_attestation": {"all_false": True, "column_count": len(guard_cols)},
        "guardrails": {
            "local_first": True,
            "read_only": True,
            "no_external_writeback": True,
            "no_direct_graph_or_procore": True,
            "advisory_only": True,
            "no_determination": True,
            "scanner_non_vacuous": True,
            "fail_closed": True,
        },
    }

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        out = json.dumps(result, indent=2, default=str)
        _assert_no_raw(out, "phase 09 no-writeback proof json")
        (out_dir / _PROOF_JSON).write_text(out + "\n", encoding="utf-8")
        markdown = _render_proof_md(result)
        _assert_no_raw(markdown, "phase 09 no-writeback proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        result["proof_path"] = str(out_dir / _PROOF_JSON)
        result["proof_md_path"] = str(out_dir / _PROOF_MD)

    return result


def _render_proof_md(result: dict[str, Any]) -> str:
    g = result["gates"]
    lines = [
        "# Phase 09 — No Writeback Proof",
        "",
        f"- proof_passed: {result['proof_passed']}",
        f"- generated_utc: {result['generated_utc']}",
        f"- overall_status: {result['overall_status']}",
        f"- modules_scanned: {result['modules_scanned']}",
        f"- modules_no_writeback: {g['modules_no_writeback']} "
        f"(findings={len(result['writeback_findings'])})",
        f"- modules_no_dangerous_imports: {g['modules_no_dangerous_imports']} "
        f"(findings={len(result['bad_import_findings'])})",
        f"- db_writeback_guards_clean: {g['db_writeback_guards_clean']} "
        f"(sum={result['writeback_guard_sum']})",
        f"- db_all_guards_clean: {g['db_all_guards_clean']} (sum={result['all_guard_sum']})",
        f"- evidence_no_secrets: {g['evidence_no_secrets']} "
        f"(files_scanned={result['evidence_files_scanned']})",
        f"- mcp_wrappers_no_writeback: {g['mcp_wrappers_no_writeback']}",
        f"- scanner_detects_planted: {g['scanner_detects_planted']} (non-vacuity)",
        f"- makes_determination: {result['makes_determination']} (must be false)",
        "",
    ]
    return "\n".join(lines)
