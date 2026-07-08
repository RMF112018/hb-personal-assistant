"""WS2 client-usability fixes: vault arg-alias normalization (Defect G) + freshness anomaly (freshness).

Unit-level coverage that doesn't need a live vault/config: the adapter's arg-normalization contract and
the freshness reporter's future-timestamp handling.
"""

from __future__ import annotations

from datetime import timedelta

import pytest

from hb_assistant.nas_mcp import freshness
from hb_assistant.nas_mcp.obsidian_adapter import _normalize_vault_args
from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError


# --- Defect G: vault tool arg aliases ---------------------------------------------------
def test_backlinks_accepts_path_alias_for_target_path() -> None:
    args = {"path": "Work/Note.md"}
    _normalize_vault_args("vault_get_backlinks", args)
    assert args["target_path"] == "Work/Note.md"


def test_unlinked_mentions_derives_title_from_path() -> None:
    args = {"target_path": "Work/03 Decisions/Big Decision.md"}
    _normalize_vault_args("vault_get_unlinked_mentions", args)
    assert args["target_title"] == "Big Decision"


def test_unlinked_mentions_accepts_title_alias() -> None:
    args = {"title": "Kickoff Meeting"}
    _normalize_vault_args("vault_get_unlinked_mentions", args)
    assert args["target_title"] == "Kickoff Meeting"


def test_search_vault_honors_max_results_alias_for_limit() -> None:
    args = {"query": "x", "max_results": 3}
    _normalize_vault_args("search_vault", args)
    assert args["limit"] == 3


def test_search_by_properties_honors_path_prefix_as_root_scope() -> None:
    args = {"path_prefix": "Work/", "filters": {}}
    _normalize_vault_args("vault_search_by_properties", args)
    assert args["root_path"] == "Work/"


def test_explicit_value_not_overridden_by_alias() -> None:
    args = {"limit": 10, "max_results": 3, "query": "x"}
    _normalize_vault_args("search_vault", args)
    assert args["limit"] == 10  # explicit canonical value wins over alias


def test_missing_required_arg_raises_clear_error() -> None:
    with pytest.raises(ObsidianMcpToolError, match="target_path"):
        _normalize_vault_args("vault_get_backlinks", {})


# --- freshness: future-dated timestamp is an anomaly, not "ok" ---------------------------
def test_future_timestamp_flagged_as_anomaly() -> None:
    future = (freshness._now() + timedelta(days=20)).isoformat()
    info = freshness._age_status(future)
    assert info["status"] == freshness.STATUS_FUTURE
    assert info["age_seconds"] < 0  # real negative age surfaced, not clamped to 0


def test_recent_timestamp_is_ok() -> None:
    recent = (freshness._now() - timedelta(minutes=1)).isoformat()
    assert freshness._age_status(recent)["status"] == freshness.STATUS_OK


def test_old_timestamp_is_stale() -> None:
    old = (freshness._now() - timedelta(days=5)).isoformat()
    assert freshness._age_status(old)["status"] == freshness.STATUS_STALE


def test_small_future_skew_within_tolerance_is_ok() -> None:
    skew = (freshness._now() + timedelta(seconds=60)).isoformat()
    assert freshness._age_status(skew)["status"] == freshness.STATUS_OK
