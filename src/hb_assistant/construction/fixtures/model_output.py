"""Synthetic raw model-output fixtures for the Ollama classifier validator.

Two parallel inventories:

- ``VALID_FIXTURES`` — well-formed JSON that the validator accepts.
- ``INVALID_FIXTURES`` — payloads paired with the expected
  :class:`InvalidModelOutputError.code` they must raise.
"""

from __future__ import annotations

import json
from typing import Any


def _raw(item_id: str, label: str, confidence: float, rationale: str = "synthetic") -> str:
    return json.dumps({
        "item_id": item_id,
        "proposed_label": label,
        "confidence": confidence,
        "rationale": rationale,
        "risk_terms": [],
    })


VALID_FIXTURES: dict[str, dict[str, Any]] = {
    "accepted_operational": {
        "raw": _raw("fixture-mc-001", "operational", 0.9),
        "expected_label": "operational",
        "expected_status": "accepted",
    },
    "review_protected_contract": {
        "raw": _raw("fixture-mc-002", "contract", 0.95),
        "expected_label": "contract",
        "expected_status": "review",  # routed by protected_category
    },
    "review_low_confidence": {
        "raw": _raw("fixture-mc-003", "other", 0.2),
        "expected_label": "other",
        "expected_status": "review",  # routed by low_confidence
    },
    "review_item_id_mismatch": {
        "raw": _raw("WRONG-ID", "operational", 0.95),
        "expected_label": "operational",
        "expected_status": "review",  # service forces review on item_id mismatch
        "expected_item_id_in_payload": "WRONG-ID",
    },
}


# Each entry carries the expected code raised by parse_and_validate.
INVALID_FIXTURES: dict[str, dict[str, Any]] = {
    "empty": {
        "raw": "",
        "expected_code": "empty_output",
    },
    "whitespace_only": {
        "raw": "   \n\t  ",
        "expected_code": "empty_output",
    },
    "not_json": {
        "raw": "not-json",
        "expected_code": "json_parse_failed",
    },
    "array_not_object": {
        "raw": "[1, 2, 3]",
        "expected_code": "not_a_json_object",
    },
    "missing_required_field": {
        "raw": json.dumps({"item_id": "x", "confidence": 0.9}),
        "expected_code": "schema_validation_failed",
    },
    "extra_field": {
        "raw": json.dumps({
            "item_id": "x", "proposed_label": "operational", "confidence": 0.9,
            "rationale": "r", "risk_terms": [], "stowaway": "leak",
        }),
        "expected_code": "schema_validation_failed",
    },
    "unknown_label": {
        "raw": json.dumps({
            "item_id": "x", "proposed_label": "chaos", "confidence": 0.9,
            "rationale": "r", "risk_terms": [],
        }),
        "expected_code": "schema_validation_failed",
    },
    "out_of_range_confidence": {
        "raw": json.dumps({
            "item_id": "x", "proposed_label": "other", "confidence": 1.5,
            "rationale": "r", "risk_terms": [],
        }),
        "expected_code": "schema_validation_failed",
    },
    "empty_rationale": {
        "raw": json.dumps({
            "item_id": "x", "proposed_label": "other", "confidence": 0.5,
            "rationale": "   ", "risk_terms": [],
        }),
        "expected_code": "schema_validation_failed",
    },
}
