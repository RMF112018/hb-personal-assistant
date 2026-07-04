"""NAS default-off gating (N8 3a).

HB_NAS_RUNTIME forces background workers off at boot (authoritative, independent of the
HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS kill-switch) and refuses on-demand watcher starts unless
the operator opts in deliberately. Full NAS-runtime app startup requires a /volume1 DB (storage
guard) and is proven on the NAS itself; here we unit-test the pure decisions plus the health
surface. All against tmp scratch DBs.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from hb_assistant.config.db_storage_guard import nas_on_demand_watch_allowed
from hb_assistant.construction.analytics.api import create_app
from hb_assistant.construction.schedule_clean_db.diagnostics import (
    resolve_background_worker_disable,
)
from hb_assistant.store.migrator import SQLiteMigrator


@pytest.mark.parametrize(
    "nas_runtime,env_disabled,expect_disable,expect_forced",
    [
        (False, False, False, False),  # dev, workers on
        (False, True, True, False),    # dev, kill-switch on
        (True, True, True, False),     # NAS + kill-switch: off, but env did it
        (True, False, True, True),     # NAS alone forces off (the new behavior)
    ],
)
def test_resolve_background_worker_disable(nas_runtime, env_disabled, expect_disable, expect_forced) -> None:
    disable, forced = resolve_background_worker_disable(
        nas_runtime=nas_runtime, env_disabled=env_disabled
    )
    assert disable is expect_disable
    assert forced is expect_forced


def test_nas_on_demand_watch_allowed(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.delenv("HB_NAS_RUNTIME", raising=False)
    monkeypatch.delenv("HB_NAS_ALLOW_WATCH", raising=False)
    assert nas_on_demand_watch_allowed() is True  # dev: allowed

    monkeypatch.setenv("HB_NAS_RUNTIME", "1")
    assert nas_on_demand_watch_allowed() is False  # NAS default-off: refused

    monkeypatch.setenv("HB_NAS_ALLOW_WATCH", "1")
    assert nas_on_demand_watch_allowed() is True  # deliberate opt-in


def test_health_surfaces_worker_and_nas_fields(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> None:
    # Non-NAS + kill-switch on: health must report workers disabled and the NAS fields (both false
    # here since this is not NAS runtime). Proves the health surface added in 3a renders.
    monkeypatch.delenv("HB_NAS_RUNTIME", raising=False)
    monkeypatch.setenv("HB_EVIDENCE_DISABLE_BACKGROUND_WORKERS", "1")
    db = tmp_path / "head.db"
    SQLiteMigrator(db_path=str(db)).apply()
    # Context-manager form runs the lifespan, which sets the worker-mode app.state.
    with TestClient(create_app(db_path=str(db))) as client:
        payload = client.get("/health").json()
    assert payload["background_worker_mode"] == "disabled"
    assert payload["background_workers_disabled_by_env"] is True
    assert payload["background_workers_forced_off_by_nas_runtime"] is False
    assert payload["nas_runtime"] is False
    workers = payload.get("background_workers", {})
    assert workers.get("quality_poll_started") is False
    assert workers.get("source_watcher_started") is False
