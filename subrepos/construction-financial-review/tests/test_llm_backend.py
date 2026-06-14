"""Advisory LLM layer: mock template, JSON validation, safety fail-closed, unavailable fallback."""
import json

from construction_financial_review.forecast_accuracy.llm import narrate
from construction_financial_review.forecast_accuracy.llm.backend import StaticBackend

FACTS = {
    "project_key": "tropical", "budget_code_key": "1000.15-02-010.SUB",
    "erp_projected_costs": "100000.00", "model_recommended_projected_cost": "130000.00",
    "model_reconciled_eac": "130000.00", "n_independent_models": 3, "reconciliation_basis": "a+b+c",
    "forecast_adequacy": "likely_low", "adequacy_severity": "high",
    "calibrated_confidence": "0.71", "confidence_band": "high",
    "schedule_remaining_work_status": "material_remaining_work",
}

VALID = json.dumps({
    "forecast_rationale": "ERP looks low vs the model.",
    "top_risks": ["Under-forecast risk."],
    "review_questions": ["Is the latest change order captured?"],
    "mapping_disambiguation_suggestion": None,
    "qualitative_confidence": "high",
})


def test_mock_mode_uses_deterministic_template():
    row, receipt = narrate.narrate_one(FACTS, None, "deterministic_template")
    assert row["source"] == "deterministic_template"
    assert receipt["status"] == "mock" and receipt["fallback_used"] is False
    assert "forecast_rationale" in row and isinstance(row["top_risks"], list)


def test_mock_is_deterministic():
    a, _ = narrate.narrate_one(FACTS, None, "deterministic_template")
    b, _ = narrate.narrate_one(FACTS, None, "deterministic_template")
    assert a == b


def test_live_valid_json_accepted():
    row, receipt = narrate.narrate_one(FACTS, StaticBackend(outputs=[VALID]), "qwen2.5:14b")
    assert receipt["status"] == "ok" and row["source"] == "ollama:qwen2.5:14b"
    assert row["qualitative_confidence"] == "high"


def test_invalid_json_falls_back_to_template():
    row, receipt = narrate.narrate_one(FACTS, StaticBackend(outputs=["not json"]), "qwen2.5:14b")
    assert row["source"] == "deterministic_template"
    assert receipt["fallback_used"] is True and receipt["status"] == "invalid_json"


def test_schema_violation_falls_back():
    bad = json.dumps({"forecast_rationale": "x"})  # missing required keys
    row, receipt = narrate.narrate_one(FACTS, StaticBackend(outputs=[bad]), "qwen2.5:14b")
    assert row["source"] == "deterministic_template"
    assert receipt["status"].startswith("schema")


def test_unsafe_output_blocked_fail_closed():
    unsafe = json.dumps({
        "forecast_rationale": "token sk-ABCDEF0123456789ABCDEF here",
        "top_risks": ["x"], "review_questions": ["y"],
        "mapping_disambiguation_suggestion": None, "qualitative_confidence": "low",
    })
    row, receipt = narrate.narrate_one(FACTS, StaticBackend(outputs=[unsafe]), "qwen2.5:14b")
    assert row["source"] == "deterministic_template"
    assert receipt["status"] == "unsafe_output_blocked"
    assert receipt["safety_passed"] is True            # the fallback template is safe


def test_unavailable_backend_falls_back():
    row, receipt = narrate.narrate_one(
        FACTS, StaticBackend(raise_unavailable=True, error_code="ollama_request_failed"), "qwen2.5:14b")
    assert row["source"] == "deterministic_template"
    assert receipt["status"] == "ollama_request_failed" and receipt["fallback_used"] is True


def test_receipts_are_hash_only():
    _, receipt = narrate.narrate_one(FACTS, StaticBackend(outputs=[VALID]), "qwen2.5:14b")
    # only hashes/flags, no raw prompt/response text
    assert set(receipt) >= {"input_facts_hash", "output_hash", "model", "status"}
    assert len(receipt["input_facts_hash"]) == 12 and len(receipt["output_hash"]) == 12
