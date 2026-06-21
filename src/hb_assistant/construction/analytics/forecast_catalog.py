"""Read-only forecast package catalog service (Implementation Phase 1).

Browses deterministic forecast packages that the construction-financial-review backend
has already written to disk as ``<name>_<project_key>_<stamp>/`` directories. This
service performs **pure file reads only**: zero DB access, zero writes, no live-endpoint
calls, no shelling out.

Hard guarantees (plan corrections #4 and #5):
  - **Fail closed:** it scans only an explicit, non-empty list of absolute, existing
    package-root directories passed at construction. There is NO implicit/home/filesystem
    default. Bad input raises rather than returning a silent empty result.
  - **Structural redaction:** every payload is built from ``forecast_dto`` DTOs that omit
    paths, raw stamps, directory names, CLI commands, and module names.

All public methods return a JSON-safe dict carrying ``surface`` + ``guardrails``, matching
the existing analytics service convention.
"""

from __future__ import annotations

import hashlib
import json
import os
import re
from pathlib import Path
from typing import Any

from hb_assistant.construction.analytics.forecast_dto import (
    TYPE_LABELS,
    ForecastRowDTO,
    ManifestDTO,
    ManifestFileDTO,
    MonthlyForecastRowDTO,
    MonthlyPointDTO,
    PackageDTO,
    PackageSummaryDTO,
    PeriodDTO,
    ProbabilityRowDTO,
    ProjectDTO,
    ReviewItemDTO,
    RiskRegisterRowDTO,
    TopRiskDTO,
    ValidationDTO,
    friendly_datetime_from_stamp,
)

_STAMP_RE = re.compile(r"_(\d{8}_\d{6})$")

# Directory-name prefix (before _<project_key>[_<variant>]_<stamp>) -> business type slug.
# Longest prefixes first so e.g. forecast_accuracy_next_package wins over forecast_accuracy_package.
_TYPE_PREFIXES: tuple[tuple[str, str], ...] = (
    ("forecast_accuracy_next_package", "accuracy_next"),
    ("forecast_comprehensive_package", "comprehensive"),
    ("forecast_history_informed_package", "history_informed"),
    ("forecast_model_controls_package", "model_controls"),
    ("forecast_cost_frequency_package", "cost_frequency"),
    ("forecast_staffing_plan_package", "staffing_plan"),
    ("schedule_integrated_forecast_package", "schedule_integrated"),
    ("actuals_erp_crosscheck_package", "actuals_erp_crosscheck"),
    ("forecast_probability_package", "probability"),
    ("forecast_intelligence_package", "intelligence"),
    ("mapping_discrepancy_workpaper", "mapping_workpaper"),
    ("cost_forecast_agent_db_json_export", "db_json_export"),
    ("forecast_accuracy_package", "accuracy"),
    ("forecast_controls_package", "controls"),
    ("forecast_analysis_package", "analysis"),
    ("forecast_context_package", "context"),
    ("forecast_monthly_package", "monthly"),
)

# Per-discovery candidate files for business rows / review items (first present wins).
_ROWS_CANDIDATES: tuple[str, ...] = (
    "integrated_final_cost_recommendations.jsonl",
    "integrated_forecast_by_budget_code.jsonl",
    "eac_estimates_by_budget_code.jsonl",
)
_REVIEW_CANDIDATES: tuple[str, ...] = (
    "integrated_human_review_queue.jsonl",
    "forecast_accuracy_recommendations.jsonl",
)
_SUMMARY_CANDIDATES: tuple[str, ...] = (
    "project_comprehensive_forecast_summary.json",
    "project_forecast_accuracy_summary.json",
)

# Phase 5 review-surface source files (present in comprehensive packages; a subset elsewhere).
_MONTHLY_BY_CODE_FILE = "integrated_monthly_forecast_by_budget_code.jsonl"
_MONTHLY_PROJECT_FILE = "integrated_monthly_project_forecast.jsonl"
_PROBABILITY_FILE = "integrated_probability_by_budget_code.jsonl"
_RISK_REGISTER_FILE = "integrated_risk_register.jsonl"
_TOP_RISKS_FILE = "top_overrun_risks.json"

_SURFACE = "analytics.forecast_catalog"
_MAX_ROWS = 2000  # defensive cap so a huge JSONL can't blow up a response

# Explicit, opt-in configuration of the package roots to scan. No implicit default.
ENV_PACKAGE_ROOTS = "HB_FORECAST_PACKAGE_ROOTS"


def resolve_package_roots_from_env() -> list[str]:
    """Return the explicitly configured package roots, or [] if unset (fail closed upstream)."""
    raw = os.environ.get(ENV_PACKAGE_ROOTS, "")
    return [p for p in (part.strip() for part in raw.split(os.pathsep)) if p]


class ForecastCatalogError(RuntimeError):
    """Raised when the catalog is misconfigured (fail closed) or an id collides."""


def _guardrails() -> dict[str, Any]:
    return {
        "read_only": True,
        "local_first": True,
        "no_cli_shellout": True,
        "no_live_endpoint_calls": True,
        "no_external_writeback": True,
        "no_db_access": True,
    }


def _humanize_check(name: str) -> str:
    return name.replace("_", " ").strip().capitalize()


def _file_kind(name: str) -> str:
    low = name.lower()
    for ext in ("jsonl", "json", "csv", "md"):
        if low.endswith("." + ext):
            return ext
    return "other"


class _PackageRef:
    """Internal, never-serialized record. Holds the raw path/stamp the DTOs must hide."""

    __slots__ = (
        "package_id",
        "path",
        "dir_name",
        "type_slug",
        "stamp",
        "project_key",
        "period",
        "project_name",
        "job_reference",
        "manifest_ok",
        "manifest",
    )

    def __init__(self, package_id: str, path: Path, dir_name: str, type_slug: str | None, stamp: str | None):
        self.package_id = package_id
        self.path = path
        self.dir_name = dir_name
        self.type_slug = type_slug
        self.stamp = stamp
        self.project_key: str | None = None
        self.period: str | None = None
        self.project_name: str | None = None
        self.job_reference: str | None = None
        self.manifest_ok = False
        self.manifest: dict[str, Any] | None = None


class ForecastCatalogService:
    """Read-only browser over forecast package directories under explicit roots."""

    def __init__(self, package_roots: list[str | Path] | None = None, db_path: str | None = None) -> None:
        # db_path is accepted for constructor parity with sibling analytics services but is
        # intentionally UNUSED in Phase 1 — the catalog never touches the DB.
        self.db_path = db_path
        self._roots = self._validate_roots(package_roots)
        self._index: dict[str, _PackageRef] | None = None

    # -- construction / fail-closed validation --------------------------------

    @staticmethod
    def _validate_roots(package_roots: list[str | Path] | None) -> list[Path]:
        if not package_roots:
            raise ForecastCatalogError(
                "package_roots must be a non-empty list of absolute package-root directories "
                "(fail closed: there is no implicit default root)."
            )
        roots: list[Path] = []
        seen: set[str] = set()
        for raw in package_roots:
            p = Path(raw)
            if not p.is_absolute():
                raise ForecastCatalogError(f"package root must be an absolute path: {raw!r}")
            if not p.exists():
                raise ForecastCatalogError(f"package root does not exist: {p}")
            if not p.is_dir():
                raise ForecastCatalogError(f"package root is not a directory: {p}")
            key = str(p.resolve())
            if key not in seen:
                seen.add(key)
                roots.append(p)
        return roots

    # -- discovery / indexing -------------------------------------------------

    @staticmethod
    def _parse_dir_name(dir_name: str) -> tuple[str | None, str | None]:
        """Return (type_slug, stamp) from a package dir name, or (None, None) if not a package."""
        m = _STAMP_RE.search(dir_name)
        if not m:
            return None, None
        stamp = m.group(1)
        head = dir_name[: m.start()]
        for prefix, slug in _TYPE_PREFIXES:
            if head == prefix or head.startswith(prefix + "_"):
                return slug, stamp
        return None, stamp  # has a stamp but unknown type -> unsupported

    def _read_json(self, path: Path) -> dict[str, Any] | None:
        try:
            with path.open("r", encoding="utf-8") as fh:
                data = json.load(fh)
            return data if isinstance(data, dict) else None
        except (OSError, ValueError, UnicodeDecodeError):
            return None

    def _dirname_project_fallback(self, ref: _PackageRef) -> str | None:
        """Recover the project_key token from the dir name so packages stay attributable."""
        if not ref.stamp:
            return None
        head = ref.dir_name[: ref.dir_name.rfind("_" + ref.stamp)]
        for prefix, _slug in _TYPE_PREFIXES:
            if head.startswith(prefix + "_"):
                rest = head[len(prefix) + 1 :]
                return rest.split("_")[0] or None
        return None

    def _hydrate_manifest(self, ref: _PackageRef) -> None:
        manifest = self._read_json(ref.path / "manifest.json")
        if manifest is None:
            ref.manifest_ok = False
        else:
            ref.manifest = manifest
            ref.manifest_ok = True
            proj = manifest.get("project")
            if isinstance(proj, dict):
                gen = manifest.get("generation")
                gen_key = gen.get("project_key") if isinstance(gen, dict) else None
                ref.project_key = proj.get("project_key") or gen_key
                ref.project_name = proj.get("project_name")
                ref.job_reference = proj.get("job_reference")
                ref.period = proj.get("forecast_period")
        # Whenever the manifest did not yield a project_key (missing or no project block),
        # fall back to the dir-name token so the package remains attributable + listable.
        if not ref.project_key:
            ref.project_key = self._dirname_project_fallback(ref)

    def _build_index(self) -> dict[str, _PackageRef]:
        if self._index is not None:
            return self._index
        index: dict[str, _PackageRef] = {}
        for root in self._roots:
            root_key = str(root.resolve())
            try:
                children = sorted(p for p in root.iterdir() if p.is_dir())
            except OSError:
                continue
            for child in children:
                dir_name = child.name
                type_slug, stamp = self._parse_dir_name(dir_name)
                if stamp is None:
                    continue  # not a package directory at all
                pid = hashlib.sha256(f"{root_key}::{dir_name}".encode("utf-8")).hexdigest()[:16]
                if pid in index:
                    raise ForecastCatalogError(
                        f"package_id collision for id {pid!r}; refusing to silently overwrite a package."
                    )
                ref = _PackageRef(pid, child, dir_name, type_slug, stamp)
                self._hydrate_manifest(ref)
                index[pid] = ref
        self._index = index
        return index

    # -- DTO builders ---------------------------------------------------------

    def _status_for(self, ref: _PackageRef) -> tuple[str, ValidationDTO]:
        if ref.type_slug is None:
            return "unsupported", ValidationDTO(ref.package_id, "unsupported", 0, 0, 0, [])
        report = self._read_json(ref.path / "validation_report.json")
        checks = report.get("checks") if isinstance(report, dict) else None
        if not isinstance(checks, dict) or not checks:
            status = "invalid" if not ref.manifest_ok else "unknown"
            return status, ValidationDTO(ref.package_id, status, 0, 0, 0, [])
        total = len(checks)
        failed_names = [k for k, v in checks.items() if v is not True]
        passed = total - len(failed_names)
        status = "validated" if not failed_names else "attention"
        return status, ValidationDTO(
            ref.package_id,
            status,
            total,
            passed,
            len(failed_names),
            [_humanize_check(n) for n in failed_names[:50]],
        )

    def _display_label(self, ref: _PackageRef) -> str:
        type_label = TYPE_LABELS.get(ref.type_slug or "", "Unrecognized package")
        friendly = friendly_datetime_from_stamp(ref.stamp)
        return f"{type_label} — {friendly}" if friendly else type_label

    def _package_dto(self, ref: _PackageRef) -> PackageDTO:
        status, validation = self._status_for(ref)
        output_files = []
        if ref.manifest and isinstance(ref.manifest.get("output_files"), list):
            output_files = ref.manifest["output_files"]
        return PackageDTO(
            package_id=ref.package_id,
            package_type=ref.type_slug or "unsupported",
            display_label=self._display_label(ref),
            status=status,
            project_key=ref.project_key,
            period=ref.period,
            job_reference=ref.job_reference,
            generated_display=friendly_datetime_from_stamp(ref.stamp),
            validation_total=validation.total_checks,
            validation_passed=validation.passed,
            validation_failed=validation.failed,
            output_file_count=len(output_files),
        )

    def _require(self, package_id: str) -> _PackageRef:
        ref = self._build_index().get(package_id)
        if ref is None:
            raise ForecastCatalogError(f"unknown package_id: {package_id!r}")
        return ref

    def _read_jsonl(self, path: Path, limit: int) -> tuple[list[dict[str, Any]], int]:
        """Defensively read up to ``limit`` JSON objects; return (rows, skipped_count)."""
        rows: list[dict[str, Any]] = []
        skipped = 0
        try:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                for line in fh:
                    if len(rows) >= limit:
                        break
                    line = line.strip()
                    if not line:
                        continue
                    try:
                        obj = json.loads(line)
                    except ValueError:
                        skipped += 1
                        continue
                    if isinstance(obj, dict):
                        rows.append(obj)
                    else:
                        skipped += 1
        except OSError:
            return [], 0
        return rows, skipped

    # -- public API (each returns surface + guardrails) -----------------------

    def list_projects(self) -> dict[str, Any]:
        index = self._build_index()
        projects: dict[str, ProjectDTO] = {}
        for ref in index.values():
            if not ref.project_key:
                continue
            if ref.project_key not in projects:
                projects[ref.project_key] = ProjectDTO(
                    project_key=ref.project_key,
                    project_name=ref.project_name,
                    job_reference=ref.job_reference,
                )
        return {
            "surface": _SURFACE + ".projects",
            "projects": [projects[k].public() for k in sorted(projects)],
            "guardrails": _guardrails(),
        }

    def list_periods(self, project_key: str) -> dict[str, Any]:
        index = self._build_index()
        counts: dict[str, int] = {}
        for ref in index.values():
            if ref.project_key == project_key and ref.period:
                counts[ref.period] = counts.get(ref.period, 0) + 1
        periods = [PeriodDTO(period=p, package_count=counts[p]) for p in sorted(counts, reverse=True)]
        return {
            "surface": _SURFACE + ".periods",
            "project_key": project_key,
            "periods": [p.public() for p in periods],
            "guardrails": _guardrails(),
        }

    def list_packages(self, project_key: str, period: str | None = None) -> dict[str, Any]:
        index = self._build_index()
        matches: list[_PackageRef] = []
        invalid = 0
        unsupported = 0
        for ref in index.values():
            if ref.project_key != project_key:
                continue
            if period is not None and ref.period != period:
                continue
            if ref.type_slug is None:
                unsupported += 1
            elif not ref.manifest_ok:
                invalid += 1
            matches.append(ref)
        # newest first by raw stamp (internal sort key; never emitted)
        matches.sort(key=lambda r: r.stamp or "", reverse=True)
        return {
            "surface": _SURFACE + ".packages",
            "project_key": project_key,
            "period": period,
            "packages": [self._package_dto(r).public() for r in matches],
            "invalid_count": invalid,
            "unsupported_count": unsupported,
            "guardrails": _guardrails(),
        }

    def read_package_summary(self, package_id: str) -> dict[str, Any]:
        ref = self._require(package_id)
        status, _ = self._status_for(ref)
        headline: dict[str, Any] = {}
        for cand in _SUMMARY_CANDIDATES:
            data = self._read_json(ref.path / cand)
            if data:
                for k in (
                    "canonical_codes_covered",
                    "integrated_final_cost_recommendations",
                    "integrated_monthly_rows",
                    "integrated_probability_rows",
                    "human_review_items",
                    "evidence_conflicts",
                    "packages_consumed",
                    "packages_missing",
                ):
                    if k in data and not isinstance(data[k], (dict,)):
                        headline[k] = data[k]
                break
        dto = PackageSummaryDTO(
            package_id=ref.package_id,
            package_type=ref.type_slug or "unsupported",
            display_label=self._display_label(ref),
            project_key=ref.project_key,
            period=ref.period,
            job_reference=ref.job_reference,
            generated_display=friendly_datetime_from_stamp(ref.stamp),
            status=status,
            headline=headline,
        )
        return {"surface": _SURFACE + ".summary", **dto.public(), "guardrails": _guardrails()}

    def read_validation_status(self, package_id: str) -> dict[str, Any]:
        ref = self._require(package_id)
        _, validation = self._status_for(ref)
        return {"surface": _SURFACE + ".validation", **validation.public(), "guardrails": _guardrails()}

    def read_manifest(self, package_id: str) -> dict[str, Any]:
        ref = self._require(package_id)
        files: list[ManifestFileDTO] = []
        if ref.manifest and isinstance(ref.manifest.get("output_files"), list):
            for entry in ref.manifest["output_files"]:
                if not isinstance(entry, dict):
                    continue
                raw_path = str(entry.get("path") or "")
                base = raw_path.rsplit("/", 1)[-1]  # basename only — strip any directory segment
                if not base:
                    continue
                files.append(
                    ManifestFileDTO(
                        file_name=base,
                        kind=_file_kind(base),
                        row_count=entry.get("row_count") if isinstance(entry.get("row_count"), int) else None,
                        size_bytes=entry.get("size_bytes") if isinstance(entry.get("size_bytes"), int) else None,
                    )
                )
        manifest_version = None
        if ref.manifest:
            mv = ref.manifest.get("manifest_version")
            manifest_version = str(mv) if mv is not None else None
        dto = ManifestDTO(
            package_id=ref.package_id,
            package_type=ref.type_slug or "unsupported",
            display_label=self._display_label(ref),
            project_key=ref.project_key,
            period=ref.period,
            job_reference=ref.job_reference,
            generated_display=friendly_datetime_from_stamp(ref.stamp),
            manifest_version=manifest_version,
            output_file_count=len(files),
            files=files,
        )
        return {"surface": _SURFACE + ".manifest", **dto.public(), "guardrails": _guardrails()}

    def read_forecast_rows(self, package_id: str) -> dict[str, Any]:
        ref = self._require(package_id)
        rows: list[ForecastRowDTO] = []
        source_present = False
        truncated = False
        for cand in _ROWS_CANDIDATES:
            path = ref.path / cand
            if not path.exists():
                continue
            source_present = True
            raw, _skipped = self._read_jsonl(path, _MAX_ROWS)
            truncated = len(raw) >= _MAX_ROWS
            for r in raw:
                rows.append(
                    ForecastRowDTO(
                        cost_code=r.get("cost_code"),
                        budget_code_key=r.get("budget_code_key"),
                        recommended_final_cost=(
                            r.get("accepted_recommended_final_cost")
                            or r.get("integrated_recommended_final_cost")
                            or r.get("recommended_final_cost")
                            or r.get("independent_eac")
                        ),
                        cost_to_complete=(
                            r.get("integrated_cost_to_complete") or r.get("cost_to_complete")
                        ),
                        change_amount=r.get("change_amount"),
                        requires_human_acceptance=r.get("requires_human_acceptance"),
                        acceptance_status=r.get("acceptance_status"),
                    )
                )
            break
        return {
            "surface": _SURFACE + ".forecast_rows",
            "package_id": ref.package_id,
            "rows_available": source_present,
            "row_count": len(rows),
            "truncated": truncated,
            "rows": [r.public() for r in rows],
            "guardrails": _guardrails(),
        }

    def read_review_items(self, package_id: str) -> dict[str, Any]:
        ref = self._require(package_id)
        items: list[ReviewItemDTO] = []
        source_present = False
        for cand in _REVIEW_CANDIDATES:
            path = ref.path / cand
            if not path.exists():
                continue
            source_present = True
            raw, _skipped = self._read_jsonl(path, _MAX_ROWS)
            for r in raw:
                items.append(
                    ReviewItemDTO(
                        cost_code=r.get("cost_code"),
                        budget_code_key=r.get("budget_code_key"),
                        review_priority=r.get("review_priority"),
                        review_reason=r.get("review_reason"),
                        acceptance_status=r.get("acceptance_status"),
                    )
                )
            break
        return {
            "surface": _SURFACE + ".review_items",
            "package_id": ref.package_id,
            "items_available": source_present,
            "item_count": len(items),
            "items": [i.public() for i in items],
            "guardrails": _guardrails(),
        }

    # -- Phase 5 review surfaces (read-only) ----------------------------------

    def _read_json_list(self, path: Path, limit: int) -> list[dict[str, Any]]:
        """Read a JSON array of objects (defensively capped); [] on absence/parse error."""
        try:
            with path.open("r", encoding="utf-8", errors="replace") as fh:
                data = json.load(fh)
        except (OSError, ValueError, UnicodeDecodeError):
            return []
        if not isinstance(data, list):
            return []
        return [obj for obj in data[:limit] if isinstance(obj, dict)]

    @staticmethod
    def _money(row: dict[str, Any], *keys: str) -> str | None:
        for k in keys:
            v = row.get(k)
            if v is not None:
                return str(v)
        return None

    def read_monthly_forecast(self, package_id: str) -> dict[str, Any]:
        ref = self._require(package_id)
        rows: list[MonthlyForecastRowDTO] = []
        by_code = ref.path / _MONTHLY_BY_CODE_FILE
        source_present = by_code.exists()
        truncated = False
        if source_present:
            raw, _skipped = self._read_jsonl(by_code, _MAX_ROWS)
            truncated = len(raw) >= _MAX_ROWS
            for r in raw:
                mc = r.get("monthly_costs")
                points: list[MonthlyPointDTO] = []
                if isinstance(mc, list):
                    for m in mc:
                        if isinstance(m, dict):
                            points.append(
                                MonthlyPointDTO(
                                    forecast_month=m.get("forecast_month"),
                                    amount=self._money(m, "integrated_month_cost", "amount"),
                                )
                            )
                rows.append(
                    MonthlyForecastRowDTO(
                        cost_code=r.get("cost_code"),
                        budget_code_key=r.get("budget_code_key"),
                        cost_to_complete=self._money(r, "integrated_cost_to_complete", "cost_to_complete"),
                        months=points,
                    )
                )
        # Project-level monthly trend (small; one point per month).
        project_monthly: list[dict[str, Any]] = []
        proj_path = ref.path / _MONTHLY_PROJECT_FILE
        if proj_path.exists():
            praw, _ = self._read_jsonl(proj_path, _MAX_ROWS)
            for p in praw:
                project_monthly.append(
                    MonthlyPointDTO(
                        forecast_month=p.get("forecast_month"),
                        amount=self._money(p, "integrated_month_cost", "amount"),
                    ).public()
                )
        return {
            "surface": _SURFACE + ".monthly",
            "package_id": ref.package_id,
            "monthly_available": source_present,
            "row_count": len(rows),
            "truncated": truncated,
            "project_monthly": project_monthly,
            "rows": [r.public() for r in rows],
            "guardrails": _guardrails(),
        }

    def read_probability(self, package_id: str) -> dict[str, Any]:
        ref = self._require(package_id)
        path = ref.path / _PROBABILITY_FILE
        source_present = path.exists()
        rows: list[ProbabilityRowDTO] = []
        truncated = False
        if source_present:
            raw, _ = self._read_jsonl(path, _MAX_ROWS)
            truncated = len(raw) >= _MAX_ROWS
            for r in raw:
                rows.append(
                    ProbabilityRowDTO(
                        cost_code=r.get("cost_code"),
                        budget_code_key=r.get("budget_code_key"),
                        actual_cost_to_date=self._money(r, "actual_cost_to_date"),
                        p10=self._money(r, "integrated_p10"),
                        p50=self._money(r, "integrated_p50"),
                        p80=self._money(r, "integrated_p80"),
                        p90=self._money(r, "integrated_p90"),
                        p95=self._money(r, "integrated_p95"),
                    )
                )
        return {
            "surface": _SURFACE + ".probability",
            "package_id": ref.package_id,
            "probability_available": source_present,
            "row_count": len(rows),
            "truncated": truncated,
            "rows": [r.public() for r in rows],
            "guardrails": _guardrails(),
        }

    def read_risk_register(self, package_id: str) -> dict[str, Any]:
        ref = self._require(package_id)
        path = ref.path / _RISK_REGISTER_FILE
        source_present = path.exists()
        rows: list[RiskRegisterRowDTO] = []
        truncated = False
        if source_present:
            raw, _ = self._read_jsonl(path, _MAX_ROWS)
            truncated = len(raw) >= _MAX_ROWS
            for r in raw:
                cc = r.get("conflict_count")
                rows.append(
                    RiskRegisterRowDTO(
                        cost_code=r.get("cost_code"),
                        budget_code_key=r.get("budget_code_key"),
                        recommended_final_cost=self._money(r, "integrated_recommended_final_cost"),
                        variance_amount=self._money(r, "integrated_minus_accepted_final_cost"),
                        conflict_count=cc if isinstance(cc, int) else None,
                        max_conflict_severity=r.get("max_conflict_severity"),
                        review_priority=r.get("review_priority"),
                    )
                )
        return {
            "surface": _SURFACE + ".risk_register",
            "package_id": ref.package_id,
            "risk_register_available": source_present,
            "row_count": len(rows),
            "truncated": truncated,
            "rows": [r.public() for r in rows],
            "guardrails": _guardrails(),
        }

    def read_top_risks(self, package_id: str) -> dict[str, Any]:
        ref = self._require(package_id)
        path = ref.path / _TOP_RISKS_FILE
        source_present = path.exists()
        rows: list[TopRiskDTO] = []
        if source_present:
            for r in self._read_json_list(path, _MAX_ROWS):
                rows.append(
                    TopRiskDTO(
                        cost_code=r.get("cost_code"),
                        budget_code_key=r.get("budget_code_key"),
                        recommended_final_cost=self._money(r, "integrated_recommended_final_cost"),
                        overrun_amount=self._money(r, "integrated_minus_accepted_final_cost"),
                        direction=r.get("integrated_direction"),
                    )
                )
        return {
            "surface": _SURFACE + ".top_risks",
            "package_id": ref.package_id,
            "top_risks_available": source_present,
            "row_count": len(rows),
            "rows": [r.public() for r in rows],
            "guardrails": _guardrails(),
        }
