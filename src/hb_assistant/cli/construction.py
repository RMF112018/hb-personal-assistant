"""construction-agent CLI subcommands.

Commands:
- ``hb-assistant construction-agent sources validate [--json]`` — load and
  validate the seeded source registry (Phase 01 Step 2).
- ``hb-assistant construction-agent graph auth status [--json]`` — report
  delegated MSAL cache status (Phase 01 Step 4).
- ``hb-assistant construction-agent graph sources resolve [--source KEY]
  [--apply] [--json]`` — resolve SharePoint/OneDrive sources to canonical
  Graph IDs (Phase 01 Step 4).
- ``hb-assistant construction-agent graph delta --source KEY [--dry-run |
  --apply] [--max-pages N] [--json]`` — read-only Graph delta crawler
  (Phase 01 Step 4).
- ``hb-assistant construction-agent data-quality project-coverage [--json] [--apply]``
  — Phase 07A local-only canonical project identity backfill + coverage matrix
  (dry-run default; --apply writes to V5 identity/match tables).
- ``hb-assistant construction-agent data-quality source-record-map [--dry-run] [--apply] [--json]``
  — Phase 07A local-only source-system record map (Prompt 03). Maps Procore live/financial,
  email messages/candidates, Graph files/ingestion decisions, body vault refs into
  V20 source_system_record_map using deterministic canonical IDs + Prompt 02 identities.
  Always emits unmapped active-pilot records with reason codes (never silent).
  Explicit --dry-run (default) / --apply; mutual exclusion enforced.
- ``hb-assistant construction-agent data-quality relationships --json``
  — Phase 07A local-only relationship orphan and confidence diagnostics (Prompt 04).
  Scans Procore edges (action_signals + timeline/change events), email relationship
  candidates, Graph file/project matches, and source-record-map cross links.
  Classifies per 08_ categories; assigns confidence from policy JSON; computes
  separate deterministic_orphan_rate and candidate_orphan_rate (never combined).
  Model-proposed / weak / sensitive relationships always review_required=1 and
  never auto-promoted (enforced + proven in test). Report-focused (dry-run semantics).
- ``hb-assistant construction-agent data-quality marts --json``
  — Phase 07A Prompt 05 agent-ready query marts (project coverage, source-record
  summary, relationship quality, cross-domain readiness) + measured latency for
  the 8 target local-agent queries (target 500 ms). Populates the four V20/V21
  marts from prior canonical artifacts. Additive only.

All commands are read-only against external systems; only SQLite metadata is
written, and only when ``--apply`` is set.
"""

from __future__ import annotations

import json
from typing import Any, Optional

import typer
from pydantic import ValidationError

from hb_assistant.auth.providers import DelegatedAuthProvider
from hb_assistant.config.loader import load_config
from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.classification import (
    ClassificationRouter,
    ClassificationService,
    InvalidModelOutputError,
    ModelRoutingError,
    ReadinessReport,
    check_readiness,
    load_model_routing_config,
)
from hb_assistant.construction.config import (
    SourceRegistry,
    load_source_registry,
)
from hb_assistant.construction.config.loader import SourceRegistryError
from hb_assistant.construction.data_quality import (
    ProjectIdentityBackfill,
    SourceRecordMapBuilder,
    RelationshipDiagnostics,
)

from hb_assistant.construction.fixtures import (
    KIND_ALIASES as FIXTURE_KIND_ALIASES,
)
from hb_assistant.construction.fixtures import (
    FixtureHarness,
)
from hb_assistant.construction.graph import (
    GRAPH_SCOPES,
    ConstructionDeltaCrawler,
    ConstructionGraphResolver,
    ResolutionResult,
    scopes_for_source_kind,
)
from hb_assistant.construction.manifests import (
    ConstructionVaultWriter,
    DocumentCardPolicyError,
    ManifestRenderer,
    ManifestService,
    VaultRootNotConfigured,
)
from hb_assistant.construction.policy import (
    ReviewPolicyEvaluator,
    ReviewQueueRouter,
    ReviewRulesError,
    load_review_rules,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.graph.http_client import GraphHttpClient
from hb_assistant.store.migrator import SQLiteMigrator

app = typer.Typer(help="Construction-management intelligence layer (read-only).")
sources_app = typer.Typer(help="Source registry inspection.")
graph_app = typer.Typer(help="Read-only Microsoft Graph crawler.")
graph_sources_app = typer.Typer(help="Graph source resolution.")
vault_app = typer.Typer(help="Construction vault preview and bootstrap.")
review_app = typer.Typer(help="Review-queue policy evaluation and inspection.")
classify_app = typer.Typer(help="Ollama-backed classification (recommendation-only).")
ollama_app = typer.Typer(help="Ollama daemon readiness (read-only; no inference).")
fixtures_app = typer.Typer(help="Canonical fixture inventory + validation harness (read-only).")
data_quality_app = typer.Typer(
    help="Data quality, canonical identity, source-record map, and gates (Phase 07A). "
    "Dry-run safe by default; --apply for local SQLite writes only."
)
app.add_typer(sources_app, name="sources")
app.add_typer(graph_app, name="graph")
graph_app.add_typer(graph_sources_app, name="sources")
app.add_typer(vault_app, name="vault")
app.add_typer(review_app, name="review")
app.add_typer(classify_app, name="classify")
app.add_typer(ollama_app, name="ollama")
app.add_typer(fixtures_app, name="fixtures")
app.add_typer(data_quality_app, name="data-quality")


def _build_report(registry: SourceRegistry) -> dict[str, Any]:
    resolved = [s for s in registry.sources if s.resolution_status == "resolved"]
    pending = [s for s in registry.sources if s.resolution_status == "pending"]
    deprecated = [s for s in registry.sources if s.resolution_status == "deprecated"]

    warnings: list[str] = []
    if pending:
        warnings.append(f"{len(pending)} sources pending live resolution")
    if deprecated:
        warnings.append(f"{len(deprecated)} sources marked deprecated")

    all_read_only = all(s.read_only is True for s in registry.sources)

    return {
        "implemented": True,
        "phase": 1,
        "step": "2-source-registry",
        "summary": {
            "project_count": len(registry.projects),
            "source_count": len(registry.sources),
            "resolved_count": len(resolved),
            "pending_count": len(pending),
            "deprecated_count": len(deprecated),
            "ok": True,
            "blocking": False,
        },
        "projects": [p.model_dump() for p in registry.projects],
        "sources": [s.model_dump() for s in registry.sources],
        "warnings": warnings,
        "guardrails": {
            "all_read_only": all_read_only,
            "no_writeback_paths": True,
            "no_live_external_calls": True,
        },
        "note": "Read-only validation. No SharePoint/OneDrive/Graph calls were made.",
    }


@sources_app.command("list")
def sources_list(
    json_out: bool = typer.Option(True, "--json", help="Emit structured JSON (default)."),
) -> None:
    """List registered construction-agent sources (minimal projection)."""

    try:
        registry = load_source_registry()
    except SourceRegistryError as e:
        payload = {
            "command": "construction-agent sources list",
            "status": "source_registry_unavailable",
            "error": str(e),
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1) from None

    items = [
        {
            "source_key": s.source_key,
            "project_key": s.project_key,
            "kind": s.kind,
            "display_name": s.display_name,
            "resolution_status": s.resolution_status,
        }
        for s in registry.sources
    ]
    payload = {
        "command": "construction-agent sources list",
        "count": len(items),
        "sources": items,
        "guardrails": {
            "external_systems": "read_only",
            "writeback": "none",
            "metadata_only": True,
        },
    }
    typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
    raise typer.Exit(0)


@sources_app.command("validate")
def validate_sources(
    json_out: bool = typer.Option(True, "--json", help="Emit structured JSON (default)."),
) -> None:
    """Validate the construction-agent source registry and emit a report."""

    try:
        registry = load_source_registry()
    except SourceRegistryError as e:
        payload = {
            "implemented": True,
            "phase": 1,
            "step": "2-source-registry",
            "summary": {"ok": False, "blocking": True},
            "error": "source_registry_unavailable",
            "detail": str(e),
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1) from None
    except ValidationError as e:
        payload = {
            "implemented": True,
            "phase": 1,
            "step": "2-source-registry",
            "summary": {"ok": False, "blocking": True},
            "error": "schema_validation_failed",
            "detail": e.errors(),
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(1) from None

    report = _build_report(registry)
    typer.echo(json.dumps(report, indent=2) if json_out else str(report))
    raise typer.Exit(0)


def _build_auth_provider() -> DelegatedAuthProvider:
    cfg = load_config()
    pp = PathPolicy(cfg)
    return DelegatedAuthProvider(
        cfg.identity.tenant_id,
        cfg.identity.client_id,
        cfg.identity.delegated_scopes,
        path_policy=pp,
    )


def _build_graph_client_or_auth_payload(
    provider: DelegatedAuthProvider,
    *,
    scopes: Optional[list[str]] = None,
) -> tuple[Optional[GraphHttpClient], Optional[dict[str, Any]]]:
    """Return (client, auth_required_payload).

    The CLI never triggers an interactive login. If no cached token exists
    for the required scopes, we return a structured ``auth_required`` payload
    so non-interactive callers (CI, sandboxes) can interpret the result.

    ``scopes`` defaults to the broadest construction-agent scope set
    (:data:`GRAPH_SCOPES`) so callers that don't know the source kind in
    advance preserve their existing behavior. Callers that know they're
    operating on a single source kind (e.g. ``graph delta`` on a
    drive-folder source) should pass the narrower set returned by
    :func:`scopes_for_source_kind` so MSAL silent acquisition succeeds
    when only the narrower subset is admin-consented.
    """

    effective_scopes = scopes if scopes is not None else GRAPH_SCOPES

    try:
        token = provider.get_token(effective_scopes)
    except Exception as e:  # noqa: BLE001 — surface as structured payload
        return None, {
            "status": "auth_required",
            "scopes": effective_scopes,
            "detail": str(e)[:200],
            "hint": "Run `hb-assistant auth login --json` interactively to obtain a delegated token.",
        }

    if "access_token" not in token:
        return None, {
            "status": "auth_required",
            "scopes": effective_scopes,
            "detail": token.get("error_description") or token.get("error") or "no_access_token_in_cache",
            "hint": "Run `hb-assistant auth login --json` interactively to obtain a delegated token.",
        }

    def token_getter(scopes: Optional[list[str]] = None) -> dict[str, Any]:
        return provider.get_token(scopes or effective_scopes)

    return GraphHttpClient(token_getter), None


@graph_app.command("auth")
def graph_auth_status(
    status: str = typer.Argument("status", help="Subcommand (only 'status' supported)."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Report delegated MSAL cache status for the construction-agent scopes."""
    if status != "status":
        payload = {"status": "runtime_error", "error": f"unknown subcommand {status!r}"}
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1)

    provider = _build_auth_provider()
    info = provider.status_info()
    payload = {
        "command": "construction-agent graph auth status",
        "required_scopes": GRAPH_SCOPES,
        "delegated": info,
        "note": "No live Graph call is made; report is from local MSAL cache only.",
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


def _resolution_to_dict(r: ResolutionResult) -> dict[str, Any]:
    return r.model_dump()


@graph_sources_app.command("resolve")
def graph_sources_resolve(
    source: Optional[str] = typer.Option(
        None, "--source", help="Resolve only this source_key (default: all)."
    ),
    apply: bool = typer.Option(False, "--apply", help="Persist resolutions to SQLite."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Resolve registered SharePoint/OneDrive sources to canonical Graph IDs."""
    registry = load_source_registry()
    targets = [s for s in registry.sources if source is None or s.source_key == source]
    if not targets:
        payload = {
            "command": "construction-agent graph sources resolve",
            "status": "not_found",
            "requested": source,
            "available": [s.source_key for s in registry.sources],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1)

    provider = _build_auth_provider()
    client, auth_payload = _build_graph_client_or_auth_payload(provider)
    if client is None:
        payload = {
            "command": "construction-agent graph sources resolve",
            "mode": "apply" if apply else "dry_run",
            "targets": [s.source_key for s in targets],
            **auth_payload,
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0)

    store = ConstructionStore() if apply else None
    resolver = ConstructionGraphResolver(client, store=store)
    results = [resolver.resolve(s, apply=apply) for s in targets]

    by_scope: dict[str, int] = {}
    for r in results:
        scope = r.scope or r.kind
        by_scope[scope] = by_scope.get(scope, 0) + 1

    payload = {
        "command": "construction-agent graph sources resolve",
        "mode": "apply" if apply else "dry_run",
        "results": [_resolution_to_dict(r) for r in results],
        "summary": {
            "total": len(results),
            "resolved": sum(1 for r in results if r.status == "resolved"),
            "pre_resolved": sum(1 for r in results if r.status == "pre_resolved"),
            "pending": sum(1 for r in results if r.status == "pending"),
            "unsupported": sum(1 for r in results if r.status == "unsupported"),
            "error": sum(1 for r in results if r.status == "error"),
            "by_scope": by_scope,
        },
        "guardrails": {
            "external_systems": "read_only",
            "writeback": "none",
            "metadata_only": True,
        },
    }
    typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
    raise typer.Exit(0)


@graph_app.command("delta")
def graph_delta(
    source: str = typer.Option(..., "--source", help="source_key from the registry."),
    dry_run: bool = typer.Option(True, "--dry-run/--apply", help="Default dry-run; --apply persists."),
    max_pages: int = typer.Option(50, "--max-pages", help="Hard cap on pages per call."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Run the read-only Graph delta crawler for a single registered source."""
    registry = load_source_registry()
    matching = [s for s in registry.sources if s.source_key == source]
    if not matching:
        payload = {
            "command": "construction-agent graph delta",
            "status": "not_found",
            "requested": source,
            "available": [s.source_key for s in registry.sources],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1)

    provider = _build_auth_provider()
    source_scopes = scopes_for_source_kind(matching[0].kind)
    client, auth_payload = _build_graph_client_or_auth_payload(
        provider, scopes=source_scopes
    )
    if client is None:
        payload = {
            "command": "construction-agent graph delta",
            "source": source,
            "mode": "dry_run" if dry_run else "apply",
            **auth_payload,
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0)

    store = ConstructionStore()
    crawler = ConstructionDeltaCrawler(client, store=store)
    receipt = crawler.crawl(source_key=source, dry_run=dry_run, max_pages=max_pages)

    payload = {
        "command": "construction-agent graph delta",
        "source": source,
        "mode": receipt.mode,
        "status": receipt.status,
        "receipt": receipt.model_dump(),
        "guardrails": {
            "external_systems": "read_only",
            "metadata_only": True,
            "delta_token_storage": "sqlite",
            "no_writeback": True,
        },
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0 if receipt.status in {"ok", "unresolved"} else 1)


def _utc_iso() -> str:
    from datetime import datetime, timezone
    return datetime.now(timezone.utc).isoformat()


@app.command("sync")
def sync_cmd(
    source: Optional[str] = typer.Option(None, "--source", help="Run only this source_key."),
    changed_only: bool = typer.Option(
        False, "--changed-only",
        help="Skip sources with no inventory changes since their last receipt.",
    ),
    dry_run: bool = typer.Option(
        True, "--dry-run/--apply",
        help="Default dry-run. --apply writes Markdown to the construction vault root.",
    ),
    source_from_receipts_only: bool = typer.Option(
        False, "--source-from-receipts-only",
        help="Skip live Graph crawl entirely and project from stored receipts.",
    ),
    max_pages: int = typer.Option(50, "--max-pages"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Build manifest + sync + processing-receipt projections (SQLite is authoritative).

    The Markdown output is a projection only — re-runnable, recomputable, never
    the source of truth for sync state.
    """

    import uuid

    registry = load_source_registry()
    targets = [s for s in registry.sources if source is None or s.source_key == source]
    if not targets:
        payload = {
            "command": "construction-agent sync",
            "status": "not_found",
            "requested": source,
            "available": [s.source_key for s in registry.sources],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1)

    store = ConstructionStore()
    service = ManifestService(store)
    run_id = str(uuid.uuid4())
    started_at = _utc_iso()

    # Construct the crawler if a token is available and the caller hasn't opted out.
    crawler: Optional[ConstructionDeltaCrawler] = None
    auth_payload: Optional[dict[str, Any]] = None
    if not source_from_receipts_only:
        provider = _build_auth_provider()
        client, auth_payload = _build_graph_client_or_auth_payload(provider)
        if client is not None:
            crawler = ConstructionDeltaCrawler(client, store)

    per_source: list = []
    skipped: list[dict[str, Any]] = []
    for src in targets:
        if changed_only:
            latest = store.list_recent_receipts(src.source_key, limit=1)
            since = latest[0]["finished_at"] if latest else "1970-01-01T00:00:00+00:00"
            changed_rows = store.list_inventory_changed_since(src.source_key, since, limit=1)
            if not changed_rows:
                skipped.append({"source_key": src.source_key, "reason": "no_changes_since_last_receipt"})
                continue

        if crawler is not None:
            crawl_receipt = crawler.crawl(
                source_key=src.source_key, dry_run=dry_run, max_pages=max_pages,
            )
            per_source.append(service.build_sync_receipt(crawl_receipt))
        else:
            per_source.append(
                service.build_sync_receipt_from_store(src.source_key, run_id, started_at)
            )

    finished_at = _utc_iso()
    mode = "dry_run" if dry_run else "apply"
    processing = service.build_processing_receipt(
        run_id=run_id,
        mode=mode,
        started_at=started_at,
        finished_at=finished_at,
        per_source=per_source,
    )
    manifests = {
        src.source_key: service.build_source_manifest(src, run_id=run_id)
        for src in targets
        if not any(s["source_key"] == src.source_key for s in skipped)
    }

    rendered_manifests = {
        k: ManifestRenderer.render_source_manifest(m) for k, m in manifests.items()
    }
    rendered_sync = {
        r.source_key: ManifestRenderer.render_sync_receipt(r) for r in per_source
    }
    rendered_processing = ManifestRenderer.render_processing_receipt(processing)

    written: list[dict[str, Any]] = []
    apply_error: Optional[str] = None
    if not dry_run:
        try:
            writer = ConstructionVaultWriter()
            for sk, rendered in rendered_manifests.items():
                wr = writer.write_source_manifest(source_key=sk, rendered=rendered)
                written.append({"kind": wr.kind, "path": str(wr.path), "bytes": wr.bytes_written})
            for r in per_source:
                wr = writer.write_sync_receipt(
                    source_key=r.source_key, run_id=r.run_id,
                    started_at=r.started_at, rendered=rendered_sync[r.source_key],
                )
                written.append({"kind": wr.kind, "path": str(wr.path), "bytes": wr.bytes_written})
            wr = writer.write_processing_receipt(
                run_id=processing.run_id, started_at=processing.started_at,
                rendered=rendered_processing,
            )
            written.append({"kind": wr.kind, "path": str(wr.path), "bytes": wr.bytes_written})
        except VaultRootNotConfigured as e:
            apply_error = str(e)

    payload: dict[str, Any] = {
        "command": "construction-agent sync",
        "mode": mode,
        "run_id": run_id,
        "started_at": started_at,
        "finished_at": finished_at,
        "targets": [s.source_key for s in targets],
        "skipped": skipped,
        "processing_receipt": processing.model_dump(),
        "manifests": {k: m.model_dump() for k, m in manifests.items()},
        "rendered": {
            "processing_receipt_md": rendered_processing,
            "sync_receipts_md": rendered_sync,
            "source_manifests_md": rendered_manifests,
        },
        "written": written,
        "guardrails": {
            "external_systems": "read_only",
            "writeback": "none",
            "metadata_only": True,
            "markdown_role": "projection_only",
            "sqlite_authoritative": True,
            "delta_token_storage": "sqlite",
        },
    }
    if auth_payload is not None:
        payload["auth"] = auth_payload
    if apply_error:
        payload["status"] = "vault_root_not_configured"
        payload["error"] = apply_error
        payload["hint"] = (
            "Set HB_CONSTRUCTION_VAULT_ROOT to a writable directory and re-run --apply."
        )
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(1)

    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


# ---------------------------------------------------------------------------
# Vault bootstrap + preview (Phase 01 Step 6 / Prompt 05)
# ---------------------------------------------------------------------------


@vault_app.command("bootstrap")
def vault_bootstrap(
    dry_run: bool = typer.Option(
        True, "--dry-run/--apply",
        help="Default dry-run; --apply creates the construction-vault subdirectories.",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Create (or plan) the 7 canonical construction-vault subdirectories."""

    writer = ConstructionVaultWriter()
    if not writer.configured:
        payload = {
            "command": "construction-agent vault bootstrap",
            "mode": "dry_run" if dry_run else "apply",
            "status": "vault_root_not_configured",
            "planned_subdirs": [s for _, s in writer.planned_subdirs()],
            "hint": (
                "Set HB_CONSTRUCTION_VAULT_ROOT or AppConfig.paths.construction_vault_root "
                "to enable apply writes."
            ),
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0 if dry_run else 1)

    try:
        results = writer.bootstrap_folders(dry_run=dry_run)
    except VaultRootNotConfigured as e:
        payload = {
            "command": "construction-agent vault bootstrap",
            "status": "vault_root_not_configured",
            "error": str(e),
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1) from None

    payload = {
        "command": "construction-agent vault bootstrap",
        "mode": "dry_run" if dry_run else "apply",
        "vault_root": str(writer.root),
        "subdirs": [
            {
                "subdir": r.subdir,
                "path": str(r.path),
                "existed_before": r.existed_before,
                "created": r.created,
            }
            for r in results
        ],
        "guardrails": {
            "external_systems": "read_only",
            "writeback": "none",
            "atomic_writes": True,
        },
    }
    typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
    raise typer.Exit(0)


@vault_app.command("preview")
def vault_preview(
    project: Optional[str] = typer.Option(None, "--project", help="Render only this project_key."),
    source: Optional[str] = typer.Option(None, "--source", help="Filter cards/manifests to this source_key."),
    include_review_required: bool = typer.Option(
        True, "--include-review-required/--no-include-review-required",
        help="Render the review-required note (empty placeholder until step 7).",
    ),
    include_document_cards: bool = typer.Option(
        False, "--include-document-cards",
        help="Opt-in to render document cards. Requires --document-item and --policy-reason.",
    ),
    document_item: Optional[str] = typer.Option(
        None, "--document-item", help="Specific item_id to render a document card for.",
    ),
    policy_reason: Optional[str] = typer.Option(
        None, "--policy-reason", help="Non-empty justification for emitting the document card.",
    ),
    apply: bool = typer.Option(False, "--apply", help="Write rendered Markdown to the vault."),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Render (or write) registry overview + project cards + review note + opt-in document card."""

    registry = load_source_registry()
    store = ConstructionStore()
    svc = ManifestService(store)

    overview = svc.build_registry_overview(registry)
    rendered_overview = ManifestRenderer.render_registry_overview(overview)

    target_projects = (
        [p for p in registry.projects if p.project_key == project]
        if project else list(registry.projects)
    )
    project_cards = [svc.build_project_card(registry, p.project_key) for p in target_projects]
    rendered_project_cards = {
        c.project_key: ManifestRenderer.render_project_card(c) for c in project_cards
    }

    rendered_review = None
    review_note = None
    if include_review_required:
        review_note = svc.build_review_required_note()
        rendered_review = ManifestRenderer.render_review_required(review_note)

    document_card = None
    rendered_document_card = None
    if include_document_cards:
        if not document_item or not policy_reason:
            payload = {
                "command": "construction-agent vault preview",
                "status": "document_card_requires_item_and_policy",
                "hint": "Pass --document-item ITEM_ID --policy-reason REASON when using --include-document-cards.",
            }
            typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
            raise typer.Exit(1)
        if not source:
            payload = {
                "command": "construction-agent vault preview",
                "status": "document_card_requires_source",
                "hint": "Pass --source KEY to scope the document card to a registered source.",
            }
            typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
            raise typer.Exit(1)
        src_match = next((s for s in registry.sources if s.source_key == source), None)
        if src_match is None:
            payload = {
                "command": "construction-agent vault preview",
                "status": "source_not_found",
                "requested": source,
                "available": [s.source_key for s in registry.sources],
            }
            typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
            raise typer.Exit(1)
        try:
            document_card = svc.build_document_card(
                source=src_match, item_id=document_item, policy_reason=policy_reason,
            )
        except (DocumentCardPolicyError, ValueError) as e:
            payload = {
                "command": "construction-agent vault preview",
                "status": "document_card_rejected",
                "error": str(e),
            }
            typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
            raise typer.Exit(1) from None
        rendered_document_card = ManifestRenderer.render_document_card(document_card)

    written: list[dict[str, Any]] = []
    if apply:
        try:
            writer = ConstructionVaultWriter()
            writer.bootstrap_folders(dry_run=False)
            wr = writer.write_registry_overview(rendered=rendered_overview)
            written.append({"kind": wr.kind, "path": str(wr.path), "bytes": wr.bytes_written})
            for pk, rendered in rendered_project_cards.items():
                wr = writer.write_project_card(project_key=pk, rendered=rendered)
                written.append({"kind": wr.kind, "path": str(wr.path), "bytes": wr.bytes_written})
            if review_note is not None and rendered_review is not None:
                wr = writer.write_review_required_note(
                    generated_at=review_note.generated_at, rendered=rendered_review,
                )
                written.append({"kind": wr.kind, "path": str(wr.path), "bytes": wr.bytes_written})
            if document_card is not None and rendered_document_card is not None:
                wr = writer.write_document_card(
                    source_key=document_card.source_key,
                    item_id=document_card.item_id,
                    rendered=rendered_document_card,
                )
                written.append({"kind": wr.kind, "path": str(wr.path), "bytes": wr.bytes_written})
        except VaultRootNotConfigured as e:
            payload = {
                "command": "construction-agent vault preview",
                "mode": "apply",
                "status": "vault_root_not_configured",
                "error": str(e),
                "hint": "Set HB_CONSTRUCTION_VAULT_ROOT or AppConfig.paths.construction_vault_root.",
            }
            typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
            raise typer.Exit(1) from None

    payload: dict[str, Any] = {
        "command": "construction-agent vault preview",
        "mode": "apply" if apply else "dry_run",
        "registry_overview": overview.model_dump(),
        "project_cards": {c.project_key: c.model_dump() for c in project_cards},
        "review_required": review_note.model_dump() if review_note else None,
        "document_card": document_card.model_dump() if document_card else None,
        "rendered": {
            "registry_overview_md": rendered_overview,
            "project_cards_md": rendered_project_cards,
            "review_required_md": rendered_review,
            "document_card_md": rendered_document_card,
        },
        "written": written,
        "guardrails": {
            "external_systems": "read_only",
            "writeback": "none",
            "metadata_only": True,
            "markdown_role": "projection_only",
            "atomic_writes": True,
            "document_card_policy": "opt_in_only",
        },
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


# ---------------------------------------------------------------------------
# Review queue (Phase 01 Step 7 / Prompt 06)
# ---------------------------------------------------------------------------


_REVIEW_GUARDRAILS = {
    "external_systems": "read_only",
    "writeback": "none",
    "metadata_only": True,
    "model_decisioning": False,
    "controller_policy_authoritative": True,
    "deterministic_rules_only": True,
}


@review_app.command("evaluate")
def review_evaluate(
    source: Optional[str] = typer.Option(
        None, "--source", help="Run only this source_key (default: all registered sources).",
    ),
    dry_run: bool = typer.Option(
        True, "--dry-run/--apply",
        help="Default dry-run; --apply persists matches to construction_review_queue.",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Apply the review-required policy across inventory and (optionally) enqueue matches."""

    try:
        rules = load_review_rules()
    except ReviewRulesError as e:
        payload = {
            "command": "construction-agent review evaluate",
            "status": "rules_unavailable",
            "error": str(e),
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1) from None

    registry = load_source_registry()
    if source is not None and not any(s.source_key == source for s in registry.sources):
        payload = {
            "command": "construction-agent review evaluate",
            "status": "not_found",
            "requested": source,
            "available": [s.source_key for s in registry.sources],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1)

    store = ConstructionStore()
    evaluator = ReviewPolicyEvaluator(rules)
    router = ReviewQueueRouter(store, evaluator)
    results = router.evaluate_registry(
        registry=registry, only_source_key=source, apply=not dry_run,
    )

    summary = {
        "sources_evaluated": len(results),
        "items_seen": sum(r.items_seen for r in results),
        "matches_found": sum(r.matches_found for r in results),
        "enqueued": sum(r.enqueued for r in results),
        "skipped_already_open": sum(r.skipped_already_open for r in results),
    }

    payload = {
        "command": "construction-agent review evaluate",
        "mode": "dry_run" if dry_run else "apply",
        "rules": {
            "version": rules.version,
            "rule_count": len(rules.rules),
            "low_confidence_threshold": rules.low_confidence_threshold,
        },
        "summary": summary,
        "results": [r.model_dump() for r in results],
        "guardrails": _REVIEW_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


@review_app.command("list")
def review_list(
    source: Optional[str] = typer.Option(
        None, "--source", help="Filter to one source_key (default: all sources).",
    ),
    status: str = typer.Option(
        "open", "--status",
        help="Filter by status: open | resolved | deferred | all (default: open).",
    ),
    limit: int = typer.Option(1000, "--limit"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """List rows in the construction review queue (read-only)."""

    allowed = {"open", "resolved", "deferred", "all"}
    if status not in allowed:
        payload = {
            "command": "construction-agent review list",
            "status": "invalid_status_filter",
            "requested": status,
            "allowed": sorted(allowed),
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1)

    store = ConstructionStore()
    rows = store.list_review_queue(
        source_key=source,
        status=None if status == "all" else status,
        limit=limit,
    )
    counts_by_status = {
        s: store.count_review_queue(source_key=source, status=s)
        for s in ("open", "resolved", "deferred")
    }

    payload = {
        "command": "construction-agent review list",
        "filter": {"source": source, "status": status, "limit": limit},
        "counts_by_status": counts_by_status,
        "total": len(rows),
        "items": rows,
        "guardrails": _REVIEW_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


# ---------------------------------------------------------------------------
# Ollama classification (Phase 01 Step 8 / Prompt 07)
# ---------------------------------------------------------------------------


_CLASSIFY_GUARDRAILS = {
    "external_systems": "read_only",
    "writeback": "none",
    "metadata_only": True,
    "model_role": "recommendation_only",
    "controller_policy_authoritative": True,
    "invalid_json_rejected": True,
    "low_confidence_routes_to_review": True,
    "no_protected_category_auto_accept": True,
    "no_source_document_body_read": True,
}


# Built-in fixture set for offline demonstration. Pairs an inventory shape
# (name + parent_path) with a raw model output for the same item_id.
_FIXTURES: dict[str, list[dict[str, Any]]] = {
    "sample": [
        {
            "item_id": "fixture-photos",
            "inventory": {
                "item_id": "fixture-photos",
                "name": "Site Photos 2026-04-12.zip",
                "parent_path": "/Tropical/General",
            },
            "raw_output": (
                '{"item_id":"fixture-photos","proposed_label":"operational",'
                '"confidence":0.92,"rationale":"daily photo upload",'
                '"risk_terms":[]}'
            ),
        },
        {
            "item_id": "fixture-contract",
            "inventory": {
                "item_id": "fixture-contract",
                "name": "Master Agreement v3.pdf",
                "parent_path": "/Tropical/Contracts/Vendors",
            },
            "raw_output": (
                '{"item_id":"fixture-contract","proposed_label":"contract",'
                '"confidence":0.95,"rationale":"contract document",'
                '"risk_terms":["agreement"]}'
            ),
        },
        {
            "item_id": "fixture-lowconf",
            "inventory": {
                "item_id": "fixture-lowconf",
                "name": "Draft Notes.docx",
                "parent_path": "/Tropical/General",
            },
            "raw_output": (
                '{"item_id":"fixture-lowconf","proposed_label":"other",'
                '"confidence":0.35,"rationale":"ambiguous draft",'
                '"risk_terms":[]}'
            ),
        },
    ],
}


@classify_app.command("run")
def classify_run(
    source: Optional[str] = typer.Option(
        None, "--source", help="Source key (required unless --fixture is set).",
    ),
    item: Optional[str] = typer.Option(
        None, "--item", help="Inventory item_id (required unless --fixture is set).",
    ),
    fixture: Optional[str] = typer.Option(
        None, "--fixture", help="Run an offline built-in fixture set by name (e.g. 'sample').",
    ),
    task: str = typer.Option(
        "classification", "--task",
        help="Model task: classification | review_reason.",
    ),
    mock_output: Optional[str] = typer.Option(
        None, "--mock-output",
        help="Raw model output to feed in offline (bypasses Ollama). For testing / proof.",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Run the classifier. With --fixture: offline demo. With --source/--item: live or mocked."""

    if task not in ("classification", "review_reason"):
        payload = {
            "command": "construction-agent classify run",
            "status": "invalid_task",
            "requested": task,
            "allowed": ["classification", "review_reason"],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1)

    try:
        config = load_model_routing_config()
    except ModelRoutingError as e:
        payload = {
            "command": "construction-agent classify run",
            "status": "routing_config_unavailable",
            "error": str(e),
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1) from None

    try:
        rules = load_review_rules()
        policy_evaluator = ReviewPolicyEvaluator(rules)
    except ReviewRulesError:
        policy_evaluator = None  # router still works; controller check is skipped

    store = ConstructionStore()
    router = ClassificationRouter(config, policy_evaluator=policy_evaluator)
    service = ClassificationService(config=config, router=router, store=store)
    task_routing = config.task_for(task)  # type: ignore[arg-type]

    if fixture is not None:
        if fixture not in _FIXTURES:
            payload = {
                "command": "construction-agent classify run",
                "status": "unknown_fixture",
                "requested": fixture,
                "available": sorted(_FIXTURES.keys()),
            }
            typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
            raise typer.Exit(1)
        decisions: list[dict[str, Any]] = []
        rejected: list[dict[str, Any]] = []
        for entry in _FIXTURES[fixture]:
            try:
                decision = service.classify_with_raw(
                    raw_output=entry["raw_output"],
                    source_key="fixture",
                    item_id=entry["item_id"],
                    project_key=None,
                    model_task=task,  # type: ignore[arg-type]
                    model_name=task_routing.model,
                    inventory_item=entry["inventory"],
                )
                decisions.append(decision.model_dump())
            except InvalidModelOutputError as e:
                rejected.append({
                    "item_id": entry["item_id"], "code": e.code, "detail": e.detail,
                })
        payload = {
            "command": "construction-agent classify run",
            "mode": "fixture",
            "fixture": fixture,
            "decisions": decisions,
            "rejected": rejected,
            "summary": {
                "total": len(_FIXTURES[fixture]),
                "accepted": sum(1 for d in decisions if d["status"] == "accepted"),
                "review": sum(1 for d in decisions if d["status"] == "review"),
                "rejected": len(rejected),
            },
            "guardrails": _CLASSIFY_GUARDRAILS,
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(0)

    # Live or mocked single-item path
    if source is None or item is None:
        payload = {
            "command": "construction-agent classify run",
            "status": "missing_required_args",
            "hint": "Either pass --fixture NAME, or pass both --source KEY and --item ITEM_ID.",
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1)

    inventory_rows = store.list_inventory_for_source(source)
    inventory_item = next((r for r in inventory_rows if r.get("item_id") == item), None)
    if inventory_item is None:
        payload = {
            "command": "construction-agent classify run",
            "status": "item_not_found",
            "source": source,
            "item": item,
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1)

    if mock_output is None:
        payload = {
            "command": "construction-agent classify run",
            "status": "live_call_disabled",
            "hint": (
                "Live Ollama calls are not wired into the CLI in this prompt. "
                "Pass --mock-output '<raw json>' to exercise the validator + router + store."
            ),
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1)

    registry = load_source_registry()
    src_entry = next((s for s in registry.sources if s.source_key == source), None)
    project_key = src_entry.project_key if src_entry is not None else None

    try:
        decision = service.classify_with_raw(
            raw_output=mock_output,
            source_key=source,
            item_id=item,
            project_key=project_key,
            model_task=task,  # type: ignore[arg-type]
            model_name=task_routing.model,
            inventory_item=inventory_item,
        )
    except InvalidModelOutputError as e:
        payload = {
            "command": "construction-agent classify run",
            "status": "invalid_model_output",
            "code": e.code,
            "detail": e.detail,
            "snippet": e.snippet,
            "guardrails": _CLASSIFY_GUARDRAILS,
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1) from None

    payload = {
        "command": "construction-agent classify run",
        "mode": "mock_output",
        "decision": decision.model_dump(),
        "guardrails": _CLASSIFY_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


@classify_app.command("decisions")
def classify_decisions(
    source: Optional[str] = typer.Option(None, "--source"),
    status: str = typer.Option(
        "all", "--status", help="Filter by status: accepted | review | all (default: all).",
    ),
    limit: int = typer.Option(1000, "--limit"),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """List the construction model-decisions audit table (read-only)."""

    allowed = {"accepted", "review", "all"}
    if status not in allowed:
        payload = {
            "command": "construction-agent classify decisions",
            "status": "invalid_status_filter",
            "requested": status,
            "allowed": sorted(allowed),
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1)

    store = ConstructionStore()
    rows = store.list_model_decisions(
        source_key=source,
        status=None if status == "all" else status,
        limit=limit,
    )
    counts = {
        s: store.count_model_decisions(source_key=source, status=s)
        for s in ("accepted", "review")
    }
    payload = {
        "command": "construction-agent classify decisions",
        "filter": {"source": source, "status": status, "limit": limit},
        "counts_by_status": counts,
        "total": len(rows),
        "items": rows,
        "guardrails": _CLASSIFY_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


# ---------------------------------------------------------------------------
# Operator surface: index status + top-level validate (Phase 01 Step 9 / Prompt 08)
# ---------------------------------------------------------------------------


_INDEX_GUARDRAILS = {
    "external_systems": "read_only",
    "writeback": "none",
    "metadata_only": True,
    "command_role": "read_only_dashboard",
}


def _per_source_index(store: "ConstructionStore", src: Any) -> dict[str, Any]:
    resolution = store.get_resolution(src.source_key) or {}
    token = store.get_delta_token(src.source_key) or {}
    counts = store.count_inventory(src.source_key)
    recent = store.list_recent_receipts(src.source_key, limit=1)
    last_receipt = recent[0] if recent else {}
    return {
        "source_key": src.source_key,
        "project_key": src.project_key,
        "kind": src.kind,
        "display_name": src.display_name,
        "resolution_status": resolution.get(
            "resolution_status", src.resolution_status,
        ),
        "drive_id_present": bool(resolution.get("drive_id")),
        "inventory_counts": dict(counts),
        "last_sync_at": token.get("last_sync_at"),
        "last_receipt_status": last_receipt.get("status"),
        "last_receipt_finished_at": last_receipt.get("finished_at"),
    }


@ollama_app.command("status")
def ollama_status(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Report local Ollama daemon readiness without running inference.

    Probes ``/api/tags`` only — never ``/api/generate``. Always exits 0;
    callers consume the ``report.ok`` and ``report.status`` fields. Designed
    so CI / offline contexts can call this command without a live daemon.
    """
    try:
        config = load_model_routing_config()
    except ModelRoutingError as e:
        payload = {
            "command": "construction-agent ollama status",
            "report": {
                "endpoint_url": "",
                "endpoint_source": "default",
                "daemon_reachable": False,
                "expected_models": [],
                "present_models": [],
                "missing_models": [],
                "suggested_pull_commands": [],
                "status": "config_invalid",
                "ok": False,
                "error_redacted": "model_routing_config_invalid",
            },
            "guardrails": {
                "external_systems": "read_only",
                "writeback": "none",
                "live_inference": "false",
                "endpoint_path": "/api/tags",
            },
            "note": str(e),
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(0) from None

    report: ReadinessReport = check_readiness(config)
    payload = {
        "command": "construction-agent ollama status",
        "report": report.model_dump(),
        "guardrails": {
            "external_systems": "read_only",
            "writeback": "none",
            "live_inference": "false",
            "endpoint_path": "/api/tags",
        },
    }
    typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
    raise typer.Exit(0)


@app.command("index")
def index_status(
    op: str = typer.Argument("status", help="Index operation. Only 'status' is supported."),
    source: Optional[str] = typer.Option(
        None, "--source", help="Filter dashboard to one registered source_key.",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Read-only dashboard across all construction-agent layers."""

    if op != "status":
        payload = {
            "command": "construction-agent index",
            "status": "unsupported_operation",
            "requested": op,
            "allowed": ["status"],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1)

    # Source registry (required)
    try:
        registry = load_source_registry()
    except SourceRegistryError as e:
        payload = {
            "command": "construction-agent index status",
            "status": "source_registry_unavailable",
            "error": str(e),
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1) from None

    if source is not None and not any(s.source_key == source for s in registry.sources):
        payload = {
            "command": "construction-agent index status",
            "status": "not_found",
            "requested": source,
            "available": [s.source_key for s in registry.sources],
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1)

    store = ConstructionStore()
    schema_version = SQLiteMigrator().current_version()

    targets = [
        s for s in registry.sources if source is None or s.source_key == source
    ]
    per_source = [_per_source_index(store, s) for s in targets]

    review_queue = {
        s: store.count_review_queue(source_key=source, status=s)
        for s in ("open", "resolved", "deferred")
    }
    model_decisions = {
        s: store.count_model_decisions(source_key=source, status=s)
        for s in ("accepted", "review")
    }

    # Policy snapshots — best-effort; failures are non-fatal and surface as
    # null entries with an explanation.
    review_rules_summary: dict[str, Any] | None = None
    try:
        rr = load_review_rules()
        review_rules_summary = {
            "version": rr.version,
            "rule_count": len(rr.rules),
            "low_confidence_threshold": rr.low_confidence_threshold,
        }
    except ReviewRulesError as e:
        review_rules_summary = {"status": "unavailable", "error": str(e)}

    model_routing_summary: dict[str, Any] | None = None
    try:
        mr = load_model_routing_config()
        model_routing_summary = {
            "version": mr.version,
            "default_model": mr.default_model,
            "low_confidence_threshold": mr.low_confidence_threshold,
            "tasks": [t.task for t in mr.tasks],
        }
    except ModelRoutingError as e:
        model_routing_summary = {"status": "unavailable", "error": str(e)}

    payload = {
        "command": "construction-agent index status",
        "schema_version": schema_version,
        "summary": {
            "project_count": len(registry.projects),
            "source_count": len(registry.sources),
            "sources_in_view": len(per_source),
        },
        "sources": per_source,
        "review_queue": review_queue,
        "model_decisions": model_decisions,
        "policies": {
            "review_rules": review_rules_summary,
            "model_routing": model_routing_summary,
        },
        "guardrails": _INDEX_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


def _validate_schema() -> dict[str, Any]:
    # apply() is idempotent and matches what every other CLI command implicitly
    # does when it instantiates ConstructionStore(). Treats schema readiness as
    # part of the validate health check.
    v = SQLiteMigrator().apply()
    ok = v >= 4
    return {
        "name": "schema",
        "ok": ok,
        "detail": f"schema_version={v}",
        "error": None if ok else f"schema below v4 (got {v})",
    }


def _validate_source_registry() -> dict[str, Any]:
    try:
        registry = load_source_registry()
    except SourceRegistryError as e:
        return {"name": "source_registry", "ok": False, "detail": None, "error": str(e)}
    except ValidationError as e:
        return {
            "name": "source_registry", "ok": False, "detail": None,
            "error": f"{len(e.errors())} validation error(s)",
        }
    return {
        "name": "source_registry", "ok": True,
        "detail": f"{len(registry.projects)} projects, {len(registry.sources)} sources",
        "error": None,
    }


def _validate_review_rules() -> dict[str, Any]:
    try:
        rr = load_review_rules()
    except ReviewRulesError as e:
        return {"name": "review_rules", "ok": False, "detail": None, "error": str(e)}
    except ValidationError as e:
        return {
            "name": "review_rules", "ok": False, "detail": None,
            "error": f"{len(e.errors())} validation error(s)",
        }
    return {
        "name": "review_rules", "ok": True,
        "detail": f"version={rr.version}; {len(rr.rules)} rules; threshold={rr.low_confidence_threshold}",
        "error": None,
    }


def _validate_model_routing() -> dict[str, Any]:
    try:
        mr = load_model_routing_config()
    except ModelRoutingError as e:
        return {"name": "model_routing", "ok": False, "detail": None, "error": str(e)}
    except ValidationError as e:
        return {
            "name": "model_routing", "ok": False, "detail": None,
            "error": f"{len(e.errors())} validation error(s)",
        }
    return {
        "name": "model_routing", "ok": True,
        "detail": f"version={mr.version}; default_model={mr.default_model}; tasks={[t.task for t in mr.tasks]}",
        "error": None,
    }


@app.command("validate")
def validate_all(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Multi-layer config sanity check (schema + source registry + review rules + model routing)."""

    checks = [
        _validate_schema(),
        _validate_source_registry(),
        _validate_review_rules(),
        _validate_model_routing(),
    ]
    passed = sum(1 for c in checks if c["ok"])
    failed = len(checks) - passed
    payload = {
        "command": "construction-agent validate",
        "checks": checks,
        "summary": {
            "total": len(checks),
            "passed": passed,
            "failed": failed,
            "ok": failed == 0,
        },
        "guardrails": _INDEX_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0 if failed == 0 else 1)


# ---------------------------------------------------------------------------
# Fixture validation harness (Phase 01 Step 11 / Prompt 10)
# ---------------------------------------------------------------------------


_FIXTURES_GUARDRAILS = {
    "external_systems": "read_only",
    "writeback": "none",
    "metadata_only": True,
    "live_calls_disabled": True,
    "no_secrets_in_fixtures": True,
    "no_source_document_body": True,
}


@fixtures_app.command("validate")
def fixtures_validate(
    kind: Optional[str] = typer.Option(
        None, "--kind",
        help=(
            "Filter to one fixture kind: "
            "graph_delta | source_registry | review_policy | model_output | procore."
        ),
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Walk the canonical fixture inventory and validate every fixture."""

    if kind is not None and kind not in FIXTURE_KIND_ALIASES:
        payload = {
            "command": "construction-agent fixtures validate",
            "status": "invalid_kind_filter",
            "requested": kind,
            "allowed": sorted(FIXTURE_KIND_ALIASES),
        }
        typer.echo(json.dumps(payload, indent=2) if json_out else str(payload))
        raise typer.Exit(1)

    report = FixtureHarness().validate_all(kind=kind)
    payload = {
        "command": "construction-agent fixtures validate",
        "filter": {"kind": kind},
        "report": report.model_dump(),
        "guardrails": _FIXTURES_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0 if report.ok else 1)


# ---------------------------------------------------------------------------
# Phase 07A Prompt 02 — data-quality subgroup (first command: project-coverage)
# ---------------------------------------------------------------------------

_DATA_QUALITY_GUARDRAILS = {
    "external_systems": "read_only",
    "writeback": "local_sqlite_only_on_apply",
    "no_raw_content": True,
    "conflicts_require_review": True,
}


@data_quality_app.command("project-coverage")
def project_coverage(
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Perform the identity backfill upserts (default is dry-run / report only).",
    ),
    project: Optional[str] = typer.Option(
        None,
        "--project",
        help="Limit to a single project_key (for focused runs).",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Local-only canonical project identity backfill + coverage matrix (Phase 07A).

    Dry-run by default: computes signals from local seeds + SQLite, emits the
    project coverage matrix and any conflicts (never auto-resolves conflicts).
    With --apply: writes to construction_project_identity and _source_matches
    (V5 tables) via idempotent upserts. All writes are local metadata only.
    """
    builder = ProjectIdentityBackfill()
    report = builder.run(dry_run=not apply, project_filter=project)

    payload = {
        "command": "construction-agent data-quality project-coverage",
        "apply": apply,
        "filter": {"project": project},
        "report": report,
        "guardrails": _DATA_QUALITY_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    # Non-zero only on internal error (not on dry-run or conflicts)
    raise typer.Exit(0)


# ---------------------------------------------------------------------------
# Phase 07A Prompt 03 — data-quality source-record-map (explicit --dry-run/--apply)
# ---------------------------------------------------------------------------

@data_quality_app.command("source-record-map")
def source_record_map(
    dry_run: bool = typer.Option(
        False,
        "--dry-run",
        help="Preview only (no writes). Default when neither flag given.",
    ),
    apply: bool = typer.Option(
        False,
        "--apply",
        help="Persist rows to source_system_record_map (V20).",
    ),
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Local-only source-system record map (Phase 07A Prompt 03).

    Deterministic canonical IDs for Procore (live + financial), email (messages +
    project-match candidates), Graph (drive items + ingestion decisions), and
    body vault refs. Links to Prompt 02 project identities or row signals.
    Weak / candidate / pilot-unmapped rows always get review_required + reason
    in the emitted unmapped list. Active-pilot sources are never silently ignored.

    No flag or --dry-run: preview (no DB writes).
    --apply: performs the upserts.
    Both flags: error (mutual exclusion).
    """
    if not dry_run and not apply:
        dry_run = True  # no flag => dry-run (per spec clarification)
    if dry_run and apply:
        payload = {
            "command": "construction-agent data-quality source-record-map",
            "status": "invalid_flags",
            "error": "--dry-run and --apply are mutually exclusive",
            "hint": "Use --dry-run (or no flag) for preview or --apply to persist.",
        }
        typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
        raise typer.Exit(2)

    builder = SourceRecordMapBuilder()
    report = builder.run(dry_run=not apply)

    payload = {
        "command": "construction-agent data-quality source-record-map",
        "dry_run": dry_run and not apply,
        "apply": apply,
        "report": report,
        "guardrails": _DATA_QUALITY_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


# ---------------------------------------------------------------------------
# Phase 07A Prompt 04 — data-quality relationships (report-focused diagnostics)
# ---------------------------------------------------------------------------

_RELATIONSHIP_GUARDRAILS = {
    "external_systems": "read_only",
    "writeback": "local_sqlite_queue_only_for_review_candidates",
    "no_raw_content": True,
    "model_proposed_always_review": True,
    "sensitive_always_review": True,
    "separate_orphan_rates": True,
    "no_auto_promotion": True,
}


@data_quality_app.command("relationships")
def relationships(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Local-only relationship orphan and confidence diagnostics (Phase 07A Prompt 04).

    Scans Procore edges (action signals + timeline/change events), email relationship
    candidates, Graph file/project matches, and source-record-map cross links.
    Resolves via Prompt 02/03 artifacts. Classifies per 08_ categories and policy JSON.
    Always emits separate deterministic_orphan_rate and candidate_orphan_rate.
    Model-proposed, weak, and sensitive relationships are always review-required and
    never auto-promoted (hard guard in builder + CLI).
    """
    diag = RelationshipDiagnostics()
    report = diag.run(dry_run=True)  # report mode per spec validation example

    payload = {
        "command": "construction-agent data-quality relationships",
        "report": report,
        "guardrails": _RELATIONSHIP_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)


# ---------------------------------------------------------------------------
# Phase 07A Prompt 05 — data-quality marts (agent-ready query marts + latency)
# ---------------------------------------------------------------------------

_MARTS_GUARDRAILS = {
    "external_systems": "read_only",
    "writeback": "local_sqlite_marts_only",
    "no_raw_content": True,
    "additive_only": True,
    "review_required_visible": True,
    "latency_measured": True,
}


@data_quality_app.command("marts")
def marts(
    json_out: bool = typer.Option(True, "--json"),
) -> None:
    """Agent-ready query marts (Phase 07A Prompt 05).

    Populates the four local read models (project coverage reuse + source-record
    summary, relationship quality, cross-domain readiness) and reports row counts
    plus wall-clock latency (perf_counter) for the eight target local-agent queries.
    """
    from hb_assistant.construction.data_quality import populate_agent_ready_query_marts

    report = populate_agent_ready_query_marts()

    payload = {
        "command": "construction-agent data-quality marts",
        "report": report,
        "guardrails": _MARTS_GUARDRAILS,
    }
    typer.echo(json.dumps(payload, indent=2, default=str) if json_out else str(payload))
    raise typer.Exit(0)
