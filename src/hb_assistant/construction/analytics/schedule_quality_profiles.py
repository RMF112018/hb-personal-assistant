"""Named CPM schedule assessment profiles (DCMA / GAO / AACE)."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

DEFAULT_ASSESSMENT_PROFILE = "dcma_14_point_plus_gao"
PROFILE_VERSION = "1.0.0"
DISCLAIMER_VERSION = "sq_disclaimer_v2"

DCMA_METRIC_SPECS: dict[str, dict[str, Any]] = {
    "dcma_logic": {
        "metric_name": "Logic integrity",
        "threshold_warning": 0.05,
        "threshold_fail": 0.10,
        "unit": "ratio",
    },
    "dcma_leads": {
        "metric_name": "Leads (negative lag)",
        "threshold_warning": 0.05,
        "threshold_fail": 0.10,
        "unit": "ratio",
    },
    "dcma_lags": {
        "metric_name": "Excessive lags",
        "threshold_warning": 0.10,
        "threshold_fail": 0.20,
        "unit": "ratio",
    },
    "dcma_relationship_types": {
        "metric_name": "Relationship type distribution",
        "threshold_warning": 0.90,
        "threshold_fail": 0.75,
        "unit": "ratio",
    },
    "dcma_hard_constraints": {
        "metric_name": "Hard constraints",
        "threshold_warning": 0.05,
        "threshold_fail": 0.15,
        "unit": "ratio",
    },
    "dcma_high_float": {
        "metric_name": "High float",
        "threshold_warning": 0.05,
        "threshold_fail": 0.15,
        "unit": "ratio",
    },
    "dcma_negative_float": {
        "metric_name": "Negative float",
        "threshold_warning": 0.01,
        "threshold_fail": 0.05,
        "unit": "ratio",
    },
    "dcma_high_duration": {
        "metric_name": "High duration",
        "threshold_warning": 0.05,
        "threshold_fail": 0.15,
        "unit": "ratio",
    },
    "dcma_invalid_dates": {
        "metric_name": "Invalid dates",
        "threshold_warning": 0.01,
        "threshold_fail": 0.05,
        "unit": "ratio",
    },
    "dcma_resources_cost_loading": {
        "metric_name": "Resources / cost loading",
        "threshold_warning": 0.50,
        "threshold_fail": 0.25,
        "unit": "ratio",
    },
    "dcma_missed_tasks": {
        "metric_name": "Missed tasks vs baseline",
        "unit": "ratio",
    },
    "dcma_critical_path_test": {
        "metric_name": "Critical path test",
        "threshold_warning": 0.10,
        "threshold_fail": 0.25,
        "unit": "ratio",
    },
    "dcma_cpli": {
        "metric_name": "Critical path length index",
        "unit": "index",
    },
    "dcma_bei": {
        "metric_name": "Baseline execution index",
        "unit": "index",
    },
}

GAO_CATEGORIES: tuple[str, ...] = (
    "capturing_all_activities",
    "sequencing_all_activities",
    "duration_reasonableness",
    "resource_cost_loading",
    "horizontal_vertical_traceability",
    "critical_path_validity",
    "float_reasonableness",
    "schedule_risk_readiness",
    "update_status_integrity",
    "baseline_maintenance",
    "source_validation",
    "data_date_integrity",
    "version_over_version_churn",
)

AACE_CATEGORIES: tuple[str, ...] = (
    "source_validation",
    "data_date_integrity",
    "update_status_integrity",
)


@dataclass(frozen=True)
class AssessmentProfile:
    profile_id: str
    profile_version: str
    method_source: str
    dcma_metrics: tuple[str, ...]
    gao_categories: tuple[str, ...]
    aace_categories: tuple[str, ...]

    def public(self) -> dict[str, str]:
        return {
            "assessment_profile": self.profile_id,
            "assessment_profile_version": self.profile_version,
            "method_source": self.method_source,
        }


_PROFILES: dict[str, AssessmentProfile] = {
    "dcma_14_point": AssessmentProfile(
        profile_id="dcma_14_point",
        profile_version=PROFILE_VERSION,
        method_source="DCMA_14PT",
        dcma_metrics=tuple(DCMA_METRIC_SPECS.keys()),
        gao_categories=(),
        aace_categories=(),
    ),
    "gao_schedule_best_practices": AssessmentProfile(
        profile_id="gao_schedule_best_practices",
        profile_version=PROFILE_VERSION,
        method_source="GAO_SCHEDULE_ASSESSMENT_GUIDE",
        dcma_metrics=(),
        gao_categories=GAO_CATEGORIES,
        aace_categories=(),
    ),
    "aace_cpm_source_validation": AssessmentProfile(
        profile_id="aace_cpm_source_validation",
        profile_version=PROFILE_VERSION,
        method_source="AACE_49R-06",
        dcma_metrics=(),
        gao_categories=(),
        aace_categories=AACE_CATEGORIES,
    ),
    "dcma_14_point_plus_gao": AssessmentProfile(
        profile_id="dcma_14_point_plus_gao",
        profile_version=PROFILE_VERSION,
        method_source="DCMA_14PT+GAO+AACE",
        dcma_metrics=tuple(DCMA_METRIC_SPECS.keys()),
        gao_categories=GAO_CATEGORIES,
        aace_categories=AACE_CATEGORIES,
    ),
}


def get_profile(profile_id: str | None = None) -> AssessmentProfile:
    key = profile_id or DEFAULT_ASSESSMENT_PROFILE
    if key not in _PROFILES:
        raise ValueError(f"unknown assessment profile: {key}")
    return _PROFILES[key]


def list_profiles() -> list[dict[str, str]]:
    return [p.public() for p in _PROFILES.values()]