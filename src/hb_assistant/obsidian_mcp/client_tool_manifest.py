"""N8C-23 Client Tool Operating Manifest — the connected-client control-plane routing guide.

Classifies every exposed tool (purpose / safety / read-write class), carries workflow recipes, a
preferred-tool replacement map, negative instructions, and freshness/checksum/review-cadence fields.
Regenerating + WRITING it to ``99 System/Manifests`` follows a staged-review pattern (stage a diff → a
server-minted operator approval + receipt to materialize). Silent rewrite is prohibited.
"""

from __future__ import annotations

import json
from typing import Any

from hb_assistant.store.connection import (
    borrow_connection,
    db_readonly,
    open_connection,
    transaction,
)

from .artifact_workspace import ArtifactWorkspaceError, _cjson, _insert, _now, _sha

REVIEW_CADENCE = "tool_surface: on_change; routing: weekly; safety: on_tool_surface_change; operator: monthly"

# Compatibility projection of the preflight WORKFLOWS seed (not an independent authoring list).
# Authority: workflow_recipe_manifest.WORKFLOWS (routing) + canonical_tool_specs.replacement_map.
# Public contract: WORKFLOW_RECIPES is a **list** of recipe dicts with key ``workflow_name``
# (stable for rendering, stage_refresh, and pa_tool_manifest_workflow_get).

CLIENT_PROJECTION_SCHEMA_VERSION = 1
# Fixed vault write bound (characters) for client-tool operating manifest MD/JSON under
# 99 System/Manifests. Must not be payload-driven. Aligns with Obsidian max_write_chars default.
MAX_VAULT_MANIFEST_CHARS = 120_000


def project_workflow_for_client(w: dict[str, Any]) -> dict[str, Any]:
    """Project one authoritative WORKFLOWS record into the public client-recipe shape."""
    fr = w.get("failure_recovery") or ""
    return {
        "workflow_name": w["workflow_id"],
        "trigger_phrases": list(w.get("trigger_phrases") or []),
        "description": w.get("when_to_use") or "",
        "tool_sequence": list(w.get("tool_sequence") or []),
        "required_operator_approval_points": list(w.get("additional_approval_points") or []),
        "negative_instructions": list(w.get("must_not_use") or []),
        "expected_outputs": list(w.get("expected_outputs") or []),
        "failure_recovery": [fr] if isinstance(fr, str) and fr else list(fr or []),
    }


def _workflow_recipes_from_routing() -> list[dict[str, Any]]:
    """List projection of WORKFLOWS where publish_to_client_manifest is True (deterministic order)."""
    from .workflow_recipe_manifest import WORKFLOWS  # noqa: PLC0415

    published = [w for w in WORKFLOWS if w.get("publish_to_client_manifest")]
    # Stable order by workflow_id for deterministic checksums.
    published.sort(key=lambda w: w["workflow_id"])
    return [project_workflow_for_client(w) for w in published]


# Derived compatibility views — do not edit independently of WORKFLOWS / replacement_map().
WORKFLOW_RECIPES: list[dict[str, Any]] = _workflow_recipes_from_routing()


def client_projection_meta() -> dict[str, Any]:
    from .workflow_recipe_manifest import WORKFLOWS  # noqa: PLC0415

    total = len(WORKFLOWS)
    published = sum(1 for w in WORKFLOWS if w.get("publish_to_client_manifest"))
    return {
        "client_projection_schema_version": CLIENT_PROJECTION_SCHEMA_VERSION,
        "published_workflow_count": published,
        "omitted_workflow_count": total - published,
    }


def build_vault_client_projection(manifest: dict[str, Any]) -> dict[str, Any]:
    """Bounded vault-facing object (not the full semantic payload)."""
    # Slim entries: identity + classification only (no empty optional noise).
    slim_entries = []
    for e in manifest.get("entries") or []:
        slim_entries.append({
            "tool_name": e.get("tool_name"),
            "tool_group": e.get("tool_group"),
            "tool_class": e.get("tool_class"),
            "safety_class": e.get("safety_class"),
            "read_write_class": e.get("read_write_class"),
            "purpose": e.get("purpose") or "",
            "required_args": e.get("required_args") or [],
            "optional_args": e.get("optional_args") or [],
            "replacement_tools": e.get("replacement_tools") or [],
        })
    meta = client_projection_meta()
    return {
        "manifest_version": manifest.get("manifest_version"),
        "client_projection_schema_version": meta["client_projection_schema_version"],
        "published_workflow_count": meta["published_workflow_count"],
        "omitted_workflow_count": meta["omitted_workflow_count"],
        "full_semantic_checksum": manifest.get("semantic_surface_checksum") or manifest.get("checksum"),
        "generated_at": manifest.get("generated_at"),
        "generated_from_runtime_commit": manifest.get("generated_from_runtime_commit"),
        "tool_count": len(slim_entries),
        "workflow_count": len(manifest.get("workflow_recipes") or WORKFLOW_RECIPES),
        "entries": slim_entries,
        "workflow_recipes": list(manifest.get("workflow_recipes") or WORKFLOW_RECIPES),
        "replacement_map": dict(manifest.get("replacement_map") or REPLACEMENT_MAP),
        "negative_instructions": list(manifest.get("negative_instructions") or NEGATIVE_INSTRUCTIONS),
    }


def serialize_vault_projection_json(projection: dict[str, Any]) -> str:
    """Deterministic compact JSON string used for write-cap measurement and vault write."""
    import json  # noqa: PLC0415

    from .canonical_json import canonicalize  # noqa: PLC0415

    return json.dumps(canonicalize(projection), ensure_ascii=False, separators=(",", ":"), sort_keys=True)


def client_projection_checksum(projection: dict[str, Any] | str) -> str:
    from .canonical_json import sha256_fingerprint  # noqa: PLC0415

    if isinstance(projection, str):
        import hashlib  # noqa: PLC0415

        return "sha256:" + hashlib.sha256(projection.encode("utf-8")).hexdigest()
    # Checksum of exact serialized projection string (character-oriented, matches writer unit).
    s = serialize_vault_projection_json(projection)
    return client_projection_checksum(s)


def _replacement_map() -> dict[str, str]:
    from .canonical_tool_specs import replacement_map  # noqa: PLC0415

    return replacement_map()


# Dict snapshot for legacy callers (``REPLACEMENT_MAP[name]``, ``.items()``).
REPLACEMENT_MAP: dict[str, str] = _replacement_map()

NEGATIVE_INSTRUCTIONS: list[str] = [
    "do not use low-level vault search as the first step for ordinary structured-intelligence queries",
    "do not use root file tools for canonical artifact retrieval when semantic tools exist",
    "do not promote artifacts without explicit operator approval",
    "do not create canonical records directly",
    "do not write arbitrary notes into the vault",
    "do not bypass staging/review/versioning",
    "do not treat advisory tools as execution tools",
    "do not treat action-stage records as permission to execute",
    "do not silently merge duplicate decisions/preferences/open-loops",
    "do not use receipt tools as primary semantic retrieval unless auditing promotion history",
]

def classify_tool(name: str, group: str | None) -> tuple[str, str, str]:
    """Return (tool_class, safety_class, read_write_class). Compatibility view of canonical classification."""
    from .canonical_tool_specs import classify_tool as _canonical_classify  # noqa: PLC0415

    return _canonical_classify(name, group)


def build_manifest(tool_index: dict[str, dict[str, Any]], *, runtime_commit: str, now: str,
                   manifest_version: int = 1,
                   surface_profile: str | None = None,
                   gate_state_snapshot: dict[str, Any] | None = None,
                   gateway_allowlist: list[str] | None = None,
                   package_version: str | None = None,
                   runtime_identity_kind: str | None = None) -> dict[str, Any]:
    """Build the manifest object from a live tool index.

    ``manifest_version`` is the **revision counter** (not schema version).
    ``manifest_schema_version`` describes the payload contract (1 = expanded semantics).
    """
    from .canonical_json import sha256_fingerprint  # noqa: PLC0415
    from .tool_family_manifest import family_for_tool  # noqa: PLC0415
    from .tool_metadata_types import MANIFEST_SCHEMA_VERSION  # noqa: PLC0415
    from .workflow_recipe_manifest import WORKFLOWS  # noqa: PLC0415

    entries = []
    for name in sorted(tool_index):
        info = tool_index[name] or {}
        group = info.get("group") or info.get("tool_group")
        tool_class, safety_class, rw = classify_tool(name, group)
        from .canonical_tool_specs import normalize_manifest_purpose  # noqa: PLC0415

        entries.append({
            "tool_name": name,
            "tool_group": group,
            "tool_family": info.get("tool_family") or info.get("family") or family_for_tool(name, group),
            "tool_class": tool_class,
            "safety_class": safety_class,
            "read_write_class": rw,
            "purpose": normalize_manifest_purpose(str(info.get("purpose") or "")),
            "preferred_for": info.get("preferred_for", []),
            "avoid_when": info.get("avoid_when", []),
            "required_args": info.get("required_args", []),
            "optional_args": info.get("optional_args", []),
            "limits": info.get("limits", {}),
            "workflow_roles": info.get("workflow_roles", []),
            "replacement_tools": (
                info.get("replacement_tools")
                or ([REPLACEMENT_MAP[name]] if name in REPLACEMENT_MAP else [])
            ),
            "common_failure_modes": info.get("common_failure_modes", []),
            "examples": info.get("examples", []),
            "directly_exposed": info.get("directly_exposed"),
            "gateway_allowlisted": info.get("gateway_allowlisted"),
            "profile_enabled": info.get("profile_enabled"),
        })

    # Workflow semantic payload (order of tool_sequence preserved).
    workflow_payload = [
        {
            "workflow_id": w["workflow_id"],
            "family_id": w["family_id"],
            "tool_sequence": list(w["tool_sequence"]),
            "trigger_phrases": sorted(w["trigger_phrases"]),
            "operator_authorization_policy": w["operator_authorization_policy"],
            "additional_approval_points": list(w.get("additional_approval_points") or []),
        }
        for w in WORKFLOWS
    ]
    semantic_payload = {
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "entries": [
            {
                "tool_name": e["tool_name"],
                "tool_group": e["tool_group"],
                "tool_family": e.get("tool_family"),
                "tool_class": e["tool_class"],
                "safety_class": e["safety_class"],
                "read_write_class": e["read_write_class"],
                "purpose": e["purpose"],
                "required_args": sorted(e["required_args"]) if isinstance(e["required_args"], list) else e["required_args"],
                "optional_args": sorted(e["optional_args"]) if isinstance(e["optional_args"], list) else e["optional_args"],
                "limits": e["limits"],
                "replacement_tools": sorted(e["replacement_tools"]) if isinstance(e["replacement_tools"], list) else e["replacement_tools"],
            }
            for e in entries
        ],
        "workflows": workflow_payload,
        "replacement_map": dict(sorted(REPLACEMENT_MAP.items())),
    }
    exposure_payload = {
        "surface_profile": surface_profile or "unknown",
        "gate_state_snapshot": gate_state_snapshot or {},
        "tools": [
            {
                "tool_name": e["tool_name"],
                "directly_exposed": e.get("directly_exposed"),
                "gateway_allowlisted": e.get("gateway_allowlisted"),
                "profile_enabled": e.get("profile_enabled"),
            }
            for e in entries
        ],
    }
    gateway_payload = {"gateway_allowlist": sorted(gateway_allowlist or [])}

    semantic_checksum = sha256_fingerprint(semantic_payload)
    exposure_checksum = sha256_fingerprint(exposure_payload)
    gateway_checksum = sha256_fingerprint(gateway_payload)
    # Legacy checksum field retained for older readers (narrow class triad) — still stable.
    legacy_checksum = _manifest_checksum(entries)

    return {
        "manifest_version": manifest_version,
        "manifest_schema_version": MANIFEST_SCHEMA_VERSION,
        "manifest_status": "active",
        "generated_at": now,
        "generated_from_runtime_commit": runtime_commit,
        "generated_from_package_version": package_version,
        "runtime_identity_kind": runtime_identity_kind or "unknown",
        "tool_count": len(entries),
        "workflow_count": len(WORKFLOW_RECIPES),
        "mapping_count": len(REPLACEMENT_MAP),
        "staleness_state": "fresh",
        "review_cadence": REVIEW_CADENCE,
        "checksum": legacy_checksum,
        "semantic_surface_checksum": semantic_checksum,
        "exposure_checksum": exposure_checksum,
        "gateway_checksum": gateway_checksum,
        "gateway_allowlist": sorted(gateway_allowlist or []),
        "manifest_payload": semantic_payload,
        "surface_profile": surface_profile or "unknown",
        "gate_state_snapshot": gate_state_snapshot or {},
        "entries": entries,
        "workflow_recipes": WORKFLOW_RECIPES,
        "replacement_map": REPLACEMENT_MAP,
        "negative_instructions": NEGATIVE_INSTRUCTIONS,
    }


def build_live_surface_fingerprints(
    tool_index: dict[str, dict[str, Any]],
    *,
    surface_profile: str | None = None,
    gate_state_snapshot: dict[str, Any] | None = None,
    gateway_allowlist: list[str] | None = None,
) -> dict[str, Any]:
    """Semantic/exposure/gateway fingerprints from a live tool index (no DB I/O)."""
    built = build_manifest(
        tool_index,
        runtime_commit="live",
        now="live",
        surface_profile=surface_profile,
        gate_state_snapshot=gate_state_snapshot,
        gateway_allowlist=gateway_allowlist,
    )
    return {
        "semantic_surface_checksum": built["semantic_surface_checksum"],
        "exposure_checksum": built["exposure_checksum"],
        "gateway_checksum": built["gateway_checksum"],
        "gateway_allowlist": built.get("gateway_allowlist") or [],
    }


def _manifest_checksum(entries: list[dict[str, Any]]) -> str:
    """Legacy narrow checksum (class triad) for backward-compatible comparison of pre-schema rows."""
    key = [(e["tool_name"], e["tool_class"], e["read_write_class"], e["safety_class"]) for e in entries]
    return _sha("manifest-v1", _cjson(key), _cjson([r["workflow_name"] for r in WORKFLOW_RECIPES]))


def render_manifest_md(manifest: dict[str, Any]) -> str:
    import yaml  # noqa: PLC0415

    fm = {"note_type": "client_tool_operating_manifest", "manifest_version": manifest["manifest_version"],
          "generated_at": manifest["generated_at"], "generated_from_runtime_commit":
          manifest["generated_from_runtime_commit"], "checksum": manifest["checksum"],
          "staleness_state": manifest["staleness_state"], "next_review_due_at": manifest.get("next_review_due_at"),
          "tags": ["second-brain/canonical", "topic/nas-mcp", "topic/structured-intelligence", "phase/n8c-23"]}
    lines = [f"---\n{yaml.safe_dump(fm, sort_keys=False, allow_unicode=True)}---\n",
             "# Client Tool Operating Manifest", "",
             f"Tools: {manifest['tool_count']} · Workflows: {manifest['workflow_count']} · "
             f"Mappings: {manifest['mapping_count']} · Staleness: **{manifest['staleness_state']}**", "",
             "## Preferred tool hierarchy", "",
             "- Normal second-brain questions → structured `assistant_*` tools first.",
             "- Source discovery → `assistant_source_*` tools first.",
             "- Durable memory creation → `pa_artifact_proposal_stage` → review → promotion.",
             "- Canonical memory → validate + `pa_artifact_promotion_apply` (operator-approved).",
             "- Auditing → receipts + manifests.",
             "- Low-level vault/root/DB tools only when explicitly requested.", "",
             "## Tools", "", "| tool | class | read/write | safety |", "|---|---|---|---|"]
    for e in manifest["entries"]:
        lines.append(f"| `{e['tool_name']}` | {e['tool_class']} | {e['read_write_class']} | {e['safety_class']} |")
    lines += ["", "## Replacement map", ""]
    lines += [f"- instead of `{k}` → {v}" for k, v in manifest["replacement_map"].items()]
    lines += ["", "## Do not", ""] + [f"- {n}" for n in manifest["negative_instructions"]]
    lines += ["", "## Workflow recipes", ""]
    for r in manifest["workflow_recipes"]:
        lines.append(f"### {r['workflow_name']}")
        lines.append(f"- triggers: {', '.join(r['trigger_phrases'])}")
        lines.append(f"- sequence: {' → '.join(r['tool_sequence'])}")
        lines.append(f"- approval points: {', '.join(r['required_operator_approval_points']) or 'none'}")
        lines.append("")
    return "\n".join(lines) + "\n"


def _hydrate_manifest_entries(hdr: dict[str, Any], rows: list[tuple[Any, ...]]) -> list[dict[str, Any]]:
    """Build freshness-comparable entry dicts from semantic payload or legacy DB rows."""
    from .tool_family_manifest import family_for_tool  # noqa: PLC0415

    payload_raw = hdr.get("manifest_payload_json")
    if payload_raw:
        try:
            payload = json.loads(payload_raw) if isinstance(payload_raw, str) else payload_raw
            entries = payload.get("entries") or []
            if entries:
                return [
                    {
                        "tool_name": e["tool_name"],
                        "tool_group": e.get("tool_group"),
                        "tool_family": e.get("tool_family") or family_for_tool(
                            e["tool_name"], e.get("tool_group")
                        ),
                        "tool_class": e.get("tool_class"),
                        "safety_class": e["safety_class"],
                        "read_write_class": e["read_write_class"],
                    }
                    for e in entries
                ]
        except (TypeError, ValueError, KeyError):
            pass

    out: list[dict[str, Any]] = []
    for row in rows:
        if len(row) >= 5:
            name, group, tool_class, safety_class, read_write_class = row[:5]
        else:
            name, tool_class, safety_class, read_write_class = row[:4]
            group = None
        out.append({
            "tool_name": name,
            "tool_group": group,
            "tool_family": family_for_tool(name, group),
            "tool_class": tool_class,
            "safety_class": safety_class,
            "read_write_class": read_write_class,
        })
    return out


class ClientToolManifestRepository:
    def __init__(self, db_path: str | None = None) -> None:
        # Internet-facing profile: the authoritative DB is a read-only snapshot, so route this
        # repo's self-contained manifest tables to the writable workspace DB (the snapshot stays
        # read-only). Persisting a manifest here is what lets the get/freshness/status surfaces
        # agree instead of one synthesizing an "active" manifest the others don't see. Local/ingest
        # hosts keep using the ambient writable managed DB.
        if db_readonly():
            from hb_assistant.store.workspace import ensure_workspace_db  # noqa: PLC0415

            self.db_path = str(ensure_workspace_db())
        else:
            self.db_path = db_path
        self._readonly = False

    def _guard_writable(self) -> None:
        # Safety net only: _readonly is False on every supported profile now that writes route to a
        # writable DB. Kept fail-closed for any future genuinely read-only surface.
        if self._readonly:
            raise ArtifactWorkspaceError("read_only_db_surface:manifest_refresh_unavailable")

    def _path(self) -> Any:
        from pathlib import Path  # noqa: PLC0415

        return Path(self.db_path) if self.db_path else None

    def save_manifest(self, manifest: dict[str, Any]) -> str:
        now = manifest["generated_at"]
        manifest_id = _sha("manifest", manifest["checksum"], now)
        self._guard_writable()
        with open_connection(self._path()) as c, transaction(c):
            c.execute("UPDATE pa_client_tool_manifests SET manifest_status='superseded' WHERE manifest_status='active'")
            row = {
                "manifest_id": manifest_id, "manifest_version": manifest["manifest_version"],
                "manifest_status": "active", "generated_at": now,
                "generated_from_runtime_commit": manifest["generated_from_runtime_commit"],
                "tool_count": manifest["tool_count"], "workflow_count": manifest["workflow_count"],
                "mapping_count": manifest["mapping_count"], "staleness_state": manifest["staleness_state"],
                "review_cadence": manifest["review_cadence"], "checksum": manifest["checksum"],
                "created_at": now, "updated_at": now,
            }
            # V118 columns (best-effort; present after schema 118).
            if "manifest_schema_version" in manifest:
                row["manifest_schema_version"] = manifest.get("manifest_schema_version", 0)
            if "manifest_payload" in manifest:
                row["manifest_payload_json"] = _cjson(manifest["manifest_payload"])
            if "semantic_surface_checksum" in manifest:
                row["semantic_surface_checksum"] = manifest["semantic_surface_checksum"]
            if "exposure_checksum" in manifest:
                row["exposure_checksum"] = manifest["exposure_checksum"]
            if "gateway_checksum" in manifest:
                row["gateway_checksum"] = manifest["gateway_checksum"]
            if "surface_profile" in manifest:
                row["surface_profile"] = manifest.get("surface_profile")
            if "gate_state_snapshot" in manifest:
                row["gate_state_snapshot_json"] = _cjson(manifest.get("gate_state_snapshot") or {})
            if "generated_from_package_version" in manifest:
                row["generated_from_package_version"] = manifest.get("generated_from_package_version")
            if "runtime_identity_kind" in manifest:
                row["runtime_identity_kind"] = manifest.get("runtime_identity_kind")
            if "gateway_allowlist" in manifest:
                row["gateway_allowlist_json"] = _cjson(manifest.get("gateway_allowlist") or [])
            _insert(c, "pa_client_tool_manifests", row)
            for e in manifest["entries"]:
                _insert(c, "pa_tool_manifest_entries", {
                    "manifest_entry_id": _sha(manifest_id, e["tool_name"]), "manifest_id": manifest_id,
                    "tool_name": e["tool_name"], "tool_group": e["tool_group"], "tool_class": e["tool_class"],
                    "safety_class": e["safety_class"], "read_write_class": e["read_write_class"],
                    "preferred_for_json": _cjson(e["preferred_for"]), "avoid_when_json": _cjson(e["avoid_when"]),
                    "required_args_json": _cjson(e["required_args"]), "optional_args_json": _cjson(e["optional_args"]),
                    "limits_json": _cjson(e["limits"]), "workflow_roles_json": _cjson(e["workflow_roles"]),
                    "replacement_tools_json": _cjson(e["replacement_tools"]),
                    "common_failure_modes_json": _cjson(e["common_failure_modes"]),
                    "examples_json": _cjson(e["examples"]), "last_verified_at": now, "freshness_state": "fresh"})
            for r in manifest["workflow_recipes"]:
                _insert(c, "pa_workflow_route_recipes", {
                    "workflow_recipe_id": _sha(manifest_id, r["workflow_name"]), "manifest_id": manifest_id,
                    "workflow_name": r["workflow_name"], "trigger_phrases_json": _cjson(r["trigger_phrases"]),
                    "description": r["description"], "tool_sequence_json": _cjson(r["tool_sequence"]),
                    "required_operator_approval_points_json": _cjson(r["required_operator_approval_points"]),
                    "negative_instructions_json": _cjson(r["negative_instructions"]),
                    "expected_outputs_json": _cjson(r["expected_outputs"]),
                    "failure_recovery_json": _cjson(r["failure_recovery"]), "last_reviewed_at": now})
        return manifest_id

    def get_active(self, *, conn: Any = None) -> dict[str, Any] | None:
        base_cols = (
            "manifest_id", "manifest_version", "manifest_status", "generated_at",
            "generated_from_runtime_commit", "tool_count", "workflow_count", "mapping_count",
            "staleness_state", "freshness_checked_at", "next_review_due_at", "review_cadence", "checksum",
            "manifest_vault_path", "manifest_json_path",
        )
        v118_cols = (
            "manifest_schema_version", "manifest_payload_json", "semantic_surface_checksum",
            "exposure_checksum", "gateway_checksum", "surface_profile", "gate_state_snapshot_json",
            "generated_from_package_version", "runtime_identity_kind",
        )
        v121_cols = ("gateway_allowlist_json",)
        with borrow_connection(conn, self._path(), readonly=self._readonly) as c:
            # Prefer V118 select; fall back if columns missing (pre-migrate open DBs).
            cols = base_cols + v118_cols + v121_cols
            try:
                row = c.execute(
                    f"SELECT {', '.join(cols)} FROM pa_client_tool_manifests WHERE manifest_status='active' "
                    f"ORDER BY generated_at DESC LIMIT 1"
                ).fetchone()
            except Exception:  # noqa: BLE001
                try:
                    cols = base_cols + v118_cols
                    row = c.execute(
                        f"SELECT {', '.join(cols)} FROM pa_client_tool_manifests WHERE manifest_status='active' "
                        f"ORDER BY generated_at DESC LIMIT 1"
                    ).fetchone()
                except Exception:  # noqa: BLE001
                    cols = base_cols
                    row = c.execute(
                        f"SELECT {', '.join(cols)} FROM pa_client_tool_manifests WHERE manifest_status='active' "
                        f"ORDER BY generated_at DESC LIMIT 1"
                    ).fetchone()
            if not row:
                return None
            hdr = dict(zip(cols, row, strict=True))
            gw_raw = hdr.get("gateway_allowlist_json")
            if gw_raw:
                try:
                    hdr["gateway_allowlist"] = json.loads(gw_raw)
                except (TypeError, json.JSONDecodeError):
                    pass
            entry_rows = c.execute(
                "SELECT tool_name, tool_group, tool_class, safety_class, read_write_class "
                "FROM pa_tool_manifest_entries WHERE manifest_id=? ORDER BY tool_name",
                (hdr["manifest_id"],),
            ).fetchall()
            hdr["entries"] = _hydrate_manifest_entries(hdr, entry_rows)
            return hdr

    def freshness_check(
        self,
        current_tool_names: set[str],
        *,
        conn: Any = None,
        live_runtime_commit: str | None = None,
    ) -> dict[str, Any]:
        """Compare live tool names (and optional runtime commit) to the active persisted manifest.

        Deployment-runtime validity is part of client-manifest freshness: a name-set match
        must not report ``fresh`` when ``generated_from_runtime_commit`` disagrees with the
        live runtime SHA (the dual-surface contradiction observed in production).
        """
        active = self.get_active(conn=conn)
        if not active:
            return {
                "tool_manifest_stale": True,
                "staleness_state": "stale",
                "tool_manifest_review_required": True,
                "tool_manifest_missing_tools": sorted(current_tool_names),
                "tool_manifest_extra_tools": [],
                "reason": "no_active_manifest",
                "deployment_runtime_drift": False,
                "generated_from_runtime_commit": None,
                "live_runtime_commit": live_runtime_commit,
            }
        recorded = {e["tool_name"] for e in active["entries"]}
        missing = sorted(current_tool_names - recorded)   # live tools not in manifest
        extra = sorted(recorded - current_tool_names)     # manifest tools no longer live
        name_changed = bool(missing or extra)

        stored_rc = active.get("generated_from_runtime_commit")
        live_s = str(live_runtime_commit or "").strip()
        stored_s = str(stored_rc or "").strip()
        looks_like_sha = bool(live_s) and len(live_s) >= 7 and all(
            c in "0123456789abcdef" for c in live_s.lower()
        )
        stored_looks_like_sha = bool(stored_s) and len(stored_s) >= 7 and all(
            c in "0123456789abcdef" for c in stored_s.lower()
        )
        deployment_runtime_drift = False
        if stored_looks_like_sha and looks_like_sha and live_s != stored_s:
            deployment_runtime_drift = True
        elif stored_looks_like_sha and live_s and not looks_like_sha:
            # Package-only / unknown live identity cannot certify the stored SHA baseline.
            deployment_runtime_drift = True

        stale = name_changed or deployment_runtime_drift
        if deployment_runtime_drift and not name_changed:
            staleness_state = "deployment_runtime_commit_mismatch"
        elif name_changed:
            staleness_state = "tool_surface_changed"
        else:
            staleness_state = active["staleness_state"]

        return {
            "tool_manifest_stale": stale,
            "tool_manifest_missing_tools": missing,
            "tool_manifest_extra_tools": extra,
            "tool_manifest_review_required": stale,
            "staleness_state": staleness_state,
            "manifest_version": active["manifest_version"],
            "checksum": active["checksum"],
            "deployment_runtime_drift": deployment_runtime_drift,
            "generated_from_runtime_commit": stored_rc,
            "live_runtime_commit": live_runtime_commit,
            "reason": (
                "deployment_runtime_commit_mismatch"
                if deployment_runtime_drift and not name_changed
                else ("tool_surface_changed" if name_changed else None)
            ),
        }

    def stage_refresh(self, new_manifest: dict[str, Any], freshness_diff: dict[str, Any]) -> dict[str, Any]:
        now = _now()
        base = self.get_active()
        refresh_id = _sha("refresh", new_manifest["checksum"], now)
        # server-minted approval, relayed by the operator to promote — never client-invented.
        approval_id = _sha("manifest-appr", refresh_id, new_manifest["checksum"], now)
        self._guard_writable()
        with open_connection(self._path()) as c, transaction(c):
            _insert(c, "pa_tool_manifest_refresh_proposals", {
                "refresh_proposal_id": refresh_id, "base_manifest_id": base["manifest_id"] if base else None,
                "proposed_manifest_version": new_manifest["manifest_version"],
                "freshness_diff_json": _cjson(freshness_diff), "checksum": new_manifest["checksum"],
                "status": "staged", "operator_approval_id": approval_id, "created_at": now})
        return {"refresh_proposal_id": refresh_id, "operator_approval_id": approval_id,
                "freshness_diff": freshness_diff, "status": "staged", "writes": False}

    def get_refresh(self, refresh_proposal_id: str, *, conn: Any = None) -> dict[str, Any] | None:
        cols = ("refresh_proposal_id", "base_manifest_id", "proposed_manifest_version", "freshness_diff_json",
                "checksum", "status", "operator_approval_id", "receipt_path", "created_at", "promoted_at")
        with borrow_connection(conn, self._path(), readonly=self._readonly) as c:
            row = c.execute(f"SELECT {', '.join(cols)} FROM pa_tool_manifest_refresh_proposals "
                            f"WHERE refresh_proposal_id=?", (refresh_proposal_id,)).fetchone()
        return dict(zip(cols, row, strict=True)) if row else None

    def mark_refresh_promoted(self, refresh_proposal_id: str, receipt_path: str) -> None:
        now = _now()
        self._guard_writable()
        with open_connection(self._path()) as c, transaction(c):
            c.execute("UPDATE pa_tool_manifest_refresh_proposals SET status='promoted', receipt_path=?, "
                      "promoted_at=? WHERE refresh_proposal_id=?", (receipt_path, now, refresh_proposal_id))

    def set_manifest_vault_paths(self, manifest_id: str, md_path: str, json_path: str) -> None:
        self._guard_writable()
        with open_connection(self._path()) as c, transaction(c):
            c.execute("UPDATE pa_client_tool_manifests SET manifest_vault_path=?, manifest_json_path=?, "
                      "freshness_checked_at=? WHERE manifest_id=?", (md_path, json_path, _now(), manifest_id))

    def mark_active_stale(self, *, reason: str = "drift") -> None:
        """Mark the active manifest stale / review_required without rewriting payload."""
        self._guard_writable()
        with open_connection(self._path()) as c, transaction(c):
            c.execute(
                "UPDATE pa_client_tool_manifests SET staleness_state=?, updated_at=? "
                "WHERE manifest_status='active'",
                ("requires_operator_review", _now()),
            )
            # reason retained for audit callers; column may not exist on legacy schemas.
            _ = reason
