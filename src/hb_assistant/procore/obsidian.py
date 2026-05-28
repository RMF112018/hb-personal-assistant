"""Procore Obsidian deterministic output layer (Prompt 10).

Surgical, read-only, dry-run default. Reuses:
- procore.redaction (for excerpts)
- ConstructionVaultWriter (root/configured + marker-bounded write patterns for apply)
- construction.policy / manifests.models (ReviewRequiredItem)
- ManifestRenderer patterns (lru_cache + PathPolicy + .format + guardrails + reset)
- procore loader (for project metadata)
- procore/sync patterns (project_key filter on procore_* tables, canonical_fields_json, review_required flag, source traceability)
- procore_sensitive_routing_rules.yaml for routing

All paths deterministic. No LLM. Zero secrets/tokens/headers/full bodies in source, comments, or outputs.
Only this file created/edited in this slice.
"""

from __future__ import annotations

import json
import os
import re
import sqlite3
import tempfile
from contextlib import suppress
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

import yaml

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.manifests.models import ReviewRequiredItem
from hb_assistant.construction.manifests.vault_writer import ConstructionVaultWriter
from hb_assistant.procore.loader import load_procore_projects
from hb_assistant.procore.redaction import redact_body
from hb_assistant.store.connection import get_connection


PROCORE_TEMPLATE_NAMES: dict[str, str] = {
    "project_card": "procore_project_card.template.md",
    "rfi_register": "procore_rfi_register.template.md",
    "submittal_register": "procore_submittal_register.template.md",
    "daily_log_index": "procore_daily_log_index.template.md",
    "financial_snapshot": "procore_financial_snapshot.template.md",
    "sync_receipt": "procore_sync_receipt.template.md",
    "endpoint_audit": "procore_endpoint_audit.template.md",
    "review_required_note": "procore_review_required.template.md",
}

PROCORE_GUARDRAILS: dict[str, str] = {
    "projection_only": "true",
    "sqlite_authoritative": "true",
    "redaction_applied": "true",
    "secrets_never": "true",
    "source": "procore (read-only GET sync)",
    "review_routing": "procore_sensitive_routing_rules.yaml + endpoint contract flags",
    "links_preserved": "true",
    "traceability": "source_url + sqlite_id + sync_run_id",
}

# Marker helpers adapted from ConstructionVaultWriter patterns (for procore-* artifacts in 01_Projects hybrid layout)
_SAFE_ITEM_ID = re.compile(r"[^A-Za-z0-9_.-]+")
_PROCORE_MARKERS: dict[str, tuple[str, str]] = {
    "project_card": ("<!-- HB-PROCORE-PROJECT-CARD:START -->", "<!-- HB-PROCORE-PROJECT-CARD:END -->"),
    "rfi_register": ("<!-- HB-PROCORE-RFI-REGISTER:START -->", "<!-- HB-PROCORE-RFI-REGISTER:END -->"),
    "submittal_register": ("<!-- HB-PROCORE-SUBMITTAL-REGISTER:START -->", "<!-- HB-PROCORE-SUBMITTAL-REGISTER:END -->"),
    "daily_log_index": ("<!-- HB-PROCORE-DAILY-LOG:START -->", "<!-- HB-PROCORE-DAILY-LOG:END -->"),
    "financial_snapshot": ("<!-- HB-PROCORE-FINANCIAL-SNAPSHOT:START -->", "<!-- HB-PROCORE-FINANCIAL-SNAPSHOT:END -->"),
    "sync_receipt": ("<!-- HB-PROCORE-SYNC-RECEIPT:START -->", "<!-- HB-PROCORE-SYNC-RECEIPT:END -->"),
    "endpoint_audit": ("<!-- HB-PROCORE-ENDPOINT-AUDIT:START -->", "<!-- HB-PROCORE-ENDPOINT-AUDIT:END -->"),
}


def _procore_date_str(iso: str | None) -> str:
    if not iso:
        return datetime.utcnow().strftime("%Y-%m-%d")
    try:
        return datetime.fromisoformat(iso.replace("Z", "+00:00")).strftime("%Y-%m-%d")
    except ValueError:
        return datetime.utcnow().strftime("%Y-%m-%d")


def _procore_safe_item_id(item_id: str) -> str:
    return _SAFE_ITEM_ID.sub("_", item_id)[:120]


def _procore_ensure_markers(existing: str, start: str, end: str) -> str:
    if start in existing and end in existing:
        return existing
    if existing and not existing.endswith("\n"):
        existing += "\n"
    return existing + f"\n{start}\n{end}\n"


def _procore_replace_bounded(existing: str, inner: str, start: str, end: str) -> str:
    pattern = re.compile(rf"({re.escape(start)})(.*?)({re.escape(end)})", re.DOTALL)
    if pattern.search(existing):
        return pattern.sub(rf"\1\n{inner}\n\3", existing)
    return existing


def _procore_atomic_write_text(target: Path, content: str) -> int:
    """Atomic write (os.replace) — adapted from ConstructionVaultWriter."""
    target.parent.mkdir(parents=True, exist_ok=True)
    fd, tmp_name = tempfile.mkstemp(
        dir=str(target.parent),
        prefix=f".{target.name}.",
        suffix=".tmp",
    )
    tmp_path = Path(tmp_name)
    try:
        with os.fdopen(fd, "w", encoding="utf-8") as f:
            f.write(content)
        os.replace(tmp_path, target)
    except Exception:
        with suppress(FileNotFoundError):
            tmp_path.unlink()
        raise
    return len(content.encode("utf-8"))


class ProcoreObsidianRenderer:
    """Deterministic renderer for Procore Obsidian artifacts (8 templates).

    Queries only procore_* normalized tables (post-sync). Applies routing + redaction.
    Dry-run safe. Testable (pure helpers + reset + injectable db_path).
    """

    def __init__(self, db_path: Optional[Path | str] = None) -> None:
        self.db_path: Optional[Path] = Path(db_path) if db_path else None
        self._routing_rules: Optional[dict[str, Any]] = None
        self._collected_review_items: list[ReviewRequiredItem] = []

    @staticmethod
    @lru_cache(maxsize=8)
    def _load_procore_template(name: str) -> str:
        if name not in PROCORE_TEMPLATE_NAMES:
            raise ValueError(f"unknown procore template name: {name!r}")
        repo_root = PathPolicy().resolve_repo_root()
        path = repo_root / "resources" / "templates" / PROCORE_TEMPLATE_NAMES[name]
        tpl = path.read_text(encoding="utf-8")
        # Robust normalizer: support Phase 03 {{ var }} (jinja-style) + {var} for .format; deterministic, converts to python format placeholders.
        tpl = re.sub(r"\{\{\s*(\w+)\s*\}\}", r"{\1}", tpl)
        return tpl

    def _load_procore_routing_rules(self) -> dict[str, Any]:
        if self._routing_rules is not None:
            return self._routing_rules
        repo_root = PathPolicy().resolve_repo_root()
        path = repo_root / "resources" / "config" / "procore_sensitive_routing_rules.yaml"
        if not path.exists():
            self._routing_rules = {"version": 1, "rules": []}
            return self._routing_rules
        with path.open("r", encoding="utf-8") as f:
            data = yaml.safe_load(f) or {}
        if not isinstance(data, dict):
            data = {"version": 1, "rules": []}
        self._routing_rules = data
        return data

    def _reset_routing_cache(self) -> None:
        self._routing_rules = None

    def _is_procore_sensitive(self, *, category: str, fields: dict[str, Any], text_blob: str = "") -> tuple[bool, str | None]:
        """Apply procore_sensitive_routing_rules.yaml (categories + keywords)."""
        rules = self._load_procore_routing_rules().get("rules", [])
        cat = (category or "").lower().replace("-", "_")
        blob = text_blob or " ".join(str(v).lower() for v in fields.values() if isinstance(v, (str, int, float)))
        for rule in rules:
            cats = rule.get("categories", [])
            for c in cats:
                c_norm = c.lower().replace("-", "_")
                if c_norm in cat or cat in c_norm:
                    return True, rule.get("rule_id")
            for kw in rule.get("keywords", []):
                if kw.lower() in blob:
                    return True, rule.get("rule_id")
        return False, None

    def _safe_excerpt(self, val: Any, max_len: int = 96) -> str:
        """Redact + truncate/hash long notes/delays using redaction primitives. Never full content."""
        if val is None or val == "":
            return ""
        s = str(val)
        if len(s) > max_len:
            red = redact_body(s)
            h = red.get("hash_prefix") or red.get("hash", "redacted")[:12]
            return f"[REDACTED len={len(s)} hash={h}]"
        return s[:max_len] + ("..." if len(s) > 64 else "")

    def _make_review_item(
        self, row: sqlite3.Row, fields: dict[str, Any], rule_id: str | None, source_table: str
    ) -> ReviewRequiredItem:
        name = str(fields.get("number") or fields.get("title") or fields.get("subject") or row["entity_stable_key"])
        return ReviewRequiredItem(
            item_id=str(row["id"]),
            source_key="procore",
            project_key=row["source_project_key"],
            name=name[:120],
            reason=f"procore {row['category']} routed by {rule_id or 'contract/review_required flag'}",
            suggested_action="Manual review of redacted record (SQLite authoritative)",
            classification_label="financial" if any(x in (rule_id or "") for x in ("financial", "budget", "invoice")) else "contractual",
            sensitivity="high",
        )

    def _query_synced_entities(self, project_key: str, category: Optional[str] = None) -> list[sqlite3.Row]:
        conn = get_connection(self.db_path)
        try:
            sql = (
                "SELECT id, source_project_key, endpoint_id, entity_stable_key, category, "
                "review_required, canonical_fields_json, fetched_at, last_seen_at "
                "FROM procore_synced_entities WHERE source_project_key = ?"
            )
            params: list[Any] = [project_key]
            if category:
                sql += " AND category = ?"
                params.append(category)
            sql += " ORDER BY last_seen_at DESC, id DESC"
            return list(conn.execute(sql, params).fetchall())
        except Exception:
            return []

    def _query_sync_runs(self, project_key: str, limit: int = 3) -> list[sqlite3.Row]:
        conn = get_connection(self.db_path)
        try:
            return list(
                conn.execute(
                    "SELECT id, correlation_id, mode, pilot_project_key, started_at, completed_at, "
                    "total_items_normalized, persisted_to_sqlite, policy_used, receipt_json "
                    "FROM procore_sync_runs WHERE pilot_project_key = ? ORDER BY started_at DESC LIMIT ?",
                    (project_key, limit),
                ).fetchall()
            )
        except Exception:
            return []

    def _query_sync_errors(self, project_key: str, limit: int = 10) -> list[sqlite3.Row]:
        conn = get_connection(self.db_path)
        try:
            return list(
                conn.execute(
                    "SELECT e.id, e.run_id, e.error_code, e.message_redacted, e.http_status, e.created_at "
                    "FROM procore_sync_errors e JOIN procore_sync_runs r ON e.run_id = r.id "
                    "WHERE r.pilot_project_key = ? ORDER BY e.created_at DESC LIMIT ?",
                    (project_key, limit),
                ).fetchall()
            )
        except Exception:
            return []

    def _query_sync_watermarks(self, project_key: str) -> list[sqlite3.Row]:
        conn = get_connection(self.db_path)
        try:
            return list(
                conn.execute(
                    """
                    SELECT endpoint_id, project_key, last_successful_watermark, updated_at
                    FROM procore_sync_watermarks
                    WHERE project_key = ?
                    ORDER BY updated_at DESC
                    """,
                    (project_key,),
                ).fetchall()
            )
        except Exception:
            return []

    def build_procore_project_card(self, project_key: str) -> dict[str, Any]:
        try:
            reg = load_procore_projects()
            mapping = reg.get(project_key)
            hb_project_number = project_key
            procore_project_id = mapping.procore_project_id if mapping else "?"
            project_name = mapping.procore_project_name if mapping else project_key
            company_id = reg.company_id
        except Exception:
            hb_project_number = project_key
            procore_project_id = "?"
            project_name = project_key
            company_id = "5280"

        counts: dict[str, int] = {}
        for row in self._query_synced_entities(project_key):
            cat = row["category"] or "unknown"
            counts[cat] = counts.get(cat, 0) + 1

        runs = self._query_sync_runs(project_key, 1)
        last_sync = runs[0]["completed_at"] if runs else "never"
        watermarks = self._query_sync_watermarks(project_key)
        watermark_count = len(watermarks)

        review_count = sum(1 for r in self._query_synced_entities(project_key) if r["review_required"])
        review_summary = f"{review_count} items flagged (see procore review required note)"

        err_count = len(self._query_sync_errors(project_key))
        audit_status = "clean" if err_count == 0 else f"issues ({err_count} redacted errors)"

        return {
            "project_key": project_key,
            "hb_project_number": hb_project_number,
            "procore_project_id": procore_project_id,
            "project_name": project_name,
            "company_id": company_id,
            "last_sync_utc": last_sync or "n/a",
            "endpoint_audit_status": audit_status,
            "rfi_count": counts.get("rfis", 0),
            "submittal_count": counts.get("submittals", 0),
            "observation_count": counts.get("observations", counts.get("daily-logs", 0)),
            "meeting_count": counts.get("meetings", 0),
            "daily_log_count": counts.get("daily-logs", 0),
            "watermark_count": watermark_count,
            "review_required_summary": review_summary,
            "guardrails": dict(PROCORE_GUARDRAILS),
            "review_sensitive": False,
            "source": "procore",
        }

    def build_rfi_register(self, project_key: str) -> dict[str, Any]:
        rows_md: list[str] = []
        for row in self._query_synced_entities(project_key, "rfis"):
            fields = json.loads(row["canonical_fields_json"] or "{}") if row["canonical_fields_json"] else {}
            is_sens, rule = self._is_procore_sensitive(category=row["category"], fields=fields)
            if is_sens or bool(row["review_required"]):
                self._collected_review_items.append(self._make_review_item(row, fields, rule, "procore_rfis"))
                continue
            num = fields.get("number") or row["entity_stable_key"]
            subj = self._safe_excerpt(fields.get("subject") or fields.get("title") or "")
            status = fields.get("status", "n/a")
            due = fields.get("due_date") or fields.get("due") or ""
            src = fields.get("url") or fields.get("source_url") or fields.get("link") or "#"
            sid = row["id"]
            rows_md.append(f"| {num} | {subj} | {status} | {due} | [{sid}]({src}) |")
        table = "\n".join(rows_md) if rows_md else "| (no non-sensitive RFIs after routing) | | | | |"
        return {
            "project_name": project_key,
            "rows": table,
            "guardrails": dict(PROCORE_GUARDRAILS),
        }

    def build_submittal_register(self, project_key: str) -> dict[str, Any]:
        rows_md: list[str] = []
        for row in self._query_synced_entities(project_key, "submittals"):
            fields = json.loads(row["canonical_fields_json"] or "{}") if row["canonical_fields_json"] else {}
            is_sens, rule = self._is_procore_sensitive(category=row["category"], fields=fields)
            if is_sens or bool(row["review_required"]):
                self._collected_review_items.append(self._make_review_item(row, fields, rule, "procore_submittals"))
                continue
            num = fields.get("number") or row["entity_stable_key"]
            title = self._safe_excerpt(fields.get("title") or fields.get("subject") or "")
            spec = fields.get("spec_section") or fields.get("spec") or ""
            status = fields.get("status", "n/a")
            due = fields.get("due_date") or ""
            src = fields.get("url") or fields.get("source_url") or "#"
            sid = row["id"]
            rows_md.append(f"| {num} | {title} | {spec} | {status} | {due} | [{sid}]({src}) |")
        table = "\n".join(rows_md) if rows_md else "| (no non-sensitive Submittals after routing) | | | | | |"
        return {
            "project_name": project_key,
            "rows": table,
            "guardrails": dict(PROCORE_GUARDRAILS),
        }

    def build_daily_log_index(self, project_key: str) -> dict[str, Any]:
        rows_md: list[str] = []
        for row in self._query_synced_entities(project_key, "daily-logs"):
            fields = json.loads(row["canonical_fields_json"] or "{}") if row["canonical_fields_json"] else {}
            is_sens, rule = self._is_procore_sensitive(category=row["category"], fields=fields)
            if is_sens or bool(row["review_required"]):
                self._collected_review_items.append(self._make_review_item(row, fields, rule, "procore_daily_logs"))
                continue
            date = fields.get("date") or fields.get("log_date") or ""
            status = fields.get("status", "n/a")
            weather = self._safe_excerpt(fields.get("weather") or "")
            manpower = self._safe_excerpt(fields.get("manpower") or fields.get("crew") or "")
            notes = self._safe_excerpt(fields.get("notes") or fields.get("note") or fields.get("delays") or "")
            review_flag = "flagged" if (is_sens or row["review_required"]) else "ok"
            rows_md.append(f"| {date} | {status} | {weather} | {manpower} | {notes} | {review_flag} |")
        table = "\n".join(rows_md) if rows_md else "| (no non-sensitive Daily Logs after routing) | | | | | |"
        return {
            "project_name": project_key,
            "rows": table,
            "guardrails": dict(PROCORE_GUARDRAILS),
        }

    def build_financial_snapshot(self, project_key: str) -> dict[str, Any]:
        """Always review_sensitive:true. Safe summary ONLY — no raw amounts, no leakable figures."""
        fin_cats = ("budget", "commitments", "invoices", "requisitions", "direct_costs",
                    "prime_contracts", "change_events", "potential_change_orders")
        total = 0
        cats_seen: set[str] = set()
        last = "n/a"
        for cat in fin_cats:
            ents = self._query_synced_entities(project_key, cat)
            if ents:
                cats_seen.add(cat)
                total += len(ents)
                last = max((e["last_seen_at"] or "" for e in ents), default=last)
            for row in ents:
                fields = json.loads(row["canonical_fields_json"] or "{}") if row["canonical_fields_json"] else {}
                is_sens, rule = self._is_procore_sensitive(category=row["category"], fields=fields)
                if is_sens or bool(row["review_required"]):
                    self._collected_review_items.append(self._make_review_item(row, fields, rule, f"procore_{cat}"))
        metric_rows = (
            f"| item_count | {total} |\n"
            f"| categories_covered | {', '.join(sorted(cats_seen)) or 'none (post-routing)'} |\n"
            f"| last_seen | {last} |\n"
            "| note | SAFE SUMMARY ONLY — no amounts, no PII, financials routed to review |"
        )
        # Force at least one review item for the snapshot itself
        if not any("financial" in (i.classification_label or "") for i in self._collected_review_items):
            self._collected_review_items.append(
                ReviewRequiredItem(
                    item_id=f"fin-snapshot-{project_key}",
                    source_key="procore",
                    project_key=project_key,
                    name="financial-snapshot",
                    reason="procore financial snapshot (high-sensitivity per rules)",
                    suggested_action="Review full financial metadata in SQLite procore_synced_entities",
                    classification_label="financial",
                    sensitivity="high",
                )
            )
        return {
            "project_key": project_key,
            "project_name": project_key,
            "metric_rows": metric_rows,
            "review_queue_link": "[[02_Review_Queue/]] (or date__review-required.md)",
            "review_sensitive": True,
            "guardrails": dict(PROCORE_GUARDRAILS),
        }

    def build_sync_receipt(self, project_key: str) -> dict[str, Any]:
        runs = self._query_sync_runs(project_key, 1)
        if not runs:
            return {
                "project_name": project_key,
                "run_id": "none",
                "mode": "n/a",
                "status": "no sync runs",
                "started_utc": "n/a",
                "completed_utc": "n/a",
                "rows_seen": 0,
                "rows_written": 0,
                "guardrails": dict(PROCORE_GUARDRAILS),
            }
        r = runs[0]
        watermarks = self._query_sync_watermarks(project_key)
        last_watermark_at = watermarks[0]["updated_at"] if watermarks else "n/a"
        watermark_count = len(watermarks)
        return {
            "project_name": project_key,
            "run_id": r["id"],
            "mode": r["mode"],
            "status": "persisted" if r["persisted_to_sqlite"] else "dry_run",
            "started_utc": r["started_at"] or "n/a",
            "completed_utc": r["completed_at"] or "n/a",
            "rows_seen": r["total_items_normalized"] or 0,
            "rows_written": r["total_items_normalized"] if r["persisted_to_sqlite"] else 0,
            "watermark_count": watermark_count,
            "last_watermark_updated_utc": last_watermark_at or "n/a",
            "guardrails": dict(PROCORE_GUARDRAILS),
        }

    def build_endpoint_audit(self, project_key: str) -> dict[str, Any]:
        runs = self._query_sync_runs(project_key, 1)
        run_id = runs[0]["id"] if runs else "none"
        mode = runs[0]["mode"] if runs else "n/a"
        errors = self._query_sync_errors(project_key, 5)
        rows_md: list[str] = []
        for e in errors:
            rows_md.append(
                f"| {e['run_id'][:8]}... | sync_error | {e['http_status'] or 'n/a'} | redacted | {self._safe_excerpt(e['message_redacted'])} |"
            )
        if not rows_md:
            rows_md.append("| (no redacted errors for project) | | | | |")
        return {
            "project_name": project_key,
            "run_id": run_id,
            "mode": mode,
            "generated_utc": datetime.now(timezone.utc).isoformat(),
            "endpoint_rows": "\n".join(rows_md),
            "guardrails": dict(PROCORE_GUARDRAILS),
        }

    def build_review_required_note(self, project_key: str) -> dict[str, Any]:
        items = list(self._collected_review_items)
        blocks: list[str] = []
        for item in items:
            safe_sum = self._safe_excerpt(item.reason, 200)
            blocks.append(
                f"""
---

# Review Required — {item.name or item.item_id}

Reason: {item.reason}

Source Table: `procore_synced_entities`
Source ID: `{item.item_id}`
Source URL: (see SQLite row for full traceability; redacted)

## Safe Summary

{safe_sum}

classification: {item.classification_label} | sensitivity: {item.sensitivity}
"""
            )
        content = f"""---
type: procore_review_required
review_id: procore-{project_key}-{datetime.now(timezone.utc).strftime('%Y%m%d%H%M')}
project_key: {project_key}
sensitivity: high
status: open
---

# Procore Review Required — {project_key}

{len(items)} sensitive items (financial/contractual/incident/personnel/delay) routed exclusively here.
**NEVER** appear in registers, cards, or snapshots.

{''.join(blocks) if blocks else "\n(no additional review items after routing)\n"}

## Guardrails
{chr(10).join(f"- {k}: {v}" for k, v in PROCORE_GUARDRAILS.items())}
"""
        return {
            "project_key": project_key,
            "rendered_content": content.strip(),
            "item_count": len(items),
            "guardrails": dict(PROCORE_GUARDRAILS),
        }

    def render(self, template_name: str, data: dict[str, Any]) -> str:
        """Render using exact template + provided data (caller ensures keys)."""
        tpl = self._load_procore_template(template_name)
        # Provide safe defaults for optional template vars
        safe_data = {k: (data.get(k, "n/a") if data.get(k) is not None else "n/a") for k in data}
        # Add common guardrails block for templates that expect it (defensive)
        if "guardrails_block" not in safe_data:
            safe_data["guardrails_block"] = "\n".join(f"- {k}: {v}" for k, v in safe_data.get("guardrails", PROCORE_GUARDRAILS).items())
        # Ensure guardrails_block injected for ALL 8 (even if template missing placeholder); append section if absent (follows non-procore pattern, deterministic).
        if "{guardrails_block}" not in tpl:
            tpl = tpl.rstrip() + "\n\n## Guardrails\n\n{guardrails_block}\n"
        try:
            return tpl.format(**safe_data)
        except KeyError:
            # Last-resort: fill any missing with n/a (still deterministic, no crash)
            all_keys = set(re.findall(r"\{(\w+)\}", tpl))
            filled = {k: safe_data.get(k, "n/a") for k in all_keys}
            return tpl.format(**filled)

    def get_collected_review_items(self) -> list[ReviewRequiredItem]:
        return list(self._collected_review_items)

    def clear_review_items(self) -> None:
        self._collected_review_items.clear()


def reset_procore_obsidian_caches() -> None:
    """Test hook: clear all caches between tests."""
    ProcoreObsidianRenderer._load_procore_template.cache_clear()


def _write_procore_artifact(
    root: Path, filename: str, rendered: str, marker_kind: str
) -> Path:
    """Marker-bounded write for procore- artifacts under 01_Projects (hybrid)."""
    target = root / "01_Projects" / filename
    start, end = _PROCORE_MARKERS.get(marker_kind, (f"<!-- HB-PROCORE-{marker_kind}:START -->", f"<!-- HB-PROCORE-{marker_kind}:END -->"))
    target.parent.mkdir(parents=True, exist_ok=True)
    existing = target.read_text(encoding="utf-8") if target.exists() else ""
    framed = _procore_ensure_markers(existing, start, end)
    new_content = _procore_replace_bounded(framed, rendered.strip(), start, end)
    _procore_atomic_write_text(target, new_content)
    return target


def procore_obsidian_preview(
    project_key: str,
    *,
    dry_run: bool = True,
    apply: bool = False,
    json_out: bool = False,
    db_path: Optional[Path | str] = None,
) -> dict[str, Any]:
    """Preview (and optional apply) all 8 Procore Obsidian artifacts.

    Dry-run DEFAULT (zero side effects). apply=True writes via VaultWriter patterns + procore- files in 01_Projects/.

    Returns dict with rendered strings + review_items + guardrails. Redacted errors only.
    """
    renderer = ProcoreObsidianRenderer(db_path=db_path)
    renderer.clear_review_items()

    try:
        card_d = renderer.build_procore_project_card(project_key)
        rfi_d = renderer.build_rfi_register(project_key)
        sub_d = renderer.build_submittal_register(project_key)
        daily_d = renderer.build_daily_log_index(project_key)
        fin_d = renderer.build_financial_snapshot(project_key)
        sync_d = renderer.build_sync_receipt(project_key)
        audit_d = renderer.build_endpoint_audit(project_key)
        review_d = renderer.build_review_required_note(project_key)

        rendered: dict[str, str] = {
            "project_card": renderer.render("project_card", card_d),
            "rfi_register": renderer.render("rfi_register", rfi_d),
            "submittal_register": renderer.render("submittal_register", sub_d),
            "daily_log_index": renderer.render("daily_log_index", daily_d),
            "financial_snapshot": renderer.render("financial_snapshot", fin_d),
            "sync_receipt": renderer.render("sync_receipt", sync_d),
            "endpoint_audit": renderer.render("endpoint_audit", audit_d),
            "review_required_note": review_d["rendered_content"],
        }

        review_items = [i.model_dump() for i in renderer.get_collected_review_items()]

        written: list[str] = []
        if apply:
            writer = ConstructionVaultWriter()
            if writer.configured:
                root = writer.root
                # Procore-specific files (hybrid) in 01_Projects/
                written.append(str(_write_procore_artifact(root, f"{project_key}.procore-project-card.md", rendered["project_card"], "project_card")))
                written.append(str(_write_procore_artifact(root, f"{project_key}.procore-rfi-register.md", rendered["rfi_register"], "rfi_register")))
                written.append(str(_write_procore_artifact(root, f"{project_key}.procore-submittal-register.md", rendered["submittal_register"], "submittal_register")))
                written.append(str(_write_procore_artifact(root, f"{project_key}.procore-daily-log-index.md", rendered["daily_log_index"], "daily_log_index")))
                written.append(str(_write_procore_artifact(root, f"{project_key}.procore-financial-snapshot.md", rendered["financial_snapshot"], "financial_snapshot")))
                written.append(str(_write_procore_artifact(root, f"{project_key}.procore-sync-receipt.md", rendered["sync_receipt"], "sync_receipt")))
                written.append(str(_write_procore_artifact(root, f"{project_key}.procore-endpoint-audit.md", rendered["endpoint_audit"], "endpoint_audit")))
                # Re-use writer for canonical review note (02_Review_Queue)
                try:
                    res = writer.write_review_required_note(
                        generated_at=datetime.now(timezone.utc).isoformat(),
                        rendered=rendered["review_required_note"],
                    )
                    written.append(str(res.path))
                except Exception as we:
                    written.append(f"review-note-write-redacted:{type(we).__name__}")
            else:
                written.append("vault-not-configured (dry paths only)")

        result: dict[str, Any] = {
            "command": "procore-obsidian-preview",
            "project_key": project_key,
            "mode": "apply" if apply else "dry_run",
            "status": "ok",
            "dry_run": (dry_run and not apply),
            "guardrails": dict(PROCORE_GUARDRAILS),
            "rendered": rendered,
            "review_items": review_items,
            "written_paths": written,
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
            "db_path_used": str(renderer.db_path) if renderer.db_path else "default",
        }
        return result

    except Exception as exc:
        # Redacted error only
        return {
            "command": "procore-obsidian-preview",
            "project_key": project_key,
            "mode": "apply" if apply else "dry_run",
            "status": "error",
            "error": f"redacted:{type(exc).__name__}",
            "guardrails": dict(PROCORE_GUARDRAILS),
            "review_items": [],
            "written_paths": [],
            "timestamp_utc": datetime.now(timezone.utc).isoformat(),
        }


# Exports (import directly from hb_assistant.procore.obsidian)
__all__ = [
    "ProcoreObsidianRenderer",
    "procore_obsidian_preview",
    "reset_procore_obsidian_caches",
    "PROCORE_GUARDRAILS",
]
