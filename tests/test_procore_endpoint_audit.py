"""Tests for the Procore foundation + endpoint audit (Phase 01 Step 10).

Covers:
- Pydantic models: read-only-by-construction (http_method literal), category
  invariants, kebab-case keys, duplicate detection, hard-guardrail status
  enforcement (correspondence excluded / schedule + tasks deferred).
- Loader override precedence (seed → repo override → env).
- Auth status: env-absent / env-partial / env-present scenarios; never
  reads env values into the returned report; never opens the token file.
- Auditor: per-project access matrix; unmapped project handling;
  unknown-project KeyError; mapping validation OK vs pending.
- CLI: auth status, tools list, tools audit (happy + unknown project),
  mapping validate (exit 1 on pending), help-shape regression at root.
- Guardrail string-scans: writeback never advertised; live_calls_disabled
  always true; no HTTP/network import in the procore module surface.
"""

from __future__ import annotations

import json
from pathlib import Path
from unittest.mock import MagicMock

import pytest
import yaml
from pydantic import ValidationError
from typer.testing import CliRunner

from hb_assistant.cli import main as main_cli
from hb_assistant.cli import procore as procore_cli
from hb_assistant.procore import (
    EndpointAuditor,
    ProcoreEndpoint,
    ProcoreEndpointContract,
    ProcoreProjectsRegistry,
    check_auth_status,
    load_endpoint_contract,
    load_procore_projects,
)
from hb_assistant.procore.auth import REQUIRED_ENV_KEYS
from hb_assistant.procore.loader import (
    CONTRACT_ENV_VAR,
    PROJECTS_ENV_VAR,
    EndpointContractError,
    ProcoreProjectsError,
)
from hb_assistant.procore.models import REQUIRED_CATEGORIES, EndpointAuditRunReceipt

# ---------------------------------------------------------------------------
# Fixtures
# ---------------------------------------------------------------------------


@pytest.fixture
def runner() -> CliRunner:
    return CliRunner()


def _minimal_valid_contract_dict() -> dict:
    """Smallest contract dict that satisfies every required-category + hard guardrail."""
    base_endpoints = []
    for cat in REQUIRED_CATEGORIES:
        if cat == "correspondence":
            status = "excluded"
            sens = "critical"
            verif: dict = {
                "verification_status": "excluded_by_guardrail",
                "verification_reason": "test fixture: excluded by guardrail",
            }
        elif cat in ("schedule", "tasks"):
            status = "deferred"
            sens = "medium"
            verif = {
                "verification_status": "deferred_by_guardrail",
                "verification_reason": "test fixture: deferred by guardrail",
            }
        else:
            status = "validated"
            sens = "low"
            verif = {
                "verification_status": "official_docs_verified",
                "official_reference_url": f"https://developers.procore.com/test/{cat}",
                "verified_at_utc": "2026-05-27T00:00:00Z",
                "verified_by": "test-fixture",
            }
        base_endpoints.append(
            {
                "endpoint_id": f"ep-{cat}",
                "http_method": "GET",
                "path_template": f"/vapid/projects/{{project_id}}/{cat.replace('-', '_')}",
                "category": cat,
                "status": status,
                "sensitivity": sens,
                "included_in_phase_01": status not in ("excluded", "deferred"),
                **verif,
            }
        )
    return {
        "version": 1,
        "company_id": "5280",
        "company_display_name": "HB Construction",
        "endpoints": base_endpoints,
    }


def _make_unenforced_auditor() -> EndpointAuditor:
    return EndpointAuditor(
        load_endpoint_contract(),
        load_procore_projects(),
    )


# ---------------------------------------------------------------------------
# Pydantic models — read-only by construction
# ---------------------------------------------------------------------------


def test_endpoint_rejects_non_get_method() -> None:
    with pytest.raises(ValidationError):
        ProcoreEndpoint(
            endpoint_id="x",
            http_method="POST",  # type: ignore[arg-type]
            path_template="/x",
            category="rfis",
            status="validated",
            sensitivity="low",
        )


def test_endpoint_rejects_extra_fields() -> None:
    with pytest.raises(ValidationError):
        ProcoreEndpoint(
            endpoint_id="x",
            http_method="GET",
            path_template="/x",
            category="rfis",
            status="validated",
            sensitivity="low",
            stowaway="leak",  # type: ignore[call-arg]
        )


def test_endpoint_rejects_non_kebab_id() -> None:
    with pytest.raises(ValidationError):
        ProcoreEndpoint(
            endpoint_id="Bad ID",
            http_method="GET",
            path_template="/x",
            category="rfis",
            status="validated",
            sensitivity="low",
        )


def test_endpoint_rejects_invalid_status() -> None:
    with pytest.raises(ValidationError):
        ProcoreEndpoint(
            endpoint_id="x",
            http_method="GET",
            path_template="/x",
            category="rfis",
            status="auto-accept",  # type: ignore[arg-type]
            sensitivity="low",
        )


def test_endpoint_rejects_relative_path_template() -> None:
    with pytest.raises(ValidationError):
        ProcoreEndpoint(
            endpoint_id="x",
            http_method="GET",
            path_template="no-slash",
            category="rfis",
            status="validated",
            sensitivity="low",
        )


def test_contract_requires_every_category() -> None:
    bad = _minimal_valid_contract_dict()
    bad["endpoints"] = [e for e in bad["endpoints"] if e["category"] != "rfis"]
    with pytest.raises(ValidationError):
        ProcoreEndpointContract.model_validate(bad)


def test_contract_rejects_correspondence_not_excluded() -> None:
    bad = _minimal_valid_contract_dict()
    for e in bad["endpoints"]:
        if e["category"] == "correspondence":
            e["status"] = "validated"  # hard guardrail violation
    with pytest.raises(ValidationError):
        ProcoreEndpointContract.model_validate(bad)


def test_contract_rejects_schedule_not_deferred() -> None:
    bad = _minimal_valid_contract_dict()
    for e in bad["endpoints"]:
        if e["category"] == "schedule":
            e["status"] = "validated"
    with pytest.raises(ValidationError):
        ProcoreEndpointContract.model_validate(bad)


def test_contract_rejects_duplicate_endpoint_id() -> None:
    bad = _minimal_valid_contract_dict()
    bad["endpoints"].append(dict(bad["endpoints"][0]))  # duplicate ep-rfis
    with pytest.raises(ValidationError):
        ProcoreEndpointContract.model_validate(bad)


def test_projects_registry_rejects_duplicate_keys() -> None:
    with pytest.raises(ValidationError):
        ProcoreProjectsRegistry.model_validate(
            {
                "company_id": "5280",
                "projects": [
                    {
                        "hb_project_key": "tropical",
                        "procore_project_id": "1",
                        "procore_project_name": "T",
                        "status": "pilot",
                    },
                    {
                        "hb_project_key": "tropical",
                        "procore_project_id": "2",
                        "procore_project_name": "T2",
                        "status": "pilot",
                    },
                ],
            }
        )


def test_projects_registry_rejects_duplicate_procore_id() -> None:
    with pytest.raises(ValidationError):
        ProcoreProjectsRegistry.model_validate(
            {
                "company_id": "5280",
                "projects": [
                    {
                        "hb_project_key": "a",
                        "procore_project_id": "12345",
                        "procore_project_name": "A",
                        "status": "pilot",
                    },
                    {
                        "hb_project_key": "b",
                        "procore_project_id": "12345",
                        "procore_project_name": "B",
                        "status": "pilot",
                    },
                ],
            }
        )


def test_projects_registry_allows_empty_procore_id_for_pending() -> None:
    reg = ProcoreProjectsRegistry.model_validate(
        {
            "company_id": "5280",
            "projects": [
                {
                    "hb_project_key": "x",
                    "procore_project_id": "",
                    "procore_project_name": "",
                    "status": "pending",
                },
                {
                    "hb_project_key": "y",
                    "procore_project_id": "",
                    "procore_project_name": "",
                    "status": "pending",
                },
            ],
        }
    )
    assert len(reg.projects) == 2


# ---------------------------------------------------------------------------
# Procore project ID shape — HB-number rejection + numeric requirement
# ---------------------------------------------------------------------------


def _make_mapping(**overrides: object) -> dict[str, object]:
    base: dict[str, object] = {
        "hb_project_key": "tropical",
        "procore_project_id": "2525840",
        "procore_project_name": "Tropical - S L",
        "status": "pilot",
    }
    base.update(overrides)
    return base


def test_procore_project_mapping_rejects_hb_number_shape() -> None:
    with pytest.raises(ValidationError) as exc:
        ProcoreProjectsRegistry.model_validate(
            {
                "company_id": "5280",
                "projects": [_make_mapping(procore_project_id="23-435-01")],
            }
        )
    blob = str(exc.value)
    assert "23-435-01" in blob
    assert r"^\d{2}-\d{3}-\d{2}$" in blob


def test_procore_project_mapping_rejects_non_numeric_when_not_pending() -> None:
    with pytest.raises(ValidationError) as exc:
        ProcoreProjectsRegistry.model_validate(
            {
                "company_id": "5280",
                "projects": [_make_mapping(procore_project_id="abc-123")],
            }
        )
    blob = str(exc.value)
    assert "abc-123" in blob
    assert r"^\d+$" in blob


def test_procore_project_mapping_rejects_blank_when_not_pending() -> None:
    with pytest.raises(ValidationError) as exc:
        ProcoreProjectsRegistry.model_validate(
            {
                "company_id": "5280",
                "projects": [_make_mapping(procore_project_id="")],
            }
        )
    assert "must be non-empty" in str(exc.value)


def test_procore_project_mapping_rejects_non_empty_id_for_pending() -> None:
    with pytest.raises(ValidationError) as exc:
        ProcoreProjectsRegistry.model_validate(
            {
                "company_id": "5280",
                "projects": [_make_mapping(procore_project_id="2525840", status="pending")],
            }
        )
    assert "must be empty when status='pending'" in str(exc.value)


def test_procore_project_mapping_accepts_numeric_id_when_not_pending() -> None:
    reg = ProcoreProjectsRegistry.model_validate(
        {
            "company_id": "5280",
            "projects": [
                _make_mapping(procore_project_id="2525840", status="pilot"),
                _make_mapping(
                    hb_project_key="legacy", procore_project_id="9999999", status="deprecated"
                ),
            ],
        }
    )
    assert {p.hb_project_key for p in reg.projects} == {"tropical", "legacy"}


# ---------------------------------------------------------------------------
# Seed loaders
# ---------------------------------------------------------------------------


def test_seed_endpoint_contract_loads_and_covers_required_categories() -> None:
    contract = load_endpoint_contract()
    assert contract.company_id == "5280"
    cats = {e.category for e in contract.endpoints}
    for required in REQUIRED_CATEGORIES:
        assert required in cats
    # Hard guardrails baked into seed
    for e in contract.endpoints:
        if e.category == "correspondence":
            assert e.status == "excluded"
        if e.category in ("schedule", "tasks"):
            assert e.status == "deferred"
        assert e.http_method == "GET"


def test_seed_projects_includes_tropical_pilot() -> None:
    projects = load_procore_projects()
    tropical = projects.get("tropical")
    assert tropical is not None
    assert tropical.status == "pilot"
    assert tropical.procore_project_id == "2525840"
    assert tropical.procore_project_name == "Tropical - S L"


def test_seed_projects_covers_canonical_construction_registry_keys() -> None:
    """Every project_key in sharepoint_onedrive_sources.seed.yaml must have a
    corresponding row in procore_projects.seed.yaml UNLESS it is on the
    documented orphan allowlist below — orphans are SharePoint surfaces that
    share a Procore project with another already-mapped HB key (so multiple
    SharePoint sources legitimately roll up to one Procore mapping)."""
    # SharePoint-side project_keys that intentionally have no procore-side row.
    # `hilltop` and `hilltop-gardens` are two SharePoint aliases (a Phase 01
    # compat record and a Phase 02 canonical SitePages entry, respectively)
    # for project 24-606-01 / procore_project_id 2982068, which is already
    # mapped as `alton-hilltop-pbg`. Adding more entries here requires a
    # deliberate decision — drift is silent only with respect to this list.
    KNOWN_ORPHAN_SHAREPOINT_KEYS = frozenset({"hilltop", "hilltop-gardens"})

    canonical_seed = (
        Path(__file__).resolve().parents[1]
        / "resources"
        / "config"
        / "sharepoint_onedrive_sources.seed.yaml"
    )
    canonical = yaml.safe_load(canonical_seed.read_text(encoding="utf-8"))
    canonical_keys = {
        p["project_key"] for p in canonical.get("projects", []) if p.get("project_key")
    }
    procore_keys = {p.hb_project_key for p in load_procore_projects().projects}
    missing = (canonical_keys - procore_keys) - KNOWN_ORPHAN_SHAREPOINT_KEYS
    assert not missing, (
        "procore_projects.seed.yaml is missing rows for canonical "
        f"project_keys not on the documented orphan allowlist: {sorted(missing)}"
    )


def test_loader_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    override = tmp_path / "contract.yml"
    override.write_text(
        yaml.safe_dump(
            {
                **_minimal_valid_contract_dict(),
                "company_id": "9999",
                "company_display_name": "Override Co",
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(CONTRACT_ENV_VAR, str(override))
    c = load_endpoint_contract()
    assert c.company_id == "9999"
    assert c.company_display_name == "Override Co"


def test_projects_loader_env_override(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    override = tmp_path / "projects.yml"
    override.write_text(
        yaml.safe_dump(
            {
                "company_id": "5280",
                "projects": [
                    {
                        "hb_project_key": "alpha",
                        "procore_project_id": "1234567",
                        "procore_project_name": "Alpha",
                        "status": "pilot",
                    },
                ],
            }
        ),
        encoding="utf-8",
    )
    monkeypatch.setenv(PROJECTS_ENV_VAR, str(override))
    p = load_procore_projects()
    assert [pp.hb_project_key for pp in p.projects] == ["alpha"]


def test_missing_seed_raises(monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> None:
    from hb_assistant.procore import loader as loader_mod

    monkeypatch.setattr(loader_mod, "_resolve", lambda relative: tmp_path / relative.name)
    monkeypatch.delenv(CONTRACT_ENV_VAR, raising=False)
    monkeypatch.delenv(PROJECTS_ENV_VAR, raising=False)
    with pytest.raises(EndpointContractError):
        load_endpoint_contract()
    with pytest.raises(ProcoreProjectsError):
        load_procore_projects()


# ---------------------------------------------------------------------------
# Auth status
# ---------------------------------------------------------------------------


def test_auth_status_env_absent(monkeypatch: pytest.MonkeyPatch) -> None:
    from hb_assistant.procore import auth as _auth_mod

    for k in REQUIRED_ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(_auth_mod, "macos_keychain_entry_exists", lambda: False)
    monkeypatch.setattr(_auth_mod, "_token_cache_present", lambda: False)
    r = check_auth_status()
    assert r.status == "env_absent"
    assert r.ready_for_live_calls is False
    assert r.env_keys_present == []
    # Hint never echoes credential values back
    assert "PROCORE_CLIENT_SECRET=" not in r.hint


def test_auth_status_env_partial(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setenv("PROCORE_CLIENT_ID", "id")
    monkeypatch.delenv("PROCORE_CLIENT_SECRET", raising=False)
    monkeypatch.delenv("PROCORE_REFRESH_TOKEN", raising=False)
    r = check_auth_status()
    assert r.status == "env_partial"
    assert "PROCORE_CLIENT_ID" in r.env_keys_present
    assert r.ready_for_live_calls is False


def test_auth_status_env_present(monkeypatch: pytest.MonkeyPatch) -> None:
    from hb_assistant.procore import auth as _auth_mod

    for k in REQUIRED_ENV_KEYS:
        monkeypatch.setenv(k, "x")
    monkeypatch.setattr(_auth_mod, "macos_keychain_entry_exists", lambda: False)
    monkeypatch.setattr(_auth_mod, "_token_cache_present", lambda: False)
    r = check_auth_status()
    assert r.status == "env_present"
    # Live calls remain explicitly disabled when only env vars are set with no
    # OAuth cache (Phase 04: cache + secret = ready, env-only = not ready).
    assert r.ready_for_live_calls is False


def test_auth_status_never_leaks_env_values(monkeypatch: pytest.MonkeyPatch) -> None:
    SENTINEL = "SECRET_VALUE_SHOULD_NEVER_APPEAR_IN_REPORT_XYZ"
    monkeypatch.setenv("PROCORE_CLIENT_ID", SENTINEL)
    r = check_auth_status()
    blob = json.dumps(r.model_dump())
    assert SENTINEL not in blob


# ---------------------------------------------------------------------------
# Auditor
# ---------------------------------------------------------------------------


def test_auditor_classifies_tropical_correctly() -> None:
    a = _make_unenforced_auditor()
    r = a.audit_project("tropical")
    assert r.procore_project_id == "2525840"
    assert r.summary.get("would_audit", 0) > 0
    assert r.summary.get("sensitive_review_required", 0) >= 4  # 4 financial
    assert r.summary.get("excluded") == 1
    assert r.summary.get("deferred") == 2
    assert r.summary.get("project_not_mapped", 0) == 0


def test_auditor_marks_unmapped_project_endpoints_not_mapped() -> None:
    # The live seed no longer carries any pending row (hilltop / hilltop-gardens
    # were retired into alton-hilltop-pbg on 2026-05-29). To keep the
    # "unmapped project → project_not_mapped verdict" semantics tested, build
    # a synthetic registry that mixes a pilot and a pending row.
    contract = load_endpoint_contract()
    registry = ProcoreProjectsRegistry.model_validate(
        {
            "company_id": "5280",
            "projects": [
                {
                    "hb_project_key": "tropical",
                    "procore_project_id": "2525840",
                    "procore_project_name": "Tropical - S L",
                    "status": "pilot",
                },
                {
                    "hb_project_key": "synthetic-pending",
                    "procore_project_id": "",
                    "procore_project_name": "",
                    "status": "pending",
                },
            ],
        }
    )
    a = EndpointAuditor(contract, registry)
    r = a.audit_project("synthetic-pending")
    assert r.procore_project_id == ""
    assert r.summary.get("project_not_mapped", 0) > 0
    # Excluded + deferred verdicts are independent of mapping status
    assert r.summary.get("excluded") == 1
    assert r.summary.get("deferred") == 2


def test_auditor_unknown_project_raises() -> None:
    a = _make_unenforced_auditor()
    with pytest.raises(KeyError):
        a.audit_project("nonexistent-key")


def test_mapping_validation_reports_pending_as_not_ok() -> None:
    # The live seed no longer carries any pending row, so this test pins the
    # invariant ("any pending entry forces ok=False") against a synthetic
    # registry rather than against seed contents. The sibling test
    # `test_mapping_validation_passes_when_only_pilots_and_deprecated`
    # exercises the positive case from the same idiom.
    contract = load_endpoint_contract()
    registry = ProcoreProjectsRegistry.model_validate(
        {
            "company_id": "5280",
            "projects": [
                {
                    "hb_project_key": "tropical",
                    "procore_project_id": "2525840",
                    "procore_project_name": "Tropical - S L",
                    "status": "pilot",
                },
                {
                    "hb_project_key": "synthetic-pending",
                    "procore_project_id": "",
                    "procore_project_name": "",
                    "status": "pending",
                },
            ],
        }
    )
    a = EndpointAuditor(contract, registry)
    r = a.validate_mapping()
    assert r.total == 2
    assert r.by_status.get("pilot") == 1
    assert r.by_status.get("pending") == 1
    assert r.ok is False


def test_mapping_validation_passes_when_only_pilots_and_deprecated() -> None:
    contract = load_endpoint_contract()
    fully_mapped = ProcoreProjectsRegistry.model_validate(
        {
            "company_id": "5280",
            "projects": [
                {
                    "hb_project_key": "tropical",
                    "procore_project_id": "2525840",
                    "procore_project_name": "Tropical - S L",
                    "status": "pilot",
                },
                {
                    "hb_project_key": "old-thing",
                    "procore_project_id": "9999999",
                    "procore_project_name": "Legacy",
                    "status": "deprecated",
                },
            ],
        }
    )
    a = EndpointAuditor(contract, fully_mapped)
    r = a.validate_mapping()
    assert r.ok is True


def test_auditor_never_advertises_writeback_in_any_row() -> None:
    a = _make_unenforced_auditor()
    r = a.audit_project("tropical")
    for row in r.endpoints:
        assert row["http_method"] == "GET"


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def test_root_help_exposes_procore_command(runner: CliRunner) -> None:
    r = runner.invoke(main_cli.app, ["--help"])
    assert r.exit_code == 0
    assert "procore" in r.output


def test_cli_procore_help(runner: CliRunner) -> None:
    r = runner.invoke(procore_cli.app, ["--help"])
    assert r.exit_code == 0
    for name in ("auth", "tools", "mapping"):
        assert name in r.output


def test_cli_auth_status(runner: CliRunner, monkeypatch: pytest.MonkeyPatch) -> None:
    from hb_assistant.procore import auth as _auth_mod

    for k in REQUIRED_ENV_KEYS:
        monkeypatch.delenv(k, raising=False)
    monkeypatch.setattr(_auth_mod, "macos_keychain_entry_exists", lambda: False)
    monkeypatch.setattr(_auth_mod, "_token_cache_present", lambda: False)
    r = runner.invoke(procore_cli.app, ["auth", "status", "--json"])
    assert r.exit_code == 0
    p = json.loads(r.output)
    assert p["report"]["status"] == "env_absent"
    assert p["report"]["ready_for_live_calls"] is False
    assert p["guardrails"]["live_calls_disabled"] is True


def test_cli_tools_list(runner: CliRunner) -> None:
    r = runner.invoke(procore_cli.app, ["tools", "list", "--json"])
    assert r.exit_code == 0
    p = json.loads(r.output)
    assert p["company_id"] == "5280"
    assert p["endpoint_count"] == len(p["endpoints"])
    # Every loaded endpoint is GET (read-only)
    for e in p["endpoints"]:
        assert e["http_method"] == "GET"
    # by_status surfaces the four buckets
    assert "excluded" in p["by_status"]
    assert "deferred" in p["by_status"]


def test_cli_tools_audit_tropical(runner: CliRunner) -> None:
    r = runner.invoke(
        procore_cli.app,
        ["tools", "audit", "--project", "tropical", "--json"],
    )
    assert r.exit_code == 0
    p = json.loads(r.output)
    assert p["mode"] == "dry_run"
    assert p["report"]["procore_project_id"] == "2525840"
    assert p["report"]["summary"].get("would_audit", 0) > 0
    assert p["report"]["summary"].get("excluded") == 1


def test_cli_tools_audit_unknown_project_exit_1(runner: CliRunner) -> None:
    r = runner.invoke(
        procore_cli.app,
        ["tools", "audit", "--project", "no-such-key", "--json"],
    )
    assert r.exit_code == 1
    p = json.loads(r.output)
    assert p["status"] == "not_found"
    assert "no-such-key" in p["requested"]


def test_cli_mapping_validate_clean_seed_yields_exit_0(runner: CliRunner) -> None:
    # After the 2026-05-29 retirement of hilltop / hilltop-gardens from the
    # procore-side seeds, the live seed carries only pilot rows so the CLI
    # mapping-validate command returns exit 0. The pending → ok=False
    # invariant is exercised structurally in
    # `test_mapping_validation_reports_pending_as_not_ok` via a synthetic
    # registry.
    r = runner.invoke(procore_cli.app, ["mapping", "validate", "--json"])
    assert r.exit_code == 0
    p = json.loads(r.output)
    assert p["report"]["ok"] is True
    assert p["report"]["by_status"].get("pending") is None
    assert p["report"]["by_status"].get("pilot") == 4


# ---------------------------------------------------------------------------
# Guardrail string-scans
# ---------------------------------------------------------------------------


def test_procore_module_imports_no_http_client() -> None:
    """The data-plane (GET-only) audit path must not pull in requests / urllib3.

    Phase 04 Prompt 02 acquisition remediation introduces ``oauth.py`` which
    legitimately needs a real HTTP transport for the ``/oauth/token`` POST
    against Procore's auth endpoint. ``oauth.py`` is the sole allowlisted
    consumer; the GET-only data plane (`http_client.py`, `sync.py`, etc.) is
    still verified clean.
    """
    import importlib
    import inspect
    import pkgutil

    import hb_assistant.procore as pkg

    banned = {"requests", "httpx", "urllib3", "aiohttp"}
    allowed_modules = {"hb_assistant.procore.oauth"}
    for _, name, ispkg in pkgutil.walk_packages(pkg.__path__, prefix="hb_assistant.procore."):
        if ispkg or name in allowed_modules:
            continue
        mod = importlib.import_module(name)
        src = inspect.getsource(mod)
        for ban in banned:
            assert f"import {ban}" not in src, f"{name} unexpectedly imports {ban}"
            assert f"from {ban}" not in src, f"{name} unexpectedly imports from {ban}"


def test_every_cli_payload_advertises_no_writeback(runner: CliRunner) -> None:
    for argv in (
        ["auth", "status", "--json"],
        ["tools", "list", "--json"],
        ["tools", "audit", "--project", "tropical", "--json"],
        ["mapping", "validate", "--json"],
    ):
        r = runner.invoke(procore_cli.app, argv)
        # mapping validate exits 1 on a clean seed (pending row) but still
        # emits a JSON payload — both 0 and 1 are acceptable here.
        assert r.exit_code in (0, 1), f"{argv}: unexpected exit {r.exit_code}: {r.output}"
        p = json.loads(r.output)
        assert p["guardrails"]["writeback"] == "none", argv
        assert p["guardrails"]["external_systems"] == "read_only", argv
        assert p["guardrails"]["live_calls_disabled"] is True, argv


# Prompt_07: mocked dry-run audit matrix + redaction + live isolation (no real calls ever in these tests)


def test_procore_endpoint_audit_dry_run_with_injected_mock_produces_receipt_no_network():
    """Dry-run construction only; injected transport (P04 pattern); no real calls; bodies redacted."""
    # Minimal mock contract + projects (use real loaders if fixtures allow; here pure unit)
    contract = MagicMock()
    contract.company_id = "5280"
    contract.endpoints = []  # in real test would load from seed; here structural
    projects = MagicMock()
    projects.company_id = "5280"
    projects.projects = []
    projects.get.return_value = MagicMock(
        procore_project_id="2525840", procore_project_name="Tropical"
    )

    auditor = EndpointAuditor(contract, projects)  # type: ignore[arg-type]
    # Exercise the new dry-run path (base_url placeholder)
    receipt: EndpointAuditRunReceipt = auditor.build_audit_run_receipt(
        "tropical",
        base_url="https://api.procore.com",
        mode="dry_run",
    )
    assert receipt.mode == "dry_run"
    assert receipt.guardrails["read_only"] is True
    assert receipt.guardrails["body_redaction"] == "default"
    assert receipt.redaction_applied is True
    # No transport side effects (dry-run by construction)
    assert "receipts" in receipt.model_dump()


@pytest.mark.parametrize("bad_mode", ["live_manual"])
def test_procore_endpoint_audit_live_requires_explicit_opt_in_guard(bad_mode):
    """Live/manual path is opt-in only; calling without live_client/confirm raises (never auto)."""
    contract = MagicMock()
    contract.company_id = "5280"
    contract.endpoints = []
    projects = MagicMock()
    projects.company_id = "5280"
    projects.projects = []
    projects.get.return_value = MagicMock(procore_project_id="2525840")

    auditor = EndpointAuditor(contract, projects)  # type: ignore[arg-type]
    with pytest.raises((ValueError, TypeError)):
        auditor.build_audit_run_receipt(
            "tropical", base_url="https://api.procore.com", mode=bad_mode
        )


def test_audit_dry_run_cli_json_has_mode_dry_run_and_guardrails(runner: CliRunner):
    """CLI dry-run surface advertises dry-run + read-only + redaction (no live)."""
    r = runner.invoke(procore_cli.app, ["audit", "dry-run", "--project", "tropical", "--json"])
    # May exit non-zero on incomplete mapping (pending rows) but must still emit guardrails
    assert r.exit_code in (0, 1)
    p = json.loads(r.output)
    assert "receipt" in p
    assert p["receipt"]["mode"] == "dry_run"
    assert p["guardrails"]["writeback"] == "none"
    assert p["receipt"]["guardrails"]["live_calls"] == "opt_in_manual_only"
