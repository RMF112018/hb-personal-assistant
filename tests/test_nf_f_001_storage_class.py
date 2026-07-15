"""NF-F-001 RC-2: exact-path storage-class classification.

The managed production, read-only snapshot, and isolated workspace NAS DB paths share the NAS
volume prefix + ``db`` parent + managed filename, so the legacy locality classifier
(``classify_db_storage``) lumps all three as ``nas_local`` and CANNOT distinguish them for
authorization. ``classify_storage_class`` fixes this by exact-path equality against the configured
managed / workspace / snapshot roots so a workspace- or snapshot-shaped path is never authorized as
managed production.
"""

from __future__ import annotations

import pytest

from hb_assistant.config import db_storage_guard as g
from hb_assistant.config.db_storage_guard import DatabaseStorageClass as SC

MANAGED = "/volume2/personal-assistant/app-support/db/hb-personal-assistant.sqlite"
WORKSPACE = "/volume2/personal-assistant/app-support/mcp-workspace/db/hb-personal-assistant.sqlite"
SNAPSHOT = "/volume2/personal-assistant/app-support/mcp-snapshot/db/hb-personal-assistant.sqlite"


@pytest.fixture
def nas(monkeypatch):
    monkeypatch.setenv("HB_NAS_RUNTIME", "1")
    monkeypatch.delenv("HB_ASSISTANT_WORKSPACE_DB", raising=False)
    monkeypatch.delenv("HB_ASSISTANT_SNAPSHOT_DB", raising=False)


def test_prove_red_legacy_classifier_cannot_distinguish_nas_paths(nas):
    # The motivating defect: the locality classifier returns the SAME label for all three, so it
    # cannot be used to tell managed from workspace/snapshot for authorization decisions.
    assert g.classify_db_storage(MANAGED) == "nas_local"
    assert g.classify_db_storage(WORKSPACE) == "nas_local"
    assert g.classify_db_storage(SNAPSHOT) == "nas_local"


def test_storage_class_distinguishes_the_three_nas_paths(nas):
    assert g.classify_storage_class(MANAGED) == SC.MANAGED_PRODUCTION
    assert g.classify_storage_class(WORKSPACE) == SC.ISOLATED_WORKSPACE
    assert g.classify_storage_class(SNAPSHOT) == SC.READ_ONLY_SNAPSHOT


def test_workspace_shaped_path_is_never_managed(nas):
    assert g.classify_storage_class(WORKSPACE) is not SC.MANAGED_PRODUCTION


def test_snapshot_shaped_path_is_never_managed(nas):
    assert g.classify_storage_class(SNAPSHOT) is not SC.MANAGED_PRODUCTION


def test_env_configured_workspace_path_classifies_as_workspace(monkeypatch, tmp_path):
    monkeypatch.setenv("HB_NAS_RUNTIME", "1")
    ws = tmp_path / "mcp-workspace" / "db" / "hb-personal-assistant.sqlite"
    monkeypatch.setenv("HB_ASSISTANT_WORKSPACE_DB", str(ws))
    # Under NAS the tmp path is not an approved locality, but the storage-class classifier keys on
    # the configured workspace root regardless — proving it tracks the actual configured target.
    assert g.classify_storage_class(str(ws)) == SC.ISOLATED_WORKSPACE


def test_unknown_nas_path_fails_closed_to_blocked(nas):
    assert g.classify_storage_class(
        "/volume2/personal-assistant/app-support/other/db/hb-personal-assistant.sqlite"
    ) == SC.BLOCKED


def test_network_and_volumes_paths_blocked(monkeypatch):
    monkeypatch.delenv("HB_NAS_RUNTIME", raising=False)
    assert g.classify_storage_class("/Volumes/share/db.sqlite") == SC.BLOCKED
    assert g.classify_storage_class("smb://server/db.sqlite") == SC.BLOCKED
