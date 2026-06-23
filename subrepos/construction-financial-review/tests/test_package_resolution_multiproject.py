"""P4 — package resolution generalizes beyond tropical (synthetic second project).

Proves the detropicalized ``package_resolution``: an eligible non-tropical project
(``fixtureproj``) resolves its context/analysis packages and builds a chain, while an
ineligible project and a structurally-invalid package still fail closed.
"""

from __future__ import annotations

import json

import pytest
from construction_financial_review.common.package_resolution import (
    PackageResolutionError,
    build_package_chain,
    resolve_explicit_package,
)

STAMP = "20260101_000000"


@pytest.fixture(autouse=True)
def _default_allowlist(monkeypatch):
    # exercise the built-in default allowlist (tropical + fixtureproj), not an env override
    monkeypatch.delenv("HB_FORECAST_EVAL_PROJECT_ALLOWLIST", raising=False)


def _context_pkg(root, project_key):
    pkg = root / f"forecast_context_package_{project_key}_{STAMP}"
    (pkg / "canonical").mkdir(parents=True)
    (pkg / "summaries").mkdir(parents=True)
    (pkg / "manifest.json").write_text(json.dumps({"project_key": project_key}), encoding="utf-8")
    (pkg / "validation_report.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
    return pkg


def _analysis_pkg(root, project_key):
    pkg = root / f"forecast_analysis_package_{project_key}_{STAMP}"
    pkg.mkdir(parents=True)
    (pkg / "manifest.json").write_text(json.dumps({"project_key": project_key}), encoding="utf-8")
    (pkg / "validation_report.json").write_text(json.dumps({"ok": True}), encoding="utf-8")
    (pkg / "forecast_recommendations_by_budget_code.jsonl").write_text("", encoding="utf-8")
    return pkg


def test_eligible_second_project_resolves_and_builds_chain(tmp_path):
    ctx = _context_pkg(tmp_path, "fixtureproj")
    ana = _analysis_pkg(tmp_path, "fixtureproj")
    ctx_ref = resolve_explicit_package(
        package_kind="context", package_path=ctx, project_key="fixtureproj"
    )
    ana_ref = resolve_explicit_package(
        package_kind="analysis", package_path=ana, project_key="fixtureproj"
    )
    assert ctx_ref.project_key == "fixtureproj"
    assert ctx_ref.stamp == STAMP
    assert ana_ref.stamp == STAMP

    chain = build_package_chain(
        project_key="fixtureproj", data_root=tmp_path, refs=[ctx_ref, ana_ref]
    )
    assert set(chain.packages) == {"context", "analysis"}
    assert chain.project_key == "fixtureproj"


def test_ineligible_project_fails_closed(tmp_path):
    ctx = _context_pkg(tmp_path, "other")
    with pytest.raises(PackageResolutionError, match="not eligible"):
        resolve_explicit_package(package_kind="context", package_path=ctx, project_key="other")
    with pytest.raises(PackageResolutionError, match="not eligible"):
        build_package_chain(project_key="other", data_root=tmp_path, refs=[])


def test_structurally_invalid_package_fails_closed(tmp_path):
    pkg = tmp_path / f"forecast_analysis_package_fixtureproj_{STAMP}"
    pkg.mkdir(parents=True)
    (pkg / "manifest.json").write_text("{}", encoding="utf-8")  # missing required members
    with pytest.raises(PackageResolutionError, match="structurally invalid"):
        resolve_explicit_package(
            package_kind="analysis", package_path=pkg, project_key="fixtureproj"
        )


def test_prefix_is_project_scoped(tmp_path):
    # a tropical-named package does NOT satisfy a fixtureproj resolution (prefix is per-project)
    ctx = _context_pkg(tmp_path, "tropical")
    with pytest.raises(PackageResolutionError, match="does not match expected prefix"):
        resolve_explicit_package(
            package_kind="context", package_path=ctx, project_key="fixtureproj"
        )
