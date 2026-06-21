"""Service-level tests for the read-only forecast package browser (Implementation Phase 1).

Covers the happy path plus the adversarial cases required by plan correction #6:
fail-closed roots, invalid/missing manifests, malformed JSONL, DTO redaction,
unsupported package types, and package_id collision handling.
"""

from __future__ import annotations

import json
from pathlib import Path

import pytest

from hb_assistant.construction.analytics import forecast_catalog as fc
from hb_assistant.construction.analytics.forecast_catalog import (
    ForecastCatalogError,
    ForecastCatalogService,
)
from hb_assistant.construction.analytics.forecast_dto import find_redaction_leaks

STAMP = "20260615_153920"

# A deliberately leaky manifest: it contains a module path, a CLI command, a raw stamp,
# and an output path with a directory segment. None of these may reach any DTO payload.
LEAKY_MANIFEST = {
    "package_name": f"forecast_comprehensive_package_tropical_{STAMP}",
    "manifest_version": "1.0.0",
    "project": {
        "project_key": "tropical",
        "project_name": "Tropical World Nursery",
        "job_reference": "23-435-01",
        "forecast_period": "2026-June",
    },
    "generation": {
        "generator": "construction_financial_review.forecast_comprehensive.generate_comprehensive_forecast_package",
        "command": "python3 -m construction_financial_review.cli forecast-comprehensive --project tropical",
        "package_stamp": STAMP,
        "project_key": "tropical",
    },
    "output_files": [
        {"path": "audit/source_files_used.json", "size_bytes": 10, "row_count": None, "sha256": "abc"},
        {"path": "integrated_final_cost_recommendations.jsonl", "size_bytes": 100, "row_count": 2, "sha256": "def"},
    ],
}

VALIDATION_OK = {
    "package_stamp": STAMP,
    "project_key": "tropical",
    "checks": {"actuals_floor_preserved": True, "monthly_reconciliation_passed": True},
}

FINAL_COST_ROWS = [
    {
        "project_key": "tropical",
        "budget_code_key": "0000.03-01-025.MAT",
        "cost_code": "03-01-025",
        "accepted_recommended_final_cost": "3561.74",
        "integrated_cost_to_complete": "2401.29",
        "change_amount": "-128.05",
        "requires_human_acceptance": True,
        "acceptance_status": "pending",
    },
    {
        "project_key": "tropical",
        "budget_code_key": "0000.03-02-010.LAB",
        "cost_code": "03-02-010",
        "integrated_recommended_final_cost": "5000.00",
        "integrated_cost_to_complete": "1000.00",
        "acceptance_status": "pending",
    },
]

REVIEW_ROWS = [
    {
        "project_key": "tropical",
        "budget_code_key": "0000.03-01-025.MAT",
        "cost_code": "03-01-025",
        "review_priority": "medium",
        "review_reason": "integrated final-cost change",
        "acceptance_status": "pending",
    }
]


def _write_package(
    root: Path,
    *,
    dir_name: str,
    manifest: dict | None = LEAKY_MANIFEST,
    validation: dict | None = VALIDATION_OK,
    rows: list[dict] | None = None,
    review: list[dict] | None = None,
    raw_rows_text: str | None = None,
    monthly: list[dict] | None = None,
    monthly_project: list[dict] | None = None,
    probability: list[dict] | None = None,
    risk_register: list[dict] | None = None,
    top_risks: list[dict] | None = None,
) -> Path:
    pkg = root / dir_name
    pkg.mkdir(parents=True)
    if manifest is not None:
        (pkg / "manifest.json").write_text(json.dumps(manifest), encoding="utf-8")
    if validation is not None:
        (pkg / "validation_report.json").write_text(json.dumps(validation), encoding="utf-8")
    if rows is not None:
        (pkg / "integrated_final_cost_recommendations.jsonl").write_text(
            "\n".join(json.dumps(r) for r in rows), encoding="utf-8"
        )
    if raw_rows_text is not None:
        (pkg / "integrated_final_cost_recommendations.jsonl").write_text(raw_rows_text, encoding="utf-8")
    if review is not None:
        (pkg / "integrated_human_review_queue.jsonl").write_text(
            "\n".join(json.dumps(r) for r in review), encoding="utf-8"
        )
    if monthly is not None:
        (pkg / "integrated_monthly_forecast_by_budget_code.jsonl").write_text(
            "\n".join(json.dumps(r) for r in monthly), encoding="utf-8"
        )
    if monthly_project is not None:
        (pkg / "integrated_monthly_project_forecast.jsonl").write_text(
            "\n".join(json.dumps(r) for r in monthly_project), encoding="utf-8"
        )
    if probability is not None:
        (pkg / "integrated_probability_by_budget_code.jsonl").write_text(
            "\n".join(json.dumps(r) for r in probability), encoding="utf-8"
        )
    if risk_register is not None:
        (pkg / "integrated_risk_register.jsonl").write_text(
            "\n".join(json.dumps(r) for r in risk_register), encoding="utf-8"
        )
    if top_risks is not None:
        (pkg / "top_overrun_risks.json").write_text(json.dumps(top_risks), encoding="utf-8")
    return pkg


@pytest.fixture
def populated_root(tmp_path: Path) -> Path:
    root = tmp_path / "2026-June"
    root.mkdir()
    _write_package(
        root,
        dir_name=f"forecast_comprehensive_package_tropical_{STAMP}",
        rows=FINAL_COST_ROWS,
        review=REVIEW_ROWS,
        monthly=MONTHLY_ROWS,
        monthly_project=MONTHLY_PROJECT_ROWS,
        probability=PROBABILITY_ROWS,
        risk_register=RISK_ROWS,
        top_risks=TOP_RISK_ROWS,
    )
    return root


# Phase 5 review-surface fixtures.
MONTHLY_ROWS = [
    {
        "cost_code": "03-01-025",
        "budget_code_key": "0000.03-01-025.MAT",
        "integrated_cost_to_complete": "2401.29",
        "monthly_costs": [
            {"forecast_month": "2026-06", "integrated_month_cost": "282.07"},
            {"forecast_month": "2026-07", "integrated_month_cost": "423.84"},
        ],
    }
]
MONTHLY_PROJECT_ROWS = [
    {"forecast_month": "2026-06", "integrated_month_cost": "282.07"},
    {"forecast_month": "2026-07", "integrated_month_cost": "423.84"},
]
PROBABILITY_ROWS = [
    {
        "cost_code": "03-01-025",
        "budget_code_key": "0000.03-01-025.MAT",
        "actual_cost_to_date": "1032.40",
        "integrated_p10": "2103.22",
        "integrated_p50": "3561.74",
        "integrated_p80": "5487.45",
        "integrated_p90": "7006.87",
        "integrated_p95": "8812.82",
    }
]
RISK_ROWS = [
    {
        "cost_code": "03-01-025",
        "budget_code_key": "0000.03-01-025.MAT",
        "integrated_recommended_final_cost": "3561.74",
        "integrated_minus_accepted_final_cost": "128.05",
        "conflict_count": 2,
        "max_conflict_severity": "high",
        "review_priority": "medium",
    }
]
TOP_RISK_ROWS = [
    {
        "cost_code": "03-01-413",
        "budget_code_key": "0000.03-01-413.LAB",
        "integrated_recommended_final_cost": "120000.00",
        "integrated_minus_accepted_final_cost": "15000.00",
        "integrated_direction": "over",
    }
]


# -- happy path ---------------------------------------------------------------


def test_list_projects_periods_packages(populated_root: Path) -> None:
    svc = ForecastCatalogService(package_roots=[populated_root])
    projects = svc.list_projects()
    assert projects["surface"].endswith(".projects")
    assert projects["guardrails"]["read_only"] is True
    assert any(p["project_key"] == "tropical" for p in projects["projects"])

    periods = svc.list_periods("tropical")
    assert [p["period"] for p in periods["periods"]] == ["2026-June"]

    packages = svc.list_packages("tropical", "2026-June")
    assert packages["packages"], "expected at least one package"
    pkg = packages["packages"][0]
    assert pkg["package_type"] == "comprehensive"
    assert pkg["status"] == "validated"
    assert pkg["display_label"].startswith("Comprehensive forecast")
    assert pkg["job_reference"] == "23-435-01"


def test_summary_validation_manifest_rows_review(populated_root: Path) -> None:
    svc = ForecastCatalogService(package_roots=[populated_root])
    pid = svc.list_packages("tropical")["packages"][0]["package_id"]

    summary = svc.read_package_summary(pid)
    assert summary["status"] == "validated"
    assert summary["package_type"] == "comprehensive"

    validation = svc.read_validation_status(pid)
    assert validation["total_checks"] == 2
    assert validation["passed"] == 2
    assert validation["failed"] == 0

    manifest = svc.read_manifest(pid)
    names = {f["file_name"] for f in manifest["files"]}
    assert names == {"source_files_used.json", "integrated_final_cost_recommendations.jsonl"}

    rows = svc.read_forecast_rows(pid)
    assert rows["rows_available"] is True
    assert rows["row_count"] == 2
    assert rows["rows"][0]["recommended_final_cost"] == "3561.74"
    assert rows["rows"][1]["recommended_final_cost"] == "5000.00"  # falls back to integrated_*

    review = svc.read_review_items(pid)
    assert review["item_count"] == 1
    assert review["items"][0]["review_priority"] == "medium"


# -- Phase 5 review surfaces --------------------------------------------------


def test_review_surfaces_read_and_redact(populated_root: Path) -> None:
    svc = ForecastCatalogService(package_roots=[populated_root])
    pid = svc.list_packages("tropical")["packages"][0]["package_id"]

    monthly = svc.read_monthly_forecast(pid)
    assert monthly["monthly_available"] is True
    assert monthly["row_count"] == 1
    assert monthly["rows"][0]["cost_to_complete"] == "2401.29"
    assert monthly["rows"][0]["months"][0] == {"forecast_month": "2026-06", "amount": "282.07"}
    assert monthly["project_monthly"] == [
        {"forecast_month": "2026-06", "amount": "282.07"},
        {"forecast_month": "2026-07", "amount": "423.84"},
    ]
    assert find_redaction_leaks(monthly) == []

    prob = svc.read_probability(pid)
    assert prob["probability_available"] is True
    assert prob["rows"][0]["p50"] == "3561.74"
    assert prob["rows"][0]["p95"] == "8812.82"
    assert prob["rows"][0]["actual_cost_to_date"] == "1032.40"
    assert find_redaction_leaks(prob) == []

    risk = svc.read_risk_register(pid)
    assert risk["risk_register_available"] is True
    assert risk["rows"][0]["max_conflict_severity"] == "high"
    assert risk["rows"][0]["variance_amount"] == "128.05"
    assert risk["rows"][0]["conflict_count"] == 2
    assert find_redaction_leaks(risk) == []

    top = svc.read_top_risks(pid)
    assert top["top_risks_available"] is True
    assert top["rows"][0]["overrun_amount"] == "15000.00"
    assert top["rows"][0]["direction"] == "over"
    assert find_redaction_leaks(top) == []


def test_review_surfaces_absent_files_degrade_gracefully(tmp_path: Path) -> None:
    # A non-comprehensive package carries none of the review-surface files.
    root = tmp_path / "2026-June"
    root.mkdir()
    _write_package(
        root,
        dir_name=f"forecast_context_package_tropical_{STAMP}",
        rows=None,
        review=None,
    )
    svc = ForecastCatalogService(package_roots=[root])
    pid = svc.list_packages("tropical")["packages"][0]["package_id"]
    assert svc.read_monthly_forecast(pid)["monthly_available"] is False
    assert svc.read_probability(pid)["probability_available"] is False
    assert svc.read_risk_register(pid)["risk_register_available"] is False
    assert svc.read_top_risks(pid)["top_risks_available"] is False
    # All still return well-formed, leak-free payloads with empty rows.
    for payload in (
        svc.read_monthly_forecast(pid),
        svc.read_probability(pid),
        svc.read_risk_register(pid),
        svc.read_top_risks(pid),
    ):
        assert payload["row_count"] == 0
        assert payload["rows"] == []
        assert find_redaction_leaks(payload) == []


def test_top_risks_ignores_non_list_json(tmp_path: Path) -> None:
    # top_overrun_risks.json must be a JSON array; a stray object must not crash the reader.
    root = tmp_path / "2026-June"
    root.mkdir()
    pkg = _write_package(root, dir_name=f"forecast_comprehensive_package_tropical_{STAMP}")
    (pkg / "top_overrun_risks.json").write_text('{"not": "a list"}', encoding="utf-8")
    svc = ForecastCatalogService(package_roots=[root])
    pid = svc.list_packages("tropical")["packages"][0]["package_id"]
    out = svc.read_top_risks(pid)
    assert out["top_risks_available"] is True
    assert out["rows"] == []
    assert find_redaction_leaks(out) == []


# -- correction #5: fail-closed roots -----------------------------------------


@pytest.mark.parametrize("bad", [None, []])
def test_empty_roots_fail_closed(bad) -> None:
    with pytest.raises(ForecastCatalogError):
        ForecastCatalogService(package_roots=bad)


def test_relative_root_fails_closed() -> None:
    with pytest.raises(ForecastCatalogError):
        ForecastCatalogService(package_roots=["relative/dir"])


def test_missing_root_fails_closed(tmp_path: Path) -> None:
    with pytest.raises(ForecastCatalogError):
        ForecastCatalogService(package_roots=[tmp_path / "does-not-exist"])


def test_file_not_dir_root_fails_closed(tmp_path: Path) -> None:
    f = tmp_path / "a-file"
    f.write_text("x", encoding="utf-8")
    with pytest.raises(ForecastCatalogError):
        ForecastCatalogService(package_roots=[f])


# -- correction #6: invalid / missing manifests -------------------------------


def test_missing_manifest_is_invalid_but_attributable(tmp_path: Path) -> None:
    root = tmp_path / "2026-June"
    root.mkdir()
    _write_package(
        root,
        dir_name=f"forecast_comprehensive_package_tropical_{STAMP}",
        manifest=None,
        validation=None,
    )
    svc = ForecastCatalogService(package_roots=[root])
    # dirname fallback keeps it attributable to the project, flagged invalid, no crash.
    packages = svc.list_packages("tropical")
    assert packages["invalid_count"] == 1
    assert packages["packages"][0]["status"] == "invalid"


def test_truncated_manifest_does_not_crash(tmp_path: Path) -> None:
    root = tmp_path / "2026-June"
    root.mkdir()
    pkg = root / f"forecast_comprehensive_package_tropical_{STAMP}"
    pkg.mkdir()
    (pkg / "manifest.json").write_text('{"project": {"project_key": "tropical"', encoding="utf-8")
    svc = ForecastCatalogService(package_roots=[root])
    packages = svc.list_packages("tropical")
    assert packages["invalid_count"] == 1
    pid = packages["packages"][0]["package_id"]
    # downstream reads still succeed (degraded), never raising.
    assert svc.read_manifest(pid)["output_file_count"] == 0
    assert svc.read_validation_status(pid)["status"] == "invalid"


def test_manifest_missing_keys(tmp_path: Path) -> None:
    root = tmp_path / "2026-June"
    root.mkdir()
    _write_package(
        root,
        dir_name=f"forecast_comprehensive_package_tropical_{STAMP}",
        manifest={"manifest_version": "1.0.0"},  # no project / output_files
        validation=None,
    )
    svc = ForecastCatalogService(package_roots=[root])
    pid = svc.list_packages("tropical")["packages"][0]["package_id"]
    manifest = svc.read_manifest(pid)
    assert manifest["output_file_count"] == 0
    assert manifest["project_key"] in (None, "tropical")


# -- correction #6: malformed JSONL -------------------------------------------


def test_malformed_jsonl_skips_bad_lines(tmp_path: Path) -> None:
    root = tmp_path / "2026-June"
    root.mkdir()
    good1 = json.dumps(FINAL_COST_ROWS[0])
    good2 = json.dumps(FINAL_COST_ROWS[1])
    raw = f"{good1}\n{{not valid json\n\n[1,2,3]\n{good2}\n"
    _write_package(
        root,
        dir_name=f"forecast_comprehensive_package_tropical_{STAMP}",
        raw_rows_text=raw,
    )
    svc = ForecastCatalogService(package_roots=[root])
    pid = svc.list_packages("tropical")["packages"][0]["package_id"]
    rows = svc.read_forecast_rows(pid)
    assert rows["row_count"] == 2  # only the two valid dict lines survive


def test_non_utf8_jsonl_does_not_crash(tmp_path: Path) -> None:
    root = tmp_path / "2026-June"
    root.mkdir()
    pkg = _write_package(
        root,
        dir_name=f"forecast_comprehensive_package_tropical_{STAMP}",
        rows=FINAL_COST_ROWS,
    )
    # append a non-UTF8 byte line; errors='replace' + json skip must keep it safe
    with (pkg / "integrated_final_cost_recommendations.jsonl").open("ab") as fh:
        fh.write(b"\n\xff\xfe bad bytes\n")
    svc = ForecastCatalogService(package_roots=[root])
    pid = svc.list_packages("tropical")["packages"][0]["package_id"]
    rows = svc.read_forecast_rows(pid)
    assert rows["row_count"] == 2


# -- correction #4/#6: DTO redaction ------------------------------------------


def test_no_dev_internals_leak_in_any_payload(populated_root: Path) -> None:
    svc = ForecastCatalogService(package_roots=[populated_root])
    pid = svc.list_packages("tropical")["packages"][0]["package_id"]
    payloads = [
        svc.list_projects(),
        svc.list_periods("tropical"),
        svc.list_packages("tropical", "2026-June"),
        svc.read_package_summary(pid),
        svc.read_validation_status(pid),
        svc.read_manifest(pid),
        svc.read_forecast_rows(pid),
        svc.read_review_items(pid),
    ]
    for payload in payloads:
        leaks = find_redaction_leaks(payload)
        assert leaks == [], f"redaction leak: {leaks}"


# -- correction #6: unsupported package types ---------------------------------


def test_unknown_type_is_unsupported(tmp_path: Path) -> None:
    root = tmp_path / "2026-June"
    root.mkdir()
    # matches the trailing stamp pattern but the prefix is not a known package type
    _write_package(
        root,
        dir_name=f"totally_unknown_thing_tropical_{STAMP}",
        manifest=LEAKY_MANIFEST,
        validation=VALIDATION_OK,
    )
    svc = ForecastCatalogService(package_roots=[root])
    packages = svc.list_packages("tropical")
    assert packages["unsupported_count"] == 1
    assert packages["packages"][0]["status"] == "unsupported"


def test_non_package_dir_is_ignored(tmp_path: Path) -> None:
    root = tmp_path / "2026-June"
    root.mkdir()
    (root / "not_a_package_no_stamp").mkdir()
    (root / "random_notes").mkdir()
    _write_package(root, dir_name=f"forecast_monthly_package_tropical_{STAMP}")
    svc = ForecastCatalogService(package_roots=[root])
    packages = svc.list_packages("tropical")
    assert len(packages["packages"]) == 1
    assert packages["packages"][0]["package_type"] == "monthly"


# -- correction #6: package_id collision --------------------------------------


def test_package_id_collision_is_refused(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    root = tmp_path / "2026-June"
    root.mkdir()
    _write_package(root, dir_name=f"forecast_monthly_package_tropical_{STAMP}")
    _write_package(root, dir_name=f"forecast_probability_package_tropical_{STAMP}")

    class _ConstDigest:
        def __init__(self, *_a, **_k) -> None:
            pass

        def hexdigest(self) -> str:
            return "deadbeefdeadbeef" * 4

    # Force every package_id to collide; the catalog must refuse rather than overwrite.
    monkeypatch.setattr(fc.hashlib, "sha256", _ConstDigest)
    svc = ForecastCatalogService(package_roots=[root])
    with pytest.raises(ForecastCatalogError):
        svc.list_packages("tropical")
