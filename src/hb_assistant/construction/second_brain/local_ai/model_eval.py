"""Local model evaluation harness (local-only, metrics-only, no raw egress).

Compares installed local models/profiles on the repo's actual structured-output tasks and produces
an **operationally decisive** result: per task family it names the recommended profile, the blocked
/ unsafe families, the fallback route, reason codes, and a ``use_next_run`` map an operator can act
on. It never persists or returns a raw prompt or raw model response — redaction and JSON checks run
on the raw output *in memory* (via a capturing backend) and only booleans, category codes, hashes,
and aggregate metrics survive.

Two modes:

* **synthetic** (default, offline): each fixture's canned ``synthetic_output`` is replayed through
  :class:`StaticOutputClient`. Deterministic, no daemon, safe for CI — exercises the full
  generate→validate→metrics path and the decisive summary.
* **live**: a real :class:`OllamaChatClient` is resolved per profile and run against the fixture's
  redacted context. Used only for explicit live workflow proof; falls closed (status ``unavailable``)
  when the daemon is unreachable.

Each profile is measured **independently with its own model** (cross-model fallback is disabled
during measurement so the comparison is clean); the fallback *route* is reported separately from the
seed's ``fallbacks`` map.
"""

from __future__ import annotations

import json
import time
from typing import Any, Literal, Optional

from pydantic import BaseModel, Field

from .contracts import Phase10ContractError, load_local_model_profiles
from .daily_brief_synthesis_schema import DailyBriefSynthesis
from .model_eval_fixtures import (
    ModelEvalFixture,
    synthetic_fixtures_for,
)
from .model_eval_metrics import (
    aggregate_mean,
    aggregate_rate,
    compute_usefulness,
    scan_text_for_forbidden,
)
from .models import ActionCandidate, LocalModelProfile, LocalModelProfiles
from .provider import resolve_local_model_client
from .structured_output import GenerationBackend, StaticOutputClient, StructuredOutputClient

EvalMode = Literal["synthetic", "live"]

#: Minimum schema-valid rate for a profile to be considered usable for a task family.
_MIN_SCHEMA_VALID_RATE = 0.5

#: Named suites -> task families.
_SUITES: dict[str, list[str]] = {
    "daily-brief": [
        "daily_brief_synthesis_quality",
        "short_operator_catchup",
        "calendar_prep_summary",
        "procore_digest_summary",
        "email_action_extraction_json",
    ],
    "synthesis": ["daily_brief_synthesis_quality", "short_operator_catchup"],
    "extraction": ["email_action_extraction_json"],
}


# --- compact eval schemas for families without a dedicated production model -------------------
class _CalendarPrepItemEval(BaseModel):
    local_time: str = ""
    title: str
    project: str = ""
    why_it_matters: str = ""
    prep: str = ""
    source_id: str = ""
    model_config = {"extra": "ignore"}


class CalendarPrepSummaryEval(BaseModel):
    """Compact eval schema for the calendar-prep task family."""

    meetings: list[_CalendarPrepItemEval] = Field(default_factory=list)
    model_config = {"extra": "ignore"}


class _ProcoreSignalEval(BaseModel):
    project: str = ""
    title: str
    risk: str = ""
    recommended_next_action: str = ""
    source_id: str = ""
    model_config = {"extra": "ignore"}


class ProcoreDigestSummaryEval(BaseModel):
    """Compact eval schema for the Procore-digest task family."""

    signals: list[_ProcoreSignalEval] = Field(default_factory=list)
    model_config = {"extra": "ignore"}


#: task family -> schema enforced for that family.
TASK_FAMILY_SCHEMAS: dict[str, type[BaseModel]] = {
    "email_action_extraction_json": ActionCandidate,
    "daily_brief_synthesis_quality": DailyBriefSynthesis,
    "short_operator_catchup": DailyBriefSynthesis,
    "calendar_prep_summary": CalendarPrepSummaryEval,
    "procore_digest_summary": ProcoreDigestSummaryEval,
}


class ModelEvalResult(BaseModel):
    """One profile × fixture measurement. Hash-only; carries no raw prompt/response."""

    fixture_id: str
    task_family: str
    schema_name: str
    profile_id: str
    model_name: str
    status: str
    json_valid: bool
    schema_valid: bool
    redaction_passed: bool
    redaction_findings: list[str] = Field(default_factory=list)
    usefulness_score: float = 0.0
    latency_ms: int = 0
    fallback_used: bool = False
    error_code: str | None = None
    output_hash: str | None = None

    model_config = {"extra": "forbid"}


class _CapturingBackend:
    """Wraps a backend to keep the last raw output in memory for metrics (never persisted)."""

    def __init__(self, inner: GenerationBackend) -> None:
        self._inner = inner
        self.last_output: str | None = None

    def generate_json(self, *, system: str, prompt: str) -> str:
        out = self._inner.generate_json(system=system, prompt=prompt)
        self.last_output = out
        return out


def _eligible_profiles(
    profiles: LocalModelProfiles, models_filter: list[str]
) -> list[LocalModelProfile]:
    """Resolve the candidate profile set from ``--models`` (``auto`` ⇒ enabled non-heavy profiles)."""
    if any(m.strip().lower() == "auto" for m in models_filter) or not models_filter:
        return [p for p in profiles.profiles if p.enabled and not p.heavy_profile]
    wanted = {m.strip() for m in models_filter}
    return [p for p in profiles.profiles if p.model_name in wanted]


def _build_prompt(fixture: ModelEvalFixture) -> tuple[str, str]:
    """Build a (system, prompt) pair from the fixture's redacted context (live mode)."""
    system = (
        "You are a local assistant for a construction executive. Return ONLY valid JSON matching "
        "the required schema for this task. Never output email addresses, URLs, join links, or "
        "tokens. Use only facts in the provided context."
    )
    prompt = (
        f"Task family: {fixture.task_family}. Produce the JSON for this redacted context:\n"
        + json.dumps(fixture.input_redacted, sort_keys=True)
    )
    return system, prompt


def _measure_one(
    *,
    fixture: ModelEvalFixture,
    profile: LocalModelProfile,
    profiles_no_fallback: LocalModelProfiles,
    schema: type[BaseModel],
    mode: EvalMode,
) -> ModelEvalResult:
    """Run a single fixture against a single profile and compute metrics (no raw retained)."""
    started = time.monotonic()
    inner: Optional[GenerationBackend]
    error_code: str | None = None
    if mode == "synthetic":
        inner = StaticOutputClient(fixture.synthetic_output)
    else:
        client, _model_name, reason = resolve_local_model_client(profile_id=profile.profile_id)
        if client is None:
            return ModelEvalResult(
                fixture_id=fixture.fixture_id,
                task_family=fixture.task_family,
                schema_name=schema.__name__,
                profile_id=profile.profile_id,
                model_name=profile.model_name,
                status="unavailable",
                json_valid=False,
                schema_valid=False,
                redaction_passed=True,
                usefulness_score=0.0,
                latency_ms=int((time.monotonic() - started) * 1000),
                error_code=reason or "live_model_client_missing",
            )
        inner = client
    capturing = _CapturingBackend(inner)
    system, prompt = _build_prompt(fixture)

    result = StructuredOutputClient().run(
        schema=schema,
        profile=profile,
        profiles=profiles_no_fallback,
        system=system,
        prompt=prompt,
        input_context=json.dumps(fixture.input_redacted, sort_keys=True),
        task_type=f"eval:{fixture.task_family}",
        backend=capturing,
        store=None,
        dry_run=True,
    )

    raw = capturing.last_output
    json_valid = False
    if raw is not None:
        try:
            json.loads(raw)
            json_valid = True
        except (ValueError, TypeError):
            json_valid = False
    schema_valid = result.status == "ok" and result.schema_valid
    findings = scan_text_for_forbidden(raw)
    usefulness = (
        compute_usefulness(result.validated, expected_sections=fixture.expected_sections)
        if schema_valid
        else 0.0
    )
    if result.status != "ok":
        error_code = result.error_redacted or result.status
    return ModelEvalResult(
        fixture_id=fixture.fixture_id,
        task_family=fixture.task_family,
        schema_name=schema.__name__,
        profile_id=result.profile_id,
        model_name=result.model_name,
        status=result.status,
        json_valid=json_valid,
        schema_valid=schema_valid,
        redaction_passed=not findings,
        redaction_findings=findings,
        usefulness_score=usefulness,
        latency_ms=result.latency_ms,
        fallback_used=result.fallback_used,
        error_code=error_code,
        output_hash=result.output_hash,
    )


def _family_recommendation(
    task_family: str,
    family_results: list[ModelEvalResult],
    fallbacks: dict[str, str],
) -> dict[str, Any]:
    """Pick the decisive recommended profile for a task family (or mark it blocked)."""
    by_profile: dict[str, list[ModelEvalResult]] = {}
    for r in family_results:
        by_profile.setdefault(r.profile_id, []).append(r)

    scored: list[dict[str, Any]] = []
    for profile_id, rs in by_profile.items():
        schema_rate = aggregate_rate([r.schema_valid for r in rs])
        redaction_rate = aggregate_rate([r.redaction_passed for r in rs])
        usefulness = aggregate_mean([r.usefulness_score for r in rs])
        latency = aggregate_mean([float(r.latency_ms) for r in rs])
        scored.append(
            {
                "profile_id": profile_id,
                "model_name": rs[0].model_name,
                "schema_valid_rate": schema_rate,
                "redaction_pass_rate": redaction_rate,
                "usefulness": usefulness,
                "latency_ms": round(latency, 1),
            }
        )

    # Eligible = redaction-clean AND schema-valid above threshold. Rank by schema rate, then
    # usefulness, then lower latency.
    eligible = [
        s
        for s in scored
        if s["redaction_pass_rate"] >= 1.0 and s["schema_valid_rate"] >= _MIN_SCHEMA_VALID_RATE
    ]
    eligible.sort(
        key=lambda s: (s["schema_valid_rate"], s["usefulness"], -s["latency_ms"]), reverse=True
    )

    if not eligible:
        any_redaction_fail = any(s["redaction_pass_rate"] < 1.0 for s in scored)
        reason = "redaction_failed" if any_redaction_fail else "no_reliable_profile"
        return {
            "task_family": task_family,
            "recommended_profile": None,
            "blocked": True,
            "reason_code": reason,
            "fallback_route": None,
            "candidates": scored,
        }

    best = eligible[0]
    return {
        "task_family": task_family,
        "recommended_profile": best["profile_id"],
        "recommended_model": best["model_name"],
        "blocked": False,
        "reason_code": "selected_best_schema_valid",
        "fallback_route": fallbacks.get(best["profile_id"]),
        "candidates": scored,
    }


def run_model_eval(
    *,
    suite: str = "daily-brief",
    task_families: list[str] | None = None,
    models: list[str] | None = None,
    mode: EvalMode = "synthetic",
    fixtures: list[ModelEvalFixture] | None = None,
    profiles: LocalModelProfiles | None = None,
) -> dict[str, Any]:
    """Run the eval suite and return an operationally decisive, raw-safe result dict."""
    warnings: list[str] = []
    blockers: list[str] = []
    try:
        profiles = profiles or load_local_model_profiles()
    except Phase10ContractError as exc:
        return {
            "command": "second-brain local-model eval",
            "ok": False,
            "applied": False,
            "dry_run": True,
            "mode": mode,
            "suite": suite,
            "models_attempted": [],
            "blockers": [f"profiles_unavailable:{str(exc)[:80]}"],
            "warnings": warnings,
            "results": [],
            "recommendations": [],
            "use_next_run": {},
            "metrics": {},
            "redaction_passed": True,
        }

    families = task_families or _SUITES.get(suite, _SUITES["daily-brief"])
    families = [f for f in families if f in TASK_FAMILY_SCHEMAS]
    fixtures = fixtures if fixtures is not None else synthetic_fixtures_for(families)
    fixtures = [f for f in fixtures if f.task_family in families]

    models_filter = models or ["auto"]
    candidate_profiles = _eligible_profiles(profiles, models_filter)
    profiles_no_fallback = profiles.model_copy(update={"fallbacks": {}})

    if not candidate_profiles:
        blockers.append("no_eligible_profiles")
    if not fixtures:
        blockers.append("no_fixtures_for_suite")

    results: list[ModelEvalResult] = []
    for fixture in fixtures:
        schema = TASK_FAMILY_SCHEMAS[fixture.task_family]
        for profile in candidate_profiles:
            results.append(
                _measure_one(
                    fixture=fixture,
                    profile=profile,
                    profiles_no_fallback=profiles_no_fallback,
                    schema=schema,
                    mode=mode,
                )
            )

    # Per-family decisive recommendation.
    recommendations: list[dict[str, Any]] = []
    use_next_run: dict[str, str] = {}
    for family in families:
        fam_results = [r for r in results if r.task_family == family]
        if not fam_results:
            continue
        rec = _family_recommendation(family, fam_results, profiles.fallbacks)
        recommendations.append(rec)
        if not rec["blocked"] and rec.get("recommended_profile"):
            use_next_run[family] = rec["recommended_profile"]

    overall_redaction_passed = all(r.redaction_passed for r in results)
    if not overall_redaction_passed:
        blockers.append("redaction_findings_present")
    if mode == "live" and results and all(r.status in {"unavailable", "timeout"} for r in results):
        blockers.append("live_daemon_unreachable")

    metrics = {
        "fixtures": len(fixtures),
        "profiles": len(candidate_profiles),
        "measurements": len(results),
        "json_valid_rate": aggregate_rate([r.json_valid for r in results]),
        "schema_valid_rate": aggregate_rate([r.schema_valid for r in results]),
        "redaction_pass_rate": aggregate_rate([r.redaction_passed for r in results]),
        "usefulness_mean": aggregate_mean([r.usefulness_score for r in results]),
        "latency_ms_mean": aggregate_mean([float(r.latency_ms) for r in results]),
        "blocked_families": [r["task_family"] for r in recommendations if r["blocked"]],
    }

    ok = not blockers and bool(results)
    return {
        "command": "second-brain local-model eval",
        "ok": ok,
        "applied": False,
        "dry_run": True,
        "mode": mode,
        "suite": suite,
        "task_families": families,
        "models_attempted": sorted({p.model_name for p in candidate_profiles}),
        "selected_profile": use_next_run.get("daily_brief_synthesis_quality"),
        "blockers": blockers,
        "warnings": warnings,
        "results": [r.model_dump() for r in results],
        "recommendations": recommendations,
        "use_next_run": use_next_run,
        "metrics": metrics,
        "redaction_passed": overall_redaction_passed,
    }
