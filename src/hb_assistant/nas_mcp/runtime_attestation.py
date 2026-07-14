"""P1 §3.1 — execution-aware runtime tool-surface attestation.

Proves each server-policy-available tool can load schema, resolve through direct and/or gateway paths,
satisfy profile/dependency gates, and accept a bounded dry diagnostic invocation. Complements static
freshness (registry/manifest/gateway/classification) with reachability smoke tests.
"""

from __future__ import annotations

import time
from datetime import UTC, datetime
from typing import Any

from .broker import runtime_commit
from .capability_registry import (
    MATRIX_SHA256,
    definitions_for_profile,
    gateway_names_for_profile,
    resolve_profile,
)
from .config import NasMcpConfig
from .exposure_audit import _synthetic_args
from .live_tool_surface import build_live_tool_surface
from .tool_registration import register_nas_mcp_tools

_ATTESTATION_CACHE: dict[str, Any] = {
    "runtime_commit": None,
    "report": None,
    "last_successful_attestation": None,
}
_ATTESTATION_DEPTH = 0
_RECURSION_SAFE_TOOLS = frozenset({
    "hb_mcp_status",
    "pa_tool_surface_freshness_check",
    "pa_tool_surface_runtime_attestation",
})


def attestation_in_progress() -> bool:
    return _ATTESTATION_DEPTH > 0


def _iso_now() -> str:
    return datetime.now(UTC).replace(microsecond=0).isoformat()


def _attestation_age_seconds(last_success: str | None) -> int | None:
    if not last_success:
        return None
    try:
        ts = datetime.fromisoformat(last_success.replace("Z", "+00:00"))
        return max(0, int((datetime.now(UTC) - ts).total_seconds()))
    except ValueError:
        return None


def _build_surface_for_config(config: NasMcpConfig) -> tuple[Any, dict[str, Any]]:
    """Real FastMCP surface over the supplied config (same path clients use)."""
    from mcp.server.fastmcp import FastMCP  # noqa: PLC0415

    from .broker import NasMcpBroker  # noqa: PLC0415

    broker = NasMcpBroker(config)
    mcp = FastMCP("hb-nas-mcp", json_response=True, stateless_http=True)
    register_nas_mcp_tools(
        mcp,
        broker,
        capability_profile=getattr(config, "capability_profile", None),
    )
    tools = {t.name: t for t in mcp._tool_manager.list_tools()}
    return broker, tools


def _active_manifest_version(config: NasMcpConfig) -> int | None:
    try:
        from hb_assistant.obsidian_mcp.client_tool_manifest import ClientToolManifestRepository  # noqa: PLC0415

        active = ClientToolManifestRepository(str(config.db_path)).get_active()
        if active:
            return int(active["manifest_version"])
    except Exception:  # noqa: BLE001
        return None
    return None


def _backend_dependency_state(config: NasMcpConfig) -> dict[str, Any]:
    from .tool_registration import schema_index_frozen  # noqa: PLC0415

    db_ok = False
    try:
        config.db_path.stat()
        db_ok = True
    except OSError:
        db_ok = False
    roots_ok = bool(config.roots)
    return {
        "database_reachable": db_ok,
        "schema_index_frozen": schema_index_frozen(),
        "vault_roots_configured": roots_ok,
    }


def _invoke_with_timeout(fn: Any, *, timeout_s: float = 3.0) -> Any:
    from concurrent.futures import ThreadPoolExecutor, TimeoutError as FuturesTimeout  # noqa: PLC0415

    with ThreadPoolExecutor(max_workers=1) as pool:
        fut = pool.submit(fn)
        try:
            return fut.result(timeout=timeout_s)
        except FuturesTimeout as exc:
            raise TimeoutError(f"dry_diagnostic_timeout:{timeout_s}s") from exc


def _dry_invoke_ok(
    *,
    tool_name: str,
    broker: Any,
    live_tools: dict[str, Any],
    schema_index: dict[str, Any],
) -> tuple[bool, str, bool]:
    """Return (ok, note, no_fixture)."""
    schema: dict[str, Any] = {}
    live = live_tools.get(tool_name)
    if live is not None:
        schema = getattr(live, "parameters", None) or {}
    elif tool_name in schema_index:
        schema = schema_index[tool_name].get("parameters") or {}
    else:
        return False, "no_schema_for_dry_diagnostic", True

    if tool_name in _RECURSION_SAFE_TOOLS:
        return True, "skipped_dry_diagnostic_recursion_safe_status_tool", False

    args = _synthetic_args(schema)

    def _run() -> Any:
        if live is not None:
            return live.fn(**args)
        return broker.dispatch(tool_name, args)

    try:
        result = _invoke_with_timeout(_run)
        if isinstance(result, dict) and result.get("ok") is False:
            return True, f"reachable; fail-closed ({result.get('error_code', 'error')})", False
        return True, "bounded result via direct wrapper" if live else "bounded result via broker dispatch", False
    except ValueError as exc:
        return True, f"reachable; fail-closed on synthetic args ({str(exc)[:40]})", False
    except OSError as exc:
        return True, f"reachable; environment path unavailable ({str(exc)[:40]})", False
    except TimeoutError as exc:
        return False, str(exc), False
    except Exception as exc:  # noqa: BLE001
        return False, f"UNEXPECTED: {type(exc).__name__}: {str(exc)[:60]}", False


def _gateway_alias_parity(
    broker: Any,
    live_tools: dict[str, Any],
    schema_index: dict[str, Any],
    profile_definitions: tuple[Any, ...],
    gateway: frozenset[str],
) -> dict[str, Any]:
    mismatches: list[str] = []
    checked = 0
    ok = 0
    for definition in profile_definitions:
        if not definition.is_alias:
            continue
        alias = definition.registered_name
        canonical = definition.alias_target
        if canonical is None:
            mismatches.append(f"{alias}:missing_target")
            continue
        checked += 1
        alias_in_gw = alias in gateway
        canon_in_gw = canonical in gateway
        if not alias_in_gw or not canon_in_gw:
            mismatches.append(f"{alias}<->{canonical}:allowlist")
            continue
        alias_ok, _, _ = _dry_invoke_ok(
            tool_name=alias, broker=broker, live_tools=live_tools, schema_index=schema_index,
        )
        canon_ok, _, _ = _dry_invoke_ok(
            tool_name=canonical, broker=broker, live_tools=live_tools, schema_index=schema_index,
        )
        if alias_ok and canon_ok:
            ok += 1
        else:
            mismatches.append(f"{alias}<->{canonical}:invoke")
    return {
        "alias_pairs_checked": checked,
        "alias_pairs_ok": ok,
        "mismatches": mismatches,
    }


def build_runtime_attestation(config: NasMcpConfig) -> dict[str, Any]:
    """Run execution-aware attestation for every server-policy-available tool."""
    global _ATTESTATION_DEPTH  # noqa: PLW0603

    _ATTESTATION_DEPTH += 1
    try:
        return _build_runtime_attestation_body(config)
    finally:
        _ATTESTATION_DEPTH -= 1


def _build_runtime_attestation_body(config: NasMcpConfig) -> dict[str, Any]:
    from .tool_registration import live_tool_schema_index  # noqa: PLC0415

    started = time.monotonic()
    commit = runtime_commit()
    broker, live_tools = _build_surface_for_config(config)
    selected_profile = resolve_profile(getattr(config, "capability_profile", None))
    profile_definitions = definitions_for_profile(selected_profile)
    gateway = gateway_names_for_profile(selected_profile)
    surface = build_live_tool_surface(config)
    schema_index = live_tool_schema_index()
    deps = _backend_dependency_state(config)

    per_tool: list[dict[str, Any]] = []
    passed = failed = skipped = no_fixture = 0
    tested = 0

    alias_skip = {item.registered_name for item in profile_definitions if item.is_alias}
    for name in sorted(surface):
        st = surface[name]
        if name in alias_skip:
            skipped += 1
            per_tool.append({
                "tool_name": name,
                "status": "skipped",
                "schema_load": name in live_tools or name in schema_index,
                "direct_discoverable": st.directly_exposed,
                "gateway_resolves": st.gateway_allowlisted,
                "dependency_available": st.profile_enabled,
                "dry_diagnostic": False,
                "notes": "gateway_alias_covered_by_parity_check",
            })
            continue
        if not st.server_policy_available:
            skipped += 1
            per_tool.append({
                "tool_name": name,
                "status": "skipped",
                "schema_load": False,
                "direct_discoverable": st.directly_exposed,
                "gateway_resolves": st.gateway_allowlisted,
                "dependency_available": st.profile_enabled,
                "dry_diagnostic": False,
                "notes": st.surface_blocked_reason or "not_server_policy_available",
            })
            continue

        tested += 1
        schema_load = name in live_tools or name in schema_index
        direct_disc = st.directly_exposed
        gateway_resolves = (not st.gateway_allowlisted) or (name in gateway)
        dependency_ok = st.profile_enabled and deps["database_reachable"] and deps["schema_index_frozen"]

        dry_ok, dry_note, is_no_fixture = _dry_invoke_ok(
            tool_name=name,
            broker=broker,
            live_tools=live_tools,
            schema_index=schema_index,
        )
        if is_no_fixture:
            no_fixture += 1

        checks = [schema_load, gateway_resolves, dependency_ok, dry_ok]
        if direct_disc:
            checks.append(direct_disc)

        status = "passed" if all(checks) else "failed"
        if status == "passed":
            passed += 1
        else:
            failed += 1

        per_tool.append({
            "tool_name": name,
            "status": status,
            "schema_load": schema_load,
            "direct_discoverable": direct_disc,
            "gateway_resolves": gateway_resolves,
            "dependency_available": dependency_ok,
            "dry_diagnostic": dry_ok,
            "notes": dry_note,
        })

    parity = _gateway_alias_parity(broker, live_tools, schema_index, profile_definitions, gateway)
    manifest_version = _active_manifest_version(config)
    all_passed = failed == 0 and tested > 0
    now_iso = _iso_now()
    last_success = _ATTESTATION_CACHE.get("last_successful_attestation")
    if all_passed:
        last_success = now_iso

    client_writes_blocked = failed > 0 or not all_passed

    report = {
        "generated_by": "runtime-tool-surface-attestation",
        "runtime_commit": commit,
        "capability_profile": selected_profile.value,
        "capability_matrix_sha256": MATRIX_SHA256,
        "registered_tool_count": len(live_tools),
        "profile_definition_count": len(profile_definitions),
        "gateway_allowlist_count": len(gateway),
        "manifest_version": manifest_version,
        "tested_tool_count": tested,
        "passed_count": passed,
        "failed_count": failed,
        "skipped_count": skipped,
        "no_fixture_count": no_fixture,
        "per_tool": per_tool,
        "backend_dependency_state": deps,
        "direct_gateway_parity": parity,
        "last_successful_attestation": last_success,
        "attestation_age_seconds": _attestation_age_seconds(last_success),
        "client_writes_must_be_blocked": client_writes_blocked,
        "attestation_ok": all_passed,
        "elapsed_ms": int((time.monotonic() - started) * 1000),
    }

    _ATTESTATION_CACHE["runtime_commit"] = commit
    _ATTESTATION_CACHE["report"] = report
    if all_passed:
        _ATTESTATION_CACHE["last_successful_attestation"] = now_iso
    return report


def attestation_summary_for_freshness(config: NasMcpConfig, *, refresh: bool = True) -> dict[str, Any]:
    """Return attestation fields for freshness/status; refresh when commit changes or cache empty."""
    if attestation_in_progress():
        cached = _ATTESTATION_CACHE.get("report")
        if cached:
            return {
                "attestation_ok": cached.get("attestation_ok", False),
                "failed_count": cached.get("failed_count", 0),
                "tested_tool_count": cached.get("tested_tool_count", 0),
                "last_successful_attestation": cached.get("last_successful_attestation"),
                "attestation_age_seconds": cached.get("attestation_age_seconds"),
                "client_writes_must_be_blocked": cached.get("client_writes_must_be_blocked", True),
                "report": cached,
            }
        return {
            "attestation_ok": None,
            "failed_count": None,
            "tested_tool_count": None,
            "last_successful_attestation": _ATTESTATION_CACHE.get("last_successful_attestation"),
            "attestation_age_seconds": _attestation_age_seconds(
                _ATTESTATION_CACHE.get("last_successful_attestation")
            ),
            "client_writes_must_be_blocked": None,
            "report": None,
        }

    commit = runtime_commit()
    cached = _ATTESTATION_CACHE.get("report")
    if (
        refresh
        or cached is None
        or _ATTESTATION_CACHE.get("runtime_commit") != commit
    ):
        cached = build_runtime_attestation(config)
    return {
        "attestation_ok": cached.get("attestation_ok", False),
        "failed_count": cached.get("failed_count", 0),
        "tested_tool_count": cached.get("tested_tool_count", 0),
        "last_successful_attestation": cached.get("last_successful_attestation"),
        "attestation_age_seconds": cached.get("attestation_age_seconds"),
        "client_writes_must_be_blocked": cached.get("client_writes_must_be_blocked", True),
        "report": cached,
    }
