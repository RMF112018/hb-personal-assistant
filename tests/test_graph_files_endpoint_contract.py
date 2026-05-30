"""Phase 06 (Files) — static validation of the Graph files endpoint contract.

Mirrors tests/test_graph_mail_endpoint_contract.py: asserts the repo-native YAML
resources authored in Prompt 01 encode a GET-only read allowlist, a complete
mutation blocklist, content-free metadata selection, and a never-persist set that
covers the short-lived download URL, tokens, and raw delta/next links.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from hb_assistant.config.path_policy import PathPolicy

_CONFIG_DIR = PathPolicy().resolve_repo_root() / "resources" / "config"
_ALLOWLIST_PATH = _CONFIG_DIR / "graph_files_read_endpoint_allowlist.yaml"
_BLOCKLIST_PATH = _CONFIG_DIR / "graph_files_mutation_endpoint_blocklist.yaml"
_METADATA_PATH = _CONFIG_DIR / "graph_files_drive_item_metadata_field_contract.yaml"


def _load(path: Path) -> dict:
    assert path.exists(), f"Expected Phase 06 files contract resource at {path}"
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict), f"{path} must contain a top-level mapping"
    return data


def _allow_paths(data: dict) -> list[str]:
    out: list[str] = []
    for e in data.get("allowed_paths", []):
        out.append(e if isinstance(e, str) else e["path"])
    return out


def _block_paths(data: dict) -> list[str]:
    out: list[str] = []
    for e in data.get("forbidden_paths", []):
        out.append(e if isinstance(e, str) else e["path"])
    return out


def test_read_allowlist_is_get_only():
    data = _load(_ALLOWLIST_PATH)
    assert data["allowed_methods"] == ["GET"]
    assert data.get("permission_tightening") == "deferred"


def test_read_allowlist_covers_repo_confirmed_endpoints():
    paths = _allow_paths(_load(_ALLOWLIST_PATH))
    # Endpoints the resolver/crawler/client actually call must be allowlisted.
    for required in (
        "/me/drive",
        "/sites/{siteId}/drives",
        "/sites/{siteId}/pages",
        "/drives/{driveId}/root/delta",
        "/me/drive/root/delta",
        "/drives/{driveId}/items/{itemId}/delta",
    ):
        assert required in paths, f"{required} missing from files read allowlist"


def test_read_allowlist_metadata_select_is_content_free():
    data = _load(_ALLOWLIST_PATH)
    select = {f.lower() for f in data.get("drive_item_metadata_select", [])}
    assert "content" not in select
    assert "@microsoft.graph.downloadurl" not in select
    assert {"id", "name", "size"}.issubset(select)


def test_read_allowlist_paging_does_not_parse_skip_token():
    paging = _load(_ALLOWLIST_PATH)["paging"]
    assert paging["follow"] == "@odata.nextLink"
    assert paging["do_not_parse_skip_token"] is True


def test_read_allowlist_delta_routes_stale_token_to_rebaseline():
    delta = _load(_ALLOWLIST_PATH)["delta"]
    assert delta["stale_token_status"] == 410
    assert delta["on_stale_token"] == "requires_rebaseline"
    assert delta["never_render_raw_delta_links"] is True


def test_blocklist_forbids_all_write_verbs():
    data = _load(_BLOCKLIST_PATH)
    assert set(data["forbidden_methods"]) == {"POST", "PUT", "PATCH", "DELETE"}


def test_blocklist_covers_mutation_keywords():
    keywords = {k.lower() for k in _load(_BLOCKLIST_PATH)["forbidden_operation_keywords"]}
    for required in (
        "upload",
        "createuploadsession",
        "createlink",
        "invite",
        "copy",
        "move",
        "checkout",
        "checkin",
        "discardcheckout",
        "permissions",
        "delete",
        "restore",
        "retentionlabel",
        "sensitivitylabel",
    ):
        assert required in keywords, f"{required} missing from files mutation keywords"


def test_blocklist_forbids_upload_and_share_paths():
    paths = _block_paths(_load(_BLOCKLIST_PATH))
    assert any(p.endswith("/content") for p in paths)  # PUT upload/replace
    assert any(p.endswith("/createUploadSession") for p in paths)
    assert any(p.endswith("/createLink") for p in paths)
    assert any(p.endswith("/permissions") for p in paths)


def test_metadata_contract_never_persists_download_url_tokens_and_raw_links():
    never = {n.lower() for n in _load(_METADATA_PATH)["never_persist"]}
    assert "@microsoft.graph.downloadurl" in never
    assert "authorization" in never
    assert "access_token" in never
    assert "refresh_token" in never
    assert "@odata.deltalink" in never
    assert "@odata.nextlink" in never
