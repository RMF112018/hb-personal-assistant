"""Deterministic narrative QA for schedule hub story and memo surfaces."""

from __future__ import annotations

import re
from typing import Any

_ADVISORY_POSTURE = "sequence_cues_not_causation"

_FORBIDDEN_TERMS = (
    "caused the delay",
    "responsible for the delay",
    "compensable delay",
    "excusable delay",
    "contractor-caused",
    "owner-caused",
    "claim impact",
    "proves delay",
    "causation finding",
    "delay responsibility",
)

_REQUIRED_DRIVER_MARKERS = (
    "appears connected",
    "review this sequence",
    "candidate driver",
    "sequence cue",
)

_BASIS_TERMS = ("prior update", "previous update", "baseline", "since baseline", "since the prior")


def validate_review_cue_text(cue: dict[str, Any]) -> dict[str, Any]:
    """Validate PM-facing review cue copy for forbidden causation/entitlement language."""

    violations: list[dict[str, str]] = []
    fields = {
        "item_title": str(cue.get("item_title") or ""),
        "cue_summary": str(cue.get("cue_summary") or cue.get("evidence", {}).get("cue_summary") or ""),
        "recommended_review_action": str(
            cue.get("recommended_review_action")
            or (cue.get("evidence") or {}).get("recommended_review_action")
            or ""
        ),
    }
    caveats = cue.get("caveats") or (cue.get("evidence") or {}).get("caveats") or []
    for index, caveat in enumerate(caveats):
        fields[f"caveat:{index}"] = str(caveat)
    combined = " ".join(fields.values()).lower()
    for term in _FORBIDDEN_TERMS:
        if _contains_forbidden_term(combined, term):
            violations.append(
                {
                    "code": "forbidden_term",
                    "message": f"Forbidden claim language detected in review cue: {term}",
                }
            )
    return {
        "passed": not violations,
        "violations": violations,
        "advisory_posture": _ADVISORY_POSTURE,
    }


def validate_summary(summary: dict[str, Any]) -> dict[str, Any]:
    violations: list[dict[str, str]] = []
    warnings: list[dict[str, str]] = []
    story = summary.get("schedule_story") or {}
    command = summary.get("command_summary") or {}
    change = summary.get("change_impact") or {}
    direct = change.get("direct_remaining_changes", {}).get("summary", {}) if change.get("available") else {}
    driver_hub = summary.get("change_driver_analysis") or {}
    prior = driver_hub.get("prior_update") or driver_hub
    baseline = driver_hub.get("baseline") or {}

    prose_fields = _story_prose_fields(story)
    combined = " ".join(prose_fields.values()).lower()

    for term in _FORBIDDEN_TERMS:
        if _contains_forbidden_term(combined, term):
            violations.append(
                {
                    "code": "forbidden_term",
                    "message": f"Forbidden claim language detected: {term}",
                }
            )

    if prior.get("available"):
        driver_text = " ".join(
            str(story.get(key) or "")
            for key in ("primary_driver_narrative", "primary_change_driver", "why_it_matters")
        ).lower()
        if driver_text and not any(marker in driver_text for marker in _REQUIRED_DRIVER_MARKERS):
            violations.append(
                {
                    "code": "missing_advisory_markers",
                    "message": "Driver narrative is missing required sequence-cue phrasing.",
                }
            )

    _check_count_consistency(
        story=story,
        command=command,
        direct=direct,
        violations=violations,
    )

    _check_basis_consistency(
        story=story,
        prior_available=bool(prior.get("available")),
        baseline_available=bool(baseline.get("available")),
        warnings=warnings,
    )

    _check_duplicate_phrasing(story=story, warnings=warnings)
    _check_zero_day_movement(story=story, violations=violations)

    source_basis = _source_basis_map(summary)

    return {
        "passed": not violations,
        "violations": violations,
        "warnings": warnings,
        "source_basis": source_basis,
        "advisory_posture": _ADVISORY_POSTURE,
    }


def _contains_forbidden_term(text: str, term: str) -> bool:
    for match in re.finditer(re.escape(term), text, flags=re.I):
        start = match.start()
        window = text[max(0, start - 48):start].lower()
        if re.search(r"\b(?:not|no|never)\b", window):
            continue
        if re.search(r"\bdoes\s+not\s+determine\b", window):
            continue
        return True
    return False


def _story_prose_fields(story: dict[str, Any]) -> dict[str, str]:
    fields = {
        key: str(story.get(key) or "")
        for key in (
            "headline",
            "synopsis",
            "what_changed",
            "why_it_matters",
            "primary_change_driver",
            "primary_driver_narrative",
            "review_next_summary",
        )
    }
    for caveat in story.get("caveats") or []:
        fields[f"caveat:{caveat[:24]}"] = str(caveat)
    return {key: value for key, value in fields.items() if value}


def _check_count_consistency(
    *,
    story: dict[str, Any],
    command: dict[str, Any],
    direct: dict[str, Any],
    violations: list[dict[str, str]],
) -> None:
    if not direct:
        return
    checks = (
        ("finish_moved_later_count", r"(\d+)\s+remaining activities moved later"),
        ("finish_moved_earlier_count", r"(\d+)\s+remaining activities moved earlier"),
        ("finish_changed_count", r"(\d+)\s+changed finish"),
        ("worsened_float_count", r"(\d+)\s+lost float"),
    )
    what_changed = str(story.get("what_changed") or "")
    for key, pattern in checks:
        expected = int(direct.get(key) or 0)
        match = re.search(pattern, what_changed, flags=re.I)
        if not match:
            continue
        claimed = int(match.group(1))
        if claimed != expected:
            violations.append(
                {
                    "code": "unsupported_count",
                    "message": f"Story count for {key} ({claimed}) does not match change_impact ({expected}).",
                }
            )

    forecast_delta = command.get("forecast_finish_delta_days")
    headline = str(story.get("headline") or "")
    if forecast_delta is not None and "moved" in headline.lower():
        match = re.search(r"moved\s+(\d+)\s+days", headline, flags=re.I)
        if match and int(match.group(1)) != abs(int(forecast_delta)):
            violations.append(
                {
                    "code": "unsupported_count",
                    "message": (
                        f"Headline movement days ({match.group(1)}) "
                        f"does not match command_summary ({forecast_delta})."
                    ),
                }
            )


def _check_basis_consistency(
    *,
    story: dict[str, Any],
    prior_available: bool,
    baseline_available: bool,
    warnings: list[dict[str, str]],
) -> None:
    if not (prior_available and baseline_available):
        return
    combined = " ".join(_story_prose_fields(story).values()).lower()
    has_prior = any(term in combined for term in ("prior update", "previous update"))
    has_baseline = "baseline" in combined
    if has_prior and has_baseline:
        warnings.append(
            {
                "code": "mixed_basis_terms",
                "message": "Story mixes prior-update and baseline terms; keep basis explicit per section.",
            }
        )


def _check_zero_day_movement(*, story: dict[str, Any], violations: list[dict[str, str]]) -> None:
    combined = " ".join(_story_prose_fields(story).values()).lower()
    if re.search(r"moved or extended by\s+0\s+days", combined):
        violations.append(
            {
                "code": "zero_day_movement",
                "message": "Driver narrative must not claim zero-day movement.",
            }
        )
    if re.search(r"\bmoved by\s+0\s+days\b", combined):
        violations.append(
            {
                "code": "zero_day_movement",
                "message": "Driver narrative must not claim zero-day movement.",
            }
        )


def _check_duplicate_phrasing(*, story: dict[str, Any], warnings: list[dict[str, str]]) -> None:
    sentences: dict[str, str] = {}
    for field, text in _story_prose_fields(story).items():
        for sentence in re.split(r"(?<=[.!?])\s+", text.strip()):
            normalized = re.sub(r"\s+", " ", sentence.strip().lower())
            if len(normalized) < 40:
                continue
            if normalized in sentences and sentences[normalized] != field:
                warnings.append(
                    {
                        "code": "duplicated_phrasing",
                        "message": f"Repeated sentence across {sentences[normalized]} and {field}.",
                    }
                )
            else:
                sentences[normalized] = field


def _source_basis_map(summary: dict[str, Any]) -> dict[str, str]:
    command = summary.get("command_summary") or {}
    change = summary.get("change_impact") or {}
    direct = change.get("direct_remaining_changes", {}).get("summary", {}) if change.get("available") else {}
    driver_hub = summary.get("change_driver_analysis") or {}
    prior = driver_hub.get("prior_update") or driver_hub
    workbench = summary.get("review_workbench") or {}
    basis: dict[str, str] = {}
    if command.get("forecast_finish") is not None:
        basis["forecast_finish"] = "command_summary.forecast_finish"
    if command.get("forecast_finish_delta_days") is not None:
        basis["forecast_finish_delta_days"] = "command_summary.forecast_finish_delta_days"
    if command.get("remaining_activity_count") is not None:
        basis["remaining_activity_count"] = "command_summary.remaining_activity_count"
    if command.get("negative_float_remaining_count") is not None:
        basis["negative_float_remaining_count"] = "command_summary.negative_float_remaining_count"
    if direct:
        basis["remaining_finish_moved_later_count"] = "change_impact.direct_remaining_changes.summary.finish_moved_later_count"
        basis["worsened_float_count"] = "change_impact.direct_remaining_changes.summary.worsened_float_count"
    if prior.get("available"):
        basis["primary_driver_narrative"] = "change_driver_analysis.prior_update"
    if workbench.get("available"):
        basis["review_workbench_counts"] = "review_workbench.summary"
    return basis