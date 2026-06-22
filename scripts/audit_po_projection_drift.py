#!/usr/bin/env python3
"""Safe PO projection drift audit (read-only SQLite). No raw payloads exported."""

from __future__ import annotations

import argparse
import hashlib
import json
import sqlite3
import sys
from collections import Counter
from pathlib import Path

_REPO_ROOT = Path(__file__).resolve().parents[1]
if str(_REPO_ROOT / "src") not in sys.path:
    sys.path.insert(0, str(_REPO_ROOT / "src"))


def _hash_key(project_key: str, contract_id: str) -> str:
    return hashlib.sha256(f"{project_key}:{contract_id}".encode()).hexdigest()[:16]


def _connect_ro(db_path: Path) -> sqlite3.Connection:
    conn = sqlite3.connect(f"file:{db_path.resolve()}?mode=ro", uri=True)
    conn.row_factory = sqlite3.Row
    return conn


def audit_po_projection_drift(db_path: Path) -> dict:
    with _connect_ro(db_path) as conn:
        ep_rows = conn.execute(
            "SELECT project_key, CAST(record_id AS TEXT) AS contract_id, status "
            "FROM procore_ep_purchase_order_contracts"
        ).fetchall()
        fin_rows = conn.execute(
            "SELECT project_key, CAST(contract_id AS TEXT) AS contract_id, status, "
            "grand_total, updated_at_utc "
            "FROM procore_financial_contracts WHERE contract_family = 'purchase_order'"
        ).fetchall()

        ep_set = {(r["project_key"], r["contract_id"]) for r in ep_rows}
        fin_set = {(r["project_key"], r["contract_id"]) for r in fin_rows}
        shared = sorted(ep_set & fin_set)
        ep_only = sorted(ep_set - fin_set)
        fin_only = sorted(fin_set - ep_set)

        classified: list[dict] = []
        for project_key, contract_id in fin_only:
            commit_fin = conn.execute(
                "SELECT 1 FROM procore_financial_contracts "
                "WHERE project_key = ? AND contract_id = ? AND contract_family = 'commitment' LIMIT 1",
                (project_key, contract_id),
            ).fetchone()
            commit_ep = conn.execute(
                "SELECT 1 FROM procore_ep_commitment_contracts "
                "WHERE project_key = ? AND CAST(record_id AS TEXT) = ? LIMIT 1",
                (project_key, contract_id),
            ).fetchone()
            fin = next(
                r for r in fin_rows if r["project_key"] == project_key and r["contract_id"] == contract_id
            )
            if commit_fin or commit_ep:
                classification = "commitment_backed_po"
                reason = (
                    "Financial PO row exists without EP PO endpoint row; same contract_id "
                    "is present as commitment (expected duplicate_of_commitment enrichment)."
                )
            else:
                classification = "unresolved"
                reason = "Financial-only PO key without matching commitment; needs manual review."
            classified.append(
                {
                    "project_key": project_key,
                    "contract_id_hash": _hash_key(project_key, contract_id),
                    "financial_status": fin["status"],
                    "grand_total_populated": bool(fin["grand_total"] and str(fin["grand_total"]).strip()),
                    "has_commitment_financial": bool(commit_fin),
                    "has_commitment_ep": bool(commit_ep),
                    "classification": classification,
                    "reason": reason,
                }
            )

        return {
            "db_path": str(db_path),
            "ep_row_count": len(ep_set),
            "financial_po_row_count": len(fin_set),
            "shared_key_count": len(shared),
            "ep_only_key_count": len(ep_only),
            "financial_only_key_count": len(fin_only),
            "financial_only_classifications": dict(Counter(c["classification"] for c in classified)),
            "financial_only_keys": classified,
            "projection_code_path": "src/hb_assistant/store/procore_commitment_projection.py::_project_purchase_order",
            "guardrails": {
                "read_only": True,
                "no_raw_payload_export": True,
                "no_live_db_mutation": True,
            },
        }


def main() -> int:
    parser = argparse.ArgumentParser(description="Audit PO EP vs financial projection drift.")
    parser.add_argument("--db-path", required=True, help="SQLite DB path (read-only).")
    parser.add_argument("--json-out", help="Optional output JSON path.")
    args = parser.parse_args()
    report = audit_po_projection_drift(Path(args.db_path))
    text = json.dumps(report, indent=2, default=str)
    if args.json_out:
        Path(args.json_out).write_text(text + "\n", encoding="utf-8")
    print(text)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())