"""Validation harness for the construction-agent fixture inventory.

Walks every fixture (or one kind), validates it against its target schema
or service, and returns a structured per-fixture pass/fail report. Pure
function — no I/O outside Pydantic validation + the deterministic
controller-policy evaluator.
"""

from __future__ import annotations

from typing import Any

from pydantic import BaseModel, Field, ValidationError

from hb_assistant.construction.classification.validator import (
    InvalidModelOutputError,
    parse_and_validate,
)
from hb_assistant.construction.config.models import SourceRegistry
from hb_assistant.construction.policy import (
    ReviewPolicyEvaluator,
    load_review_rules,
)
from hb_assistant.procore.models import (
    ProcoreEndpointContract,
    ProcoreProjectsRegistry,
)


class HarnessReport(BaseModel):
    total: int
    passed: int
    failed: int
    by_kind: dict[str, dict[str, int]] = Field(default_factory=dict)
    results: list[dict[str, Any]] = Field(default_factory=list)
    ok: bool

    model_config = {"extra": "forbid"}


# Fields that, if present anywhere in a graph-delta entry, would mean a
# document body has leaked into the fixture. The harness rejects any
# fixture carrying these.
_BODY_LEAK_FIELDS: tuple[str, ...] = ("content", "body", "text", "excerpt")


def _check_graph_delta(payload: dict[str, Any]) -> None:
    if "value" not in payload or not isinstance(payload["value"], list):
        raise ValueError("graph_delta payload must carry a 'value' list")
    has_next = "@odata.nextLink" in payload
    has_delta = "@odata.deltaLink" in payload
    if has_next == has_delta:
        raise ValueError(
            "graph_delta payload must carry exactly one of '@odata.nextLink' or '@odata.deltaLink'"
        )
    for entry in payload["value"]:
        if not isinstance(entry, dict):
            raise ValueError("graph_delta entries must be dicts")
        for leak in _BODY_LEAK_FIELDS:
            if leak in entry:
                raise ValueError(f"graph_delta entry illegally carries body field {leak!r}")


def _check_review_policy(payload: dict[str, Any], evaluator: ReviewPolicyEvaluator) -> None:
    inventory = payload["inventory"]
    expected: set[str] = set(payload.get("expected_rule_ids") or set())
    matches = evaluator.evaluate(
        source_key="fixture",
        project_key=None,
        item=inventory,
    )
    actual_ids = {m.rule_id for m in matches}
    if expected and not expected.issubset(actual_ids):
        missing = expected - actual_ids
        raise ValueError(
            f"review_policy fixture expected rules {sorted(expected)} but "
            f"evaluator produced {sorted(actual_ids)} (missing: {sorted(missing)})"
        )
    if not expected and actual_ids:
        raise ValueError(
            f"review_policy fixture expected NO rule matches but evaluator "
            f"produced {sorted(actual_ids)}"
        )


def _check_model_output_valid(payload: dict[str, Any]) -> None:
    classification = parse_and_validate(payload["raw"])
    if classification.proposed_label != payload["expected_label"]:
        raise ValueError(
            f"model_output_valid fixture expected label {payload['expected_label']!r} "
            f"but parsed {classification.proposed_label!r}"
        )


def _check_model_output_invalid(payload: dict[str, Any]) -> None:
    expected_code = payload["expected_code"]
    try:
        parse_and_validate(payload["raw"])
    except InvalidModelOutputError as e:
        if e.code != expected_code:
            raise ValueError(
                f"model_output_invalid fixture expected error code "
                f"{expected_code!r} but got {e.code!r}"
            ) from None
        return
    raise ValueError(
        f"model_output_invalid fixture expected to raise "
        f"InvalidModelOutputError with code {expected_code!r} but it did not raise"
    )


class FixtureHarness:
    def __init__(self) -> None:
        # Single evaluator instance reused across review_policy fixtures
        self._evaluator: ReviewPolicyEvaluator | None = None

    def _get_evaluator(self) -> ReviewPolicyEvaluator:
        if self._evaluator is None:
            self._evaluator = ReviewPolicyEvaluator(load_review_rules())
        return self._evaluator

    def validate_fixture(self, name: str, entry: dict[str, Any]) -> dict[str, Any]:
        """Validate one fixture; never raises (errors become a failed result)."""
        kind = entry["kind"]
        payload = entry["payload"]
        result: dict[str, Any] = {
            "name": name,
            "kind": kind,
            "passed": False,
            "error_code": None,
            "error_detail": None,
        }
        try:
            if kind == "graph_delta":
                _check_graph_delta(payload)
            elif kind == "source_registry":
                SourceRegistry.model_validate(payload)
            elif kind == "review_policy":
                _check_review_policy(payload, self._get_evaluator())
            elif kind == "model_output_valid":
                _check_model_output_valid(payload)
            elif kind == "model_output_invalid":
                _check_model_output_invalid(payload)
            elif kind == "procore_contract":
                ProcoreEndpointContract.model_validate(payload)
            elif kind == "procore_projects":
                ProcoreProjectsRegistry.model_validate(payload)
            else:
                raise ValueError(f"unknown fixture kind: {kind!r}")
        except ValidationError as e:
            result["error_code"] = "validation_error"
            result["error_detail"] = f"{len(e.errors())} validation error(s)"
            return result
        except (ValueError, InvalidModelOutputError) as e:
            result["error_code"] = type(e).__name__
            # Detail truncated to keep the report tidy.
            result["error_detail"] = str(e)[:200]
            return result
        result["passed"] = True
        return result

    def validate_all(self, kind: str | None = None) -> HarnessReport:
        # Local import to avoid circular reference; this module is imported
        # by fixtures/__init__.py.
        from hb_assistant.construction.fixtures import iter_fixtures

        results = [self.validate_fixture(name, entry) for name, entry in iter_fixtures(kind)]
        by_kind: dict[str, dict[str, int]] = {}
        for r in results:
            slot = by_kind.setdefault(r["kind"], {"passed": 0, "failed": 0})
            slot["passed" if r["passed"] else "failed"] += 1

        passed = sum(1 for r in results if r["passed"])
        failed = len(results) - passed
        return HarnessReport(
            total=len(results),
            passed=passed,
            failed=failed,
            by_kind=by_kind,
            results=results,
            ok=failed == 0,
        )
