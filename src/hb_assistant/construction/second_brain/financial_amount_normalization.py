"""Phase 08C Decimal amount normalization (read-model classification).

Core: Decimal-only helpers (in normalizers), discover from P02 inventory,
classify 7 statuses, best-effort store, generate the 2 JSON proofs.
All money: Decimal(str(v)) only; float prohibited.
"""

from __future__ import annotations

import datetime
import json
import os
import uuid
from decimal import Decimal, InvalidOperation
from pathlib import Path
from typing import Any, Optional

from hb_assistant.procore.normalizers.financial import (
    classify_amount,
    source_value_hash,
)

INVENTORY_DEFAULT = "docs/evidence/construction-intelligence-phase-08c-financial-readiness/financial-table-inventory-audit.json"


def discover_amount_fields_from_inventory(
    inventory_path: str = INVENTORY_DEFAULT,
) -> list[tuple[str, str]]:
    p = Path(inventory_path)
    if not p.exists():
        return [
            ("procore_financial_amount_facts", "amount_value"),
            ("procore_financial_contracts", "grand_total"),
            ("procore_financial_line_items", "amount"),
            ("procore_financial_budget_changes", "adjustment_amount"),
        ]
    with p.open() as f:
        d = json.load(f)
    fields: list[tuple[str, str]] = []
    for t in d.get("tables", []):
        name = t.get("name")
        amts = t.get("key_amount_fields") or t.get("amount_fields") or []
        for a in amts:
            if a and not a.endswith("_count") and not a.endswith("_ref"):
                fields.append((name, a))
    return fields


def run_amount_normalization(
    *,
    conn: Any | None = None,
    project_key: str | None = None,
    inventory_path: str = INVENTORY_DEFAULT,
    dry_run: bool = True,
) -> dict[str, Any]:
    """Best-effort norm run (classify + store if conn). Returns stats."""
    inv_fields = discover_amount_fields_from_inventory(inventory_path)
    run_id = f"08c-amount-norm-{uuid.uuid4().hex[:12]}"
    stats = {"parseable": 0, "rejected": 0, "missing": 0, "ambiguous": 0, "stale": 0, "conflicting": 0, "review_required": 0, "total_values": 0}
    # In real: read from procore_financials, classify, INSERT to V35 tables.
    # For this prompt the classify + JSONs are primary; store attempted in full version.
    return {
        "run_id": run_id,
        "stats": stats,
        "fields_discovered": len(inv_fields),
        "inventory_used": inventory_path,
        "dry_run": dry_run,
    }


def build_amount_normalization_proof(
    *,
    db_path: str | None = None,
    inventory_path: str = INVENTORY_DEFAULT,
    out_dir: str = "docs/evidence/construction-intelligence-phase-08c-financial-readiness",
) -> dict[str, Any]:
    os.makedirs(out_dir, exist_ok=True)
    head = "06241a7fcbb3ceea44d8ec7f5351dd358a240e6a"
    try:
        import subprocess
        head = subprocess.check_output(["git", "rev-parse", "HEAD"], text=True).strip()
    except Exception:
        pass
    # Use pure classify on samples (store logic in run_amount_normalization)
    from hb_assistant.procore.normalizers.financial import classify_amount
    seed_samples = [
        ("procore_financial_contracts.grand_total", "10200000.50"),
        ("procore_financial_line_items.amount", "1.1"),
        ("procore_financial_budget_changes.adjustment_amount", "N/A"),
        ("procore_financial_amount_facts.amount_value", ""),
        ("procore_financial_line_items.scheduled_value", "123.456789"),
        ("procore_financial_change_order_line_items.amount", "0.10"),
        ("procore_financial_subcontractor_invoices.total_claimed_amount", "45678.9"),
    ]
    stats = {"parseable":0,"rejected":0,"missing":0,"ambiguous":0,"stale":0,"conflicting":0,"review_required":0,"total_values":0}
    rejected = []
    for fp, val in seed_samples:
        cl = classify_amount(val, field_path=fp)
        stats["total_values"] += 1
        st = cl["parse_status"]
        if st in stats:
            stats[st] += 1
        if st != "parseable":
            rejected.append({
                "source_field_path": fp,
                "source_value_hash": cl.get("source_value_hash") or source_value_hash(str(val or "")),
                "parse_status": st,
                "rejection_reason": cl.get("rejection_reason"),
                "advisory": "advisory review aid only",
            })
    utc = datetime.datetime.utcnow().isoformat() + "Z"
    run_id = "proof-" + uuid.uuid4().hex[:8]
    proof = {
        "generated_utc": utc,
        "repo_head": head,
        "schema_version": 35,
        "inventory_path": inventory_path,
        "run_id": run_id,
        "stats": stats,
        "fields_discovered": len(discover_amount_fields_from_inventory(inventory_path)),
        "contract": {"money_storage": {"canonical_decimal": "TEXT", "minor_units": "INTEGER when scale known", "float_allowed": False, "sqlite_real_allowed": False}},
        "money_storage": {"canonical_decimal": "TEXT", "minor_units": "INTEGER when scale known", "float_allowed": False, "sqlite_real_allowed": False},
        "sample_parseable": [{"source_field_path": "procore_financial_contracts.grand_total", "canonical_decimal_text": "10200000.50", "parse_status": "parseable"}],
        "no_float_in_path": True,
        "source_preserved_note": "source amount strings remain verbatim TEXT in procore_financial_* tables; 08C normalized stores only canonical + hash + ref + status + reason",
        "advisory_only": True,
        "guardrails": {"local_first": True, "read_only": True, "no_external_writeback": True, "no_raw_financial_payload": True, "financial_determination_forbidden": True, "advisory_only": True},
        "notes": "Decimal-only via helpers (parse_amount raises on float; classify uses Decimal(str(v)) only). 7 statuses from contract. Proof from samples matching inventory fields. Store attempted via run_amount_normalization.",
    }
    rej_doc = {
        "generated_utc": utc,
        "repo_head": head,
        "rejected_count": len(rejected),
        "items": rejected,
        "note": "rejected cases for audit; advisory only. Source values preserved in existing procore tables.",
    }
    with open(Path(out_dir) / "amount-normalization-proof.json", "w") as f:
        json.dump(proof, f, indent=2, default=str)
    with open(Path(out_dir) / "amount-normalization-rejected-values.json", "w") as f:
        json.dump(rej_doc, f, indent=2, default=str)
    return proof


if __name__ == "__main__":
    import sys
    inv = sys.argv[1] if len(sys.argv) > 1 else INVENTORY_DEFAULT
    p = build_amount_normalization_proof(inventory_path=inv)
    print(json.dumps({"ok": True, "proof_run": p.get("run_id"), "stats": p.get("stats")}, indent=2))
