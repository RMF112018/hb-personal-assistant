"""Connection setup services for the optional analytics UI shell."""

from __future__ import annotations

import contextlib
import hashlib
import re
from typing import Any
from urllib.parse import parse_qs, urlparse, urlunparse

from hb_assistant.construction.calendar.policy import load_calendar_source_policy
from hb_assistant.construction.config import load_source_registry
from hb_assistant.construction.store import ConstructionStore

_PENDING = "pending_admin_approval"
_APPROVED = "approved_first_sync_not_started"
_USER_REFRESH_REQUESTED = "user_refresh_requested"
_PROJECT_ID_RE = re.compile(r"/projects/(?P<project_id>\d+)(?:/|$)")
_FOLDER_ID_RE = re.compile(r"(?:id|resid|cid)=([^&]+)", re.IGNORECASE)


def _guardrails() -> dict[str, Any]:
    return {
        "local_setup_only": True,
        "no_cli_shellout": True,
        "no_live_endpoint_calls": True,
        "no_external_writeback": True,
        "tokens_returned": False,
        "secrets_returned": False,
        "first_sync_triggered": False,
        "user_refresh_requests_supported": True,
        "freshness_computed_from_local_sync_state": True,
    }


def _fingerprint(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()[:16]


def _slug(value: str) -> str:
    text = re.sub(r"[^a-z0-9]+", "-", value.strip().lower()).strip("-")
    return text[:80] or "connection"


def _safe_url_parts(url: str) -> tuple[str, str, list[str], dict[str, list[str]]]:
    parsed = urlparse(url.strip())
    host = parsed.netloc.lower()
    path = parsed.path or ""
    segments = [s for s in path.split("/") if s]
    query = parse_qs(parsed.query)
    return host, path, segments, query


def _without_query_fragment(url: str) -> str:
    parsed = urlparse(url.strip())
    return urlunparse((parsed.scheme, parsed.netloc, parsed.path, "", "", ""))


def _site_url(url: str, segments: list[str]) -> str | None:
    if len(segments) >= 2 and segments[0].lower() in {"sites", "teams"}:
        parsed = urlparse(url.strip())
        return urlunparse(
            (parsed.scheme, parsed.netloc, f"/{segments[0]}/{segments[1]}", "", "", "")
        )
    return None


class ConnectionSetupService:
    """Preview and persist local connection setup metadata.

    The service never starts live sync and never calls Graph, Procore, Typer, or
    source-system data APIs. Writes are local SQLite setup/sync-state rows only.
    """

    def __init__(self, *, db_path: str | None = None) -> None:
        self._db_path = db_path
        self._store = ConstructionStore(db_path)

    def preview_connection(self, request: dict[str, Any]) -> dict[str, Any]:
        url = str(request.get("url") or "").strip()
        connection_type = str(request.get("connection_type") or "").strip().lower()
        if (
            connection_type in {"outlook", "calendar"}
            or request.get("include_outlook")
            or request.get("include_calendar")
        ):
            return self._preview_microsoft_options(request)
        if not url:
            return self._unavailable("missing_url", "Provide a URL or Microsoft scope option.")

        host, path, segments, query = _safe_url_parts(url)
        if "procore" in host:
            return self._preview_procore(url, segments, query, request)
        if "sharepoint.com" in host:
            if "-my.sharepoint.com" in host or connection_type == "onedrive":
                return self._preview_onedrive(url, host, path, query, request)
            return self._preview_sharepoint(url, host, segments, request)
        if "onedrive.live.com" in host:
            return self._preview_onedrive(url, host, path, query, request)
        return self._unavailable(
            "unsupported_url", "Only Procore, SharePoint, and OneDrive URLs are supported."
        )

    def save_connection(self, request: dict[str, Any]) -> dict[str, Any]:
        preview = self.preview_connection(request)
        if preview.get("status") != "ready_to_save":
            return {
                "ok": False,
                "kind": "connection_save_rejected",
                "reason_code": preview.get("reason_code", "preview_not_saveable"),
                "preview": preview,
                "guardrails": _guardrails(),
            }
        connection_id = str(request.get("connection_id") or preview["connection_id"])
        source = preview["proposed_source"]
        kind = preview["detected_source_type"]
        if kind == "procore_project":
            self._save_procore(connection_id, source)
        elif kind in {
            "sharepoint_site",
            "sharepoint_folder",
            "sharepoint_site_page",
            "onedrive_scope",
        }:
            self._save_file_source(connection_id, source)
        elif kind == "microsoft365_options":
            self._save_microsoft_options(connection_id, preview["options"])
        else:
            return {
                "ok": False,
                "kind": "connection_save_rejected",
                "reason_code": "unsupported_connection_type",
                "guardrails": _guardrails(),
            }
        return {
            "ok": True,
            "kind": "connection_saved",
            "connection_id": connection_id,
            "detected_source_type": kind,
            "first_sync_status": _PENDING,
            "admin_approval_required": True,
            "guardrails": _guardrails(),
        }

    def approve_first_sync(self, connection_id: str) -> dict[str, Any]:
        source = self._store.get_source_location(connection_id)
        if source:
            self._store.upsert_source_sync_state(
                source_id=connection_id,
                drive_id=source.get("drive_id"),
                folder_item_id=source.get("folder_item_id"),
                sync_status=_APPROVED,
            )
            return self._approval_response(connection_id, "graph_file_source")
        identity = self._store.get_project_identity(connection_id.replace("procore_", "", 1))
        if identity:
            return self._approval_response(connection_id, "procore_project")
        return {
            "ok": False,
            "kind": "connection_not_found",
            "connection_id": connection_id,
            "reason_code": "requires_saved_connection",
            "guardrails": _guardrails(),
        }

    def save_project_sync_schedule(
        self, project_key: str, request: dict[str, Any]
    ) -> dict[str, Any]:
        sources = self._store.list_source_locations(project_key=project_key, limit=1000)
        if not sources:
            return {
                "ok": False,
                "kind": "requires_read_model",
                "project_key": project_key,
                "reason_code": "no_saved_project_sources",
                "guardrails": _guardrails(),
            }
        cadence = request.get("cadence_minutes")
        priority = str(request.get("priority") or "normal")
        rate_limit = request.get("rate_limit")
        status = f"schedule_pending_admin:cadence={cadence or 'default'};priority={priority}"
        if rate_limit:
            status += f";rate_limit={rate_limit}"
        updated: list[str] = []
        for source in sources:
            self._store.upsert_source_sync_state(
                source_id=source["source_id"],
                drive_id=source.get("drive_id"),
                folder_item_id=source.get("folder_item_id"),
                sync_status=status,
            )
            # Persist cadence into the location's frequency (supported field) for downstream use
            with contextlib.suppress(Exception):
                self._store.upsert_source_location(
                    source_id=source["source_id"],
                    source_system=source.get("source_system") or "unknown",
                    source_scope=source.get("source_scope") or "unknown",
                    source_name=source.get("source_name") or source["source_id"],
                    project_key=source.get("project_key"),
                    project_number=source.get("project_number"),
                    project_name=source.get("project_name"),
                    tenant_id=source.get("tenant_id"),
                    site_url=source.get("site_url"),
                    site_id=source.get("site_id"),
                    drive_id=source.get("drive_id"),
                    folder_item_id=source.get("folder_item_id"),
                    folder_path=source.get("folder_path"),
                    folder_web_url=source.get("folder_web_url"),
                    library_name=source.get("library_name"),
                    list_id=source.get("list_id"),
                    local_sync_path=source.get("local_sync_path"),
                    sync_mode=source.get("sync_mode"),
                    sync_frequency_minutes=(
                        int(cadence)
                        if cadence is not None
                        else source.get("sync_frequency_minutes")
                    ),
                    enabled=bool(source.get("enabled", True)),
                    read_only=True,
                    folder_policies=source.get("folder_policies"),
                )
            updated.append(source["source_id"])
        return {
            "ok": True,
            "kind": "project_sync_schedule_saved",
            "project_key": project_key,
            "scheduled_source_count": len(updated),
            "cadence_minutes": cadence,
            "priority": priority,
            "first_sync_triggered": False,
            "guardrails": _guardrails(),
        }

    def request_user_refresh(self, project_key: str) -> dict[str, Any]:
        """Low-friction user (CM) surface to request a refresh for a project.

        Sets local sync_state marker to _USER_REFRESH_REQUESTED on the project's
        sources. Does not trigger live sync or require immediate admin action
        (admin can observe via pending or schedule). Operator or admin role.
        """
        sources = self._store.list_source_locations(project_key=project_key, limit=1000)
        if not sources:
            return {
                "ok": False,
                "kind": "requires_read_model",
                "project_key": project_key,
                "reason_code": "no_saved_project_sources",
                "guardrails": _guardrails(),
            }
        updated: list[str] = []
        for source in sources:
            self._store.upsert_source_sync_state(
                source_id=source["source_id"],
                drive_id=source.get("drive_id"),
                folder_item_id=source.get("folder_item_id"),
                sync_status=_USER_REFRESH_REQUESTED,
            )
            updated.append(source["source_id"])
        return {
            "ok": True,
            "kind": "user_refresh_requested",
            "project_key": project_key,
            "affected_source_count": len(updated),
            "admin_approval_required": True,
            "guardrails": _guardrails(),
        }

    def get_project_sync_freshness(self, project_key: str) -> dict[str, Any]:
        """Automatic freshness status derived purely from local sync_state.

        Returns per-source last timestamps, computed minutes_ago, and coarse
        freshness label (fresh/stale/never) plus the current sync_status marker.
        Viewer accessible (read-only metadata). No live calls.
        """
        from datetime import datetime, timezone

        sources = self._store.list_source_locations(project_key=project_key, limit=1000)
        items: list[dict[str, Any]] = []
        ages: list[int] = []
        for source in sources:
            state = self._store.get_source_sync_state(source["source_id"]) or {}
            last_s = state.get("last_successful_sync_utc")
            last_a = state.get("last_attempted_sync_utc")
            last = last_s or last_a
            minutes_ago: int | None = None
            freshness = "never"
            if last:
                try:
                    # tolerate Z or offset
                    ts = last.replace("Z", "+00:00")
                    dt = datetime.fromisoformat(ts)
                    if dt.tzinfo is None:
                        dt = dt.replace(tzinfo=timezone.utc)
                    delta_min = int((datetime.now(timezone.utc) - dt).total_seconds() / 60)
                    minutes_ago = max(0, delta_min)
                    if minutes_ago < 60:
                        freshness = "fresh"
                    elif minutes_ago < 1440:
                        freshness = "stale"
                    else:
                        freshness = "stale"
                    ages.append(minutes_ago)
                except Exception:
                    pass
            items.append(
                {
                    "source_id": source["source_id"],
                    "source_name": source.get("source_name"),
                    "last_successful_sync_utc": last_s,
                    "last_attempted_sync_utc": last_a,
                    "sync_status": state.get("sync_status"),
                    "minutes_ago": minutes_ago,
                    "freshness": freshness,
                }
            )
        overall = "unknown"
        if ages:
            min_age = min(ages)
            overall = "fresh" if min_age < 60 else "stale"
        elif items:
            overall = "never" if all(i["freshness"] == "never" for i in items) else "stale"
        return {
            "surface": "analytics.sync_governance.project_freshness",
            "project_key": project_key,
            "overall_freshness": overall,
            "source_count": len(items),
            "sources": items,
            "guardrails": _guardrails(),
        }

    def list_pending_approvals(self) -> dict[str, Any]:
        """Admin view of connections/sources awaiting first-sync approval or
        carrying user refresh requests. Scans local state (no live).
        """
        # For simplicity scan known construction sources (others may be mailbox/calendar)
        # Use broad list and filter by status markers.
        all_sources = self._store.list_source_locations(limit=5000)
        pending: list[dict[str, Any]] = []
        for src in all_sources:
            if not src:
                continue
            st = self._store.get_source_sync_state(src["source_id"]) or {}
            status = st.get("sync_status") or ""
            if any(
                m in status
                for m in (
                    "pending_admin",
                    _PENDING,
                    _USER_REFRESH_REQUESTED,
                    "schedule_pending_admin",
                )
            ):
                pending.append(
                    {
                        "connection_like_id": src["source_id"],
                        "project_key": src.get("project_key"),
                        "source_name": src.get("source_name"),
                        "sync_status": status,
                        "last_attempted": st.get("last_attempted_sync_utc"),
                    }
                )
        return {
            "surface": "analytics.sync_governance.pending_approvals",
            "count": len(pending),
            "items": pending,
            "guardrails": _guardrails(),
        }

    def _preview_procore(
        self,
        url: str,
        segments: list[str],
        query: dict[str, list[str]],
        request: dict[str, Any],
    ) -> dict[str, Any]:
        match = _PROJECT_ID_RE.search("/" + "/".join(segments))
        project_id = (
            match.group("project_id")
            if match
            else (query.get("project_id") or query.get("project"))[0]
            if (query.get("project_id") or query.get("project"))
            else None
        )
        # Support homepage form https://app.procore.com/<id>/project/home (and similar)
        # where the first path segment is the numeric Procore project ID.
        if not project_id and segments and segments[0].isdigit():
            project_id = segments[0]
        if not project_id or not project_id.isdigit():
            return self._unavailable(
                "procore_project_id_not_found", "No Procore project ID was found."
            )
        project = self._match_project_by_procore_id(project_id) or str(
            request.get("project_key") or ""
        )
        connection_id = f"procore_{_slug(project or project_id)}"
        return self._ready(
            connection_id=connection_id,
            detected_source_type="procore_project",
            source={
                "source_system": "procore",
                "source_scope": "procore_project",
                "source_name": str(request.get("source_name") or f"Procore Project {project_id}"),
                "project_key": project or None,
                "procore_project_id": project_id,
                "url_fingerprint": _fingerprint(url),
            },
            warnings=[] if project else ["project_association_unmatched"],
        )

    def _preview_sharepoint(
        self,
        url: str,
        host: str,
        segments: list[str],
        request: dict[str, Any],
    ) -> dict[str, Any]:
        # Detect encoded SharePoint folder/share-link forms (e.g. /:f:/s/SiteName/...)
        # These must classify as folder/share-link scope (not fail site lookup) and
        # indicate first-sync admin approval. Fully offline, no Graph resolution.
        lower_path = (url or "").lower()
        is_share_link = (
            "/:f:/" in lower_path
            or "/:u:/" in lower_path
            or (segments and segments[0].startswith(":"))
        )

        site = _site_url(url, segments)
        if site is None:
            if not is_share_link:
                return self._unavailable(
                    "sharepoint_site_not_found", "SharePoint site path was not recognized."
                )
            # Derive a best-effort site base for naming from /s/<name> or /teams/<name>
            site_name = None
            for i, seg in enumerate(segments):
                if seg.lower() in {"s", "teams"} and i + 1 < len(segments):
                    site_name = segments[i + 1]
                    break
            if site_name:
                p = urlparse(url.strip())
                site = urlunparse((p.scheme, p.netloc, f"/sites/{site_name}", "", "", ""))
            # else keep site=None; we will treat as folder/share using the raw link url

        lower_segments = [s.lower() for s in segments]
        if is_share_link:
            # Share links are treated as explicit folder/share scope
            is_page = False
            is_folder = True
        else:
            is_page = any(s == "sitepages" for s in lower_segments) or urlparse(
                url
            ).path.lower().endswith(".aspx")
            is_folder = len(segments) > 2 and not is_page
        source_scope = (
            "sharepoint_site_page"
            if is_page
            else "sharepoint_project_drive_folder"
            if is_folder
            else "sharepoint_site"
        )
        detected = (
            "sharepoint_site_page"
            if is_page
            else "sharepoint_folder"
            if is_folder
            else "sharepoint_site"
        )
        source_name = str(request.get("source_name") or segments[-1] if segments else host)
        connection_id = f"sp_{_slug(source_name)}"
        return self._ready(
            connection_id=connection_id,
            detected_source_type=detected,
            source={
                "source_system": "sharepoint",
                "source_scope": source_scope,
                "source_name": source_name,
                "project_key": request.get("project_key"),
                "site_url": site,
                "folder_web_url": _without_query_fragment(url) if is_folder or is_page else None,
                "url_fingerprint": _fingerprint(url),
            },
            warnings=["graph_resolution_pending"],
        )

    def _preview_onedrive(
        self,
        url: str,
        host: str,
        path: str,
        query: dict[str, list[str]],
        request: dict[str, Any],
    ) -> dict[str, Any]:
        scope_mode = str(request.get("scope_mode") or "selected_folders").strip().lower()
        if scope_mode not in {"selected_folders", "all_folders_explicit", "excluded"}:
            return self._unavailable(
                "onedrive_scope_mode_invalid",
                "OneDrive scope must be selected, all explicit, or excluded.",
            )
        folder_ids = request.get("selected_folder_item_ids")
        selected = [str(v) for v in folder_ids] if isinstance(folder_ids, list) else []
        if not selected:
            match = _FOLDER_ID_RE.search(urlparse(url).query)
            selected = [match.group(1)] if match and scope_mode == "selected_folders" else []
        if scope_mode == "selected_folders" and not selected:
            return self._unavailable(
                "onedrive_selected_folder_required",
                "Selected-folder OneDrive setup requires a folder item ID.",
            )
        if scope_mode == "excluded":
            enabled = False
            first_sync = "excluded"
        else:
            enabled = True
            first_sync = _PENDING
        source_name = str(request.get("source_name") or host or path or "OneDrive Scope")
        connection_id = f"od_{_slug(source_name)}"
        return self._ready(
            connection_id=connection_id,
            detected_source_type="onedrive_scope",
            source={
                "source_system": "onedrive_business"
                if "sharepoint.com" in host
                else "onedrive_personal",
                "source_scope": "onedrive_business_root"
                if "sharepoint.com" in host
                else "onedrive_personal_root",
                "source_name": source_name,
                "project_key": request.get("project_key"),
                "folder_item_id": selected[0] if selected else None,
                "folder_policies": {
                    "scope_mode": scope_mode,
                    "selected_folder_item_ids": selected,
                    "allow_all_folders": scope_mode == "all_folders_explicit",
                },
                "enabled": enabled,
                "url_fingerprint": _fingerprint(url),
            },
            warnings=[]
            if scope_mode != "all_folders_explicit"
            else ["onedrive_all_folders_requires_admin_approval"],
            first_sync_status=first_sync,
        )

    def _preview_microsoft_options(self, request: dict[str, Any]) -> dict[str, Any]:
        calendar = load_calendar_source_policy()
        source_name = str(request.get("source_name") or "Microsoft 365 Read-only Sources")
        connection_id = f"m365_{_slug(source_name)}"
        return self._ready(
            connection_id=connection_id,
            detected_source_type="microsoft365_options",
            source={"source_name": source_name},
            warnings=["mailbox_folder_resolution_pending"],
            options={
                "outlook": {
                    "scope": "selected_readonly_folders",
                    "include_defaults": ["Inbox", "Sent Items", "Archive"],
                    "exclude_defaults": ["Deleted Items", "Junk Email", "Drafts"],
                    "mailbox_mutation_allowed": False,
                    "full_body_persisted": False,
                    # project_matching_only false by default: index selected mailbox scope safely,
                    # then classify / project-match relevant items after ingestion (not at setup time).
                    "project_matching_only": False,
                },
                "calendar": {
                    "scope": "primary_calendar_readonly",
                    "lookback_days": calendar.defaults.lookback_days,
                    "lookahead_days": calendar.defaults.lookahead_days,
                    "persist_event_body": calendar.defaults.persist_event_body,
                    "persist_join_url": calendar.defaults.persist_join_url,
                    # project_matching_only false by default: index selected calendar window safely,
                    # then classify / project-match relevant events after ingestion (not at setup time).
                    "project_matching_only": False,
                },
            },
        )

    def _save_file_source(self, connection_id: str, source: dict[str, Any]) -> None:
        self._store.upsert_source_location(
            source_id=connection_id,
            source_system=source["source_system"],
            source_scope=source["source_scope"],
            source_name=source["source_name"],
            project_key=source.get("project_key"),
            site_url=source.get("site_url"),
            folder_item_id=source.get("folder_item_id"),
            folder_web_url=source.get("folder_web_url"),
            sync_mode="setup_pending",
            enabled=bool(source.get("enabled", True)),
            read_only=True,
            folder_policies=source.get("folder_policies"),
        )
        self._store.upsert_source_sync_state(
            source_id=connection_id,
            folder_item_id=source.get("folder_item_id"),
            sync_status="excluded" if source.get("enabled") is False else _PENDING,
        )

    def _save_procore(self, connection_id: str, source: dict[str, Any]) -> None:
        project_key = str(source.get("project_key") or connection_id.replace("procore_", "", 1))
        self._store.upsert_project_identity(
            project_key=project_key,
            project_name_raw=source.get("source_name"),
            is_active=True,
            procore_project_id=source.get("procore_project_id"),
            project_stage="setup_pending_admin_approval",
            match_status="pending",
            match_confidence="medium" if source.get("project_key") else "low",
        )

    def _save_microsoft_options(self, connection_id: str, options: dict[str, Any]) -> None:
        self._store.upsert_calendar_source_location(
            source_id=f"{connection_id}_calendar",
            mailbox_owner_hash="current_user_hash_only",
            calendar_role="primary",
            read_only=True,
            lookback_days=int(options["calendar"]["lookback_days"]),
            lookahead_days=int(options["calendar"]["lookahead_days"]),
            policy_id="setup_pending_admin_approval",
        )
        self._store.upsert_calendar_sync_state(
            source_id=f"{connection_id}_calendar",
            sync_status=_PENDING,
        )
        for folder in options["outlook"]["include_defaults"]:
            source_id = f"{connection_id}_mail_{_slug(folder)}"
            self._store.upsert_email_source_location(
                source_id=source_id,
                mailbox_owner_hash="current_user_hash_only",
                folder_role=_slug(folder),
                folder_display_name=folder,
                include_in_sync=True,
                read_only=True,
            )
            self._store.upsert_email_sync_state(
                source_id=source_id,
                folder_id=_slug(folder),
                sync_mode="bounded_lookback",
                sync_status=_PENDING,
            )

    def _match_project_by_procore_id(self, project_id: str) -> str | None:
        try:
            registry = load_source_registry()
        except Exception:
            return None
        for project in registry.projects:
            if project.procore_project_id == project_id:
                return project.project_key
        return None

    @staticmethod
    def _ready(
        *,
        connection_id: str,
        detected_source_type: str,
        source: dict[str, Any],
        warnings: list[str],
        options: dict[str, Any] | None = None,
        first_sync_status: str = _PENDING,
    ) -> dict[str, Any]:
        payload = {
            "status": "ready_to_save",
            "connection_id": connection_id,
            "detected_source_type": detected_source_type,
            "proposed_source": source,
            "local_baseline": {"status": "unavailable", "reason_code": "baseline_not_loaded"},
            "warnings": warnings,
            "admin_approval_required": True,
            "first_sync_status": first_sync_status,
            "guardrails": _guardrails(),
        }
        if options is not None:
            payload["options"] = options
        return payload

    @staticmethod
    def _unavailable(reason_code: str, message: str) -> dict[str, Any]:
        return {
            "status": "unavailable",
            "reason_code": reason_code,
            "message": message,
            "admin_approval_required": True,
            "guardrails": _guardrails(),
        }

    @staticmethod
    def _approval_response(connection_id: str, source_type: str) -> dict[str, Any]:
        return {
            "ok": True,
            "kind": "first_sync_approved",
            "connection_id": connection_id,
            "source_type": source_type,
            "first_sync_status": _APPROVED,
            "first_sync_triggered": False,
            "guardrails": _guardrails(),
        }
