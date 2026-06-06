"""Application services for future FastAPI/UI analytics surfaces.

This module is intentionally framework-free. Future FastAPI routes should call
``AnalyticsService`` methods directly instead of invoking command-line adapters.
"""

from __future__ import annotations

import json
import sqlite3
from collections.abc import Callable
from datetime import datetime, timedelta, timezone
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.store.connection import get_connection
from hb_assistant.store.migrator import LATEST_SCHEMA_VERSION, SQLiteMigrator

_CATALOG_PATH = Path("docs/evidence/future-fastapi-analytics-dashboard-metrics-catalog/02-metrics-catalog.json")
_FORBIDDEN_KEYS = {
    "raw_body",
    "raw_document_text",
    "raw_calendar_payload",
    "raw_prompt",
    "raw_response",
    "access_token",
    "client_secret",
    "signed_url",
    "download_url",
}


def _utc_now() -> str:
    return datetime.now(timezone.utc).isoformat()


def _guardrails() -> dict[str, Any]:
    return {
        "read_only": True,
        "local_first": True,
        "no_cli_shellout": True,
        "no_external_writeback": True,
        "sensitive_field_values_excluded": True,
        "makes_determination": False,
    }


def _empty_metric(metric_id: str, name: str, status: str, reason_code: str) -> dict[str, Any]:
    return {
        "metric_id": metric_id,
        "name": name,
        "status": status,
        "reason_code": reason_code,
        "source": None,
        "value": None,
        "confidence": "not_available",
        "limitations": [reason_code],
    }


class AnalyticsService:
    """Reusable read-only analytics boundary for future UI route adapters."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path

    def build_operations_summary(self) -> dict[str, Any]:
        """Return Top-20 operations metric status without raw detail rows."""
        generated = _utc_now()
        project_keys = self._project_keys()
        metrics: list[dict[str, Any]] = [
            _empty_metric(
                "OPS-001",
                "Projects Needing Executive Attention",
                "requires_read_model",
                "requires_new_mart",
            ),
            _empty_metric(
                "OPS-003",
                "Projects With Aging Decisions",
                "requires_read_model",
                "requires_minor_read_model",
            ),
            _empty_metric(
                "OPS-086",
                "Open Closeout Action Signals",
                "requires_read_model",
                "requires_new_mart",
            ),
            _empty_metric(
                "HYB-001",
                "Executive Attention With Confidence Flags",
                "requires_read_model",
                "requires_minor_read_model",
            ),
            _empty_metric(
                "HYB-002",
                "Cost Exposure With Readiness Context",
                "requires_read_model",
                "requires_minor_read_model",
            ),
        ]

        if not project_keys:
            metrics.extend(
                [
                    _empty_metric("OPS-002", "Portfolio Cost Exposure Signals", "unavailable", "no_projects_with_procore_records"),
                    _empty_metric("OPS-009", "Open Project Action Signals", "unavailable", "no_projects_with_procore_records"),
                    _empty_metric("OPS-015", "Recent Project Changes Since Last Review", "unavailable", "no_projects_with_procore_records"),
                    _empty_metric("OPS-033", "Schedule Exposure Signals", "unavailable", "no_projects_with_procore_records"),
                    _empty_metric("ADC-001", "Project Source Coverage Confidence", "unavailable", "no_projects_with_procore_records"),
                ]
            )
        else:
            metrics.extend(self._operations_metrics_for_projects(project_keys, generated))

        status_counts = self._status_counts(metrics)
        return {
            "surface": "analytics.operations_summary",
            "generated_utc": generated,
            "schema_version": self._schema_version(),
            "schema_expected": LATEST_SCHEMA_VERSION,
            "project_count": len(project_keys),
            "project_keys": project_keys,
            "metric_count": len(metrics),
            "status_counts": status_counts,
            "metrics": sorted(metrics, key=lambda m: str(m["metric_id"])),
            "guardrails": _guardrails(),
            "readiness_overstated": False,
            "makes_determination": False,
        }

    def build_admin_confidence_summary(self) -> dict[str, Any]:
        """Return data-confidence metric status from existing read-only evaluators."""
        generated = _utc_now()
        metrics = [
            self._metric_from_call(
                "ADC-013",
                "Data Quality Gate Status",
                "hb_assistant.construction.second_brain.phase_09_gates.evaluate_phase_09_data_quality_gates",
                self._phase_09_gates,
                value_keys=("status_counts", "ok", "proof_passed"),
            ),
            self._metric_from_call(
                "ADC-015",
                "No-Raw / No-Writeback Proof Status",
                "hb_assistant.construction.second_brain.safety.build_second_brain_no_writeback_proof",
                self._second_brain_no_writeback,
                value_keys=("proof_passed", "raw_content_findings", "writeback_findings"),
            ),
            self._metric_from_call(
                "ADC-018",
                "Evidence Freshness By Domain",
                "hb_assistant.construction.second_brain.freshness.evaluate_observability",
                self._observability,
                value_keys=("overall_status", "reason_code", "schema_version"),
            ),
            self._metric_from_call(
                "ADC-031",
                "Full Table Inventory Coverage",
                "hb_assistant.construction.data_quality.table_inventory.build_table_inventory_report",
                self._table_inventory,
                value_keys=("schema_version", "table_count", "proof_passed"),
            ),
            self._metric_from_call(
                "ADC-001",
                "Project Source Coverage Confidence",
                "hb_assistant.construction.second_brain.corpus_balance_mart.build_coverage_parity_report",
                self._coverage_parity,
                value_keys=("schema_version", "coverage_parity_ok", "covered_family_count"),
            ),
            self._metric_from_call(
                "ADC-008",
                "Daily Brief Run Health",
                "hb_assistant.construction.second_brain.automation_health.evaluate_automation_health",
                self._automation_health,
                value_keys=("overall_status", "reason_code", "schema_version"),
            ),
        ]
        schema_version = self._schema_version()
        schema_ready = schema_version >= LATEST_SCHEMA_VERSION
        return {
            "surface": "analytics.admin_confidence_summary",
            "generated_utc": generated,
            "schema_version": schema_version,
            "schema_expected": LATEST_SCHEMA_VERSION,
            "schema_ready": schema_ready,
            "metric_count": len(metrics),
            "status_counts": self._status_counts(metrics),
            "metrics": metrics,
            "guardrails": _guardrails(),
            "readiness_overstated": False,
            "makes_determination": False,
        }

    def build_metric_catalog_status(self) -> dict[str, Any]:
        """Return local catalog metadata for UI planning, without exposing catalog rows."""
        generated = _utc_now()
        path = Path.cwd() / _CATALOG_PATH
        value: dict[str, Any] = {}
        status = "unavailable"
        reason_code = "catalog_missing"
        if path.exists():
            try:
                data = json.loads(path.read_text(encoding="utf-8"))
                value = {
                    "catalog_version": data.get("catalog_version"),
                    "metric_count": data.get("metric_count"),
                    "layer_counts": data.get("layer_counts", {}),
                    "dashboard_area_counts": data.get("dashboard_area_counts", {}),
                }
                status = "available"
                reason_code = "catalog_loaded"
            except (OSError, json.JSONDecodeError):
                status = "unavailable"
                reason_code = "catalog_unreadable"
        return {
            "surface": "analytics.metric_catalog_status",
            "generated_utc": generated,
            "catalog_path": str(_CATALOG_PATH),
            "status": status,
            "reason_code": reason_code,
            "value": value,
            "guardrails": _guardrails(),
            "readiness_overstated": False,
            "makes_determination": False,
        }

    def _operations_metrics_for_projects(self, project_keys: list[str], generated: str) -> list[dict[str, Any]]:
        since = (datetime.fromisoformat(generated) - timedelta(days=7)).isoformat()
        return [
            self._project_metric(
                "OPS-002",
                "Portfolio Cost Exposure Signals",
                "hb_assistant.store.procore_cost_exposure.build_cost_exposure",
                project_keys,
                lambda p: self._cost_exposure(p, generated),
                ("summary", "item_count", "review_required_count"),
            ),
            self._project_metric(
                "OPS-009",
                "Open Project Action Signals",
                "hb_assistant.store.procore_action_queue.build_overdue_queue",
                project_keys,
                lambda p: self._overdue_queue(p, generated),
                ("summary", "item_count", "review_required_count"),
            ),
            self._project_metric(
                "OPS-015",
                "Recent Project Changes Since Last Review",
                "hb_assistant.store.procore_history.get_procore_changes",
                project_keys,
                lambda p: self._recent_changes(p, since),
                ("change_count", "review_required_count"),
            ),
            self._project_metric(
                "OPS-033",
                "Schedule Exposure Signals",
                "hb_assistant.store.procore_schedule_exposure.build_schedule_exposure",
                project_keys,
                lambda p: self._schedule_exposure(p, generated),
                ("summary", "item_count", "review_required_count"),
            ),
            self._project_metric(
                "ADC-001",
                "Project Source Coverage Confidence",
                "hb_assistant.store.procore_freshness.build_freshness_report",
                project_keys,
                lambda p: self._procore_freshness(p, generated),
                ("summary", "stale_or_never_count"),
            ),
        ]

    def _project_metric(
        self,
        metric_id: str,
        name: str,
        source: str,
        project_keys: list[str],
        builder: Callable[[str], dict[str, Any]],
        value_keys: tuple[str, ...],
    ) -> dict[str, Any]:
        per_project: list[dict[str, Any]] = []
        failures: list[str] = []
        for project_key in project_keys:
            try:
                report = builder(project_key)
                per_project.append({"project_key": project_key, "value": self._select(report, value_keys)})
            except Exception as exc:
                failures.append(f"{project_key}:{exc.__class__.__name__}")
        status = "available" if per_project else "unavailable"
        reason_code = "direct_read_model_called" if per_project else "read_model_unavailable"
        return {
            "metric_id": metric_id,
            "name": name,
            "status": status,
            "reason_code": reason_code,
            "source": source,
            "value": {"projects": per_project, "failed_projects": failures},
            "confidence": "source_backed" if per_project else "not_available",
            "limitations": ["metadata_summary_only", "no_final_determination"],
        }

    def _metric_from_call(
        self,
        metric_id: str,
        name: str,
        source: str,
        builder: Callable[[], dict[str, Any]],
        *,
        value_keys: tuple[str, ...],
    ) -> dict[str, Any]:
        try:
            report = builder()
        except Exception as exc:
            return {
                "metric_id": metric_id,
                "name": name,
                "status": "unavailable",
                "reason_code": exc.__class__.__name__,
                "source": source,
                "value": None,
                "confidence": "not_available",
                "limitations": ["fail_closed"],
            }
        return {
            "metric_id": metric_id,
            "name": name,
            "status": "available",
            "reason_code": "direct_read_model_called",
            "source": source,
            "value": self._select(report, value_keys),
            "confidence": "source_backed",
            "limitations": ["metadata_summary_only", "no_final_determination"],
        }

    def _schema_version(self) -> int:
        try:
            return int(SQLiteMigrator(db_path=self._resolved_db_path()).current_version())
        except Exception:
            return 0

    def _resolved_db_path(self) -> str:
        if self.db_path is not None:
            return self.db_path
        return str(PathPolicy().get_db_path())

    def _project_keys(self) -> list[str]:
        try:
            conn = get_connection(Path(self._resolved_db_path()))
            if not self._table_exists(conn, "procore_live_records"):
                return []
            rows = conn.execute(
                "SELECT DISTINCT project_key FROM procore_live_records "
                "WHERE project_key IS NOT NULL AND project_key != '' ORDER BY project_key"
            ).fetchall()
            return [str(r["project_key"]) for r in rows]
        except (OSError, sqlite3.Error):
            return []

    @staticmethod
    def _table_exists(conn: sqlite3.Connection, table_name: str) -> bool:
        row = conn.execute(
            "SELECT name FROM sqlite_master WHERE type='table' AND name=?", (table_name,)
        ).fetchone()
        return row is not None

    @staticmethod
    def _select(report: dict[str, Any], keys: tuple[str, ...]) -> dict[str, Any]:
        return {key: report.get(key) for key in keys if key in report}

    @staticmethod
    def _status_counts(metrics: list[dict[str, Any]]) -> dict[str, int]:
        counts: dict[str, int] = {}
        for metric in metrics:
            status = str(metric.get("status", "unknown"))
            counts[status] = counts.get(status, 0) + 1
        return counts

    def _cost_exposure(self, project_key: str, now_utc: str) -> dict[str, Any]:
        from hb_assistant.store.procore_cost_exposure import build_cost_exposure

        report = build_cost_exposure(project_key, now_utc=now_utc, db_path=Path(self._resolved_db_path()))
        return {
            "summary": report.get("summary", {}),
            "item_count": len(report.get("items", [])),
            "review_required_count": sum(1 for item in report.get("items", []) if item.get("review_required")),
        }

    def _overdue_queue(self, project_key: str, now_utc: str) -> dict[str, Any]:
        from hb_assistant.store.procore_action_queue import build_overdue_queue

        report = build_overdue_queue(project_key, now_utc=now_utc, db_path=Path(self._resolved_db_path()))
        return {
            "summary": report.get("summary", {}),
            "item_count": len(report.get("items", [])),
            "review_required_count": sum(1 for item in report.get("items", []) if item.get("review_required")),
        }

    def _schedule_exposure(self, project_key: str, now_utc: str) -> dict[str, Any]:
        from hb_assistant.store.procore_schedule_exposure import build_schedule_exposure

        report = build_schedule_exposure(project_key, now_utc=now_utc, db_path=Path(self._resolved_db_path()))
        return {
            "summary": report.get("summary", {}),
            "item_count": len(report.get("items", [])),
            "review_required_count": sum(1 for item in report.get("items", []) if item.get("review_required")),
        }

    def _recent_changes(self, project_key: str, since_utc: str) -> dict[str, Any]:
        from hb_assistant.store.procore_history import get_procore_changes

        changes = get_procore_changes(
            project_key=project_key,
            since_utc=since_utc,
            db_path=Path(self._resolved_db_path()),
        )
        return {
            "change_count": len(changes),
            "review_required_count": sum(1 for change in changes if change.get("review_required")),
        }

    def _procore_freshness(self, project_key: str, now_utc: str) -> dict[str, Any]:
        from hb_assistant.store.procore_freshness import build_freshness_report

        report = build_freshness_report(project_key, now_utc=now_utc, db_path=Path(self._resolved_db_path()))
        summary = report.get("summary", {})
        stale = int(summary.get("stale", 0) or 0)
        never = int(summary.get("never_synced", 0) or 0)
        return {"summary": summary, "stale_or_never_count": stale + never}

    def _phase_09_gates(self) -> dict[str, Any]:
        from hb_assistant.construction.second_brain.phase_09_gates import (
            evaluate_phase_09_data_quality_gates,
        )

        return evaluate_phase_09_data_quality_gates(db_path=self._resolved_db_path())

    def _second_brain_no_writeback(self) -> dict[str, Any]:
        from hb_assistant.construction.second_brain.safety import (
            build_second_brain_no_writeback_proof,
        )

        return build_second_brain_no_writeback_proof(db_path=self._resolved_db_path())

    def _observability(self) -> dict[str, Any]:
        from hb_assistant.construction.second_brain.freshness import evaluate_observability

        return evaluate_observability(db_path=self._resolved_db_path()).model_dump()

    def _table_inventory(self) -> dict[str, Any]:
        from hb_assistant.construction.data_quality.table_inventory import (
            build_table_inventory_report,
        )

        return build_table_inventory_report(db_path=self._resolved_db_path())

    def _coverage_parity(self) -> dict[str, Any]:
        from hb_assistant.construction.second_brain.corpus_balance_mart import (
            build_coverage_parity_report,
        )

        return build_coverage_parity_report(db_path=self._resolved_db_path())

    def _automation_health(self) -> dict[str, Any]:
        from hb_assistant.construction.second_brain.automation_health import (
            evaluate_automation_health,
        )

        return evaluate_automation_health(db_path=self._resolved_db_path()).model_dump()
