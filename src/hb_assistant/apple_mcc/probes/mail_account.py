"""Apple Mail account resolution (exact name locator)."""

from __future__ import annotations

import json
import subprocess
from collections.abc import Callable, Sequence
from typing import Any

from hb_assistant.apple_mcc.probes.status import ProbeResult, ProbeState

# Operator override: exact Mail account name (source locator only — not product brand).
DEFAULT_MAIL_ACCOUNT_NAME = "BF-Personal"

_JXA_LIST_ACCOUNTS = """
function run() {
  var Mail = Application("Mail");
  var out = [];
  var accounts = Mail.accounts();
  for (var i = 0; i < accounts.length; i++) {
    var a = accounts[i];
    out.push({name: String(a.name()), id: String(a.id())});
  }
  return JSON.stringify(out);
}
"""


def list_mail_accounts_via_jxa(
    runner: Callable[[Sequence[str]], subprocess.CompletedProcess[str]] | None = None,
) -> list[dict[str, str]]:
    """Enumerate Mail accounts via JXA. Injectable for tests."""
    run = runner or (
        lambda argv: subprocess.run(list(argv), capture_output=True, text=True, check=False)
    )
    proc = run(["osascript", "-l", "JavaScript", "-e", _JXA_LIST_ACCOUNTS])
    if proc.returncode != 0:
        raise RuntimeError(f"mail_jxa_failed rc={proc.returncode} err={proc.stderr!r}")
    data = json.loads(proc.stdout or "[]")
    if not isinstance(data, list):
        raise RuntimeError("mail_jxa_invalid_payload")
    out: list[dict[str, str]] = []
    for item in data:
        if isinstance(item, dict) and "name" in item:
            out.append({"name": str(item["name"]), "id": str(item.get("id", ""))})
    return out


def resolve_mail_account(
    *,
    expected_name: str = DEFAULT_MAIL_ACCOUNT_NAME,
    accounts: Sequence[dict[str, Any]] | None = None,
    runner: Callable[[Sequence[str]], subprocess.CompletedProcess[str]] | None = None,
) -> ProbeResult:
    """Resolve exactly one Mail account whose name equals ``expected_name`` (case-sensitive)."""
    try:
        items = list(accounts) if accounts is not None else list_mail_accounts_via_jxa(runner)
    except Exception as exc:  # noqa: BLE001
        return ProbeResult(
            domain="mail",
            state=ProbeState.ERROR,
            detail=f"enumeration_failed:{exc}",
        )
    names = [str(a.get("name", "")) for a in items]
    matches = [n for n in names if n == expected_name]
    if len(matches) == 1:
        return ProbeResult(
            domain="mail",
            state=ProbeState.OK,
            detail="exact_match",
            selected=expected_name,
            candidates=tuple(names),
            metadata={"expected_name": expected_name},
        )
    if len(matches) == 0:
        return ProbeResult(
            domain="mail",
            state=ProbeState.MISSING,
            detail=f"no_account_named:{expected_name}",
            candidates=tuple(names),
            metadata={"expected_name": expected_name},
        )
    return ProbeResult(
        domain="mail",
        state=ProbeState.AMBIGUOUS,
        detail=f"multiple_accounts_named:{expected_name}",
        candidates=tuple(names),
        metadata={"expected_name": expected_name, "match_count": len(matches)},
    )
