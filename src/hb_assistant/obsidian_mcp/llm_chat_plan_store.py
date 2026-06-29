"""Durable local store for LLM chat memory plans and apply receipts."""

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

_PLAN_ID_RE = re.compile(r"^llm_chat_[0-9TZ]+_[0-9a-f]{12}$")


def plan_dir() -> Path:
    root = PathPolicy().get_app_support() / "analytics" / "obsidian_mcp" / "llm_chat_plans"
    root.mkdir(parents=True, exist_ok=True)
    return root


def new_plan_id() -> str:
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return f"llm_chat_{stamp}_{secrets.token_hex(6)}"


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


def list_plans(limit: int = 20) -> list[dict[str, Any]]:
    root = plan_dir()
    entries: list[tuple[str, dict[str, Any]]] = []
    for path in root.glob("llm_chat_*.json"):
        if path.name.endswith(".receipt.json"):
            continue
        plan = _read(path)
        if plan is None:
            continue
        entries.append((str(plan.get("created_at", "")), plan))
    entries.sort(key=lambda item: item[0], reverse=True)
    return [plan for _, plan in entries[:limit]]


def plan_count() -> int:
    return len([p for p in plan_dir().glob("llm_chat_*.json") if not p.name.endswith(".receipt.json")])
