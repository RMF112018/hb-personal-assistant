"""Shared helpers for schedule project association tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def seed_procore_ep_project_row(
    db_path: str | Path,
    *,
    project_key: str,
    display_name: str,
    project_number: str | None = None,
    project_id: str = "9001",
    record_key: str | None = None,
    is_current: int = 1,
    updated_utc: str = "2026-06-22T00:00:00Z",
) -> str:
    resolved_record_key = record_key or f"rk-{project_key}-{project_id}"
    with sqlite3.connect(str(db_path)) as conn:
        conn.execute(
            """
            INSERT INTO procore_ep_projects (
              record_key, endpoint_key, project_key, project_id, display_name, project_number,
              record_id, source_quality, is_current, created_utc, updated_utc,
              external_writeback_performed, raw_payload_emitted_to_read_model,
              raw_payload_emitted_to_evidence
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                resolved_record_key,
                "projects",
                project_key,
                project_id,
                display_name,
                project_number,
                project_id,
                "ok",
                is_current,
                updated_utc,
                updated_utc,
                0,
                0,
                0,
            ),
        )
        conn.commit()
    return resolved_record_key


def seed_procore_ep_project(
    db_path: str | Path,
    *,
    project_key: str,
    display_name: str,
    project_number: str | None = None,
    project_id: str = "9001",
) -> None:
    seed_procore_ep_project_row(
        db_path,
        project_key=project_key,
        display_name=display_name,
        project_number=project_number,
        project_id=project_id,
    )