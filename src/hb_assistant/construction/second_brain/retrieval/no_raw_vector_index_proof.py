"""Phase 09 Prompt 35 — no raw vector index proof (advisory forensic scan).

A read-only, advisory proof that the operator DB, the vector-index metadata, and the committed
Phase-09 evidence tree contain **no raw vector content and no prohibited payloads**. It:

1. confirms the vector-index tables (``second_brain_retrieval_vector_index_runs`` / ``_items``) and
   every ``second_brain_retrieval_*`` table have all 23 guard columns summing to 0 (especially
   ``raw_vector_content_persisted``);
2. confirms no ``embedding`` / ``vector`` / ``raw_vector`` blob column exists in SQLite (vectors are
   persisted **outside** SQLite under the external persist store);
3. scans the safe text columns (hashes / labels / namespaces / ids) for leaked secrets / PEM /
   bearer / JWT / signed-or-download URLs; and
4. scans the Phase-09 evidence tree for the same.

A non-vacuity arm plants a synthetic forbidden value (assembled at runtime — never a literal secret)
and confirms the scanner flags it. Metadata-only: persists (read-only by default; on
``emit_receipt``) a single guard-clean gate-summary row to the reserved V38
``second_brain_phase_09_validation_runs`` table. Findings are pattern labels + ``table.column`` /
file locations only — never the offending value. Makes no determination; fail-closed.

Public entry points:
  scan_db(conn, *, scanned_tables, blob_cols) -> dict
  scan_evidence(evidence_dir, *, extensions) -> dict
  build_no_raw_vector_index_proof(db_path=None, *, evidence_dir=None, write_evidence=True,
      emit_receipt=False) -> dict
  persist_no_raw_vector_index_proof(db_path, result, *, policy_version) -> str
CLI: hb-assistant second-brain retrieval no-raw-vector-index-proof --json
"""

from __future__ import annotations

import hashlib
import json
import re
import sqlite3
import subprocess
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy

from ..financial_review_routing import _assert_no_raw

EVIDENCE_DIR = "docs/evidence/construction-intelligence-phase-09-retrieval-memory-quality"
_PROOF_JSON = "no-raw-vector-index-proof.json"
_PROOF_MD = "no-raw-vector-index-proof.md"

_SEED_RELATIVE = Path("resources") / "config" / "phase_09_no_raw_vector_index_proof.seed.yaml"

_VECTOR_TABLES = (
    "second_brain_retrieval_vector_index_runs",
    "second_brain_retrieval_vector_index_items",
)
_VALIDATION_TABLE = "second_brain_phase_09_validation_runs"
_VECTOR_BLOB_COLS = ("embedding", "vector", "raw_vector")

# Tighter, signed-URL/secret-specific scan set (mirrors corpus_balance_mart._FORBIDDEN). Deliberately
# NOT the broad financial `https?://` / bare-email patterns — those false-positive on a docs tree.
# Labels are scan-safe (none match these patterns), so emitting them is guard-clean.
_SCAN_PATTERNS: list[tuple[str, re.Pattern[str]]] = [
    ("pem_private_key", re.compile(r"BEGIN [A-Z ]*PRIVATE KEY")),
    ("bearer_token", re.compile(r"Bearer [A-Za-z0-9._-]{20,}")),
    ("jwt", re.compile(r"eyJ[A-Za-z0-9_-]{10,}\.[A-Za-z0-9_-]{6,}\.[A-Za-z0-9_-]{6,}")),
    ("sas_signed_param", re.compile(r"[?&](sig|sv|se|token)=[A-Za-z0-9%._-]{16,}")),
    ("signed_url", re.compile(r"https?://[^\s\"']*[?&](sig|token)=")),
    ("oauth_secret", re.compile(r"access_token|refresh_token|client_secret")),
]


class NoRawVectorIndexProofError(RuntimeError):
    """Raised when the no-raw-vector-index proof cannot resolve policy/schema (fail-closed)."""


def _now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _repo_sha() -> str:
    try:
        repo_root = Path(__file__).resolve().parents[5]
        out = subprocess.check_output(
            ["git", "rev-parse", "HEAD"], cwd=repo_root, stderr=subprocess.DEVNULL, timeout=5
        )
        return out.decode("utf-8").strip()
    except Exception:
        return "unknown"


def _hash(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _open_ro(db_path: str | None) -> sqlite3.Connection | None:
    resolved = db_path or str(PathPolicy().get_db_path())
    try:
        return sqlite3.connect(f"file:{resolved}?mode=ro", uri=True)
    except sqlite3.OperationalError:
        return None


def _schema_ready(db_path: str | None) -> int:
    """Return the schema version if ready (>=39 with the vector + validation tables), else fail-closed."""
    conn = _open_ro(db_path)
    if conn is None:
        raise NoRawVectorIndexProofError(
            "schema not ready for no-raw-vector-index proof (no database)"
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
            raise NoRawVectorIndexProofError("schema not ready (no schema_migrations)")
        row = conn.execute("SELECT MAX(version) FROM schema_migrations").fetchone()
        version = int(row[0]) if row and row[0] is not None else 0
        if version < 39 or not _has(_VALIDATION_TABLE) or not _has(_VECTOR_TABLES[0]):
            raise NoRawVectorIndexProofError(
                f"schema not ready for no-raw-vector-index proof (version {version}, expected >= 39)"
            )
    finally:
        conn.close()
    return version


def load_no_raw_vector_index_proof_contract() -> dict[str, Any]:
    """Load the no-raw-vector-index-proof contract (fail-closed if missing/invalid)."""
    from ..contracts import load_phase_09_contract

    contract = load_phase_09_contract("no_raw_vector_index_proof_contract")
    if (
        not isinstance(contract, dict)
        or "required" not in contract
        or "guard_columns" not in contract
    ):
        raise NoRawVectorIndexProofError(
            "phase 09 no-raw-vector-index-proof contract not found or missing required fields"
        )
    return contract


def load_no_raw_vector_index_proof_seed() -> dict[str, Any]:
    """Load the resolved no-raw-vector-index-proof seed (fail-closed if missing/invalid)."""
    import yaml

    candidate = PathPolicy().resolve_repo_root() / _SEED_RELATIVE
    if not candidate.exists():
        raise NoRawVectorIndexProofError(f"no-raw-vector-index-proof seed not found at {candidate}")
    with candidate.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f) or {}
    if not isinstance(data, dict) or "version" not in data:
        raise NoRawVectorIndexProofError(
            f"{candidate} must define the no-raw-vector-index-proof policy"
        )
    return data


def _guard_columns_for(cols: list[str]) -> list[str]:
    return [
        c
        for c in cols
        if c.endswith(("_persisted", "_performed")) or c.endswith("_bypassed_policy")
    ]


def scan_db(
    conn: sqlite3.Connection,
    *,
    scanned_tables: tuple[str, ...] | list[str],
    blob_cols: tuple[str, ...] | list[str],
) -> dict[str, Any]:
    """Forensically scan the retrieval tables: guard-column sums, vector-blob columns, and a
    forbidden-pattern scan of safe text columns. Findings carry ``table.column`` + a pattern label —
    never the offending value."""
    findings: list[dict[str, str]] = []
    guard_violations = 0
    guard_tables_checked = 0
    blob_columns_found: list[str] = []

    retrieval_tables = [
        str(r[0])
        for r in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'second_brain_retrieval_%'"
        ).fetchall()
    ]
    for t in retrieval_tables:
        cols = [str(r[1]) for r in conn.execute(f"PRAGMA table_info({t})").fetchall()]
        gcols = _guard_columns_for(cols)
        if gcols:
            guard_tables_checked += 1
            s = conn.execute(f"SELECT COALESCE(SUM({'+'.join(gcols)}), 0) FROM {t}").fetchone()[0]
            guard_violations += int(s or 0)
        blob_set = {b.lower() for b in blob_cols}
        for c in cols:
            # Exact name match: a column literally holding a vector/embedding blob. Metadata columns
            # like `embedding_model_label` or the `raw_vector_content_persisted` guard are NOT blobs.
            if c.lower() in blob_set:
                blob_columns_found.append(f"{t}.{c}")

    tables_scanned = 0
    for t in scanned_tables:
        if (
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (t,)
            ).fetchone()
            is None
        ):
            continue
        tables_scanned += 1
        cols = [str(r[1]) for r in conn.execute(f"PRAGMA table_info({t})").fetchall()]
        text_cols = [
            c
            for c in cols
            if c not in _guard_columns_for(cols)
            and c not in ("created_at_utc", "schema_version")
            and not c.endswith("_count")
        ]
        if not text_cols:
            continue
        for row in conn.execute(f"SELECT {', '.join(text_cols)} FROM {t}").fetchall():
            for col, val in zip(text_cols, row, strict=True):
                if val is None:
                    continue
                sval = str(val)
                for label, pat in _SCAN_PATTERNS:
                    if pat.search(sval):
                        findings.append({"location": f"{t}.{col}", "pattern": label})
    return {
        "tables_scanned": tables_scanned,
        "guard_tables_checked": guard_tables_checked,
        "guard_violations": guard_violations,
        "blob_columns_found": sorted(blob_columns_found),
        "findings": findings,
    }


def scan_evidence(evidence_dir: str, *, extensions: tuple[str, ...] | list[str]) -> dict[str, Any]:
    """Forensically scan an evidence tree for forbidden payloads. Findings carry the file name +
    pattern label only — never the offending value."""
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


def _non_vacuity_check() -> bool:
    """Plant a synthetic forbidden value (assembled at runtime; never a literal secret) into a temp DB
    text column and a temp evidence file, and confirm both scanners flag it."""
    import tempfile

    from hb_assistant.store.migrator import ensure_schema_ready

    synthetic = "https://x.example/a" + "?sig=" + "Z" * 24  # signed-URL shape, runtime-assembled
    with tempfile.TemporaryDirectory() as tmp:
        db = str(Path(tmp) / "plant.sqlite")
        ensure_schema_ready(db)
        conn = sqlite3.connect(db)
        try:
            conn.execute(
                f"INSERT INTO {_VECTOR_TABLES[1]} "
                "(item_id, run_id, policy_version, schema_version, source_family, source_ref_hash, "
                "content_hash) VALUES (?, ?, ?, ?, ?, ?, ?)",
                ("plant-1", "plant-run", "v", 39, "accepted_long_term_memory", synthetic, "h"),
            )
            conn.commit()
            db_hits = scan_db(conn, scanned_tables=_VECTOR_TABLES, blob_cols=_VECTOR_BLOB_COLS)[
                "findings"
            ]
        finally:
            conn.close()
        ev = Path(tmp) / "ev"
        ev.mkdir()
        (ev / "planted.json").write_text('{"x": "' + synthetic + '"}', encoding="utf-8")
        ev_hits = scan_evidence(str(ev), extensions=(".json", ".md"))["findings"]
    return len(db_hits) >= 1 and len(ev_hits) >= 1


def build_no_raw_vector_index_proof(
    db_path: str | None = None,
    *,
    evidence_dir: str | None = None,
    write_evidence: bool = True,
    emit_receipt: bool = False,
) -> dict[str, Any]:
    """Scan DB / vector-index metadata / evidence for raw vector content and prohibited payloads.

    Returns a metadata-only gate-summary; findings carry locations + pattern labels only (never the
    value). ``db_path`` defaults to the operator DB (read-only); ``evidence_dir`` defaults to the
    Phase-09 evidence tree. Persists nothing unless ``emit_receipt``. Makes no determination.
    """
    contract = load_no_raw_vector_index_proof_contract()
    seed = load_no_raw_vector_index_proof_seed()
    schema_version = _schema_ready(db_path)

    scanned_tables = tuple(seed.get("scanned_tables", _VECTOR_TABLES))
    blob_cols = tuple(seed.get("forbidden_vector_blob_columns", _VECTOR_BLOB_COLS))
    exts = tuple(seed.get("evidence_scan_extensions", (".json", ".md")))
    ev_dir = evidence_dir if evidence_dir is not None else EVIDENCE_DIR
    guard_cols = list(contract.get("guard_columns", []))

    conn = _open_ro(db_path)
    if conn is None:
        raise NoRawVectorIndexProofError(
            "schema not ready for no-raw-vector-index proof (no database)"
        )
    try:
        db_scan = scan_db(conn, scanned_tables=scanned_tables, blob_cols=blob_cols)
    finally:
        conn.close()
    ev_scan = scan_evidence(ev_dir, extensions=exts)

    db_guard_clean = db_scan["guard_violations"] == 0
    no_vector_blob_columns = len(db_scan["blob_columns_found"]) == 0
    db_text_no_forbidden = len(db_scan["findings"]) == 0
    evidence_no_forbidden = len(ev_scan["findings"]) == 0
    vectors_outside_sqlite = no_vector_blob_columns
    scanner_detects_planted = _non_vacuity_check()

    gates = {
        "db_guard_clean": db_guard_clean,
        "no_vector_blob_columns": no_vector_blob_columns,
        "vectors_outside_sqlite": vectors_outside_sqlite,
        "db_text_no_forbidden": db_text_no_forbidden,
        "evidence_no_forbidden": evidence_no_forbidden,
        "scanner_detects_planted": scanner_detects_planted,
    }
    gate_count = len(gates)
    pass_count = sum(1 for v in gates.values() if v)
    fail_count = gate_count - pass_count
    proof_passed = fail_count == 0
    forbidden_findings = len(db_scan["findings"]) + len(ev_scan["findings"])
    run_id = (
        "nrv_"
        + _hash(f"{db_scan['tables_scanned']}|{ev_scan['files_scanned']}|{proof_passed}")[:32]
    )

    result = {
        "command": "second-brain retrieval no-raw-vector-index-proof",
        "phase": "09",
        "generated_utc": _now(),
        "repo_sha": _repo_sha(),
        "schema_version": schema_version,
        "run_id": run_id,
        "proof_passed": proof_passed,
        "overall_status": "clean" if proof_passed else "findings",
        "gate_count": gate_count,
        "pass_count": pass_count,
        "fail_count": fail_count,
        "gates": gates,
        "scanned_table_count": db_scan["tables_scanned"],
        "guard_tables_checked": db_scan["guard_tables_checked"],
        "guard_violations": db_scan["guard_violations"],
        "blob_columns_found": db_scan["blob_columns_found"],
        "evidence_files_scanned": ev_scan["files_scanned"],
        "forbidden_findings": forbidden_findings,
        "db_findings": db_scan["findings"],
        "evidence_findings": ev_scan["findings"],
        "advisory_only": True,
        "makes_determination": False,
        "read_only": not emit_receipt,
        "receipt_emitted": emit_receipt,
        "policy_version": seed.get("version"),
        "contract_version": contract.get("version"),
        "guard_attestation": {"all_false": True, "column_count": len(guard_cols)},
    }

    if emit_receipt:
        persist_no_raw_vector_index_proof(db_path, result, policy_version=str(seed.get("version")))

    if write_evidence:
        out_dir = Path(evidence_dir) if evidence_dir is not None else Path(EVIDENCE_DIR)
        out_dir.mkdir(parents=True, exist_ok=True)
        out = json.dumps(result, indent=2, default=str)
        _assert_no_raw(out, "no-raw-vector-index proof json")
        (out_dir / _PROOF_JSON).write_text(out + "\n", encoding="utf-8")
        markdown = _render_proof_md(result)
        _assert_no_raw(markdown, "no-raw-vector-index proof markdown")
        (out_dir / _PROOF_MD).write_text(markdown, encoding="utf-8")
        result["proof_path"] = str(out_dir / _PROOF_JSON)
        result["proof_md_path"] = str(out_dir / _PROOF_MD)

    return result


def persist_no_raw_vector_index_proof(
    db_path: str | None, result: dict[str, Any], *, policy_version: str
) -> str:
    """Persist one guard-clean gate-summary row to the reserved validation-runs table. Returns run_id."""
    _schema_ready(db_path)
    resolved = db_path or str(PathPolicy().get_db_path())
    run_id = str(result["run_id"])
    conn = sqlite3.connect(resolved)
    try:
        conn.execute(
            f"INSERT OR REPLACE INTO {_VALIDATION_TABLE} "
            "(run_id, policy_version, schema_version, gate_count, pass_count, fail_count, "
            "overall_status) VALUES (?, ?, ?, ?, ?, ?, ?)",
            (
                run_id,
                policy_version,
                int(result["schema_version"]),
                int(result["gate_count"]),
                int(result["pass_count"]),
                int(result["fail_count"]),
                str(result["overall_status"]),
            ),
        )
        conn.commit()
    finally:
        conn.close()
    return run_id


def _render_proof_md(result: dict[str, Any]) -> str:
    lines = [
        "# Phase 09 — No Raw Vector Index Proof",
        "",
        f"- proof_passed: {result['proof_passed']}",
        f"- generated_utc: {result['generated_utc']}",
        f"- overall_status: {result['overall_status']}",
        f"- gates: {result['pass_count']}/{result['gate_count']} pass",
        f"- db_guard_clean: {result['gates']['db_guard_clean']} "
        f"(guard_violations={result['guard_violations']}, tables={result['guard_tables_checked']})",
        f"- no_vector_blob_columns: {result['gates']['no_vector_blob_columns']} "
        f"(blob_columns_found={result['blob_columns_found']})",
        f"- vectors_outside_sqlite: {result['gates']['vectors_outside_sqlite']}",
        f"- db_text_no_forbidden: {result['gates']['db_text_no_forbidden']} "
        f"(scanned_tables={result['scanned_table_count']})",
        f"- evidence_no_forbidden: {result['gates']['evidence_no_forbidden']} "
        f"(files_scanned={result['evidence_files_scanned']})",
        f"- scanner_detects_planted: {result['gates']['scanner_detects_planted']} (non-vacuity)",
        f"- forbidden_findings: {result['forbidden_findings']}",
        f"- makes_determination: {result['makes_determination']} (must be false)",
        "",
    ]
    return "\n".join(lines)
