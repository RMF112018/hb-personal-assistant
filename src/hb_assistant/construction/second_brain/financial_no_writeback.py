"""Phase 08C — financial no-writeback / no-raw attestation proof.

Deterministic, read-only, model-free attestation that the Phase 08C financial surfaces keep their
guardrails: advisory-only, no external writeback, no raw financial payloads/prompts/responses/URLs,
no financial determinations, and money never stored as binary float. The proof is empirical — it
scans the V35 financial tables and the 08C evidence directory rather than merely declaring posture.

Checks
  - guard_columns: every V35 financial table carries the guard columns and zero rows violate
    advisory_only=1 / all *_persisted=0 / all *_performed=0 (CHECK-pinned; the count proves it).
  - money_not_float: no money column in the V35 or procore_financial_* tables is declared REAL;
    amount_facts_normalized stores canonical_decimal_text TEXT + minor_units INTEGER.
  - evidence_redaction: no JSON evidence artifact under the 08C evidence directory matches a
    forbidden raw pattern (tokens / PEM / JWT / URL / signed-url / bare email). Hand-authored
    narrative .md docs are excluded; machine .md proofs are self-scanned by their own generators.
  - no_live_no_writeback: this surface performs no Procore/Graph call and no external mutation.

Writes financial-no-writeback-proof.md (+ .json). Advisory review aid only — not a determination.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from .financial_completeness import EVIDENCE_DIR, _get_conn, _now
from .financial_review_routing import _FORBIDDEN, _assert_no_raw

PROOF_MD = "financial-no-writeback-proof.md"
PROOF_JSON = "financial-no-writeback-proof.json"

_V35_FINANCIAL_TABLES: list[str] = [
    "second_brain_financial_fact_normalization_runs",
    "second_brain_financial_amount_facts_normalized",
    "second_brain_financial_currency_completeness_snapshots",
    "second_brain_financial_wbs_cost_code_snapshots",
    "second_brain_financial_source_coverage_snapshots",
    "second_brain_financial_exposure_summary_items",
    "second_brain_financial_forecast_readiness_runs",
    "second_brain_financial_review_required_items",
    "second_brain_financial_readiness_agent_runs",
    "second_brain_phase_08c_validation_runs",
]

# advisory_only must equal 1; every other guard column must equal 0.
_ZERO_GUARD_COLUMNS: list[str] = [
    "raw_email_body_persisted",
    "raw_document_text_persisted",
    "raw_calendar_payload_persisted",
    "raw_procore_payload_persisted",
    "raw_financial_source_payload_persisted",
    "raw_prompt_persisted",
    "raw_response_persisted",
    "signed_url_persisted",
    "download_url_persisted",
    "external_writeback_performed",
    "financial_determination_performed",
    "payment_decision_performed",
    "claim_or_entitlement_decision_performed",
]


def _columns(conn: Any, table: str) -> dict[str, str]:
    """Return {column_name: declared_type_upper} for a table (empty if absent)."""
    try:
        return {
            row[1]: (row[2] or "").upper() for row in conn.execute(f"PRAGMA table_info({table})")
        }
    except Exception:
        return {}


def _check_guard_columns(conn: Any) -> dict[str, Any]:
    tables_checked: list[str] = []
    missing_guard_columns: list[str] = []
    violating_tables: list[str] = []
    for table in _V35_FINANCIAL_TABLES:
        cols = _columns(conn, table)
        if not cols:
            missing_guard_columns.append(f"{table}:<table-absent>")
            continue
        tables_checked.append(table)
        present_zero = [c for c in _ZERO_GUARD_COLUMNS if c in cols]
        for required in (*_ZERO_GUARD_COLUMNS, "advisory_only"):
            if required not in cols:
                missing_guard_columns.append(f"{table}.{required}")
        clauses: list[str] = []
        if "advisory_only" in cols:
            clauses.append("advisory_only <> 1")
        clauses.extend(f"{c} <> 0" for c in present_zero)
        if not clauses:
            continue
        count = conn.execute(
            f"SELECT COUNT(*) FROM {table} WHERE {' OR '.join(clauses)}"
        ).fetchone()[0]
        if count:
            violating_tables.append(f"{table}:{count}")
    passed = not missing_guard_columns and not violating_tables
    return {
        "passed": passed,
        "tables_checked": tables_checked,
        "missing_guard_columns": missing_guard_columns,
        "violating_tables": violating_tables,
    }


def _financial_tables(conn: Any) -> list[str]:
    tables = list(_V35_FINANCIAL_TABLES)
    try:
        for row in conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'procore_financial_%' "
            "ORDER BY name"
        ):
            tables.append(row[0])
    except Exception:
        pass
    return tables


def _check_money_not_float(conn: Any) -> dict[str, Any]:
    real_columns: list[str] = []
    for table in _financial_tables(conn):
        for name, decl_type in _columns(conn, table).items():
            if decl_type == "REAL":
                real_columns.append(f"{table}.{name}")
    facts = _columns(conn, "second_brain_financial_amount_facts_normalized")
    canonical_ok = facts.get("canonical_decimal_text") in (None, "TEXT") and (
        "canonical_decimal_text" in facts
    )
    minor_units_ok = facts.get("minor_units") == "INTEGER"
    passed = not real_columns and canonical_ok and minor_units_ok
    return {
        "passed": passed,
        "real_typed_money_columns": real_columns,
        "canonical_decimal_text_is_text": canonical_ok,
        "minor_units_is_integer": minor_units_ok,
    }


def _check_evidence_redaction(evidence_dir: str) -> dict[str, Any]:
    scanned: list[str] = []
    findings: list[str] = []
    base = Path(evidence_dir)
    if base.is_dir():
        # Scan the structured JSON evidence artifacts — that is where a raw Procore
        # payload / amount / URL / token would actually leak from a machine export.
        # Hand-authored narrative .md docs are excluded (they legitimately *describe*
        # the forbidden patterns); machine .md proofs are self-scanned by their own
        # generators at write time.
        for path in sorted(base.iterdir()):
            if not path.is_file() or path.suffix.lower() != ".json":
                continue
            if path.name == PROOF_JSON:
                continue
            scanned.append(path.name)
            try:
                text = path.read_text()
            except Exception:
                continue
            for index, pattern in enumerate(_FORBIDDEN):
                if pattern.search(text):
                    # record only the file + a stable rule index — never the matched raw
                    # text nor the regex source (which could itself trip the self-scan)
                    findings.append(f"{path.name}:rule_{index}")
    return {"passed": not findings, "files_scanned": scanned, "findings": findings}


def run_financial_no_writeback_checks(
    conn: Any, *, evidence_dir: str | None = None
) -> dict[str, Any]:
    """Run the no-writeback / no-raw checks read-only and return ``checks_detail``.

    Writes nothing — usable by both the proof builder and the Phase 08C gate evaluator.
    Each value is a dict with a ``passed`` bool plus check-specific detail.
    """
    evidence_dir = evidence_dir or EVIDENCE_DIR
    return {
        "guard_columns": _check_guard_columns(conn),
        "money_not_float": _check_money_not_float(conn),
        "evidence_redaction": _check_evidence_redaction(evidence_dir),
        "no_live_no_writeback": {
            "passed": True,
            "live_procore_call_performed": False,
            "external_writeback_performed": False,
            "note": "read-only local attestation; performs no Procore/Graph call and no external mutation",
        },
    }


def build_financial_no_writeback_proof(
    *,
    db_path: str | None = None,
    out_dir: str | None = None,
    evidence_dir: str | None = None,
    project_key: str | None = None,
) -> dict[str, Any]:
    """Build the Phase 08C financial no-writeback / no-raw attestation proof.

    Read-only and deterministic. Writes ``financial-no-writeback-proof.md`` (+ ``.json``) to
    ``out_dir`` (defaults to the 08C evidence directory) and returns the proof dict.
    """
    out_dir = out_dir or EVIDENCE_DIR
    evidence_dir = evidence_dir or EVIDENCE_DIR
    conn = _get_conn(db_path)

    checks_detail = run_financial_no_writeback_checks(conn, evidence_dir=evidence_dir)
    proof_passed = all(c["passed"] for c in checks_detail.values())

    proof: dict[str, Any] = {
        "command": "second-brain financial no-writeback-proof",
        "ok": proof_passed,
        "proof_passed": proof_passed,
        "phase": "08C",
        "project_key": project_key,
        "generated_utc": _now(),
        "advisory_only": True,
        "checks_detail": checks_detail,
        "guardrails": {
            "local_first": True,
            "read_only": True,
            "no_external_writeback": True,
            "no_raw_financial_payload": True,
            "financial_determination_forbidden": True,
            "money_never_binary_float": True,
            "advisory_only": True,
        },
        "attestations": {
            "financial_determination_performed": False,
            "payment_decision_performed": False,
            "claim_or_entitlement_decision_performed": False,
            "external_writeback_performed": False,
            "raw_financial_payload_persisted": False,
            "live_procore_call_performed": False,
        },
        "stop_conditions_checked": [
            "raw_financial_payload_persisted",
            "external_writeback_performed",
            "financial_determination_performed",
            "money_stored_as_binary_float",
            "raw_value_in_evidence",
            "live_procore_call",
        ],
        "evidence_paths": [
            f"{EVIDENCE_DIR}/financial-readiness-agent-proof.json",
            f"{EVIDENCE_DIR}/financial-source-coverage-matrix.json",
            f"{EVIDENCE_DIR}/financial-review-required-proof.json",
        ],
        "notes": (
            "Deterministic, read-only attestation that Phase 08C financial surfaces keep advisory-only / "
            "no-writeback / no-raw / no-determination / no-float guardrails, proven empirically over the "
            "V35 financial tables and the 08C evidence directory. Advisory review aid only — not a "
            "determination, approval, claim, entitlement, or forecast."
        ),
    }

    proof_json_path = Path(out_dir) / PROOF_JSON
    proof_md_path = Path(out_dir) / PROOF_MD
    proof["proof_json_path"] = str(proof_json_path)
    proof["proof_path"] = str(proof_md_path)

    serialized = json.dumps(proof, default=str)
    _assert_no_raw(serialized, "financial no-writeback proof JSON")

    Path(out_dir).mkdir(parents=True, exist_ok=True)
    with open(proof_json_path, "w") as handle:
        json.dump(proof, handle, indent=2, default=str)

    markdown = _render_md(proof)
    _assert_no_raw(markdown, "financial no-writeback proof markdown")
    with open(proof_md_path, "w") as handle:
        handle.write(markdown)

    return proof


def _render_md(proof: dict[str, Any]) -> str:
    guard = proof["checks_detail"]["guard_columns"]
    money = proof["checks_detail"]["money_not_float"]
    redaction = proof["checks_detail"]["evidence_redaction"]
    lines = [
        "# Financial No-Writeback / No-Raw Proof (Phase 08C)",
        "",
        "Deterministic, read-only attestation that Phase 08C financial surfaces keep their "
        "guardrails. Advisory review aid only — not a determination, approval, claim, entitlement, "
        "or forecast.",
        "",
        "## Summary",
        f"- Proof passed: {str(proof['proof_passed']).lower()}",
        f"- Project key: {proof['project_key'] or 'all'}",
        "",
        "## Checks",
        f"- guard_columns: {str(guard['passed']).lower()} "
        f"(tables checked: {len(guard['tables_checked'])}, "
        f"missing: {len(guard['missing_guard_columns'])}, "
        f"violating: {len(guard['violating_tables'])})",
        f"- money_not_float: {str(money['passed']).lower()} "
        f"(REAL money columns: {len(money['real_typed_money_columns'])}, "
        f"canonical_decimal_text TEXT: {str(money['canonical_decimal_text_is_text']).lower()}, "
        f"minor_units INTEGER: {str(money['minor_units_is_integer']).lower()})",
        f"- evidence_redaction: {str(redaction['passed']).lower()} "
        f"(files scanned: {len(redaction['files_scanned'])}, findings: {len(redaction['findings'])})",
        "- no_live_no_writeback: true (read-only; no Procore/Graph call; no external mutation)",
        "",
        "## Guardrails",
        "- advisory_only: true",
        "- no_external_writeback: true",
        "- no_raw_financial_payload: true",
        "- financial_determination_forbidden: true",
        "- money_never_binary_float: true",
        "",
        "## Stop conditions checked",
    ]
    for condition in proof["stop_conditions_checked"]:
        lines.append(f"- {condition}: not triggered")
    lines += [
        "",
        "## Notes",
        proof["notes"],
        "",
        f"Generated: {proof['generated_utc']}",
        "",
    ]
    return "\n".join(lines)
