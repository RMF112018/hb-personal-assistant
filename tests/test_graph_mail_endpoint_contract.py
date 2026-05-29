"""Phase 06 Prompt 01 — Graph mail endpoint contract resource validation.

Static-resource guardrail test (no runtime loader yet; the Pydantic loader +
HTTP-guard wiring land in Phase 06 Prompt 04). Asserts that the read allowlist
and mutation blocklist YAML resources hold the read-only invariants:

- read allowlist is GET-only;
- message $select never requests full ``body``;
- attachment $select never requests ``contentBytes`` (Graph returns it by default);
- the immutable-ID Prefer header is declared;
- mutation blocklist forbids all write verbs and the send/raw-content paths.
"""

from __future__ import annotations

from pathlib import Path

import yaml

from hb_assistant.config.path_policy import PathPolicy

_CONFIG_DIR = PathPolicy().resolve_repo_root() / "resources" / "config"
_ALLOWLIST_PATH = _CONFIG_DIR / "graph_mail_read_endpoint_allowlist.yaml"
_BLOCKLIST_PATH = _CONFIG_DIR / "graph_mail_mutation_endpoint_blocklist.yaml"


def _load(path: Path) -> dict:
    assert path.exists(), f"Expected Phase 06 mail contract resource at {path}"
    with path.open("r", encoding="utf-8") as f:
        data = yaml.safe_load(f)
    assert isinstance(data, dict), f"{path} must contain a top-level mapping"
    return data


def test_read_allowlist_is_get_only() -> None:
    data = _load(_ALLOWLIST_PATH)
    assert data["allowed_methods"] == ["GET"]


def test_read_allowlist_message_select_excludes_full_body() -> None:
    data = _load(_ALLOWLIST_PATH)
    select = data["message_metadata_select"]
    assert "bodyPreview" in select, "metadata-first workflow needs bodyPreview"
    assert "body" not in select, "full body must never be requested by default"


def test_read_allowlist_attachment_select_excludes_content_bytes() -> None:
    data = _load(_ALLOWLIST_PATH)
    select = data["attachment_metadata_select"]
    # Graph returns contentBytes by default when listing attachments; the
    # metadata-only $select must omit it to avoid downloading attachment content.
    assert "contentBytes" not in select
    assert {"id", "name", "contentType", "size"}.issubset(set(select))


def test_read_allowlist_declares_immutable_id_header() -> None:
    data = _load(_ALLOWLIST_PATH)
    assert any("ImmutableId" in h for h in data["prefer_headers"])


def test_read_allowlist_paging_does_not_parse_skip_token() -> None:
    data = _load(_ALLOWLIST_PATH)
    paging = data["paging"]
    assert paging["follow"] == "@odata.nextLink"
    assert paging["do_not_parse_skip_token"] is True
    assert paging["max_top"] == 1000


def test_blocklist_forbids_all_write_verbs() -> None:
    data = _load(_BLOCKLIST_PATH)
    assert data["forbidden_methods"] == ["POST", "PATCH", "DELETE", "PUT"]


def test_blocklist_forbids_send_and_raw_attachment_content() -> None:
    data = _load(_BLOCKLIST_PATH)
    paths = data["forbidden_paths"]
    assert "/me/sendMail" in paths
    assert any(p.endswith("/$value") for p in paths), "raw attachment content path must be blocked"


def test_blocklist_covers_mutation_keywords() -> None:
    data = _load(_BLOCKLIST_PATH)
    keywords = set(data["forbidden_operation_keywords"])
    for kw in ("send", "forward", "reply", "delete", "move", "copy", "markRead", "categorize", "flag"):
        assert kw in keywords
    assert "before HTTP request" in data["on_match"]
