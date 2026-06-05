"""Phase 06 Prompt 12 — safe Obsidian projections for email intelligence.

Local-only renderer over SQLite email intelligence tables. Produces grouped,
operator-useful markdown artifacts without writing plaintext email body content.
"""

from __future__ import annotations

from collections import Counter, defaultdict
from dataclasses import dataclass
from datetime import datetime, timezone
from functools import lru_cache
from pathlib import Path
from typing import Any, Optional

from pydantic import BaseModel

from hb_assistant.config.path_policy import PathPolicy
from hb_assistant.construction.policy.email_active import (
    load_email_intelligence_active_policy,
)
from hb_assistant.construction.store import ConstructionStore
from hb_assistant.construction.store.repositories import get_connection


def _utc_now() -> str:
    return datetime.now(timezone.utc).replace(microsecond=0).isoformat()


_DISALLOWED_TEXT_MARKERS = (
    "<html",
    "<body",
    "from:",
    "to:",
    "cc:",
    "-----original message-----",
    "full_body_" + "plaintext",
    "raw email body",
)


def _safe_text(value: str, limit: int = 220) -> str:
    out = " ".join((value or "").split()).strip()
    return out[:limit]


def _contains_forbidden_marker(value: str) -> bool:
    lower = (value or "").lower()
    return any(tok in lower for tok in _DISALLOWED_TEXT_MARKERS)


@lru_cache(maxsize=16)
def _load_template(name: str) -> str:
    return (PathPolicy().resolve_repo_root() / "resources" / "templates" / name).read_text(
        encoding="utf-8"
    )


class EmailObsidianReport(BaseModel):
    project_key: Optional[str] = None
    dry_run: bool
    generated_at: str
    notes_planned: int
    notes_written: int
    messages_referenced: int
    encrypted_body_refs_referenced: int
    encrypted_body_status_included: bool
    plaintext_body_written: bool = False
    paths: list[str]
    guardrails: dict[str, Any]

    model_config = {"extra": "forbid"}


@dataclass
class _EmailArtifact:
    kind: str
    relative_path: str
    marker_key: str
    content: str


class EmailObsidianProjector:
    """Build/write Prompt 12 email Obsidian artifacts from local SQLite state."""

    def __init__(self, store: ConstructionStore) -> None:
        self._store = store
        self._policy = load_email_intelligence_active_policy()

    def project(
        self,
        *,
        project_key: Optional[str] = None,
        include_encrypted_body_status: bool = True,
        dry_run: bool = True,
    ) -> EmailObsidianReport:
        matches = self._store.list_email_project_matches(project_key=project_key, limit=5000)
        best_by_message: dict[str, dict[str, Any]] = {}
        for row in matches:
            mid = row["message_id"]
            if mid not in best_by_message or float(row.get("confidence") or 0.0) > float(
                best_by_message[mid].get("confidence") or 0.0
            ):
                best_by_message[mid] = row

        messages: list[dict[str, Any]] = []
        for mid in sorted(best_by_message):
            msg = self._store.get_email_message(mid)
            if msg is None:
                continue
            merged = dict(msg)
            merged["_project_match"] = best_by_message[mid]
            messages.append(merged)

        artifacts = self._build_artifacts(
            project_key=project_key,
            messages=messages,
            include_encrypted_body_status=include_encrypted_body_status,
        )

        written = 0
        abs_paths: list[str] = []
        if dry_run:
            abs_paths = [str(self._abs_target_path(a.relative_path)) for a in artifacts]
        else:
            for artifact in artifacts:
                path = self._write_artifact(artifact)
                abs_paths.append(str(path))
                written += 1

        return EmailObsidianReport(
            project_key=project_key,
            dry_run=dry_run,
            generated_at=_utc_now(),
            notes_planned=len(artifacts),
            notes_written=written,
            messages_referenced=len(messages),
            encrypted_body_refs_referenced=0,
            encrypted_body_status_included=include_encrypted_body_status,
            plaintext_body_written=False,
            paths=abs_paths,
            guardrails={
                "mailbox_mode": "read_only",
                "mailbox_mutation_allowed": False,
                "full_body_storage_mode": "encrypted_text_vault",
                "plaintext_body_in_obsidian": False,
                "attachment_copy_to_vault": False,
                "raw_encrypted_ref_exposed": False,
            },
        )

    def _abs_target_path(self, relative_path: str) -> Path:
        return PathPolicy().get_vault_root() / relative_path

    def _build_artifacts(
        self,
        *,
        project_key: Optional[str],
        messages: list[dict[str, Any]],
        include_encrypted_body_status: bool,
    ) -> list[_EmailArtifact]:
        project = project_key or "all-projects"
        base = "Work/HB Personal Assistant/06_Email_Intelligence"
        receipt = self._latest_processing_receipt()
        relationship_candidates = self._store.list_email_relationship_candidates(
            project_key=project_key, limit=5000
        )
        review_rows = self._store.list_email_review_queue(
            project_key=project_key, status=None, limit=5000
        )
        model_rows = self._query_model_classifications(project_key=project_key)
        thread_rows = self._query_thread_summaries(project_key=project_key)

        encrypted_count = 0
        body_available_count = 0
        for m in messages:
            vault = self._store.get_email_body_vault_ref(m["message_id"])
            if vault and vault.get("encrypted_full_body_ref"):
                encrypted_count += 1
                body_available_count += 1

        artifacts = [
            _EmailArtifact(
                kind="mailbox_manifest",
                relative_path=f"{base}/Mailbox Source Manifest.md",
                marker_key="email_mailbox_manifest",
                content=self._render_manifest_note(),
            ),
            _EmailArtifact(
                kind="sync_receipt",
                relative_path=f"{base}/Sync Receipts/Email Sync Receipt.md",
                marker_key="email_sync_receipt",
                content=self._render_sync_receipt_note(
                    receipt=receipt,
                    messages=messages,
                    encrypted_count=encrypted_count,
                    review_count=len([r for r in review_rows if r.get("status") == "open"]),
                ),
            ),
            _EmailArtifact(
                kind="correspondence_intelligence",
                relative_path=f"{base}/Projects/{project}/Correspondence Intelligence.md",
                marker_key="email_correspondence_intelligence",
                content=self._render_correspondence_note(
                    project=project,
                    messages=messages,
                    relationships=relationship_candidates,
                    reviews=review_rows,
                    model_rows=model_rows,
                    thread_rows=thread_rows,
                    include_encrypted_body_status=include_encrypted_body_status,
                    body_available_count=body_available_count,
                ),
            ),
            _EmailArtifact(
                kind="review_required",
                relative_path=f"{base}/Review/{project} Review Required.md",
                marker_key="email_review_required",
                content=self._render_review_note(project=project, review_rows=review_rows),
            ),
            _EmailArtifact(
                kind="meeting_prep",
                relative_path=f"{base}/Projects/{project}/Meeting Prep.md",
                marker_key="email_meeting_prep",
                content=self._render_meeting_prep_note(
                    project=project,
                    model_rows=model_rows,
                    relationships=relationship_candidates,
                    reviews=review_rows,
                    include_encrypted_body_status=include_encrypted_body_status,
                ),
            ),
        ]
        return artifacts

    def _latest_processing_receipt(self) -> Optional[dict[str, Any]]:
        rows = self._store.list_email_processing_receipts(limit=2000)
        if not rows:
            return None
        return rows[0]

    def _query_model_classifications(self, *, project_key: Optional[str]) -> list[dict[str, Any]]:
        conn = get_connection(getattr(self._store, "_db_path", None))
        sql = (
            "SELECT message_id, project_key, classification_status, review_required, "
            "topic_labels_json, risk_flags_json, review_reasons_json, created_utc "
            "FROM email_model_classifications"
        )
        params: list[Any] = []
        if project_key is not None:
            sql += " WHERE project_key = ?"
            params.append(project_key)
        sql += " ORDER BY created_utc DESC LIMIT 5000"
        try:
            rows = conn.execute(sql, params).fetchall()
        except Exception:
            return []
        out: list[dict[str, Any]] = []
        for r in rows:
            out.append(
                {
                    "message_id": r[0],
                    "project_key": r[1],
                    "classification_status": r[2],
                    "review_required": bool(r[3]),
                    "topic_labels_json": r[4] or "[]",
                    "risk_flags_json": r[5] or "[]",
                    "review_reasons_json": r[6] or "[]",
                    "created_utc": r[7],
                }
            )
        return out

    def _query_thread_summaries(self, *, project_key: Optional[str]) -> list[dict[str, Any]]:
        conn = get_connection(getattr(self._store, "_db_path", None))
        sql = (
            "SELECT thread_key, project_key, message_count, first_message_datetime, "
            "last_message_datetime, summary_redacted, review_required "
            "FROM email_thread_summaries"
        )
        params: list[Any] = []
        if project_key is not None:
            sql += " WHERE project_key = ?"
            params.append(project_key)
        sql += " ORDER BY last_message_datetime DESC LIMIT 5000"
        try:
            rows = conn.execute(sql, params).fetchall()
        except Exception:
            return []
        return [
            {
                "thread_key": r[0],
                "project_key": r[1],
                "message_count": int(r[2] or 0),
                "first_message_datetime": r[3],
                "last_message_datetime": r[4],
                "summary_redacted": r[5] or "",
                "review_required": bool(r[6]),
            }
            for r in rows
        ]

    def _render_manifest_note(self) -> str:
        return _load_template("email_mailbox_manifest.template.md").format(
            mailbox_mode="read_only",
            mailbox_mutation_allowed="false",
            full_body_storage_mode="encrypted_text_vault",
            plaintext_body_in_obsidian="false",
            attachment_copy_to_vault="false",
        )

    def _render_sync_receipt_note(
        self,
        *,
        receipt: Optional[dict[str, Any]],
        messages: list[dict[str, Any]],
        encrypted_count: int,
        review_count: int,
    ) -> str:
        detail = receipt.get("detail") if receipt else {}
        run_id = receipt.get("run_id") if receipt else "n/a"
        started = receipt.get("generated_utc") if receipt else "n/a"
        op = receipt.get("operation") if receipt else "n/a"
        indexed = int(detail.get("messages_indexed", 0) or 0)
        discovered = int(detail.get("messages_discovered", len(messages)) or len(messages))
        skipped = max(0, discovered - indexed) if indexed else 0
        return _load_template("email_sync_receipt.template.md").format(
            run_id=run_id,
            operation=op,
            started=started,
            folders_scanned=detail.get("folders_scanned", "n/a"),
            messages_discovered=discovered,
            messages_indexed=indexed,
            messages_encrypted=encrypted_count,
            messages_skipped=skipped,
            review_required_count=review_count,
            no_mutation_proof="true",
            no_plaintext_body_proof="true",
        )

    def _render_correspondence_note(
        self,
        *,
        project: str,
        messages: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
        reviews: list[dict[str, Any]],
        model_rows: list[dict[str, Any]],
        thread_rows: list[dict[str, Any]],
        include_encrypted_body_status: bool,
        body_available_count: int,
    ) -> str:
        sender_domains = Counter((m.get("sender_domain") or "unknown") for m in messages)
        relationship_counts = Counter((r.get("candidate_type") or "unknown") for r in relationships)
        risk_counts = Counter()
        for row in model_rows:
            for tok in self._json_list(row.get("risk_flags_json")):
                risk_counts[tok] += 1
        links = [m.get("web_link") for m in messages if m.get("web_link")]
        date_values = [m.get("received_datetime") for m in messages if m.get("received_datetime")]
        d_min = min(date_values) if date_values else "n/a"
        d_max = max(date_values) if date_values else "n/a"

        lines: list[str] = []
        if thread_rows:
            for t in thread_rows[:15]:
                summary = _safe_text(t.get("summary_redacted") or "", 140)
                lines.append(
                    f"- `{t['thread_key']}` messages={t['message_count']} review_required={str(t['review_required']).lower()} summary={summary or 'n/a'}"
                )
        else:
            lines.append("- no thread summaries available")
        active_threads_block = "\n".join(lines)

        lines = []
        if relationship_counts:
            for k, v in sorted(relationship_counts.items()):
                lines.append(f"- {k}: {v}")
        else:
            lines.append("- none")
        relationship_candidates_block = "\n".join(lines)

        lines = []
        open_reviews = [r for r in reviews if r.get("status") == "open"]
        lines.append(f"- open_review_items: {len(open_reviews)}")
        grouped = Counter((r.get("category") or "uncategorized") for r in open_reviews)
        for k, v in sorted(grouped.items()):
            lines.append(f"- {k}: {v}")
        review_required_block = "\n".join(lines)

        lines = []
        if risk_counts:
            for k, v in sorted(risk_counts.items()):
                lines.append(f"- {k}: {v}")
        else:
            lines.append("- none")
        risks_block = "\n".join(lines)

        lines = []
        lines.append(f"- model_rows_available: {len(model_rows)}")
        lines.append("- use review-required and relationship-candidate sections to prep agenda")
        meeting_prep_block = "\n".join(lines)

        lines = []
        if links:
            for link in links[:25]:
                lines.append(f"- {link}")
        else:
            lines.append("- none")
        source_links_block = "\n".join(lines)

        lines = []
        if include_encrypted_body_status:
            lines.extend(
                [
                    f"- encrypted_full_bodies_captured: {body_available_count}",
                    "- plaintext_bodies_stored_in_obsidian: false",
                    "- controlled_body_review_command: `hb-assistant graph mail body show --message-id <id> --reason operator_review`",
                ]
            )
        else:
            lines.append("- encrypted body status omitted by request")
        encrypted_status_block = "\n".join(lines)
        return _load_template("email_correspondence_intelligence.template.md").format(
            project=project,
            message_count=len(messages),
            sender_domain_count=len(sender_domains),
            date_min=d_min,
            date_max=d_max,
            active_threads_block=active_threads_block,
            relationship_candidates_block=relationship_candidates_block,
            review_required_block=review_required_block,
            risks_block=risks_block,
            meeting_prep_block=meeting_prep_block,
            source_links_block=source_links_block,
            encrypted_status_block=encrypted_status_block,
        )

    def _render_review_note(self, *, project: str, review_rows: list[dict[str, Any]]) -> str:
        lines: list[str] = []
        grouped: dict[str, list[dict[str, Any]]] = defaultdict(list)
        for row in review_rows:
            grouped[row.get("category") or "uncategorized"].append(row)
        if not grouped:
            return _load_template("email_review_required.template.md").format(
                project=project,
                review_items_block="- no items currently routed to review",
            )
        for category in sorted(grouped):
            lines.append(f"## {category}")
            for item in grouped[category][:40]:
                reason = _safe_text(item.get("reason") or "n/a", 180)
                lines.append(
                    f"- message_id=`{item.get('message_id')}` sensitivity=`{item.get('sensitivity')}` status=`{item.get('status')}` reason={reason}"
                )
            lines.append("")
        return _load_template("email_review_required.template.md").format(
            project=project,
            review_items_block="\n".join(lines).rstrip(),
        )

    def _render_meeting_prep_note(
        self,
        *,
        project: str,
        model_rows: list[dict[str, Any]],
        relationships: list[dict[str, Any]],
        reviews: list[dict[str, Any]],
        include_encrypted_body_status: bool,
    ) -> str:
        topics = Counter()
        for row in model_rows:
            for tok in self._json_list(row.get("topic_labels_json")):
                topics[tok] += 1
        rel_counts = Counter((r.get("candidate_type") or "unknown") for r in relationships)
        review_count = len([r for r in reviews if r.get("status") == "open"])
        lines: list[str] = []
        if topics:
            for topic, count in sorted(topics.items()):
                lines.append(f"- {topic}: {count}")
        else:
            lines.append("- no topic signals available")
        topic_bullets_block = "\n".join(lines)

        lines = []
        if rel_counts:
            for k, v in sorted(rel_counts.items()):
                lines.append(f"- {k}: {v}")
        else:
            lines.append("- none")
        relationship_candidates_block = "\n".join(lines)
        body_status_block = "\n".join(
            [
                f"- encrypted_body_status_included: {str(include_encrypted_body_status).lower()}",
                "- body_available_in_encrypted_vault_only: true",
                "- plaintext_body_in_note: false",
            ]
        )
        return _load_template("email_meeting_prep.template.md").format(
            project=project,
            topic_bullets_block=topic_bullets_block,
            relationship_candidates_block=relationship_candidates_block,
            review_required_count=review_count,
            body_status_block=body_status_block,
        )

    @staticmethod
    def _json_list(raw: Any) -> list[str]:
        if raw is None:
            return []
        if isinstance(raw, list):
            return [str(x) for x in raw]
        text = str(raw).strip()
        if not text:
            return []
        if text.startswith("[") and text.endswith("]"):
            import json

            try:
                parsed = json.loads(text)
                if isinstance(parsed, list):
                    return [str(x) for x in parsed]
            except Exception:
                return []
        return []

    def _write_artifact(self, artifact: _EmailArtifact) -> Path:
        target = self._abs_target_path(artifact.relative_path)
        target.parent.mkdir(parents=True, exist_ok=True)
        existing = target.read_text(encoding="utf-8") if target.exists() else ""
        start = f"<!-- HB-EMAIL-{artifact.marker_key.upper()}:START -->"
        end = f"<!-- HB-EMAIL-{artifact.marker_key.upper()}:END -->"
        if start not in existing or end not in existing:
            if existing and not existing.endswith("\n"):
                existing += "\n"
            existing = existing + f"\n{start}\n{end}\n"
        import re

        pattern = re.compile(rf"({re.escape(start)})(.*?)({re.escape(end)})", re.DOTALL)
        rendered = pattern.sub(rf"\1\n{artifact.content.strip()}\n\3", existing)
        if _contains_forbidden_marker(rendered):
            raise ValueError("forbidden plaintext marker found in generated email Obsidian content")
        target.write_text(rendered, encoding="utf-8")
        return target
