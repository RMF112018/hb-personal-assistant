"""N8C-23 Client Tool Operating Manifest — the connected-client control-plane routing guide.

Classifies every exposed tool (purpose / safety / read-write class), carries workflow recipes, a
preferred-tool replacement map, negative instructions, and freshness/checksum/review-cadence fields.
Regenerating + WRITING it to ``99 System/Manifests`` follows a staged-review pattern (stage a diff → a
server-minted operator approval + receipt to materialize). Silent rewrite is prohibited.
"""

from __future__ import annotations

from typing import Any

from hb_assistant.store.connection import (
    borrow_connection,
    db_readonly,
    open_connection,
    transaction,
)

from .artifact_workspace import ArtifactWorkspaceError, _cjson, _insert, _now, _sha

REVIEW_CADENCE = "tool_surface: on_change; routing: weekly; safety: on_tool_surface_change; operator: monthly"

# Static, organization-neutral workflow recipes (Part 11.7).
WORKFLOW_RECIPES: list[dict[str, Any]] = [
    {"workflow_name": "document_session",
     "trigger_phrases": ["document this session", "record our discussion", "save the key points",
                         "turn this into second-brain artifacts", "capture the decisions from this chat"],
     "description": "Stage a session capture + artifact proposals, review, then operator-approved promotion.",
     "tool_sequence": ["pa_session_capture_stage", "pa_artifact_proposal_stage", "pa_artifact_proposal_list",
                       "pa_artifact_proposal_review", "pa_artifact_proposal_revise",
                       "pa_artifact_proposal_plan_promotion", "pa_artifact_promotion_validate",
                       "pa_artifact_promotion_apply", "pa_artifact_promotion_receipt_get"],
     "required_operator_approval_points": ["pa_artifact_proposal_review", "pa_artifact_promotion_apply"],
     "negative_instructions": ["never promote without validation", "never invent an approval id",
                               "never write vault notes directly"],
     "expected_outputs": ["proposal review packet", "validation receipt", "promotion receipt", "materialized cards"],
     "failure_recovery": ["on revalidation_required, re-run pa_artifact_promotion_validate"]},
    {"workflow_name": "find_source_file",
     "trigger_phrases": ["find the file", "search my documents", "look in the project folder"],
     "description": "Discover + read source files via the semantic source connector, not root/vault tools.",
     "tool_sequence": ["assistant_source_query_plan", "assistant_source_file_search",
                       "assistant_source_file_metadata", "assistant_source_file_read"],
     "required_operator_approval_points": [], "negative_instructions": ["do not use hb_root_search",
       "do not use file search alone when a folder map is needed"],
     "expected_outputs": ["bounded file excerpt with provenance"], "failure_recovery": []},
    {"workflow_name": "map_source_project",
     "trigger_phrases": ["map the tropical project", "map project folder", "folder structure under project"],
     "description": "Folder-first NAS project map using structure tools (not file search only).",
     "tool_sequence": ["assistant_source_query_plan", "assistant_source_project_map",
                       "assistant_source_folder_map", "assistant_source_folder_summary"],
     "required_operator_approval_points": [],
     "negative_instructions": ["do not fall back to generic file search only for map prompts"],
     "expected_outputs": ["bounded folder map with folder_ids + counts + freshness"],
     "failure_recovery": ["assistant_source_index_health if map empty"]},
    {"workflow_name": "source_index_health_check",
     "trigger_phrases": ["is my source index fresh", "source index health"],
     "description": "Per-root source index health for trust decisions.",
     "tool_sequence": ["assistant_source_index_health"],
     "required_operator_approval_points": [], "negative_instructions": [],
     "expected_outputs": ["per-root freshness + safe_for_client_answering"], "failure_recovery": []},
    {"workflow_name": "generate_client_output",
     "trigger_phrases": ["create a markdown output", "save as docx", "temporary zip output"],
     "description": "Stage/commit generated files via pa_output_* or assistant_output_* aliases.",
     "tool_sequence": ["assistant_output_stage", "assistant_output_commit", "pa_output_stage", "pa_output_commit"],
     "required_operator_approval_points": ["assistant_output_commit"],
     "negative_instructions": ["never write arbitrary host paths", "never use vault write for generated files"],
     "expected_outputs": ["output_id + receipt"], "failure_recovery": []},
    {"workflow_name": "retrieve_decision",
     "trigger_phrases": ["what did we decide", "find the decision"],
     "description": "Retrieve a canonical decision + provenance.",
     "tool_sequence": ["pa_canonical_artifact_list", "pa_canonical_artifact_get", "assistant_list_decisions"],
     "required_operator_approval_points": [], "negative_instructions": ["do not use hb_db_select"],
     "expected_outputs": ["canonical id + links"], "failure_recovery": []},
    {"workflow_name": "check_tool_manifest_freshness",
     "trigger_phrases": ["is the tool map current", "check tool manifest"],
     "description": "Compare the live tool surface to the recorded manifest.",
     "tool_sequence": ["pa_tool_manifest_freshness_check", "pa_tool_manifest_review_plan"],
     "required_operator_approval_points": ["pa_tool_manifest_refresh_promote"],
     "negative_instructions": ["never silently rewrite the manifest"],
     "expected_outputs": ["staleness state + missing/extra tools"], "failure_recovery": []},
]

REPLACEMENT_MAP: dict[str, str] = {
    "hb_root_search": "assistant_source_file_search",
    "hb_root_read_file": "assistant_source_file_read",
    "search_vault": "assistant_search_sources",
    "hb_db_select": "assistant_* semantic retrieval tools",
    "direct_note_creation": "pa_artifact_proposal_stage → review → pa_artifact_promotion_apply",
}

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

_DENIED = {"raw_sql", "sql", "shell", "exec", "read_file_absolute", "hb_output_delete"}
_LEGACY_LOW_LEVEL = {"hb_db_select", "hb_root_list", "hb_root_stat", "hb_root_search", "hb_root_read_file",
                     "hb_root_read_excerpt", "search_vault"}


def classify_tool(name: str, group: str | None) -> tuple[str, str, str]:
    """Return (tool_class, safety_class, read_write_class)."""
    if name in _DENIED:
        return "blocked_or_deprecated", "blocked", "blocked"
    if name == "ai_outputs_card_upsert":
        return "canonical_promotion", "canonical_promotion_requires_explicit_approval", "canonical_write"
    if name in ("pa_artifact_promotion_apply", "pa_tool_manifest_refresh_promote"):
        return "canonical_promotion", "canonical_promotion_requires_explicit_approval", "canonical_write"
    if name in ("pa_session_capture_stage", "pa_artifact_proposal_stage", "pa_artifact_proposal_revise",
                "pa_artifact_proposal_review", "pa_tool_manifest_refresh_stage"):
        return "staged_write", "staged_write_requires_review", "staged_write"
    # N8C-24 client generated-output workspace: 3 controlled writes + 7 bounded reads.
    if name in ("pa_output_stage", "pa_output_commit", "pa_output_archive_commit"):
        return "staged_write", "staged_write_requires_review", "staged_write"
    if name.startswith("pa_output_"):
        return "read_only_retrieval", "bounded_read", "read_only"
    if name in ("pa_artifact_proposal_plan_promotion", "pa_artifact_promotion_validate",
                "pa_tool_manifest_review_plan", "pa_vault_path_resolve"):
        return "advisory_routing", "advisory_only", "read_only"
    if name.startswith("pa_tool_manifest") or name in ("hb_assistant_catalog", "hb_assistant_tool_help",
                                                        "hb_assistant_tool_query"):
        return "manifest_lookup", "bounded_read", "read_only"
    if name in ("hb_mcp_status", "hb_data_freshness", "hb_queue_status", "hb_recent_failures",
                "hb_last_successful_runs", "hb_capability_mode"):
        return "read_only_status", "safe_read", "read_only"
    if name in _LEGACY_LOW_LEVEL or name.startswith("hb_output_"):
        return "legacy_low_level", "bounded_read", "read_only"
    if group == "review" or "review" in name:
        return "read_only_review", "bounded_read", "read_only"
    return "read_only_retrieval", "bounded_read", "read_only"


def build_manifest(tool_index: dict[str, dict[str, Any]], *, runtime_commit: str, now: str,
                   manifest_version: int = 1) -> dict[str, Any]:
    """Build the manifest object from a live tool index {name: {group, required_args, optional_args, limits}}."""
    entries = []
    for name in sorted(tool_index):
        info = tool_index[name] or {}
        tool_class, safety_class, rw = classify_tool(name, info.get("group"))
        entries.append({
            "tool_name": name, "tool_group": info.get("group"), "tool_class": tool_class,
            "safety_class": safety_class, "read_write_class": rw, "purpose": info.get("purpose", ""),
            "preferred_for": info.get("preferred_for", []), "avoid_when": info.get("avoid_when", []),
            "required_args": info.get("required_args", []), "optional_args": info.get("optional_args", []),
            "limits": info.get("limits", {}), "workflow_roles": info.get("workflow_roles", []),
            "replacement_tools": [REPLACEMENT_MAP[name]] if name in REPLACEMENT_MAP else [],
            "common_failure_modes": info.get("common_failure_modes", []), "examples": info.get("examples", []),
        })
    checksum = _manifest_checksum(entries)
    return {
        "manifest_version": manifest_version, "manifest_status": "active", "generated_at": now,
        "generated_from_runtime_commit": runtime_commit, "tool_count": len(entries),
        "workflow_count": len(WORKFLOW_RECIPES), "mapping_count": len(REPLACEMENT_MAP),
        "staleness_state": "fresh", "review_cadence": REVIEW_CADENCE, "checksum": checksum,
        "entries": entries, "workflow_recipes": WORKFLOW_RECIPES, "replacement_map": REPLACEMENT_MAP,
        "negative_instructions": NEGATIVE_INSTRUCTIONS,
    }


def _manifest_checksum(entries: list[dict[str, Any]]) -> str:
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
            _insert(c, "pa_client_tool_manifests", {
                "manifest_id": manifest_id, "manifest_version": manifest["manifest_version"],
                "manifest_status": "active", "generated_at": now,
                "generated_from_runtime_commit": manifest["generated_from_runtime_commit"],
                "tool_count": manifest["tool_count"], "workflow_count": manifest["workflow_count"],
                "mapping_count": manifest["mapping_count"], "staleness_state": manifest["staleness_state"],
                "review_cadence": manifest["review_cadence"], "checksum": manifest["checksum"],
                "created_at": now, "updated_at": now})
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
        cols = ("manifest_id", "manifest_version", "manifest_status", "generated_at",
                "generated_from_runtime_commit", "tool_count", "workflow_count", "mapping_count",
                "staleness_state", "freshness_checked_at", "next_review_due_at", "review_cadence", "checksum",
                "manifest_vault_path", "manifest_json_path")
        with borrow_connection(conn, self._path(), readonly=self._readonly) as c:
            row = c.execute(f"SELECT {', '.join(cols)} FROM pa_client_tool_manifests WHERE manifest_status='active' "
                            f"ORDER BY generated_at DESC LIMIT 1").fetchone()
            if not row:
                return None
            hdr = dict(zip(cols, row, strict=True))
            hdr["entries"] = [dict(zip(("tool_name", "tool_class", "safety_class", "read_write_class"), r,
                                       strict=True)) for r in c.execute(
                "SELECT tool_name, tool_class, safety_class, read_write_class FROM pa_tool_manifest_entries "
                "WHERE manifest_id=? ORDER BY tool_name", (hdr["manifest_id"],)).fetchall()]
            return hdr

    def freshness_check(self, current_tool_names: set[str], *, conn: Any = None) -> dict[str, Any]:
        active = self.get_active(conn=conn)
        if not active:
            return {"tool_manifest_stale": True, "staleness_state": "stale", "tool_manifest_review_required": True,
                    "tool_manifest_missing_tools": sorted(current_tool_names), "tool_manifest_extra_tools": [],
                    "reason": "no_active_manifest"}
        recorded = {e["tool_name"] for e in active["entries"]}
        missing = sorted(current_tool_names - recorded)   # live tools not in manifest
        extra = sorted(recorded - current_tool_names)     # manifest tools no longer live
        changed = bool(missing or extra)
        return {
            "tool_manifest_stale": changed, "tool_manifest_missing_tools": missing,
            "tool_manifest_extra_tools": extra, "tool_manifest_review_required": changed,
            "staleness_state": "tool_surface_changed" if changed else active["staleness_state"],
            "manifest_version": active["manifest_version"], "checksum": active["checksum"],
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
