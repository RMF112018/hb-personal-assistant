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
from hb_assistant.construction.config import (
    SourceRegistry,
    load_source_registry,
)
from hb_assistant.construction.config.loader import SourceRegistryError
from hb_assistant.construction.graph import (
    GRAPH_SCOPES,
    ConstructionDeltaCrawler,
    ConstructionGraphResolver,
    ResolutionResult,
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

app = typer.Typer(help="Construction-management intelligence layer (read-only).")
sources_app = typer.Typer(help="Source registry inspection.")
graph_app = typer.Typer(help="Read-only Microsoft Graph crawler.")
graph_sources_app = typer.Typer(help="Graph source resolution.")
vault_app = typer.Typer(help="Construction vault preview and bootstrap.")
review_app = typer.Typer(help="Review-queue policy evaluation and inspection.")
app.add_typer(sources_app, name="sources")
app.add_typer(graph_app, name="graph")
graph_app.add_typer(graph_sources_app, name="sources")
app.add_typer(vault_app, name="vault")
app.add_typer(review_app, name="review")


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
) -> tuple[Optional[GraphHttpClient], Optional[dict[str, Any]]]:
    """Return (client, auth_required_payload).

    The CLI never triggers an interactive login. If no cached token exists
    for the required scopes, we return a structured ``auth_required`` payload
    so non-interactive callers (CI, sandboxes) can interpret the result.
    """

    try:
        token = provider.get_token(GRAPH_SCOPES)
    except Exception as e:  # noqa: BLE001 — surface as structured payload
        return None, {
            "status": "auth_required",
            "scopes": GRAPH_SCOPES,
            "detail": str(e)[:200],
            "hint": "Run `hb-assistant auth login --json` interactively to obtain a delegated token.",
        }

    if "access_token" not in token:
        return None, {
            "status": "auth_required",
            "scopes": GRAPH_SCOPES,
            "detail": token.get("error_description") or token.get("error") or "no_access_token_in_cache",
            "hint": "Run `hb-assistant auth login --json` interactively to obtain a delegated token.",
        }

    def token_getter(scopes: Optional[list[str]] = None) -> dict[str, Any]:
        return provider.get_token(scopes or GRAPH_SCOPES)

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

    payload = {
        "command": "construction-agent graph sources resolve",
        "mode": "apply" if apply else "dry_run",
        "results": [_resolution_to_dict(r) for r in results],
        "summary": {
            "total": len(results),
            "resolved": sum(1 for r in results if r.status == "resolved"),
            "pending": sum(1 for r in results if r.status == "pending"),
            "unsupported": sum(1 for r in results if r.status == "unsupported"),
            "error": sum(1 for r in results if r.status == "error"),
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
    client, auth_payload = _build_graph_client_or_auth_payload(provider)
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
