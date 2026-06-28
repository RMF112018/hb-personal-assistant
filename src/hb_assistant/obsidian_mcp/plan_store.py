"""Durable local store for Obsidian MCP curation plans and apply receipts.

Plans produced by ``vault_curation_plan`` are persisted here so that
``vault_curation_apply`` can execute *only* a server-generated ``plan_id`` — no
crawl-and-mutate in one call, no arbitrary write instructions at apply time.
Storage mirrors ``oauth_store.py`` (atomic JSON writes with ``0o600`` perms)
and lives outside the repo under the macOS Application Support root.
"""

from __future__ import annotations

import json
import os
import re
import secrets
from contextlib import suppress
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

from hb_assistant.config.path_policy import PathPolicy

# ``curation_<utc-compact-stamp>_<hex>`` — also the on-disk filename stem, so the
# shape is validated before any path join to keep raw input out of the path.
_PLAN_ID_RE = re.compile(r"^curation_[0-9TZ]+_[0-9a-f]{12}$")


def plan_dir() -> Path:
    root = PathPolicy().get_app_support() / "analytics" / "obsidian_mcp" / "plans"
    root.mkdir(parents=True, exist_ok=True)
    return root


def new_plan_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"curation_{stamp}_{secrets.token_hex(6)}"


def is_valid_plan_id(plan_id: str) -> bool:
    return bool(_PLAN_ID_RE.match(plan_id or ""))


def _write(path: Path, data: dict[str, Any]) -> None:
    tmp = path.with_suffix(".tmp")
    tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
    os.replace(tmp, path)
    with suppress(OSError):
        path.chmod(0o600)


def _read(path: Path) -> dict[str, Any] | None:
    if not path.exists():
        return None
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return raw if isinstance(raw, dict) else None


def save_plan(plan: dict[str, Any]) -> None:
    plan_id = str(plan.get("plan_id", ""))
    if not is_valid_plan_id(plan_id):
        raise ValueError("invalid_plan_id")
    _write(plan_dir() / f"{plan_id}.json", plan)


def load_plan(plan_id: str) -> dict[str, Any] | None:
    if not is_valid_plan_id(plan_id):
        return None
    return _read(plan_dir() / f"{plan_id}.json")


def write_receipt(plan_id: str, receipt: dict[str, Any]) -> Path:
    if not is_valid_plan_id(plan_id):
        raise ValueError("invalid_plan_id")
    path = plan_dir() / f"{plan_id}.receipt.json"
    _write(path, receipt)
    return path


def load_receipt(plan_id: str) -> dict[str, Any] | None:
    if not is_valid_plan_id(plan_id):
        return None
    return _read(plan_dir() / f"{plan_id}.receipt.json")
