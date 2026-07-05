"""``ai_outputs_card_upsert`` — the single sanctioned remote write tool.

Creates/updates/appends a Markdown card **locked to the vault's AI Outputs folder**,
reusing the gated Obsidian write engine (SHA optimistic-concurrency, backup-before-
overwrite, mutation receipt). Any target outside the AI Outputs folder is refused.
"""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

from hb_assistant.obsidian_mcp import mutations
from hb_assistant.obsidian_mcp.tools import ObsidianMcpToolError

from .config import NasMcpConfig
from .obsidian_config import apply_obsidian_support_env, obsidian_config_from_nas

ALLOWED_CLIENTS = frozenset({"claude", "chatgpt", "grok", "local", "unknown"})
ALLOWED_MODES = frozenset({"create", "update", "append"})
MAX_TITLE_LEN = 120
MAX_REL_PATH_LEN = 200
MAX_BODY_BYTES = 262_144

_SLUG_STRIP = re.compile(r"[^A-Za-z0-9 _-]+")
_SLUG_WS = re.compile(r"\s+")


class AiOutputsError(ValueError):
    """Bounded failure for the AI Outputs write tool (surfaced as a broker deny)."""


def _slug(title: str) -> str:
    cleaned = _SLUG_STRIP.sub("", title).strip()
    return _SLUG_WS.sub(" ", cleaned).strip()


def _render_card(title: str, tags: list[str], source_client: str, body: str) -> str:
    tag_line = ", ".join(sorted({t.strip() for t in tags if t.strip()}))
    front = [
        "---",
        f"title: {title}",
        f"tags: [{tag_line}]",
        f"source_client: {source_client}",
        "hb_managed: ai_outputs_card",
        "---",
        "",
    ]
    return "\n".join(front) + body.rstrip() + "\n"


def ai_outputs_card_upsert(
    *,
    config: NasMcpConfig,
    title: str,
    body_markdown: str,
    tags: list[str] | None = None,
    source_client: str = "unknown",
    expected_sha: str | None = None,
    mode: str = "create",
) -> dict[str, Any]:
    if config.obsidian is None:
        raise AiOutputsError("obsidian_not_configured")
    if mode not in ALLOWED_MODES:
        raise AiOutputsError("invalid_mode")
    if source_client not in ALLOWED_CLIENTS:
        raise AiOutputsError("invalid_source_client")
    title = str(title).strip()
    if not title or len(title) > MAX_TITLE_LEN:
        raise AiOutputsError("invalid_title")
    slug = _slug(title)
    if not slug:
        raise AiOutputsError("invalid_title_slug")

    folder = str(config.obsidian.ai_outputs_folder).strip("/")
    if not folder:
        raise AiOutputsError("ai_outputs_folder_not_configured")
    rel_path = f"{folder}/{slug}.md"
    # Folder-lock + traversal guards (defense in depth on top of vault-root containment).
    if (
        ".." in rel_path
        or rel_path.startswith("/")
        or "\\" in rel_path
        or "\x00" in rel_path
        or len(rel_path) > MAX_REL_PATH_LEN
        or Path(rel_path).parts[0] != folder.split("/")[0]
    ):
        raise AiOutputsError("path_not_allowed")

    body = str(body_markdown)
    if len(body.encode("utf-8")) > MAX_BODY_BYTES:
        raise AiOutputsError("body_too_large")
    tag_list = [str(t) for t in (tags or [])]

    apply_obsidian_support_env(config)
    ob = obsidian_config_from_nas(config)
    common = {"caller_surface": "nas_mcp_ai_outputs", "tool_name": "ai_outputs_card_upsert", "principal_kind": source_client}

    try:
        if mode == "create":
            content = _render_card(title, tag_list, source_client, body)
            result = mutations.create_note(ob, path=rel_path, content=content, overwrite=False, **common)
        elif mode == "update":
            if not expected_sha:
                raise AiOutputsError("expected_sha_required_for_update")
            content = _render_card(title, tag_list, source_client, body)
            result = mutations.patch_note(ob, path=rel_path, content=content, expected_sha256=str(expected_sha), **common)
        else:  # append
            target = Path(str(ob.vault_root)) / rel_path
            if not target.is_file():
                # Nothing to append to — create the card.
                content = _render_card(title, tag_list, source_client, body)
                result = mutations.create_note(ob, path=rel_path, content=content, overwrite=False, **common)
            else:
                current_sha = mutations.sha256_file(target)
                if expected_sha and str(expected_sha) != current_sha:
                    raise AiOutputsError("sha256_mismatch")
                new_content = target.read_text(encoding="utf-8").rstrip() + "\n\n" + body.rstrip() + "\n"
                if len(new_content.encode("utf-8")) > MAX_BODY_BYTES:
                    raise AiOutputsError("body_too_large")
                result = mutations.patch_note(ob, path=rel_path, content=new_content, expected_sha256=current_sha, **common)
    except ObsidianMcpToolError as exc:
        raise AiOutputsError(str(getattr(exc, "code", exc))) from exc

    sha = str(result.get("sha256") or "")
    return {
        "status": "written",
        "mode": mode,
        "relative_path": rel_path,
        "path_display": f"vault/{rel_path}",
        "source_client": source_client,
        "created": bool(result.get("created")),
        "overwritten": bool(result.get("overwritten")),
        "sha256": sha,
        "sha256_prefix": sha[:12],
        "backup_path": bool(result.get("backup_path")),
    }
