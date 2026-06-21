"""Read-only forecast configuration catalog service (Implementation Phase 2).

Browses the immutable v60 config-registry snapshot already in the local DB:
``forecast_config_snapshots`` / ``forecast_config_snapshot_items`` (plus ``forecast_config_sources``
for per-domain source counts). This is the app layer's **first DB read** — it is strictly
read-only: the DB is opened with ``mode=ro`` (which also fails closed if the file is absent),
and the service never writes.

Fail-closed: refuses if the DB is missing/unreadable, if the schema is below v60, or if the
required config tables are absent. Payloads are built from ``forecast_config_dto`` DTOs with
domain-aware redaction (project-domain field whitelist; shared leak scan as backstop).
"""

from __future__ import annotations

import json
import sqlite3
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.analytics.forecast_config_dto import (
    DOMAIN_LABELS,
    ConfigDomainDTO,
    ConfigItemDTO,
    ConfigSnapshotDTO,
    _friendly_utc,
    domain_item_fields,
)

_SURFACE = "analytics.forecast_config"
_REQUIRED_SCHEMA_VERSION = 60
_REQUIRED_TABLES = (
    "forecast_config_snapshots",
    "forecast_config_snapshot_items",
    "forecast_config_sources",
    "forecast_config_items",
)
_MAX_ITEMS = 2000  # defensive cap on a single domain's item list
_DEFAULT_PROJECT = "tropical"


class ForecastConfigError(RuntimeError):
    """Raised when the config catalog is unavailable (fail closed) or a record is unknown."""


def _guardrails() -> dict[str, Any]:
    # Honest about the posture change from Phase 1: this service DOES read the DB (read-only).
    return {
        "read_only": True,
        "no_db_write": True,
        "db_access": "read_only",
        "local_first": True,
        "no_cli_shellout": True,
        "no_live_endpoint_calls": True,
        "no_external_writeback": True,
    }


class ForecastConfigCatalogService:
    """Read-only browser over the v60 forecast config-registry snapshot (mode=ro)."""

    def __init__(self, db_path: str | None = None) -> None:
        self.db_path = db_path

    # -- read-only connection / fail-closed validation ------------------------

    def _resolved_db_path(self) -> str:
        return self.db_path if self.db_path is not None else str(PathPolicy().get_db_path())

    def _connect(self) -> sqlite3.Connection:
        path = Path(self._resolved_db_path())
        if not path.exists():
            raise ForecastConfigError("forecast config DB is not available")
        try:
            # mode=ro guarantees read-only and fails if the file cannot be opened read-only.
            conn = sqlite3.connect(f"{path.resolve().as_uri()}?mode=ro", uri=True)
            conn.row_factory = sqlite3.Row
        except sqlite3.Error as exc:
            raise ForecastConfigError("forecast config DB could not be opened read-only") from exc
        try:
            self._assert_ready(conn)
        except ForecastConfigError:
            conn.close()
            raise
        return conn

    def _assert_ready(self, conn: sqlite3.Connection) -> None:
        try:
            row = conn.execute("SELECT MAX(version) AS v FROM schema_migrations").fetchone()
            version = int(row["v"]) if row and row["v"] is not None else 0
        except sqlite3.Error as exc:
            raise ForecastConfigError("forecast config DB schema is unreadable") from exc
        if version < _REQUIRED_SCHEMA_VERSION:
            raise ForecastConfigError(
                f"forecast config requires schema v{_REQUIRED_SCHEMA_VERSION}; DB is at v{version}"
            )
        present = {
            r["name"]
            for r in conn.execute(
                "SELECT name FROM sqlite_master WHERE type='table' AND name LIKE 'forecast_config_%'"
            ).fetchall()
        }
        missing = [t for t in _REQUIRED_TABLES if t not in present]
        if missing:
            raise ForecastConfigError("forecast config tables are not present")

    # -- helpers --------------------------------------------------------------

    @staticmethod
    def _parse_raw(raw: Any) -> dict[str, Any]:
        if not isinstance(raw, str):
            return {}
        try:
            obj = json.loads(raw)
        except (ValueError, TypeError):
            return {}
        return obj if isinstance(obj, dict) else {}

    def _domain_counts(self, conn: sqlite3.Connection, snapshot_id: str) -> dict[str, int]:
        rows = conn.execute(
            "SELECT config_domain, COUNT(*) AS n FROM forecast_config_snapshot_items "
            "WHERE config_snapshot_id = ? GROUP BY config_domain",
            (snapshot_id,),
        ).fetchall()
        return {r["config_domain"]: int(r["n"]) for r in rows}

    def _source_counts(self, conn: sqlite3.Connection, project_key: str) -> dict[str, int]:
        rows = conn.execute(
            "SELECT config_domain, COUNT(*) AS n FROM forecast_config_sources "
            "WHERE project_key = ? GROUP BY config_domain",
            (project_key,),
        ).fetchall()
        return {r["config_domain"]: int(r["n"]) for r in rows}

    def _snapshot_header(self, conn: sqlite3.Connection, snapshot_id: str) -> sqlite3.Row | None:
        return conn.execute(
            "SELECT config_snapshot_id, project_key, snapshot_name, snapshot_created_utc, "
            "snapshot_reason, source_mode, item_count, created_by "
            "FROM forecast_config_snapshots WHERE config_snapshot_id = ?",
            (snapshot_id,),
        ).fetchone()

    def _snapshot_dto(self, header: sqlite3.Row, domain_counts: dict[str, int]) -> ConfigSnapshotDTO:
        return ConfigSnapshotDTO(
            snapshot_id=header["config_snapshot_id"],
            snapshot_name=header["snapshot_name"],
            created_display=_friendly_utc(header["snapshot_created_utc"]),
            reason=header["snapshot_reason"],
            source_mode=header["source_mode"],
            item_count=int(header["item_count"]) if header["item_count"] is not None else 0,
            domain_counts=dict(sorted(domain_counts.items())),
        )

    # -- public API (each returns surface + guardrails) -----------------------

    def list_snapshots(self, project_key: str = _DEFAULT_PROJECT) -> dict[str, Any]:
        conn = self._connect()
        try:
            headers = conn.execute(
                "SELECT config_snapshot_id, project_key, snapshot_name, snapshot_created_utc, "
                "snapshot_reason, source_mode, item_count, created_by "
                "FROM forecast_config_snapshots WHERE project_key = ? "
                "ORDER BY snapshot_created_utc DESC, config_snapshot_id",
                (project_key,),
            ).fetchall()
            snapshots = [
                self._snapshot_dto(h, self._domain_counts(conn, h["config_snapshot_id"])).public()
                for h in headers
            ]
        finally:
            conn.close()
        return {
            "surface": _SURFACE + ".snapshots",
            "project_key": project_key,
            "snapshots": snapshots,
            "guardrails": _guardrails(),
        }

    def read_snapshot(self, snapshot_id: str) -> dict[str, Any]:
        conn = self._connect()
        try:
            header = self._snapshot_header(conn, snapshot_id)
            if header is None:
                raise ForecastConfigError(f"unknown snapshot_id: {snapshot_id!r}")
            domain_counts = self._domain_counts(conn, snapshot_id)
            source_counts = self._source_counts(conn, header["project_key"])
            snapshot = self._snapshot_dto(header, domain_counts).public()
            domains = [
                ConfigDomainDTO(
                    domain=d,
                    display_label=DOMAIN_LABELS.get(d, d.replace("_", " ").capitalize()),
                    item_count=domain_counts[d],
                    source_count=source_counts.get(d, 0),
                ).public()
                for d in sorted(domain_counts)
            ]
        finally:
            conn.close()
        return {
            "surface": _SURFACE + ".snapshot",
            **snapshot,
            "domains": domains,
            "guardrails": _guardrails(),
        }

    def read_domain(self, snapshot_id: str, config_domain: str) -> dict[str, Any]:
        conn = self._connect()
        try:
            if self._snapshot_header(conn, snapshot_id) is None:
                raise ForecastConfigError(f"unknown snapshot_id: {snapshot_id!r}")
            rows = conn.execute(
                "SELECT config_item_id, config_name, item_key, item_order, raw_json "
                "FROM forecast_config_snapshot_items "
                "WHERE config_snapshot_id = ? AND config_domain = ? "
                "ORDER BY item_order, config_item_id LIMIT ?",
                (snapshot_id, config_domain, _MAX_ITEMS + 1),
            ).fetchall()
            truncated = len(rows) > _MAX_ITEMS
            items = [
                ConfigItemDTO(
                    item_id=r["config_item_id"],
                    domain=config_domain,
                    config_name=r["config_name"],
                    item_key=r["item_key"],
                    item_order=int(r["item_order"]) if r["item_order"] is not None else 0,
                    fields=domain_item_fields(config_domain, self._parse_raw(r["raw_json"])),
                ).public()
                for r in rows[:_MAX_ITEMS]
            ]
        finally:
            conn.close()
        return {
            "surface": _SURFACE + ".domain",
            "snapshot_id": snapshot_id,
            "domain": config_domain,
            "display_label": DOMAIN_LABELS.get(config_domain, config_domain.replace("_", " ").capitalize()),
            "item_count": len(items),
            "truncated": truncated,
            "items": items,
            "guardrails": _guardrails(),
        }

    def read_item(self, snapshot_id: str, item_id: str) -> dict[str, Any]:
        conn = self._connect()
        try:
            row = conn.execute(
                "SELECT config_item_id, config_domain, config_name, item_key, item_order, raw_json "
                "FROM forecast_config_snapshot_items "
                "WHERE config_snapshot_id = ? AND config_item_id = ?",
                (snapshot_id, item_id),
            ).fetchone()
            if row is None:
                raise ForecastConfigError(f"unknown item_id: {item_id!r}")
            dto = ConfigItemDTO(
                item_id=row["config_item_id"],
                domain=row["config_domain"],
                config_name=row["config_name"],
                item_key=row["item_key"],
                item_order=int(row["item_order"]) if row["item_order"] is not None else 0,
                fields=domain_item_fields(row["config_domain"], self._parse_raw(row["raw_json"])),
            )
        finally:
            conn.close()
        return {"surface": _SURFACE + ".item", **dto.public(), "guardrails": _guardrails()}
