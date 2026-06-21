"""External-forecast evaluation orchestrator (Implementation Phase 4).

Composes ingest -> mapping -> comparison -> anomaly into a single deterministic evaluation that
(a) writes an evidence package to an isolated per-run directory under the eval-root and (b)
projects the result rows into an isolated per-run SQLite (the v61 schema only) — never the live
DB, never the live data root, never an LLM, no network. Reads are read-only: the v59 baseline DB
is opened ``mode=ro`` and the backend forecast package is read off disk.

Run records persist a redacted summary for ``list_evaluations``/``read_evaluation`` and the
external-by-code map so a later evaluation can use this one as its ``prior_external`` baseline.
"""

from __future__ import annotations

import csv
import hashlib
import json
import sqlite3
import uuid
from datetime import datetime
from decimal import Decimal
from pathlib import Path
from typing import Any

from hb_assistant.construction.analytics import forecast_external_anomaly as anomaly
from hb_assistant.construction.analytics.forecast_external_compare import (
    ForecastExternalCompareService,
    external_value_by_code,
)
from hb_assistant.construction.analytics.forecast_external_dto import (
    BASELINE_LABELS,
    AccuracyRowDTO,
    AnomalyFindingDTO,
    ComparisonRowDTO,
    EvaluationListItemDTO,
    EvaluationSummaryDTO,
    ReviewItemDTO,
    eval_label,
)
from hb_assistant.construction.analytics.forecast_external_ingest import (
    ForecastExternalError,
    ForecastExternalIngestService,
    resolve_eval_root,
)
from hb_assistant.construction.analytics.forecast_external_mapping import (
    ForecastExternalMappingService,
)
from hb_assistant.forecasting.project_eligibility import (
    assert_eval_project_eligible,
    load_eval_project_allowlist,
)
from hb_assistant.store.migrator import SQLiteMigrator

_SURFACE = "analytics.forecast_external"
_EVALS_DIRNAME = "evaluations"
_EVAL_RECORD = "eval_record.json"
_EVAL_DB = "eval.sqlite"
_DEFAULT_PROJECT = "tropical"
_COMPREHENSIVE_PREFIX = "forecast_comprehensive_package_"


def _guardrails() -> dict[str, Any]:
    return {
        "writes_isolated_eval_root": True,
        "no_live_db_write": True,
        "no_live_data_root_write": True,
        "no_llm": True,
        "no_live_endpoint_calls": True,
        "local_first": True,
    }


class ForecastExternalEvalService:
    """Runs and lists external-forecast evaluations confined to the isolated eval-root."""

    def __init__(
        self,
        eval_root: str | None = None,
        db_path: str | None = None,
        package_roots: list[str] | None = None,
    ) -> None:
        self._eval_root_override = eval_root
        self._db_path_override = db_path
        self._package_roots = package_roots
        self._ingest = ForecastExternalIngestService(eval_root=eval_root)
        self._mapping = ForecastExternalMappingService(eval_root=eval_root, db_path=db_path)
        self._compare = ForecastExternalCompareService(db_path=db_path)

    # -- config ---------------------------------------------------------------

    def _eval_root(self) -> Path:
        return resolve_eval_root(self._eval_root_override)

    def _evals_root(self) -> Path:
        root = self._eval_root() / _EVALS_DIRNAME
        root.mkdir(parents=True, exist_ok=True)
        return root

    def _resolve_model_package(self, explicit: str | None) -> Path | None:
        if explicit:
            p = Path(explicit)
            return p if p.is_dir() else None
        # Auto-select the newest comprehensive backend package from the configured package roots.
        newest: Path | None = None
        for root in self._iter_package_roots():
            try:
                children = [c for c in root.iterdir() if c.is_dir()]
            except OSError:
                continue
            for c in children:
                if c.name.startswith(_COMPREHENSIVE_PREFIX) and (
                    newest is None or c.name > newest.name
                ):
                    newest = c
        return newest

    def _iter_package_roots(self) -> list[Path]:
        import os

        raw = self._package_roots or [
            r for r in (os.environ.get("HB_FORECAST_PACKAGE_ROOTS") or "").split(os.pathsep) if r
        ]
        return [Path(r) for r in raw if r and Path(r).is_dir()]

    # -- public API -----------------------------------------------------------

    def evaluate(
        self,
        import_id: str,
        column_roles: dict[str, str],
        project_key: str = _DEFAULT_PROJECT,
        model_package_dir: str | None = None,
    ) -> dict[str, Any]:
        assert_eval_project_eligible(project_key)
        evals_root = self._evals_root()
        record = self._ingest.read_import_record(import_id)
        eval_id = uuid.uuid4().hex[:12]
        created_stamp = datetime.now().strftime("%Y%m%d_%H%M%S")  # noqa: DTZ005 local stamp
        eval_dir = evals_root / eval_id
        eval_dir.mkdir(parents=True, exist_ok=True)

        source_system = record.get("source_system")
        period = record.get("period")
        try:
            mapping = self._mapping.validate_mapping(import_id, column_roles, project_key)
            mapped_rows = mapping["mapped_rows"]
            unmapped_rows = mapping["unmapped_rows"]

            package_dir = self._resolve_model_package(model_package_dir)
            prior_external = self._load_prior_external(project_key, exclude=eval_id)
            external = external_value_by_code(mapped_rows)
            baselines = self._compare.load_baselines(project_key, package_dir, prior_external)
            comparison = self._compare.compare_maps(external, baselines)
            anomalies = anomaly.detect(
                mapped_rows, unmapped_rows, external, baselines, source_system, period
            )

            pkg = self._write_package(
                eval_dir,
                record,
                mapping,
                comparison,
                anomalies,
                created_stamp,
                project_key=project_key,
            )
            self._project_eval_db(
                eval_dir,
                eval_id,
                record,
                mapping,
                comparison,
                anomalies,
                pkg,
                created_stamp,
                project_key=project_key,
            )
            stored = {
                "eval_id": eval_id,
                "created_stamp": created_stamp,
                "project_key": project_key,
                "source_system": source_system,
                "period": period,
                "status": "succeeded",
                "mapped_count": mapping["mapped_count"],
                "unmapped_count": mapping["unmapped_count"],
                "baselines_compared": comparison["baselines_compared"],
                "accuracy_results": comparison["accuracy_results"],
                "comparison_results": comparison["comparison_results"],
                "anomaly_findings": anomalies["anomaly_findings"],
                "review_items": anomalies["review_items"],
                "external_by_code": comparison["external_by_code"],
            }
        except ForecastExternalError:
            raise
        except Exception as exc:  # noqa: BLE001 — record any evaluation failure as a failed run
            stored = {
                "eval_id": eval_id,
                "created_stamp": created_stamp,
                "project_key": project_key,
                "source_system": source_system,
                "period": period,
                "status": "failed",
                "message": f"Forecast evaluation did not complete ({type(exc).__name__}).",
            }
        (eval_dir / _EVAL_RECORD).write_text(
            json.dumps(stored, indent=2, sort_keys=True), encoding="utf-8"
        )
        return {
            "surface": _SURFACE + ".evaluation",
            **self._record_to_summary(stored).public(),
            "guardrails": _guardrails(),
        }

    def list_evaluations(self) -> dict[str, Any]:
        evals_root = self._evals_root()
        records = self._read_all_records(evals_root)
        records.sort(key=lambda r: str(r.get("created_stamp") or ""), reverse=True)
        return {
            "surface": _SURFACE + ".evaluations",
            "evaluations": [self._record_to_list_item(r).public() for r in records],
            "guardrails": _guardrails(),
        }

    def read_evaluation(self, eval_id: str) -> dict[str, Any]:
        rec = self._read_record(self._evals_root(), eval_id)
        if rec is None:
            raise ForecastExternalError(f"unknown eval_id: {eval_id!r}")
        return {
            "surface": _SURFACE + ".evaluation",
            **self._record_to_summary(rec).public(),
            "guardrails": _guardrails(),
        }

    # -- prior-external baseline ---------------------------------------------

    def _load_prior_external(self, project_key: str, exclude: str) -> dict[str, Decimal]:
        records = [
            r
            for r in self._read_all_records(self._evals_root())
            if r.get("eval_id") != exclude
            and r.get("project_key") == project_key
            and r.get("status") == "succeeded"
        ]
        if not records:
            return {}
        records.sort(key=lambda r: str(r.get("created_stamp") or ""), reverse=True)
        prior = records[0].get("external_by_code") or {}
        out: dict[str, Decimal] = {}
        for code, val in prior.items():
            d = _safe_decimal(val)
            if d is not None:
                out[str(code)] = d
        return out

    # -- record IO ------------------------------------------------------------

    def _read_all_records(self, evals_root: Path) -> list[dict[str, Any]]:
        out: list[dict[str, Any]] = []
        try:
            children = [p for p in evals_root.iterdir() if p.is_dir()]
        except OSError:
            return out
        for child in children:
            rec = self._read_record(evals_root, child.name)
            if rec is not None:
                out.append(rec)
        return out

    @staticmethod
    def _read_record(evals_root: Path, eval_id: str) -> dict[str, Any] | None:
        path = evals_root / eval_id / _EVAL_RECORD
        try:
            obj = json.loads(path.read_text(encoding="utf-8"))
        except (OSError, ValueError):
            return None
        return obj if isinstance(obj, dict) else None

    # -- DTO assembly (redacted) ---------------------------------------------

    def _record_to_summary(self, rec: dict[str, Any]) -> EvaluationSummaryDTO:
        status = rec.get("status") or "failed"
        return EvaluationSummaryDTO(
            eval_id=str(rec.get("eval_id") or ""),
            display_label=eval_label(rec.get("source_system"), rec.get("period"), rec.get("created_stamp")),
            status=status,
            source_system=rec.get("source_system"),
            period=rec.get("period"),
            generated_display=_friendly(rec.get("created_stamp")),
            mapped_count=int(rec.get("mapped_count") or 0),
            unmapped_count=int(rec.get("unmapped_count") or 0),
            baselines_compared=[
                BASELINE_LABELS.get(b, b) for b in (rec.get("baselines_compared") or [])
            ],
            accuracy=[
                AccuracyRowDTO(
                    baseline=a["baseline"],
                    baseline_label=a.get("baseline_label", BASELINE_LABELS.get(a["baseline"], a["baseline"])),
                    metric=a["metric"],
                    metric_value=a["metric_value"],
                    sample_n=int(a.get("sample_n") or 0),
                )
                for a in (rec.get("accuracy_results") or [])
            ],
            comparison=[
                ComparisonRowDTO(
                    budget_code_key=c["budget_code_key"],
                    baseline=c["baseline"],
                    baseline_label=c.get("baseline_label", BASELINE_LABELS.get(c["baseline"], c["baseline"])),
                    external_value=c.get("external_value"),
                    baseline_value=c.get("baseline_value"),
                    gap_absolute=c.get("gap_absolute"),
                    gap_percent=c.get("gap_percent"),
                )
                for c in (rec.get("comparison_results") or [])
            ],
            anomalies=[
                AnomalyFindingDTO(
                    flag_code=f["flag_code"],
                    severity=f["severity"],
                    budget_code_key=f.get("budget_code_key"),
                    message=f["message"],
                )
                for f in (rec.get("anomaly_findings") or [])
            ],
            review_items=[
                ReviewItemDTO(
                    reason_code=r["reason_code"],
                    severity=r["severity"],
                    budget_code_key=r.get("budget_code_key"),
                    detail=r["detail"],
                    status=r.get("status", "open"),
                )
                for r in (rec.get("review_items") or [])
            ],
            message=rec.get("message"),
        )

    def _record_to_list_item(self, rec: dict[str, Any]) -> EvaluationListItemDTO:
        return EvaluationListItemDTO(
            eval_id=str(rec.get("eval_id") or ""),
            display_label=eval_label(rec.get("source_system"), rec.get("period"), rec.get("created_stamp")),
            status=rec.get("status") or "failed",
            generated_display=_friendly(rec.get("created_stamp")),
        )

    # -- evidence package + per-run eval DB ----------------------------------

    def _write_package(
        self,
        eval_dir: Path,
        record: dict[str, Any],
        mapping: dict[str, Any],
        comparison: dict[str, Any],
        anomalies: dict[str, Any],
        stamp: str,
        *,
        project_key: str,
    ) -> dict[str, Any]:
        pkg_dir = eval_dir / f"external_forecast_evaluation_package_{project_key}_{stamp}"
        pkg_dir.mkdir(parents=True, exist_ok=True)

        import_receipt = {
            "source_system": record.get("source_system"),
            "period": record.get("period"),
            "source_filename": record.get("source_filename"),
            "format": record.get("format"),
            "byte_count": record.get("byte_count"),
            "row_count": record.get("row_count"),
            "columns": record.get("columns"),
        }
        fingerprint = {
            "file_sha256": record.get("file_sha256"),
            "byte_count": record.get("byte_count"),
        }
        validation_report = {
            "mapped_count": mapping["mapped_count"],
            "unmapped_count": mapping["unmapped_count"],
            "canonical_available": mapping["canonical_available"],
            "baselines_compared": comparison["baselines_compared"],
            "accuracy_metric_count": len(comparison["accuracy_results"]),
            "comparison_row_count": len(comparison["comparison_results"]),
            "anomaly_count": len(anomalies["anomaly_findings"]),
            "review_item_count": len(anomalies["review_items"]),
        }
        _write_json(pkg_dir / "import_receipt.json", import_receipt)
        _write_json(pkg_dir / "source_file_fingerprint.json", fingerprint)
        _write_json(pkg_dir / "validation_report.json", validation_report)
        _write_csv(
            pkg_dir / "mapped_forecast_rows.csv",
            ["budget_code_key", "month", "value", "eac", "remaining", "mapping_status"],
            mapping["mapped_rows"],
        )
        _write_csv(
            pkg_dir / "unmapped_rows.csv",
            ["raw_label", "month", "value", "eac", "remaining"],
            mapping["unmapped_rows"],
        )
        _write_csv(
            pkg_dir / "accuracy_results.csv",
            ["baseline", "metric", "metric_value", "sample_n"],
            comparison["accuracy_results"],
        )
        _write_csv(
            pkg_dir / "comparison_results.csv",
            ["budget_code_key", "baseline", "external_value", "baseline_value", "gap_absolute", "gap_percent"],
            comparison["comparison_results"],
        )
        _write_jsonl(pkg_dir / "anomaly_findings.jsonl", anomalies["anomaly_findings"])
        _write_jsonl(pkg_dir / "human_review_queue.jsonl", anomalies["review_items"])
        (pkg_dir / "summary.md").write_text(
            _summary_md(record, validation_report), encoding="utf-8"
        )
        files = sorted(p.name for p in pkg_dir.iterdir() if p.is_file())
        manifest = {
            "package_kind": "external_forecast_evaluation",
            "project_key": project_key,
            "eligible_projects": sorted(load_eval_project_allowlist()),
            "schema_version": 1,
            "files": files,
            "file_count": len(files),
        }
        _write_json(pkg_dir / "manifest.json", manifest)
        manifest_sha = hashlib.sha256(
            json.dumps(manifest, sort_keys=True).encode("utf-8")
        ).hexdigest()
        return {"dir": pkg_dir, "manifest_sha256": manifest_sha, "file_count": len(files) + 1}

    def _project_eval_db(
        self,
        eval_dir: Path,
        eval_id: str,
        record: dict[str, Any],
        mapping: dict[str, Any],
        comparison: dict[str, Any],
        anomalies: dict[str, Any],
        pkg: dict[str, Any],
        stamp: str,
        *,
        project_key: str,
    ) -> None:
        """Project results into an ISOLATED per-run SQLite (v61 tables only) — never the live DB."""
        db_path = eval_dir / _EVAL_DB
        conn = sqlite3.connect(str(db_path))
        try:
            for stmt in SQLiteMigrator.V61_STATEMENTS:
                conn.execute(stmt)
            now = stamp
            project = project_key
            ef_id = eval_id
            conn.execute(
                "INSERT INTO forecast_external_forecasts (external_forecast_id, project_key, "
                "source_system, forecast_origin, period, source_filename, file_sha256, "
                "content_sha256, byte_count, row_count, import_run_id, imported_at_utc, created_utc) "
                "VALUES (?,?,?,?,?,?,?,?,?,?,?,?,?)",
                (
                    ef_id, project, record.get("source_system") or "other", "external",
                    record.get("period") or "", record.get("source_filename") or "",
                    record.get("file_sha256") or "", record.get("file_sha256") or "",
                    int(record.get("byte_count") or 0), int(record.get("row_count") or 0),
                    eval_id, now, now,
                ),
            )
            for i, row in enumerate(mapping["mapped_rows"]):
                conn.execute(
                    "INSERT INTO forecast_external_forecast_rows (external_forecast_row_id, "
                    "external_forecast_id, project_key, budget_code_key, month, value, eac, "
                    "remaining, confidence, notes, row_order, created_utc) VALUES (?,?,?,?,?,?,?,?,?,?,?,?)",
                    (
                        f"{ef_id}-r{i}", ef_id, project, str(row.get("budget_code_key") or ""),
                        _s(row.get("month")), _s(row.get("value")), _s(row.get("eac")),
                        _s(row.get("remaining")), _s(row.get("confidence")), _s(row.get("notes")),
                        int(row.get("row_order") or i), now,
                    ),
                )
            for i, row in enumerate([*mapping["mapped_rows"], *mapping["unmapped_rows"]]):
                conn.execute(
                    "INSERT INTO forecast_external_forecast_mappings (external_forecast_mapping_id, "
                    "external_forecast_id, project_key, raw_label, canonical_budget_code_key, "
                    "canonical_month, mapping_confidence, mapping_status, created_utc) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (
                        f"{ef_id}-m{i}", ef_id, project, _s(row.get("raw_label")),
                        _s(row.get("budget_code_key")), _s(row.get("month")),
                        _s(row.get("confidence")), str(row.get("mapping_status") or "unmapped"), now,
                    ),
                )
            for i, a in enumerate(comparison["accuracy_results"]):
                conn.execute(
                    "INSERT INTO forecast_accuracy_results (accuracy_result_id, external_forecast_id, "
                    "project_key, baseline, metric, metric_value, sample_n, created_utc) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (f"{ef_id}-a{i}", ef_id, project, a["baseline"], a["metric"],
                     a["metric_value"], int(a["sample_n"]), now),
                )
            for i, c in enumerate(comparison["comparison_results"]):
                conn.execute(
                    "INSERT INTO forecast_comparison_results (comparison_result_id, external_forecast_id, "
                    "project_key, budget_code_key, baseline, external_value, baseline_value, "
                    "gap_absolute, gap_percent, created_utc) VALUES (?,?,?,?,?,?,?,?,?,?)",
                    (f"{ef_id}-c{i}", ef_id, project, c["budget_code_key"], c["baseline"],
                     _s(c.get("external_value")), _s(c.get("baseline_value")),
                     _s(c.get("gap_absolute")), _s(c.get("gap_percent")), now),
                )
            for i, f in enumerate(anomalies["anomaly_findings"]):
                conn.execute(
                    "INSERT INTO forecast_anomaly_findings (anomaly_finding_id, external_forecast_id, "
                    "project_key, budget_code_key, flag_code, severity, evidence_json, created_utc) "
                    "VALUES (?,?,?,?,?,?,?,?)",
                    (f"{ef_id}-f{i}", ef_id, project, _s(f.get("budget_code_key")), f["flag_code"],
                     f["severity"], json.dumps({"message": f["message"]}, sort_keys=True), now),
                )
            for i, r in enumerate(anomalies["review_items"]):
                conn.execute(
                    "INSERT INTO forecast_review_items (review_item_id, external_forecast_id, "
                    "project_key, budget_code_key, reason_code, severity, status, detail, created_utc) "
                    "VALUES (?,?,?,?,?,?,?,?,?)",
                    (f"{ef_id}-i{i}", ef_id, project, _s(r.get("budget_code_key")), r["reason_code"],
                     r["severity"], r.get("status", "open"), r["detail"], now),
                )
            conn.execute(
                "INSERT INTO forecast_evidence_packages (evidence_package_id, external_forecast_id, "
                "project_key, package_kind, manifest_sha256, file_count, created_utc) "
                "VALUES (?,?,?,?,?,?,?)",
                (f"{ef_id}-pkg", ef_id, project, "external_forecast_evaluation",
                 pkg["manifest_sha256"], int(pkg["file_count"]), now),
            )
            conn.commit()
        finally:
            conn.close()


# --- module helpers ----------------------------------------------------------


def _friendly(stamp: object) -> str | None:
    from hb_assistant.construction.analytics.forecast_dto import friendly_datetime_from_stamp

    return friendly_datetime_from_stamp(stamp if isinstance(stamp, str) else None)


def _safe_decimal(value: object) -> Decimal | None:
    from hb_assistant.construction.analytics.forecast_external_metrics import to_decimal

    return to_decimal(value)


def _s(value: object) -> str | None:
    return None if value is None else str(value)


def _write_json(path: Path, obj: Any) -> None:
    path.write_text(json.dumps(obj, indent=2, sort_keys=True), encoding="utf-8")


def _write_jsonl(path: Path, rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8") as fh:
        for row in rows:
            fh.write(json.dumps(row, sort_keys=True) + "\n")


def _write_csv(path: Path, columns: list[str], rows: list[dict[str, Any]]) -> None:
    with path.open("w", encoding="utf-8", newline="") as fh:
        writer = csv.DictWriter(fh, fieldnames=columns, extrasaction="ignore")
        writer.writeheader()
        for row in rows:
            writer.writerow({c: ("" if row.get(c) is None else row.get(c)) for c in columns})


def _summary_md(record: dict[str, Any], validation: dict[str, Any]) -> str:
    lines = [
        "# External forecast evaluation",
        "",
        f"- Source: {record.get('source_system')}",
        f"- Period: {record.get('period') or 'not specified'}",
        f"- Mapped rows: {validation['mapped_count']}",
        f"- Unmapped rows: {validation['unmapped_count']}",
        f"- Baselines compared: {', '.join(validation['baselines_compared']) or 'none'}",
        f"- Anomalies: {validation['anomaly_count']} ({validation['review_item_count']} for review)",
    ]
    return "\n".join(lines) + "\n"
