"""Phase 10 Prompt 06 — Action candidate fixture suite runner (advisory, dry-run, regression).

A batch validation/regression harness over a directory of declarative scenario fixtures. It does
**not** re-implement the action-candidate model, schema, single-fixture runner, or validation
behaviour — those land in Prompts 01/04. The runner orchestrates the existing
:class:`StructuredOutputClient` over :class:`ActionCandidate` for every fixture in a suite, classifies
each run's outcome, and compares it against the fixture's declared ``expected_outcome``. The result is
a deterministic pass/fail matrix used by tests and the Prompt 06 evidence proof.

Each fixture is a JSON object carrying a ``scenario`` label, an ``expected_outcome`` category, and one
of the following backend descriptors (checked in order):

- ``malformed_payload`` (str): returned verbatim by the backend — exercises invalid-JSON handling.
- ``raw_candidate`` (object): serialized and fed directly to the validator — exercises missing-field,
  empty-source-refs, stale/forbidden-field, and high-stakes-pre-accepted rejection.
- ``unavailable`` (true): simulates an unreachable backend.
- otherwise: a positive fixture; the candidate is built with the shared
  :func:`action_candidate_dict_from_fixture` helper (low-confidence and high-risk-review variants).

``expected_outcome`` is one of ``valid`` | ``schema_invalid`` | ``unavailable`` | ``blocked``. The
runner maps the closed run ``status`` to that category and reports ``matched``.

The harness is always dry-run and never persists raw content — only SHA-256[:12] hashes flow into the
per-fixture rows. An optional ``store`` is accepted solely so the evidence proof can assert that a
dry-run pass writes zero receipt rows.

Public entry point:
    run_fixture_suite(*, fixtures_dir=..., profile_id="default_extract", store=None,
                      dry_run=True, low_confidence_threshold=0.4) -> dict
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any, Optional

from .contracts import load_local_model_profiles
from .models import HIGH_STAKES_CATEGORIES, ActionCandidate
from .structured_output import (
    StaticOutputClient,
    StructuredOutputClient,
    action_candidate_dict_from_fixture,
)

#: Default suite directory (relative to the repo root). Deliberately a *subdirectory* of
#: ``tests/fixtures/local_ai`` so the non-recursive ``ai_jobs`` glob over the parent never sees these
#: intentionally-invalid fixtures.
DEFAULT_SUITE_DIR = "tests/fixtures/local_ai/fixture_suite"

#: Maps a closed run ``status`` to the ``expected_outcome`` category fixtures declare.
_STATUS_TO_OUTCOME: dict[str, str] = {
    "ok": "valid",
    "schema_invalid": "schema_invalid",
    "unavailable": "unavailable",
    "timeout": "unavailable",
    "blocked": "blocked",
}


def _backend_for(fixture: dict[str, Any]) -> StaticOutputClient:
    """Build the deterministic offline backend a fixture's scenario calls for."""
    if "malformed_payload" in fixture:
        return StaticOutputClient(str(fixture["malformed_payload"]))
    if "raw_candidate" in fixture:
        return StaticOutputClient(json.dumps(fixture["raw_candidate"]))
    if fixture.get("unavailable"):
        return StaticOutputClient(raise_unavailable=True)
    return StaticOutputClient(json.dumps(action_candidate_dict_from_fixture(fixture)))


def _run_one(
    *,
    fixture: dict[str, Any],
    rel: str,
    client: StructuredOutputClient,
    profile: Any,
    profiles: Any,
    store: Optional[Any],
    dry_run: bool,
    low_confidence_threshold: float,
) -> dict[str, Any]:
    input_context = json.dumps(
        fixture.get("input_redacted") or {"fixture_id": fixture.get("fixture_id")},
        sort_keys=True,
    )
    result = client.run(
        schema=ActionCandidate,
        profile=profile,
        profiles=profiles,
        system="fixture suite",
        prompt="extract action candidate",
        input_context=input_context,
        task_type="extract_email_tasks",
        backend=_backend_for(fixture),
        store=store,
        dry_run=dry_run,
    )
    expected = str(fixture.get("expected_outcome", "valid"))
    actual_outcome = _STATUS_TO_OUTCOME.get(result.status, result.status)

    validated = result.validated or {}
    confidence = validated.get("confidence")
    safety_category = validated.get("safety_category")
    next_action = validated.get("recommended_next_action")
    low_confidence = (
        result.schema_valid
        and isinstance(confidence, (int, float))
        and float(confidence) < low_confidence_threshold
    )
    high_risk_review = result.schema_valid and safety_category in HIGH_STAKES_CATEGORIES
    # A surfaced high-risk candidate must route to review (never auto-act).
    high_risk_routing_ok = (not high_risk_review) or next_action == "review"

    return {
        "fixture": rel,
        "fixture_id": fixture.get("fixture_id"),
        "scenario": fixture.get("scenario"),
        "expected_outcome": expected,
        "status": result.status,
        "actual_outcome": actual_outcome,
        "matched": actual_outcome == expected,
        "schema_valid": result.schema_valid,
        "fallback_used": result.fallback_used,
        "low_confidence": bool(low_confidence),
        "high_risk_review": bool(high_risk_review),
        "high_risk_routing_ok": bool(high_risk_routing_ok),
        "error_redacted": result.error_redacted,
        "input_context_hash": result.input_context_hash,
        "output_hash": result.output_hash,
        "receipt_id": result.receipt_id,
    }


def run_fixture_suite(
    *,
    fixtures_dir: str | Path = DEFAULT_SUITE_DIR,
    profile_id: str = "default_extract",
    store: Optional[Any] = None,
    dry_run: bool = True,
    low_confidence_threshold: float = 0.4,
) -> dict[str, Any]:
    """Run every fixture in ``fixtures_dir`` through the schema-enforced client and classify it.

    Returns a dict with per-fixture rows and summary counts. ``all_matched`` is True when every
    fixture's actual outcome matched its declared ``expected_outcome``. Advisory and dry-run by
    default; only SHA-256[:12] hashes are surfaced — no raw payloads.
    """
    profiles = load_local_model_profiles()
    profile = next((p for p in profiles.profiles if p.profile_id == profile_id), None)
    if profile is None:
        raise ValueError(f"unknown profile_id {profile_id!r}")

    base = Path(fixtures_dir)
    client = StructuredOutputClient()
    fixtures: list[dict[str, Any]] = []
    for path in sorted(base.glob("*.json")):
        rel = str(path)
        try:
            fixture = json.loads(path.read_text(encoding="utf-8"))
        except Exception as exc:  # pragma: no cover - suite-authoring robustness
            fixtures.append(
                {"fixture": rel, "scenario": "unreadable", "matched": False, "error": str(exc)[:120]}
            )
            continue
        fixtures.append(
            _run_one(
                fixture=fixture,
                rel=rel,
                client=client,
                profile=profile,
                profiles=profiles,
                store=store,
                dry_run=dry_run,
                low_confidence_threshold=low_confidence_threshold,
            )
        )

    by_outcome: dict[str, int] = {}
    for row in fixtures:
        by_outcome[row.get("actual_outcome", "unknown")] = (
            by_outcome.get(row.get("actual_outcome", "unknown"), 0) + 1
        )
    all_matched = bool(fixtures) and all(row.get("matched") for row in fixtures)
    routing_ok = all(row.get("high_risk_routing_ok", True) for row in fixtures)

    return {
        "fixtures_dir": str(base),
        "profile_id": profile_id,
        "dry_run": dry_run,
        "low_confidence_threshold": low_confidence_threshold,
        "count": len(fixtures),
        "matched_count": sum(1 for row in fixtures if row.get("matched")),
        "by_outcome": by_outcome,
        "all_matched": all_matched,
        "high_risk_routing_ok": routing_ok,
        "fixtures": fixtures,
    }
