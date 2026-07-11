"""source_index_health must reuse caller RO conn (NAS snapshot is not writable)."""

from __future__ import annotations

from pathlib import Path
from unittest.mock import MagicMock, patch

from hb_assistant.obsidian_mcp.source_health_service import source_index_health


def test_source_index_health_threads_conn_to_bootstrap(tmp_path: Path) -> None:
    """Regression: missing conn= opens RW path and fails on RO snapshot mounts."""
    repo = MagicMock()
    repo.db_path = str(tmp_path / "db.sqlite")
    repo.queue_health.return_value = {}
    repo.get_watcher_owner.return_value = None
    config = MagicMock()
    config.external_source_watch_enabled = False
    config.external_sources = []

    fake_conn = object()
    captured: dict[str, object] = {}

    def _list_bootstrap_state(*, conn=None):
        captured["bootstrap_conn"] = conn
        return []

    with (
        patch(
            "hb_assistant.obsidian_mcp.source_health_service.source_status",
            return_value={
                "last_indexed_at": None,
                "skipped_by_code": {},
                "roots": [],
            },
        ),
        patch(
            "hb_assistant.obsidian_mcp.source_health_service.list_source_roots",
            return_value={"roots": []},
        ),
        patch(
            "hb_assistant.obsidian_mcp.source_health_service.SourceStructureRepository"
        ) as srepo_cls,
        patch(
            "hb_assistant.obsidian_mcp.source_health_service.SourceIndexBootstrapRepository"
        ) as bstate_cls,
        patch(
            "hb_assistant.obsidian_mcp.source_health_service.SourceIndexScanGenerationsRepository"
        ) as gen_cls,
    ):
        srepo = srepo_cls.return_value
        srepo.status.return_value = {}
        srepo.list_roots.return_value = []
        bstate = bstate_cls.return_value
        bstate.list_bootstrap_state.side_effect = _list_bootstrap_state
        bstate.last_reconciliation.return_value = {}
        bstate.get_structure_drift.return_value = {
            "directory_change_detected": False,
            "structure_rebuild_required": False,
        }
        gen_cls.return_value.latest_generations.return_value = {}

        out = source_index_health(repo, config, conn=fake_conn)

    assert captured.get("bootstrap_conn") is fake_conn
    bstate.list_bootstrap_state.assert_called()
    repo.queue_health.assert_called_with(conn=fake_conn)
    assert isinstance(out, dict)
    # empty roots still produces a structured payload (not a raised StoreReadinessError)
    assert (
        "roots" in out
        or out.get("error_code") == "source_index_health_unavailable"
        or "overall" in out
        or per_root_ok(out)
    )


def per_root_ok(out: dict) -> bool:
    return "per_root" in out or "freshness_status" in str(out)
