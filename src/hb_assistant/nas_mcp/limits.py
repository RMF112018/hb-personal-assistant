"""Rate limits / abuse containment for the NAS MCP surface.

The existing per-call bounds (response bytes, DB rows, excerpt/search caps, card size) are
kept as the enforcement mechanism — this module makes their *values* env-overridable
(``HB_MCP_MAX_*``) and operator-override-aware (raise-only, see ``overrides.py``), and adds
the genuinely new controls the remote surface needs: a per-window AI-Outputs write limiter
and a concurrent-call cap. Every limit fails closed and is audited; none leak content.

Effective limits are resolved once at the broker boundary into a config copy, so the deep
read/write paths automatically honor env + override values without threading auth through
every function.
"""

from __future__ import annotations

import dataclasses
import json
import os
import threading
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

from .config import NasMcpConfig
from .overrides import (
    SCOPE_CARD_SIZE,
    SCOPE_FILE_EXCERPT,
    SCOPE_RESPONSE_SIZE,
    SCOPE_ROWS,
    SCOPE_SEARCH_RESULTS,
    SCOPE_TIMEOUT,
    SCOPE_WRITE_COUNT,
    OverrideStore,
)

# Deny reason classes (audited; returned as structured errors — never leak content).
DENY_WRITE_RATE = "write_rate_exceeded"
DENY_WRITE_STATE = "write_rate_state_unavailable"
DENY_CONCURRENCY = "too_many_concurrent_calls"


class WriteWindowStateError(RuntimeError):
    """The AI-Outputs write-window receipt state exists but cannot be read/parsed. The write
    limiter treats this as fail-closed (deny) — a missing file on a clean first run does NOT
    raise this (it counts as zero)."""

# scope -> (env var, NasMcpConfig attribute, hard default). Each config attr feeds the
# existing enforcement site; the env var overrides it; an operator override raises it.
_LIMIT_REGISTRY: dict[str, tuple[str, str, int]] = {
    SCOPE_RESPONSE_SIZE: ("HB_MCP_MAX_RESPONSE_BYTES", "max_response_bytes", 256_000),
    SCOPE_FILE_EXCERPT: ("HB_MCP_MAX_FILE_EXCERPT_BYTES", "max_excerpt_bytes", 16_384),
    SCOPE_SEARCH_RESULTS: ("HB_MCP_MAX_SEARCH_RESULTS", "max_search_results", 50),
    SCOPE_ROWS: ("HB_MCP_MAX_ROWS", "max_db_rows", 100),
    SCOPE_CARD_SIZE: ("HB_MCP_MAX_CARD_BYTES", "max_card_bytes", 262_144),
    SCOPE_WRITE_COUNT: ("HB_MCP_MAX_AI_OUTPUTS_WRITES_PER_WINDOW", "max_ai_outputs_writes_per_window", 20),
    SCOPE_TIMEOUT: ("HB_MCP_TOOL_TIMEOUT_SECONDS", "tool_timeout_seconds", 30),
}

# Config attributes whose effective (env+override) values are baked into the per-request
# config copy so the deep enforcement paths honor them.
_EFFECTIVE_CONFIG_SCOPES = (
    SCOPE_RESPONSE_SIZE,
    SCOPE_FILE_EXCERPT,
    SCOPE_SEARCH_RESULTS,
    SCOPE_ROWS,
    SCOPE_CARD_SIZE,
)


def _env_int(name: str) -> int | None:
    raw = os.environ.get(name)
    if raw is None or not raw.strip():
        return None
    try:
        return int(raw.strip())
    except ValueError:
        return None


def resolve_int_limit(scope: str, config: NasMcpConfig) -> int:
    """Base limit for a scope: env override > config value > hard default."""
    env_name, attr, default = _LIMIT_REGISTRY[scope]
    env_val = _env_int(env_name)
    if env_val is not None and env_val > 0:
        return env_val
    return int(getattr(config, attr, default) or default)


def write_window_seconds(config: NasMcpConfig) -> int:
    env_val = _env_int("HB_MCP_WRITE_WINDOW_SECONDS")
    if env_val is not None and env_val > 0:
        return env_val
    return int(getattr(config, "write_window_seconds", 3600) or 3600)


def max_concurrent_calls(config: NasMcpConfig) -> int:
    env_val = _env_int("HB_MCP_MAX_CONCURRENT_CALLS")
    if env_val is not None and env_val > 0:
        return env_val
    return int(getattr(config, "max_concurrent_calls", 8) or 8)


def effective_limit(
    scope: str,
    config: NasMcpConfig,
    client_label: str,
    override_store: OverrideStore | None = None,
    tool_name: str | None = None,
) -> tuple[int, str | None]:
    """(value, override_id). An operator override can only RAISE the base, never lower it."""
    base = resolve_int_limit(scope, config)
    if override_store is None:
        return base, None
    active = override_store.active(scope, client_label, tool_name)
    if active is not None and active.max_value > base:
        return active.max_value, active.override_id
    return base, None


def apply_effective_limits(
    config: NasMcpConfig, client_label: str, override_store: OverrideStore | None
) -> tuple[NasMcpConfig, list[str]]:
    """Return a config copy with size/row/search/card limits set to their effective (env +
    raise-only override) values, plus the override ids that applied."""
    updates: dict[str, Any] = {}
    applied: list[str] = []
    for scope in _EFFECTIVE_CONFIG_SCOPES:
        _env, attr, _default = _LIMIT_REGISTRY[scope]
        value, override_id = effective_limit(scope, config, client_label, override_store)
        updates[attr] = value
        if override_id:
            applied.append(override_id)
    return dataclasses.replace(config, **updates), applied


# ---------------------------------------------------------------- write-window limiter


def _mutations_path(config: NasMcpConfig) -> Path | None:
    env = os.environ.get("HB_OBSIDIAN_MCP_SUPPORT_DIR", "").strip()
    if env:
        return Path(env) / "mutations.jsonl"
    if config.obsidian is not None:
        return Path(config.obsidian.support_dir) / "mutations.jsonl"
    return None


def _now() -> datetime:
    return datetime.now(UTC)


def recent_ai_outputs_write_count(config: NasMcpConfig, window_seconds: int) -> int:
    """Count APPLIED AI-Outputs writes in mutations.jsonl within the trailing window.

    Fail-closed for the write limiter: a **missing** file (clean first run) counts as 0, but
    an **existing-but-unreadable** file, an **unresolvable** receipt location, or a
    **corrupt/unparseable** line raises ``WriteWindowStateError`` — skipping a bad line could
    undercount (an in-window write we can't classify) and silently break the window guarantee.
    """
    path = _mutations_path(config)
    if path is None:
        raise WriteWindowStateError("receipt_location_unresolved")
    if not path.exists():
        return 0  # clean first run — no receipts yet
    try:
        text = path.read_text(encoding="utf-8")
    except OSError as exc:
        raise WriteWindowStateError("receipt_file_unreadable") from exc
    cutoff = _now() - timedelta(seconds=window_seconds)
    count = 0
    for line in text.splitlines():
        if not line.strip():
            continue
        try:
            rec = json.loads(line)
        except json.JSONDecodeError as exc:
            # A corrupt line could be an in-window AI-Outputs write we can't identify;
            # skipping it would risk exceeding the window. Fail closed instead.
            raise WriteWindowStateError("receipt_file_corrupt") from exc
        if rec.get("caller_surface") != "nas_mcp_ai_outputs":
            continue
        if rec.get("status") not in (None, "applied"):
            continue
        ts = rec.get("timestamp")
        if not ts:
            continue
        try:
            when = datetime.fromisoformat(str(ts))
        except ValueError:
            continue
        if when.tzinfo is None:
            when = when.replace(tzinfo=UTC)
        if when >= cutoff:
            count += 1
    return count


def check_write_window(
    config: NasMcpConfig, client_label: str, override_store: OverrideStore | None = None
) -> dict[str, Any]:
    """{allowed, count, limit, window_seconds, override_id, reason}. Fails closed both at the
    limit (``write_rate_exceeded``) and when receipt state is unreadable/corrupt
    (``write_rate_state_unavailable``). ``reason`` is None when allowed."""
    window = write_window_seconds(config)
    limit, override_id = effective_limit(SCOPE_WRITE_COUNT, config, client_label, override_store)
    try:
        count = recent_ai_outputs_write_count(config, window)
    except WriteWindowStateError:
        return {
            "allowed": False,
            "count": None,
            "limit": limit,
            "window_seconds": window,
            "override_id": override_id,
            "reason": DENY_WRITE_STATE,
        }
    allowed = count < limit
    return {
        "allowed": allowed,
        "count": count,
        "limit": limit,
        "window_seconds": window,
        "override_id": override_id,
        "reason": None if allowed else DENY_WRITE_RATE,
    }


# ---------------------------------------------------------------- concurrency limiter


class ConcurrencyLimiter:
    """Thread-safe in-flight call cap. Best-effort under the uvicorn threading model."""

    def __init__(self, max_calls: int) -> None:
        self._max = max(1, int(max_calls))
        self._lock = threading.Lock()
        self._in_flight = 0

    def try_acquire(self) -> bool:
        with self._lock:
            if self._in_flight >= self._max:
                return False
            self._in_flight += 1
            return True

    def release(self) -> None:
        with self._lock:
            if self._in_flight > 0:
                self._in_flight -= 1

    @property
    def in_flight(self) -> int:
        with self._lock:
            return self._in_flight
