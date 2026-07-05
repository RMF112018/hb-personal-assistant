"""Operator-scoped temporary limit overrides for the NAS MCP surface.

Lets the operator (Bobby) intentionally raise a specific limit for a specific client/tool for
a bounded time — WITHOUT giving remote LLMs any way to relax limits. Creation/revocation is
local/operator-only (``override_cli.py``); there is deliberately **no MCP tool** that mints
or approves an override, so remote self-approval is structurally impossible. Overrides are:

* narrow (per scope, per client, optionally per tool),
* **raise-only** — an override can only increase a limit, never lower it,
* **always expiring** — no indefinite overrides,
* **reason-required**, revocable, and auditable.

Store is JSON at ``0600`` (atomic write), modeled on ``origin_auth.py``. Records contain no
secrets — an ``override_id`` is a public handle, not a credential.
"""

from __future__ import annotations

import contextlib
import json
import secrets
from dataclasses import dataclass
from datetime import UTC, datetime, timedelta
from pathlib import Path
from typing import Any

# Override scopes map 1:1 to the rate-limit scopes in limits.py.
SCOPE_RESPONSE_SIZE = "response_size"
SCOPE_FILE_EXCERPT = "file_excerpt"
SCOPE_SEARCH_RESULTS = "search_results"
SCOPE_ROWS = "rows"
SCOPE_CARD_SIZE = "card_size"
SCOPE_WRITE_COUNT = "write_count"
SCOPE_TIMEOUT = "timeout"
SCOPE_SPECIFIC_TOOL = "specific_tool"
KNOWN_SCOPES = frozenset(
    {
        SCOPE_RESPONSE_SIZE,
        SCOPE_FILE_EXCERPT,
        SCOPE_SEARCH_RESULTS,
        SCOPE_ROWS,
        SCOPE_CARD_SIZE,
        SCOPE_WRITE_COUNT,
        SCOPE_TIMEOUT,
        SCOPE_SPECIFIC_TOOL,
    }
)
CLIENT_ANY = "any"
STORE_VERSION = 1


class OverrideError(RuntimeError):
    """Override store operation failed."""


def _now() -> datetime:
    return datetime.now(UTC)


@dataclass(frozen=True)
class ActiveOverride:
    override_id: str
    scope: str
    max_value: int
    client_label: str
    tool_name: str | None


@dataclass
class OverrideStore:
    path: Path

    def _load(self) -> dict[str, Any]:
        if not self.path.is_file():
            return {"version": STORE_VERSION, "overrides": {}}
        try:
            data = json.loads(self.path.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError) as exc:
            raise OverrideError(f"override store unreadable: {exc}") from exc
        if not isinstance(data, dict) or not isinstance(data.get("overrides"), dict):
            raise OverrideError("override store malformed")
        return data

    def _save(self, data: dict[str, Any]) -> None:
        self.path.parent.mkdir(parents=True, exist_ok=True)
        tmp = self.path.with_suffix(self.path.suffix + ".tmp")
        tmp.write_text(json.dumps(data, indent=2, sort_keys=True), encoding="utf-8")
        with contextlib.suppress(OSError):
            tmp.chmod(0o600)
        tmp.replace(self.path)
        with contextlib.suppress(OSError):
            self.path.chmod(0o600)

    def create(
        self,
        *,
        scope: str,
        max_value: int,
        client_label: str,
        expires_minutes: int,
        reason: str,
        created_by: str,
        actor: str | None = None,
        tool_name: str | None = None,
    ) -> dict[str, Any]:
        if scope not in KNOWN_SCOPES:
            raise OverrideError(f"unknown scope '{scope}'; allowed: {sorted(KNOWN_SCOPES)}")
        if int(max_value) <= 0:
            raise OverrideError("max_value must be positive")
        if int(expires_minutes) <= 0:
            raise OverrideError("expires_minutes must be positive (no indefinite overrides)")
        if not (reason or "").strip():
            raise OverrideError("reason is required")
        if scope == SCOPE_SPECIFIC_TOOL and not tool_name:
            raise OverrideError("scope 'specific_tool' requires --tool")
        now = _now()
        expires = now + timedelta(minutes=int(expires_minutes))
        override_id = secrets.token_hex(8)
        record = {
            "override_id": override_id,
            "scope": scope,
            "max_value": int(max_value),
            "client_label": client_label or CLIENT_ANY,
            "actor": actor,
            "tool_name": tool_name,
            "reason": reason.strip(),
            "created_by": created_by,
            "created_ts": now.isoformat(),
            "expires_at": expires.isoformat(),
            "expires_ts": expires.timestamp(),
            "revoked": False,
            "audit_receipt_id": secrets.token_hex(8),
        }
        data = self._load()
        data["overrides"][override_id] = record
        self._save(data)
        return dict(record)

    def revoke(self, override_id: str) -> bool:
        data = self._load()
        rec = data["overrides"].get(override_id)
        if rec is None or rec.get("revoked"):
            return False
        rec["revoked"] = True
        rec["revoked_at"] = _now().isoformat()
        self._save(data)
        return True

    def list_overrides(self) -> list[dict[str, Any]]:
        return sorted(
            (dict(r) for r in self._load()["overrides"].values()),
            key=lambda r: r["created_ts"],
        )

    def _live(self) -> list[dict[str, Any]]:
        now_ts = _now().timestamp()
        return [
            r
            for r in self._load()["overrides"].values()
            if not r.get("revoked") and now_ts <= float(r.get("expires_ts", 0.0))
        ]

    def active(self, scope: str, client_label: str, tool_name: str | None = None) -> ActiveOverride | None:
        """Largest live override matching this scope + client (+ tool for specific_tool)."""
        matches = []
        for r in self._live():
            if r.get("scope") != scope:
                continue
            rec_client = r.get("client_label", CLIENT_ANY)
            if rec_client not in (CLIENT_ANY, client_label):
                continue
            if scope == SCOPE_SPECIFIC_TOOL and r.get("tool_name") != tool_name:
                continue
            matches.append(r)
        if not matches:
            return None
        best = max(matches, key=lambda r: int(r.get("max_value", 0)))
        return ActiveOverride(
            override_id=str(best["override_id"]),
            scope=scope,
            max_value=int(best["max_value"]),
            client_label=str(best.get("client_label", CLIENT_ANY)),
            tool_name=best.get("tool_name"),
        )

    def active_summary(self) -> dict[str, Any]:
        """Redacted, secret-free summary for status tools (counts + scope/client/expiry)."""
        live = self._live()
        return {
            "active_count": len(live),
            "active": [
                {
                    "override_id": r["override_id"],
                    "scope": r["scope"],
                    "max_value": r["max_value"],
                    "client_label": r.get("client_label", CLIENT_ANY),
                    "tool_name": r.get("tool_name"),
                    "expires_at": r.get("expires_at"),
                }
                for r in sorted(live, key=lambda r: r["expires_at"])
            ],
        }
