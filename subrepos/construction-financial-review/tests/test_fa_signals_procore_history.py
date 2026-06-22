"""load_procore_history: group mapped procore pay-app lines by budget key, sorted by period_end."""

from __future__ import annotations

import json

from construction_financial_review.forecast_accuracy import signals


def _write(pkg, rows):
    canon = pkg / "canonical"
    canon.mkdir(parents=True)
    (canon / "procore_subcontractor_payment_app_line_items_mapped.jsonl").write_text(
        "\n".join(json.dumps(r) for r in rows) + "\n", encoding="utf-8"
    )


def test_load_procore_history_groups_and_sorts(tmp_path):
    _write(
        tmp_path,
        [
            {
                "mapped_budget_code_key": "A.SUB",
                "mapping_status": "mapped",
                "period_end": "2025-03-25",
                "commitment_id": 1,
                "total_completed_and_stored_to_date": "70000",
                "scheduled_value": "100000",
            },
            {
                "mapped_budget_code_key": "A.SUB",
                "mapping_status": "mapped",
                "period_end": "2025-01-25",
                "commitment_id": 1,
                "total_completed_and_stored_to_date": "40000",
                "scheduled_value": "100000",
            },
            # unmapped + keyless rows are dropped
            {
                "mapped_budget_code_key": "B.SUB",
                "mapping_status": "unmapped",
                "period_end": "2025-02-25",
            },
            {"mapping_status": "mapped", "period_end": "2025-02-25"},
        ],
    )
    hist = signals.load_procore_history(tmp_path)
    assert set(hist) == {"A.SUB"}
    rows = hist["A.SUB"]
    assert [r["period_end"] for r in rows] == ["2025-01-25", "2025-03-25"]  # sorted
    assert rows[0]["scheduled_value"] == "100000"


def test_load_procore_history_missing_file_is_empty(tmp_path):
    assert signals.load_procore_history(tmp_path) == {}
