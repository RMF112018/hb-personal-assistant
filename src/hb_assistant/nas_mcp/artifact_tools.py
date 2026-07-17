"""N8C-23 MCP handler surface for the artifact workspace + client tool operating manifest.

Centralizes every ``pa_*`` tool so the broker only needs a thin delegation. Read/advisory tools operate on
the live workspace DB (read-your-writes); staged-write tools persist proposals/reviews (never the vault);
the two canonical-write tools (``pa_artifact_promotion_apply`` / ``pa_tool_manifest_refresh_promote``) are
the only ones that write the vault, and only behind server-minted approval + validation + idempotency.
"""

from __future__ import annotations

from typing import Any

from ..obsidian_mcp.artifact_workspace import ArtifactWorkspaceError, ArtifactWorkspaceRepository
from ..obsidian_mcp.client_tool_manifest import (
    WORKFLOW_RECIPES,
    ClientToolManifestRepository,
    build_manifest,
    render_manifest_md,
)
from ..obsidian_mcp.vault_path_resolver import MANIFESTS_FOLDER, resolve_relative_path
from .artifact_template_registry import SUPPORTED_ARTIFACT_TYPES, resolve_template

# Tool-name tuples. NONE contains the write-verb substrings (write/upsert/delete/create/persist) guarded by
# test_ai_outputs_is_the_only_write_tool, and none is added to ALL_ASSISTANT_TOOLS / the assistant gateway.
PA_ARTIFACT_TOOLS: tuple[str, ...] = (
    "pa_session_capture_stage",
    "pa_session_capture_get",
    "pa_artifact_proposal_stage",
    "pa_artifact_proposal_list",
    "pa_artifact_proposal_get",
    "pa_artifact_proposal_revise",
    "pa_artifact_proposal_review",
    "pa_artifact_proposal_compare",
    "pa_artifact_proposal_plan_promotion",
    "pa_artifact_promotion_validate",
    "pa_artifact_promotion_apply",
    "pa_artifact_promotion_receipt_get",
    "pa_artifact_manifest_get",
    "pa_vault_path_resolve",
    "pa_canonical_artifact_list",
    "pa_canonical_artifact_get",
    # Template-based vault-markdown artifact author (the sanctioned client artifact-creation path on
    # the read-only-DB profile). Name carries no write-verb substring (write/upsert/delete/create/
    # persist) so the finality-name guard stays green; classified as a canonical write below.
    "pa_artifact_author",
)

PA_MANIFEST_TOOLS: tuple[str, ...] = (
    "pa_tool_manifest_get",
    "pa_tool_manifest_tool_help",
    "pa_tool_manifest_workflow_get",
    "pa_tool_manifest_freshness_check",
    "pa_tool_manifest_review_plan",
    "pa_tool_manifest_refresh_stage",
    "pa_tool_manifest_refresh_promote",
)

# Canonical writes (vault + canonical DB) — gated like ai_outputs; require server-minted approval.
PA_CANONICAL_WRITE_TOOLS: frozenset[str] = frozenset(
    {"pa_artifact_promotion_apply", "pa_tool_manifest_refresh_promote", "pa_artifact_author"}
)
# Staged writes (workspace DB only; never the vault). Includes pa_artifact_promotion_validate: it persists
# promotion-bundle + validation-receipt rows and mints an operator_approval_id, so it is a workspace DB write
# and must be gated by safe mode / classified as a write like the other staged tools.
PA_STAGED_WRITE_TOOLS: frozenset[str] = frozenset(
    {"pa_session_capture_stage", "pa_artifact_proposal_stage", "pa_artifact_proposal_revise",
     "pa_artifact_proposal_review", "pa_tool_manifest_refresh_stage", "pa_artifact_promotion_validate"}
)

ALL_PA_TOOLS: tuple[str, ...] = PA_ARTIFACT_TOOLS + PA_MANIFEST_TOOLS


def current_tool_names(config: Any) -> set[str]:
    """The current registered client tool surface (for manifest build + freshness).

    Includes prompt-routing tools when the preflight gate is enabled. Delegates to the live
    tool surface join so help/manifest/freshness share one universe.
    """
    from .live_tool_surface import tool_name_set  # noqa: PLC0415

    return tool_name_set(config)


def _build_tool_index(config: Any, *, for_manifest: bool = False) -> dict[str, dict[str, Any]]:
    """Build manifest/help index from the live surface (includes routing tools + classifications)."""
    from .live_tool_surface import build_tool_index  # noqa: PLC0415

    return build_tool_index(config, for_manifest=for_manifest)


def _runtime_manifest_build_kwargs(config: Any | None = None) -> dict[str, Any]:
    """Exposure/runtime context stamped into promoted manifests for independent freshness checks."""
    from .broker import GATEWAY_ALLOWLIST, runtime_identity  # noqa: PLC0415
    from .live_tool_surface import gate_state_snapshot, surface_profile_label  # noqa: PLC0415

    ident = runtime_identity()
    return {
        "surface_profile": surface_profile_label(config),
        "gate_state_snapshot": gate_state_snapshot(),
        "gateway_allowlist": sorted(GATEWAY_ALLOWLIST),
        "package_version": ident.package_version,
        "runtime_identity_kind": ident.runtime_identity_kind.value,
    }


def _require(args: dict[str, Any], key: str) -> Any:
    val = args.get(key)
    if val in (None, ""):
        raise ArtifactWorkspaceError(f"missing_required_arg:{key}")
    return val


# Total-content cap for an authored artifact (mirrors ai_outputs; effective cap is config.max_card_bytes).
_AUTHOR_MAX_BYTES = 262_144


def _redact_map(raw: Any, redact: Any) -> tuple[dict[str, str], bool]:
    """Redact every string value in a {key: text} mapping. Returns (clean_map, any_redacted)."""
    out: dict[str, str] = {}
    applied = False
    for k, v in (raw or {}).items():
        text, hit = redact(str(v if v is not None else ""))
        out[str(k)] = text
        applied = applied or hit
    return out, applied


def _author_artifact(config: Any, a: dict[str, Any]) -> dict[str, Any]:
    """Create a structured-intelligence artifact as a TEMPLATE-BASED vault markdown file (no DB rows).

    Resolves the in-taxonomy destination + the matching vault template, redacts caller content, injects
    canonical frontmatter, and writes atomically via the shared template engine. Fails closed for unmapped
    artifact types (``template_not_available``) and for oversized content. This is the sanctioned client
    artifact-creation path on the read-only-DB profile (the staged-DB pipeline cannot persist there)."""
    import hashlib  # noqa: PLC0415
    from datetime import datetime, timezone  # noqa: PLC0415

    from hb_assistant.naming import CREATED_VIA_MCP, MANAGED_BY, sanitize_domain  # noqa: PLC0415

    from ..obsidian_mcp.artifact_card_renderer import required_tags  # noqa: PLC0415
    from ..obsidian_mcp.artifact_vault_writer import md_config  # noqa: PLC0415
    from ..obsidian_mcp.templates import create_note_from_template  # noqa: PLC0415
    from .ai_outputs import normalize_source_client  # noqa: PLC0415
    from .redaction import redact_text  # noqa: PLC0415

    artifact_type = str(_require(a, "artifact_type")).strip()
    title = str(_require(a, "title")).strip()
    if not title or len(title) > 200:
        raise ArtifactWorkspaceError("invalid_title")
    domain = a.get("domain") or a.get("domain_class")
    source_client = normalize_source_client(a.get("source_client") or "unknown")

    # Deterministic canonical id from (type, domain, title): re-authoring the same artifact resolves to the
    # same path and fails closed (note_already_exists) rather than silently duplicating.
    seed = f"{artifact_type}|{sanitize_domain(domain)}|{title}".encode("utf-8")
    canonical_id = "PA-" + hashlib.sha256(seed).hexdigest()[:12].upper()

    # Destination + template both fail closed off-taxonomy / for unmapped types (order: cheap resolves first).
    resolved = resolve_relative_path(artifact_type=artifact_type, domain=domain, canonical_id=canonical_id,
                                     title=title, operator_override_path=a.get("operator_override_path"))
    template_path = resolve_template(artifact_type, domain)

    variables, v_red = _redact_map(a.get("variables"), redact_text)
    sections, s_red = _redact_map(a.get("sections"), redact_text)
    variables.setdefault("title", title)
    total_bytes = sum(len(v.encode("utf-8")) for v in variables.values()) \
        + sum(len(v.encode("utf-8")) for v in sections.values())
    cap = int(getattr(config, "max_card_bytes", _AUTHOR_MAX_BYTES) or _AUTHOR_MAX_BYTES)
    if total_bytes > cap:
        raise ArtifactWorkspaceError(f"artifact_content_too_large:{total_bytes}>{cap}")

    frontmatter = {
        "canonical_id": canonical_id,
        "artifact_type": artifact_type,
        "title": title,
        "domain": sanitize_domain(domain) or "unknown",
        "source_client": source_client,
        "managed_by": MANAGED_BY,
        "created_via": CREATED_VIA_MCP,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "tags": required_tags(artifact_type, source_client, sanitize_domain(domain), "authored"),
    }
    result = create_note_from_template(
        md_config(config), template_path=template_path,
        target_path=resolved.resolved_relative_path, variables=variables, frontmatter=frontmatter,
        sections=sections, overwrite=False, principal_kind=source_client,
    )
    return {
        "status": "written",
        "artifact_type": artifact_type,
        "canonical_id": canonical_id,
        "relative_path": resolved.resolved_relative_path,
        "path_display": f"vault/{resolved.resolved_relative_path}",
        "template_path": result.get("template_path"),
        "sha256": result.get("sha256"),
        "redaction_applied": bool(v_red or s_red),
        "path_warnings": list(resolved.path_warnings),
        "supported_artifact_types": list(SUPPORTED_ARTIFACT_TYPES),
    }


def dispatch_artifact_tool(config: Any, tool_name: str, arguments: dict[str, Any], *,
                           runtime_commit: str = "unknown") -> dict[str, Any]:
    db = str(config.db_path)
    repo = ArtifactWorkspaceRepository(db)
    a = arguments or {}

    # ---- session capture ----
    if tool_name == "pa_session_capture_stage":
        return repo.stage_session_capture(a)
    if tool_name == "pa_session_capture_get":
        r = repo.get_session_capture(_require(a, "session_id"))
        if not r:
            raise ArtifactWorkspaceError("session_not_found")
        return r

    # ---- proposals ----
    if tool_name == "pa_artifact_proposal_stage":
        return repo.stage_proposal_bundle(_require(a, "session_id"), a.get("candidate_artifacts") or [])
    if tool_name == "pa_artifact_proposal_list":
        return {"proposals": repo.list_proposals(bundle_id=a.get("proposal_bundle_id"),
                                                 review_status=a.get("review_status"),
                                                 limit=int(a.get("limit", 50)))}
    if tool_name == "pa_artifact_proposal_get":
        r = repo.get_proposal(_require(a, "proposal_id"))
        if not r:
            raise ArtifactWorkspaceError("proposal_not_found")
        return r
    if tool_name == "pa_artifact_proposal_compare":
        return repo.compare_proposals(list(a.get("proposal_ids") or []))
    if tool_name == "pa_artifact_proposal_revise":
        return repo.revise_proposal(_require(a, "proposal_id"), body_markdown=a.get("body_markdown"),
                                    structured_payload=a.get("structured_payload"),
                                    operator_instruction=a.get("operator_instruction"),
                                    revision_summary=a.get("revision_summary"),
                                    created_by_client=a.get("created_by_client"))
    if tool_name == "pa_artifact_proposal_review":
        return repo.review_proposal(_require(a, "proposal_id"), str(_require(a, "decision")),
                                    operator_id=a.get("operator_id"), review_notes=a.get("review_notes"))

    # ---- promotion (advisory + validated + apply) ----
    if tool_name == "pa_artifact_proposal_plan_promotion":
        return repo.plan_promotion(_require(a, "proposal_bundle_id"))
    if tool_name == "pa_artifact_promotion_validate":
        return repo.validate_promotion(_require(a, "proposal_bundle_id"), operator_id=a.get("operator_id"))
    if tool_name == "pa_artifact_promotion_apply":
        from ..obsidian_mcp.artifact_promotion import (
            promote_bundle,  # lazy: avoids broker import cycle
        )
        return promote_bundle(config, db, promotion_bundle_id=_require(a, "promotion_bundle_id"),
                              operator_approval_id=str(_require(a, "operator_approval_id")),
                              idempotency_key=a.get("idempotency_key"), operator_id=a.get("operator_id"),
                              runtime_commit=runtime_commit)
    if tool_name == "pa_artifact_promotion_receipt_get":
        r = repo.get_receipt(_require(a, "promotion_receipt_id"))
        if not r:
            raise ArtifactWorkspaceError("receipt_not_found")
        return r

    # ---- canonical + resolver ----
    if tool_name == "pa_artifact_manifest_get":
        return {"canonical_artifacts": repo.list_canonical(artifact_type=a.get("artifact_type"),
                                                           limit=int(a.get("limit", 50)))}
    if tool_name == "pa_canonical_artifact_list":
        return {"canonical_artifacts": repo.list_canonical(artifact_type=a.get("artifact_type"),
                                                           limit=int(a.get("limit", 50)))}
    if tool_name == "pa_canonical_artifact_get":
        r = repo.get_canonical(_require(a, "canonical_id"))
        if not r:
            raise ArtifactWorkspaceError("canonical_not_found")
        return r
    if tool_name == "pa_artifact_author":
        return _author_artifact(config, a)
    if tool_name == "pa_vault_path_resolve":
        resolved = resolve_relative_path(
            artifact_type=str(_require(a, "artifact_type")), domain=a.get("domain"),
            canonical_id=str(a.get("canonical_id") or "PREVIEW-00000000-000000"),
            title=str(_require(a, "title")), operator_override_path=a.get("operator_override_path"))
        return {"resolved_relative_path": resolved.resolved_relative_path, "folder": resolved.folder,
                "filename": resolved.filename, "path_warnings": list(resolved.path_warnings)}

    return dispatch_manifest_tool(config, tool_name, a, runtime_commit=runtime_commit)


def dispatch_manifest_tool(config: Any, tool_name: str, a: dict[str, Any], *,
                           runtime_commit: str = "unknown") -> dict[str, Any]:
    db = str(config.db_path)
    mrepo = ClientToolManifestRepository(db)

    if tool_name == "pa_tool_manifest_get":
        active = mrepo.get_active()
        if not active:
            # No manifest has been persisted yet (the manifest tables start empty until an operator
            # runs pa_tool_manifest_refresh_promote). Return a usable manifest built from the LIVE tool
            # surface, but label it honestly as ephemeral/unpersisted so it AGREES with
            # pa_tool_manifest_freshness_check and hb_mcp_status instead of claiming active/fresh
            # (that fabrication was the source of the cross-surface manifest contradiction).
            ephemeral = build_manifest(
                _build_tool_index(config, for_manifest=True),
                runtime_commit=runtime_commit,
                now=_now(),
            )
            ephemeral.update({
                "manifest_status": "ephemeral_live_surface",
                "staleness_state": "no_persisted_manifest",
                "persisted": False,
                "review_required": True,
                "note": "Built from the live tool surface; NOT persisted. Run pa_tool_manifest_refresh_stage "
                        "then pa_tool_manifest_refresh_promote (operator-approved) to persist an active manifest.",
            })
            return ephemeral
        active["persisted"] = True
        return active
    if tool_name == "pa_tool_manifest_tool_help":
        name = str(_require(a, "tool_name"))
        idx = _build_tool_index(config, for_manifest=True)
        if name not in idx:
            raise ArtifactWorkspaceError(f"unknown_tool:{name}")
        m = build_manifest(idx, runtime_commit=runtime_commit, now=_now())
        entry = next((e for e in m["entries"] if e["tool_name"] == name), None)
        if not entry:
            raise ArtifactWorkspaceError(f"unknown_tool:{name}")
        return entry
    if tool_name == "pa_tool_manifest_workflow_get":
        name = a.get("workflow_name")
        recipes = [r for r in WORKFLOW_RECIPES if not name or r["workflow_name"] == name]
        if name and not recipes:
            raise ArtifactWorkspaceError(f"unknown_workflow:{name}")
        return {"workflow_recipes": recipes}
    if tool_name == "pa_tool_manifest_freshness_check":
        return mrepo.freshness_check(
            current_tool_names(config), live_runtime_commit=runtime_commit
        )
    if tool_name == "pa_tool_manifest_review_plan":
        fr = mrepo.freshness_check(
            current_tool_names(config), live_runtime_commit=runtime_commit
        )
        return {
            "review_required": fr["tool_manifest_review_required"],
            "staleness": fr.get("staleness_state"),
            "missing_tools": fr.get("tool_manifest_missing_tools", []),
            "extra_tools": fr.get("tool_manifest_extra_tools", []),
            "deployment_runtime_drift": fr.get("deployment_runtime_drift", False),
            "generated_from_runtime_commit": fr.get("generated_from_runtime_commit"),
            "live_runtime_commit": fr.get("live_runtime_commit"),
            "recommendation": "stage a manifest refresh, then operator-approve promotion",
            "writes": False,
        }
    if tool_name == "pa_tool_manifest_refresh_stage":
        from .live_tool_surface import manifest_schema_parity_check  # noqa: PLC0415
        from .tool_registration import ensure_schema_index_frozen  # noqa: PLC0415

        ensure_schema_index_frozen(config)
        parity = manifest_schema_parity_check(config)
        if not parity["ok"]:
            raise ArtifactWorkspaceError(
                f"manifest_schema_parity_failed:{parity.get('reason') or 'unknown'}"
            )
        active = mrepo.get_active()
        version = (active["manifest_version"] + 1) if active else 1
        new_manifest = build_manifest(
            _build_tool_index(config, for_manifest=True),
            runtime_commit=runtime_commit,
            now=_now(),
            manifest_version=version,
            **_runtime_manifest_build_kwargs(config),
        )
        fr = mrepo.freshness_check(
            current_tool_names(config), live_runtime_commit=runtime_commit
        )
        staged = mrepo.stage_refresh(new_manifest, fr)
        staged["schema_parity"] = {
            "ok": True,
            "frozen_tool_count": parity.get("frozen_tool_count"),
        }
        return staged
    if tool_name == "pa_tool_manifest_refresh_promote":
        return _promote_manifest_refresh(config, mrepo, a, runtime_commit=runtime_commit)

    raise ArtifactWorkspaceError(f"unknown_pa_tool:{tool_name}")


def _promote_manifest_refresh(config: Any, mrepo: ClientToolManifestRepository, a: dict[str, Any], *,
                              runtime_commit: str) -> dict[str, Any]:
    refresh_id = str(_require(a, "refresh_proposal_id"))
    approval = str(_require(a, "operator_approval_id"))
    proposal = mrepo.get_refresh(refresh_id)
    if not proposal:
        raise ArtifactWorkspaceError("unknown_refresh_proposal")
    if proposal["status"] == "promoted":
        return {"status": "promoted", "idempotent_reuse": True, "receipt_path": proposal["receipt_path"]}
    if approval != proposal["operator_approval_id"]:
        raise ArtifactWorkspaceError("operator_approval_mismatch")
    # Rebuild the current manifest and confirm the surface still matches the staged checksum (no drift).
    version = int(proposal["proposed_manifest_version"])
    manifest = build_manifest(
        _build_tool_index(config, for_manifest=True),
        runtime_commit=runtime_commit,
        now=_now(),
        manifest_version=version,
        **_runtime_manifest_build_kwargs(config),
    )
    if manifest["checksum"] != proposal["checksum"]:
        raise ArtifactWorkspaceError("manifest_revalidation_required")
    from ..obsidian_mcp.artifact_vault_writer import write_manifest_pair  # noqa: PLC0415

    manifest_id = mrepo.save_manifest(manifest)
    md = render_manifest_md(manifest)
    from ..obsidian_mcp.client_tool_manifest import (  # noqa: PLC0415
        MAX_VAULT_MANIFEST_CHARS,
        build_vault_client_projection,
        client_projection_checksum,
        serialize_vault_projection_json,
    )

    # Vault JSON is a bounded client projection (not the full semantic DB payload).
    projection = build_vault_client_projection(manifest)
    json_str = serialize_vault_projection_json(projection)
    proj_cs = client_projection_checksum(json_str)
    # Writer enforces character length (mutations._validate_content uses len(content)).
    if len(md) > MAX_VAULT_MANIFEST_CHARS:
        raise ArtifactWorkspaceError(
            f"vault_manifest_md_exceeds_cap:{len(md)}>{MAX_VAULT_MANIFEST_CHARS}"
        )
    if len(json_str) > MAX_VAULT_MANIFEST_CHARS:
        raise ArtifactWorkspaceError(
            f"vault_manifest_json_exceeds_cap:{len(json_str)}>{MAX_VAULT_MANIFEST_CHARS}"
        )
    # Stamp projection checksum into MD frontmatter path via render is already done; attach in return.
    paths = write_manifest_pair(config, "client-tool-operating-manifest", md, json_str,
                                tool_name="pa_tool_manifest_refresh_promote")
    mrepo.set_manifest_vault_paths(manifest_id, paths["md_path"], paths["json_path"])
    receipt_rel = f"{MANIFESTS_FOLDER}/client-tool-operating-manifest.md"
    mrepo.mark_refresh_promoted(refresh_id, receipt_rel)
    return {
        "status": "promoted", "manifest_id": manifest_id, "manifest_paths": paths,
        "checksum": manifest["checksum"],
        "full_semantic_checksum": manifest.get("semantic_surface_checksum") or manifest.get("checksum"),
        "client_projection_checksum": proj_cs,
        "client_projection_chars": len(json_str),
        "client_projection_md_chars": len(md),
        "idempotent_reuse": False,
    }


def bootstrap_persisted_manifest(config: Any, *, runtime_commit: str = "unknown") -> dict[str, Any]:
    """Ensure an internal baseline or detect drift — never silent vault auto-promote on drift.

    Policy:
    * No active manifest: persist an **internal baseline snapshot** (DB only) for freshness
      comparison; vault materialization stays pending operator review unless
      ``HB_MCP_MANIFEST_FIRST_INSTALL_AUTOPROMOTE=1`` is explicitly enabled.
    * Active + matching checksum: no-op.
    * Active + drift: mark stale / review_required; do **not** stage by default; never auto-promote.
      Optional auto-stage only when ``HB_MCP_MANIFEST_AUTO_STAGE_ON_DRIFT=1`` (idempotent; never promote).

    A server-minted approval id is not operator consent. Gated to NAS read-only profile.
    """
    import os  # noqa: PLC0415

    from hb_assistant.store.connection import db_readonly  # noqa: PLC0415

    from .profile import client_tool_manifest_enabled  # noqa: PLC0415

    if not (db_readonly() and client_tool_manifest_enabled()):
        return {"bootstrapped": False, "reason": "not_nas_readonly_profile"}
    mrepo = ClientToolManifestRepository(str(config.db_path))
    active = mrepo.get_active()
    version = (active["manifest_version"] + 1) if active else 1
    built = build_manifest(
        _build_tool_index(config, for_manifest=True),
        runtime_commit=runtime_commit,
        now=_now(),
        manifest_version=version,
        **_runtime_manifest_build_kwargs(config),
    )
    # Prefer independent semantic checksums when both sides have them; else legacy checksum.
    active_fp = None
    live_fp = built.get("checksum")
    if active:
        if active.get("semantic_surface_checksum") and built.get("semantic_surface_checksum"):
            active_fp = active["semantic_surface_checksum"]
            live_fp = built["semantic_surface_checksum"]
        else:
            active_fp = active.get("checksum")
            live_fp = built.get("checksum")

    if active and active_fp and active_fp == live_fp:
        return {"bootstrapped": False, "reason": "already_active", "checksum": live_fp}

    first_install_autopromote = os.environ.get("HB_MCP_MANIFEST_FIRST_INSTALL_AUTOPROMOTE", "").strip() == "1"
    auto_stage = os.environ.get("HB_MCP_MANIFEST_AUTO_STAGE_ON_DRIFT", "").strip() == "1"

    if not active:
        # Internal baseline: persist active DB snapshot for freshness; vault write only if flag.
        if first_install_autopromote:
            fr = mrepo.freshness_check(
                current_tool_names(config), live_runtime_commit=runtime_commit
            )
            staged = mrepo.stage_refresh(built, fr)
            promoted = _promote_manifest_refresh(
                config, mrepo,
                {"refresh_proposal_id": staged["refresh_proposal_id"],
                 "operator_approval_id": staged["operator_approval_id"]},
                runtime_commit=runtime_commit)
            return {
                "bootstrapped": True,
                "reason": "first_install_autopromote",
                "manifest_id": promoted.get("manifest_id"),
                "checksum": promoted.get("checksum"),
                "vault_materialization": "promoted",
            }
        manifest_id = mrepo.save_manifest(built)
        return {
            "bootstrapped": True,
            "reason": "internal_baseline_pending_review",
            "manifest_id": manifest_id,
            "vault_materialization": "pending_operator_review",
            "checksum": live_fp,
        }

    # Existing active with drift — never auto-promote.
    mrepo.mark_active_stale(reason="semantic_or_exposure_drift")
    out: dict[str, Any] = {
        "bootstrapped": False,
        "reason": "drift_review_required",
        "stale": True,
        "review_required": True,
        "active_checksum": active_fp,
        "live_checksum": live_fp,
        "vault_materialization": "unchanged",
    }
    if auto_stage:
        fr = mrepo.freshness_check(
            current_tool_names(config), live_runtime_commit=runtime_commit
        )
        staged = mrepo.stage_refresh(built, fr)
        out["auto_staged"] = True
        out["refresh_proposal_id"] = staged.get("refresh_proposal_id")
        out["promoted"] = False
    return out


def _now() -> str:
    from datetime import datetime, timezone  # noqa: PLC0415

    return datetime.now(timezone.utc).isoformat()


def artifact_workspace_status(config: Any) -> dict[str, Any]:
    """Status fields for hb_mcp_status — never crashes if tables are empty/absent."""
    from .profile import artifact_workspace_enabled, client_tool_manifest_enabled  # noqa: PLC0415

    out: dict[str, Any] = {
        "artifact_workspace_enabled": artifact_workspace_enabled(),
        "artifact_workspace_schema_version": 112,
        "client_tool_manifest_enabled": client_tool_manifest_enabled(),
    }
    try:
        repo = ArtifactWorkspaceRepository(str(config.db_path))
        counts = repo.pending_counts()
        out.update({
            "artifact_workspace_pending_proposal_count": counts["pending_proposal_count"],
            "artifact_workspace_pending_review_count": counts["pending_review_count"],
            "artifact_workspace_pending_promotion_count": counts["pending_promotion_count"],
        })
        last = repo.list_canonical(limit=1)
        out["artifact_workspace_last_promotion_at"] = last[0]["promoted_at"] if last else None
        out["artifact_workspace_last_receipt_id"] = last[0]["promotion_receipt_id"] if last else None
    except Exception:  # noqa: BLE001 — status must never crash
        out["artifact_workspace_status_error"] = "unavailable"
    try:
        from .broker import runtime_commit as _runtime_commit  # noqa: PLC0415

        mrepo = ClientToolManifestRepository(str(config.db_path))
        live_rc = _runtime_commit()
        fr = mrepo.freshness_check(
            current_tool_names(config), live_runtime_commit=live_rc
        )
        active = mrepo.get_active()
        out.update({
            "client_tool_manifest_version": active["manifest_version"] if active else None,
            "client_tool_manifest_generated_at": active["generated_at"] if active else None,
            "client_tool_manifest_freshness_checked_at": active["freshness_checked_at"] if active else None,
            "client_tool_manifest_next_review_due_at": active["next_review_due_at"] if active else None,
            "client_tool_manifest_staleness_state": fr.get("staleness_state", "stale"),
            "client_tool_manifest_tool_count": active["tool_count"] if active else 0,
            "client_tool_manifest_workflow_count": active["workflow_count"] if active else 0,
            "client_tool_manifest_mapping_count": active["mapping_count"] if active else 0,
            "client_tool_manifest_missing_tool_count": len(fr.get("tool_manifest_missing_tools", [])),
            "client_tool_manifest_extra_tool_count": len(fr.get("tool_manifest_extra_tools", [])),
            "client_tool_manifest_review_required": fr.get("tool_manifest_review_required", True),
            "client_tool_manifest_deployment_runtime_drift": fr.get("deployment_runtime_drift", False),
            "client_tool_manifest_generated_from_runtime_commit": fr.get(
                "generated_from_runtime_commit"
            ),
            "client_tool_manifest_live_runtime_commit": fr.get("live_runtime_commit"),
        })
    except Exception:  # noqa: BLE001
        out["client_tool_manifest_status_error"] = "unavailable"
    return out
