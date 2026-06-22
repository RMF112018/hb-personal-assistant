"""Shared helpers for schedule project association tests."""

from __future__ import annotations

import sqlite3
from pathlib import Path


def seed_procore_ep_project(
    db_path: str | Path,
    *,
    project_key: str,
    display_name: str,
    project_number: str | None = None,
    project_id: str = "9001",
) -> None:
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
                f"rk-{project_key}",
                "projects",
                project_key,
                project_id,
                display_name,
                project_number,
                project_id,
                "ok",
                1,
                "2026-06-22T00:00:00Z",
                "2026-06-22T00:00:00Z",
                0,
                0,
                0,
            ),
        )
        conn.commit()